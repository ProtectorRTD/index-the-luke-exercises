#!/usr/bin/env python3
"""Index Lab: проверка заданий по «Use The Index, Luke» на PostgreSQL.

Запускается внутри контейнера `lab` через обёртки ./lab и lab.cmd.
Работает только через psql, сторонних драйверов не нужно.
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("LAB_ROOT") or Path(__file__).resolve().parent.parent)
MODULES = ROOT / "modules"
SOLUTIONS = ROOT / "solutions"
STATE_FILE = ROOT / ".lab" / "state.json"

SCALES = {
    "s": dict(n_customers=100_000, n_products=10_000, n_orders=1_000_000, n_events=2_000_000),
    "m": dict(n_customers=1_000_000, n_products=50_000, n_orders=10_000_000, n_events=20_000_000),
}
# Подстановки в эталонах ответов: «оптовики» — первый 1% клиентов, они делают половину заказов.
SCALE_VARS = {"s": {"heavy": "1000"}, "m": {"heavy": "10000"}}
BASE_TABLES = ["categories", "customers", "products", "orders", "order_items", "events"]

# Что нельзя писать ни в одном решении: это обходы планировщика, а не решения.
DEFAULT_FORBIDDEN = [
    (r"^\s*(SET|RESET)\b", "SET/RESET в решении запрещены"),
    (r"\benable_\w+", "переключатели enable_* запрещены"),
    (r"\bset_config\s*\(", "set_config запрещён"),
    (r"/\*\+", "хинты планировщика запрещены"),
    (r"^\s*LOAD\b", "LOAD запрещён"),
]
INDEX_TASK_ALLOWED = re.compile(r"^\s*(CREATE\s+(UNIQUE\s+)?INDEX|DROP\s+INDEX|ANALYZE|VACUUM)\b", re.I)
QUERY_ALLOWED = re.compile(r"^\s*(SELECT|WITH|VALUES|TABLE)\b", re.I)

TYPE_NAMES = {
    "index": "индексы",
    "query": "запросы",
    "mixed": "индексы и запросы",
    "answers": "ответы по плану",
}

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def color(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def green(t):
    return color(t, "32")


def red(t):
    return color(t, "31")


def dim(t):
    return color(t, "2")


def bold(t):
    return color(t, "1")


class LabError(Exception):
    pass


# ---------------------------------------------------------------------------
# psql
# ---------------------------------------------------------------------------

def psql(script, *, csv_out=False, variables=None, file=None, timeout=None):
    args = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-P", "pager=off"]
    args += ["--csv", "-t"] if csv_out else ["-A", "-t"]
    for k, v in (variables or {}).items():
        args += ["-v", f"{k}={v}"]
    if file:
        args += ["-f", str(file)]
    try:
        p = subprocess.run(args, input=None if file else script, text=True,
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LabError("psql не уложился в таймаут")
    if p.returncode != 0:
        raise LabError(p.stderr.strip() or f"psql завершился с кодом {p.returncode}")
    return p.stdout


def scalar(sql):
    return psql(sql).strip()


def current_scale():
    try:
        return scalar("SELECT value FROM lab_meta.settings WHERE key = 'scale'")
    except LabError:
        return ""


def require_seed():
    scale = current_scale()
    if not scale:
        raise LabError("База пустая. Сначала запустите: lab seed --scale s")
    return scale


# ---------------------------------------------------------------------------
# SQL: разбор решений
# ---------------------------------------------------------------------------

def split_sql(text):
    """Делит текст на операторы, выбрасывая комментарии. Учитывает кавычки и $$-строки."""
    out, buf, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and text.startswith("/*", i):
            if text.startswith("/*+", i):
                buf.append("/*+")  # оставляем след, чтобы поймать хинты
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            buf.append(" ")
            continue
        if c in ("'", '"'):
            j = i + 1
            while j < n:
                if text[j] == c:
                    if j + 1 < n and text[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            buf.append(text[i:j + 1])
            i = j + 1
            continue
        if c == "$":
            m = re.match(r"\$[A-Za-z_]*\$", text[i:])
            if m:
                tag = m.group(0)
                j = text.find(tag, i + len(tag))
                j = n if j == -1 else j + len(tag)
                buf.append(text[i:j])
                i = j
                continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    stmt = "".join(buf).strip()
    if stmt:
        out.append(stmt)
    return out


def check_forbidden(statements, extra):
    problems = []
    for stmt in statements:
        for pattern, msg in DEFAULT_FORBIDDEN + [(p, f"запрещено: {p}") for p in extra]:
            if re.search(pattern, stmt, re.I | re.M):
                problems.append(msg)
    return sorted(set(problems))


def read_query_file(path, allow=QUERY_ALLOWED):
    if not path.exists():
        raise LabError(f"нет файла {path.relative_to(ROOT)}")
    stmts = split_sql(path.read_text(encoding="utf-8"))
    if not stmts:
        raise LabError(f"{path.name} пустой: напишите запрос")
    if len(stmts) != 1:
        raise LabError(f"{path.name} должен содержать ровно один запрос, а в нём {len(stmts)}")
    q = stmts[0]
    if "___" in q:
        raise LabError(f"в {path.name} остались пропуски ___: заполните их")
    if not allow.match(q):
        raise LabError(f"{path.name}: ожидается запрос SELECT/WITH, а не «{q.split()[0]}»")
    return q


# ---------------------------------------------------------------------------
# Состояние базы: манифест и сброс
# ---------------------------------------------------------------------------

def write_manifest():
    psql("""
        CREATE TABLE IF NOT EXISTS lab_meta.manifest (kind text, name text);
        TRUNCATE lab_meta.manifest;
        INSERT INTO lab_meta.manifest
        SELECT c.relkind::text, c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r','i','S','v','m','p');
        CREATE TABLE IF NOT EXISTS lab_meta.table_stats AS
            SELECT relname, 0::bigint AS changes FROM pg_stat_user_tables WHERE false;
        TRUNCATE lab_meta.table_stats;
        SELECT pg_stat_force_next_flush();
        INSERT INTO lab_meta.table_stats
        SELECT relname, n_tup_upd + n_tup_del + n_tup_ins
        FROM pg_stat_user_tables WHERE schemaname = 'public';
    """)


RESET_SQL = """
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.relname, c.relkind FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('v','m')
          AND NOT EXISTS (SELECT 1 FROM lab_meta.manifest m WHERE m.name = c.relname)
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('DROP %s IF EXISTS public.%I CASCADE',
                       CASE r.relkind WHEN 'v' THEN 'VIEW' ELSE 'MATERIALIZED VIEW' END, r.relname);
    END LOOP;
    FOR r IN
        SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r','p')
          AND NOT EXISTS (SELECT 1 FROM lab_meta.manifest m WHERE m.name = c.relname)
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.relname);
    END LOOP;
    FOR r IN
        SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'i'
          AND NOT EXISTS (SELECT 1 FROM lab_meta.manifest m WHERE m.name = c.relname)
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS public.%I CASCADE', r.relname);
    END LOOP;
    FOR r IN
        SELECT s.stxname FROM pg_statistic_ext s
        JOIN pg_namespace n ON n.oid = s.stxnamespace WHERE n.nspname = 'public'
    LOOP
        EXECUTE format('DROP STATISTICS IF EXISTS public.%I', r.stxname);
    END LOOP;
    FOR r IN
        SELECT p.oid::regprocedure AS sig FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
    END LOOP;
END $$;
DEALLOCATE ALL;
"""


def reset_db(quiet=False):
    require_seed()
    psql(RESET_SQL)
    psql("SELECT pg_stat_force_next_flush();")
    changed = psql("""
        SELECT s.relname FROM pg_stat_user_tables s
        JOIN lab_meta.table_stats t USING (relname)
        WHERE s.schemaname = 'public' AND s.n_tup_upd + s.n_tup_del + s.n_tup_ins > t.changes
    """).split()
    if changed and not quiet:
        print(red("Внимание: данные в таблицах " + ", ".join(changed) + " менялись после генерации."))
        print(red("Планы и пороги могут разойтись с эталоном. Перегенерируйте: lab seed --scale "
                  + current_scale()))


def list_indexes():
    rows = psql("""
        SELECT c.relname, t.relname, pg_relation_size(c.oid)
        FROM pg_class c
        JOIN pg_index i ON i.indexrelid = c.oid
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
    """, csv_out=True)
    return {r[0]: (r[1], int(r[2])) for r in csv.reader(io.StringIO(rows))}


# ---------------------------------------------------------------------------
# Выполнение запросов
# ---------------------------------------------------------------------------

def tx_begin(writes):
    return "BEGIN;" if writes else "BEGIN TRANSACTION READ ONLY;"


def settings_sql(settings):
    return "".join(f"SET LOCAL {k} = '{v}';\n" for k, v in (settings or {}).items())


def normalize_value(v):
    if v == "":
        return v
    try:
        d = Decimal(v)
        if d.is_finite():
            d = d.normalize()
            return format(d, "f") if d == d.to_integral() else str(d)
    except InvalidOperation:
        pass
    return v


def run_rows(query, *, writes=False, settings=None, timeout_s=300):
    script = (tx_begin(writes) + f"\nSET LOCAL statement_timeout = '{timeout_s}s';\n"
              + settings_sql(settings) + query + ";\nROLLBACK;\n")
    out = psql(script, csv_out=True, timeout=timeout_s + 30)
    return [tuple(normalize_value(x) for x in row) for row in csv.reader(io.StringIO(out))]


def explain(query, *, writes=False, settings=None, runs=2, timeout_s=300):
    plans = []
    for _ in range(runs):
        script = (tx_begin(writes) + f"\nSET LOCAL statement_timeout = '{timeout_s}s';\n"
                  + settings_sql(settings)
                  + f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query};\nROLLBACK;\n")
        out = psql(script, timeout=timeout_s + 30)
        plans.append(json.loads(out)[0])
    return plans[-1]


# ---------------------------------------------------------------------------
# План: обход и метрики
# ---------------------------------------------------------------------------

def walk(node, depth=0):
    yield node, depth
    for child in node.get("Plans", []) or []:
        yield from walk(child, depth + 1)


def node_buffers(node):
    return int(node.get("Shared Hit Blocks", 0)) + int(node.get("Shared Read Blocks", 0))


def total_buffers(plan):
    return node_buffers(plan["Plan"])


def rows_removed(plan):
    total = 0.0
    for node, _ in walk(plan["Plan"]):
        total += float(node.get("Rows Removed by Filter", 0)) * float(node.get("Actual Loops", 1))
    return int(round(total))


_index_table_cache = {}


def index_table(index_name):
    if index_name not in _index_table_cache:
        _index_table_cache[index_name] = scalar(
            f"SELECT indrelid::regclass::text FROM pg_index WHERE indexrelid = to_regclass('public.{index_name}')")
    return _index_table_cache[index_name]


def node_relation(node):
    if node.get("Relation Name"):
        return node["Relation Name"]
    if node.get("Index Name"):
        return index_table(node["Index Name"])
    return None


def match_node(node, spec):
    names = spec["node"] if isinstance(spec["node"], list) else [spec["node"]]
    if node.get("Node Type") not in names:
        return False
    if spec.get("relation") and node_relation(node) != spec["relation"]:
        return False
    if spec.get("index") and node.get("Index Name") != spec["index"]:
        return False
    return True


def scan_node_type(plan, relation):
    for node, _ in walk(plan["Plan"]):
        if node.get("Relation Name") == relation and "Scan" in node.get("Node Type", ""):
            return node["Node Type"]
    return None


def short(text, width=70):
    text = re.sub(r"\s+", " ", text or "")
    return text if len(text) <= width else text[:width - 1] + "…"


def format_plan(plan, indent="    "):
    lines = []
    for node, depth in walk(plan["Plan"]):
        title = node["Node Type"]
        if node.get("Strategy") and node["Node Type"] == "Aggregate":
            title = f"{node['Strategy']} Aggregate" if node["Strategy"] != "Plain" else "Aggregate"
        if node.get("Join Type") and node["Join Type"] != "Inner":
            title += f" {node['Join Type']}"
        if node.get("Relation Name"):
            title += f" on {node['Relation Name']}"
        if node.get("Index Name"):
            title += f" using {node['Index Name']}"
        stats = (f"rows={node.get('Actual Rows')} loops={node.get('Actual Loops')} "
                 f"buffers={node_buffers(node)}")
        rel = node.get("Parent Relationship")
        prefix = indent + "  " * depth + ("-> " if depth else "")
        if rel in ("InitPlan", "SubPlan"):
            prefix += f"[{rel}] "
        lines.append(f"{prefix}{title}  {dim(stats)}")
        pad = indent + "  " * depth + ("   " if depth else "") + "   "
        for key in ("Index Cond", "Recheck Cond", "Hash Cond", "Merge Cond", "Join Filter", "Filter"):
            if node.get(key):
                lines.append(dim(f"{pad}{key}: {short(node[key])}"))
        if node.get("Rows Removed by Filter"):
            lines.append(dim(f"{pad}Rows Removed by Filter: {node['Rows Removed by Filter']}"))
        if node["Node Type"] == "Index Only Scan":
            lines.append(dim(f"{pad}Heap Fetches: {node.get('Heap Fetches', 0)}"))
        if node.get("Sort Method"):
            lines.append(dim(f"{pad}Sort Method: {node['Sort Method']}"))
    return "\n".join(lines)


def plan_summary(plan):
    return (f"буферы: {total_buffers(plan)} · отброшено фильтром: {rows_removed(plan)} · "
            f"время: {plan.get('Execution Time', 0):.2f} ms")


# ---------------------------------------------------------------------------
# Правила
# ---------------------------------------------------------------------------

def rule_label(rule):
    name = next(iter(rule))
    return name, rule[name]


def eval_plan_rule(name, arg, plan, scale):
    if name == "must_have_node":
        ok = any(match_node(n, arg) for n, _ in walk(plan["Plan"]))
        return ok, f"в плане есть {describe_node(arg)}"
    if name == "must_not_have_node":
        bad = [n for n, _ in walk(plan["Plan"]) if match_node(n, arg)]
        return not bad, f"в плане нет {describe_node(arg)}"
    if name == "index_cond_contains":
        cols = arg["columns"]
        conds = [n.get("Index Cond", "") for n, _ in walk(plan["Plan"])
                 if n.get("Index Cond") and node_relation(n) == arg["relation"]]
        ok = any(all(re.search(rf"\b{re.escape(c)}\b", cond) for c in cols) for cond in conds)
        return ok, f"колонки {', '.join(cols)} в Index Cond по {arg['relation']}"
    if name == "max_buffers":
        limit = arg[scale] if isinstance(arg, dict) else arg
        got = total_buffers(plan)
        return got <= limit, f"буферов не больше {limit} (сейчас {got})"
    if name == "min_buffers":
        limit = arg[scale] if isinstance(arg, dict) else arg
        got = total_buffers(plan)
        return got >= limit, f"буферов не меньше {limit} (сейчас {got})"
    if name == "max_rows_removed_by_filter":
        got = rows_removed(plan)
        return got <= arg, f"отброшено фильтром не больше {arg} строк (сейчас {got})"
    if name == "heap_fetches_zero":
        ios = [n for n, _ in walk(plan["Plan"]) if n["Node Type"] == "Index Only Scan"]
        ok = bool(ios) and all(int(n.get("Heap Fetches", 0)) == 0 for n in ios)
        return ok, "Index Only Scan без походов в таблицу (Heap Fetches = 0)"
    raise LabError(f"неизвестное правило {name}")


def describe_node(spec):
    names = spec["node"] if isinstance(spec["node"], list) else [spec["node"]]
    text = " или ".join(names)
    if spec.get("relation"):
        text += f" по {spec['relation']}"
    if spec.get("index"):
        text += f" через {spec['index']}"
    return text


PLAN_RULES = {"must_have_node", "must_not_have_node", "index_cond_contains", "max_buffers",
              "min_buffers", "max_rows_removed_by_filter", "heap_fetches_zero"}


# ---------------------------------------------------------------------------
# Задания
# ---------------------------------------------------------------------------

def all_tasks():
    tasks = []
    for check_file in MODULES.glob("*/tasks/*/check.yaml"):
        cfg = yaml.safe_load(check_file.read_text(encoding="utf-8"))
        cfg["dir"] = check_file.parent
        cfg["module_dir"] = check_file.parent.parent.parent
        tasks.append(cfg)
    tasks.sort(key=lambda t: [int(x) for x in str(t["id"]).split(".")])
    return tasks


def find_task(task_id):
    for t in all_tasks():
        if str(t["id"]) == task_id:
            return t
    raise LabError(f"нет задания {task_id}. Список: lab status")


def module_tasks(module):
    return [t for t in all_tasks() if str(t["id"]).split(".")[0] == str(int(module))]


def solution_dir(task):
    return SOLUTIONS / task["dir"].name


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"hints": {}, "results": {}}


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def prediction_filled(task):
    path = task["dir"] / "prediction.md"
    if not path.exists():
        return True
    lines = path.read_text(encoding="utf-8").splitlines()
    return not any(line.strip() == ">" for line in lines)


class Result:
    def __init__(self):
        self.items = []  # (ok, text)
        self.error = None
        self.plans = []  # (title, before, after)

    def add(self, ok, text):
        self.items.append((ok, text))

    @property
    def passed(self):
        return self.error is None and bool(self.items) and all(ok for ok, _ in self.items)


def run_setup(task):
    setup = task["dir"] / "setup.sql"
    if setup.exists():
        psql(None, file=setup)


def apply_index_solution(task, path, res, limits):
    if not path.exists():
        raise LabError(f"нет файла {path.relative_to(ROOT)}")
    stmts = split_sql(path.read_text(encoding="utf-8"))
    if not stmts:
        raise LabError(f"{path.name} пустой: создайте индекс")
    bad = [s for s in stmts if not INDEX_TASK_ALLOWED.match(s)]
    if bad:
        raise LabError("в задании на индексы разрешены только CREATE INDEX, DROP INDEX, ANALYZE, VACUUM. "
                       f"Лишнее: «{short(bad[0], 50)}»")
    problems = check_forbidden(stmts, task.get("forbidden_sql", []))
    if problems:
        raise LabError("; ".join(problems))
    before = list_indexes()
    try:
        psql(";\n".join(stmts) + ";\n")
    except LabError as e:
        raise LabError(f"ошибка при выполнении {path.name}:\n{e}")
    after = list_indexes()
    new = {k: v for k, v in after.items() if k not in before}
    if "max_indexes" in limits:
        res.add(len(new) <= limits["max_indexes"],
                f"новых индексов не больше {limits['max_indexes']} (создано {len(new)})")
    for table, limit in (limits.get("max_table_indexes") or {}).items():
        count = int(scalar(f"""
            SELECT count(*) FROM pg_index i
            WHERE i.indrelid = 'public.{table}'::regclass AND NOT i.indisprimary"""))
        res.add(count <= limit, f"на {table} не больше {limit} индекс(ов) кроме первичного ключа (сейчас {count})")
    if "max_index_size_mb" in limits:
        size = sum(v[1] for v in new.values()) / 1024 / 1024
        res.add(size <= limits["max_index_size_mb"],
                f"новые индексы занимают не больше {limits['max_index_size_mb']} МБ ({size:.1f} МБ)")
    return new


def evaluate_query(task, spec, query, res, scale, *, label="", reference=None, baseline=None):
    writes = bool(task.get("writes"))
    settings = task.get("settings")
    rules = spec.get("rules", [])
    prefix = f"{label}: " if label else ""
    for r in rules:
        name, arg = rule_label(r)
        if name == "must_match":
            pattern = arg["pattern"] if isinstance(arg, dict) else arg
            text = arg.get("message", f"запрос подходит под шаблон {pattern}") if isinstance(arg, dict) else \
                f"запрос подходит под шаблон {pattern}"
            res.add(bool(re.search(pattern, query, re.I | re.S)), prefix + text)
    want_results = any(rule_label(r)[0] == "results_equal" for r in rules)
    if want_results:
        if reference is None:
            raise LabError("для results_equal нет эталонного запроса")
        exp_rows = run_rows(reference, writes=writes, settings=settings)
        got_rows = run_rows(query, writes=writes, settings=settings)
        ordered = spec.get("ordered", task.get("ordered", False))
        if not ordered:
            exp_rows, got_rows = sorted(exp_rows), sorted(got_rows)
        ok = exp_rows == got_rows
        detail = ""
        if not ok:
            detail = f" (строк: ожидалось {len(exp_rows)}, получено {len(got_rows)}"
            if exp_rows and got_rows and len(exp_rows[0]) != len(got_rows[0]):
                detail += f"; колонок: ожидалось {len(exp_rows[0])}, получено {len(got_rows[0])}"
            elif len(exp_rows) == len(got_rows):
                diff = next((i for i, (a, b) in enumerate(zip(exp_rows, got_rows)) if a != b), None)
                if diff is not None:
                    detail += f"; первое расхождение в строке {diff + 1}"
            detail += ")"
        res.add(ok, prefix + "результат совпадает с эталоном" + ("" if not ordered else ", включая порядок")
                + detail)
    plan_rules = [r for r in rules if rule_label(r)[0] in PLAN_RULES]
    if not plan_rules:
        return
    plan = explain(query, writes=writes, settings=settings)
    for r in plan_rules:
        name, arg = rule_label(r)
        ok, text = eval_plan_rule(name, arg, plan, scale)
        res.add(ok, prefix + text)
    before = None
    if baseline is not None:
        try:
            before = explain(baseline, writes=writes, settings=settings, runs=1)
        except LabError:
            before = None
    res.plans.append((label, before, plan))


def load_expected_answers(task):
    path = solution_dir(task) / "answers.yaml"
    if not path.exists():
        raise LabError(f"нет эталона ответов {path.relative_to(ROOT)}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def subst(text, scale):
    for k, v in SCALE_VARS.get(scale, {}).items():
        text = text.replace("{" + k + "}", v)
    return text


def compute_expected(spec, scale):
    if not isinstance(spec, dict):
        return spec
    if "value" in spec:
        v = spec["value"]
        return v[scale] if isinstance(v, dict) and scale in v else v
    if "sql" in spec:
        return scalar(subst(spec["sql"], scale))
    if "plan" in spec:
        p = spec["plan"]
        plan = explain(subst(p["query"], scale), settings=p.get("settings"))
        what = p["extract"]
        if what == "buffers":
            return total_buffers(plan)
        if what.startswith("scan_node:"):
            return scan_node_type(plan, what.split(":", 1)[1])
        if what == "rows_removed":
            return rows_removed(plan)
        raise LabError(f"неизвестный extract {what}")
    raise LabError(f"не понимаю эталон {spec}")


def norm_text(v):
    return re.sub(r"\s+", " ", str(v).strip().lower())


def answer_matches(got, expected, spec):
    tolerance = spec.get("tolerance", 0) if isinstance(spec, dict) else 0
    alts = expected if isinstance(expected, list) else [expected]
    for exp in alts:
        try:
            g, e = float(str(got).replace(",", ".")), float(exp)
            if abs(g - e) <= abs(e) * tolerance + 1e-9:
                return True
            continue
        except (TypeError, ValueError):
            pass
        if norm_text(got) == norm_text(exp):
            return True
    return False


def check_answers(task, res, scale, answers_override=None):
    expected = load_expected_answers(task)
    if answers_override is not None:
        got = answers_override
    else:
        path = task["dir"] / "answers.yaml"
        if not path.exists():
            raise LabError("нет файла answers.yaml")
        try:
            got = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise LabError(f"answers.yaml не разбирается: {e}")
    for key, spec in expected.items():
        exp = compute_expected(spec, scale)
        value = got.get(key)
        question = spec.get("label", key) if isinstance(spec, dict) else key
        if value is None or str(value).strip() == "":
            res.add(False, f"{question}: нет ответа")
            continue
        res.add(answer_matches(value, exp, spec), f"{question}: ответ «{value}»")
    return expected


def check_task(task, *, source="student", files=None, answers_override=None, show_baseline=True):
    """source=student: файлы ученика; files: подмена путей для selftest."""
    res = Result()
    scale = require_seed()
    ttype = task["type"]
    files = files or {}
    try:
        reset_db(quiet=source != "student")
        run_setup(task)
        if source == "student" and not prediction_filled(task):
            res.add(False, "prediction.md заполнен (строки «>» с прогнозом не пустые)")
        if ttype == "answers":
            check_answers(task, res, scale, answers_override)
            return res
        limits = task.get("limits", {})
        reference_path = solution_dir(task) / "solution.sql"
        baseline_path = task["dir"] / "query.sql"
        baseline = read_query_file(baseline_path) if baseline_path.exists() and show_baseline else None

        if ttype == "index":
            parts = task.get("parts") or [dict(task, file="query.sql", label="")]
            queries = [read_query_file(task["dir"] / p["file"]) for p in parts]
            befores = [explain(q, runs=1) if show_baseline else None for q in queries]
            apply_index_solution(task, files.get("solution.sql", task["dir"] / "solution.sql"), res, limits)
            for part, query, before in zip(parts, queries, befores):
                label = part.get("label", part["file"]) if task.get("parts") else ""
                n_plans = len(res.plans)
                evaluate_query(task, part, query, res, scale, label=label, reference=query)
                if len(res.plans) > n_plans:
                    res.plans[-1] = (label, before, res.plans[-1][2])
        elif ttype == "mixed":
            apply_index_solution(task, files.get("indexes.sql", task["dir"] / "indexes.sql"), res, limits)
            sol = files.get("solution.sql", task["dir"] / "solution.sql")
            query = read_query_file(sol)
            problems = check_forbidden([query], task.get("forbidden_sql", []))
            if problems:
                raise LabError("; ".join(problems))
            reference = read_query_file(reference_path)
            evaluate_query(task, task, query, res, scale, reference=reference, baseline=baseline)
        elif ttype == "query":
            if task.get("parts"):
                for part in task["parts"]:
                    path = files.get(part["file"], task["dir"] / part["file"])
                    try:
                        q = read_query_file(path)
                    except LabError as e:
                        res.add(False, f"{part['file']}: {e}")
                        continue
                    problems = check_forbidden([q], task.get("forbidden_sql", []))
                    if problems:
                        res.add(False, f"{part['file']}: " + "; ".join(problems))
                        continue
                    ref = None
                    if any(rule_label(r)[0] == "results_equal" for r in part.get("rules", [])):
                        ref = read_query_file(solution_dir(task) / part["file"])
                    evaluate_query(task, part, q, res, scale, label=part["file"], reference=ref)
            else:
                sol = files.get("solution.sql", task["dir"] / "solution.sql")
                query = read_query_file(sol)
                problems = check_forbidden([query], task.get("forbidden_sql", []))
                if problems:
                    raise LabError("; ".join(problems))
                reference = read_query_file(reference_path)
                evaluate_query(task, task, query, res, scale, reference=reference, baseline=baseline)
        else:
            raise LabError(f"неизвестный тип задания {ttype}")
    except LabError as e:
        res.error = str(e)
    return res


def print_result(task, res, verbose_plan=True):
    print()
    print(bold(f"Задание {task['id']}. {task['title']}") + dim(f"  [{TYPE_NAMES[task['type']]}]"))
    for ok, text in res.items:
        mark = green("  [OK]  ") if ok else red("  [FAIL]")
        print(f"{mark} {text}")
    if res.error:
        print(red("  [ERROR] ") + res.error.replace("\n", "\n          "))
    if verbose_plan:
        for label, before, after in res.plans:
            if before is not None:
                print(dim(f"\n  Было{(' (' + label + ')') if label else ''}: {plan_summary(before)}"))
                print(format_plan(before))
            print(f"\n  {'Стало' if before is not None else 'План'}"
                  f"{(' (' + label + ')') if label else ''}: {plan_summary(after)}")
            print(format_plan(after))
    print()
    print(bold("  ИТОГ: ") + (green(bold("PASS")) if res.passed else red(bold("FAIL"))))
    print()


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

def cmd_seed(args):
    sizes = SCALES[args.scale]
    print(f"Генерирую данные, масштаб {args.scale}: "
          + ", ".join(f"{k[2:]}={v:,}".replace(",", " ") for k, v in sizes.items()))
    t0 = time.time()
    psql(None, file=ROOT / "db" / "seed.sql", variables=sizes, timeout=3 * 3600)
    psql(f"""
        CREATE TABLE lab_meta.settings (key text PRIMARY KEY, value text);
        INSERT INTO lab_meta.settings VALUES ('scale', '{args.scale}'),
            ('seeded_at', now()::text);
    """)
    write_manifest()
    sizes_out = psql("""
        SELECT relname || ': ' || to_char(n_live_tup, 'FM999G999G999') || ' строк, '
               || pg_size_pretty(pg_total_relation_size(relid))
        FROM pg_stat_user_tables WHERE schemaname = 'public' ORDER BY relname
    """)
    print(sizes_out.rstrip())
    print(green(f"Готово за {time.time() - t0:.0f} с."))


def cmd_reset(args):
    reset_db()
    print(green("База возвращена к исходному состоянию."))


def cmd_check(args):
    state = load_state()
    if args.module is not None:
        tasks = module_tasks(args.module)
    elif args.task:
        tasks = [find_task(args.task)]
    else:
        raise LabError("укажите задание (lab check 1.1) или модуль (lab check --module 1)")
    summary = []
    for task in tasks:
        res = check_task(task)
        print_result(task, res, verbose_plan=args.module is None)
        status = "PASS" if res.passed else "FAIL"
        summary.append((task["id"], status))
        state["results"][str(task["id"])] = {"status": status, "at": dt.datetime.now().isoformat(timespec="seconds"),
                                             "scale": current_scale()}
    save_state(state)
    if len(summary) > 1:
        print(bold("Сводка: ") + "  ".join(
            f"{tid} {green('PASS') if s == 'PASS' else red('FAIL')}" for tid, s in summary))
    return 0 if all(s == "PASS" for _, s in summary) else 1


def cmd_hint(args):
    task = find_task(args.task)
    path = solution_dir(task) / "hints.md"
    if not path.exists():
        raise LabError("для этого задания подсказок нет")
    parts = re.split(r"^## .*$", path.read_text(encoding="utf-8"), flags=re.M)[1:]
    state = load_state()
    shown = state["hints"].get(str(task["id"]), 0)
    level = args.level if args.level else min(shown + 1, len(parts))
    level = max(1, min(level, len(parts)))
    for i in range(1, level + 1):
        print(bold(f"Подсказка {i} из {len(parts)}"))
        print(parts[i - 1].strip())
        print()
    if level >= len(parts):
        print(dim("Подсказок больше нет. Эталон и разбор лежат в solutions/, открывайте после PASS."))
    else:
        print(dim(f"Следующая: lab hint {task['id']}"))
    state["hints"][str(task["id"])] = max(shown, level)
    save_state(state)


def cmd_status(args):
    state = load_state()
    print(bold("Задание  Тип                 Статус  Подсказок  Название"))
    current = None
    for t in all_tasks():
        mod = t["module_dir"].name
        if mod != current:
            current = mod
            print(dim(f"-- {mod}"))
        r = state["results"].get(str(t["id"]))
        s = r["status"] if r else "-"
        s_col = green(s.ljust(6)) if s == "PASS" else red(s.ljust(6)) if s == "FAIL" else s.ljust(6)
        hints = state["hints"].get(str(t["id"]), 0)
        print(f"{str(t['id']).ljust(8)} {TYPE_NAMES[t['type']].ljust(19)} {s_col}  {str(hints).ljust(9)}  {t['title']}")
    passed = sum(1 for r in state["results"].values() if r["status"] == "PASS")
    print(dim(f"\nПройдено {passed} из {len(all_tasks())}. Масштаб базы: {current_scale() or 'не сгенерирована'}"))


def cmd_demo(args):
    mods = sorted(MODULES.glob(f"{int(args.module):02d}-*"))
    if not mods:
        raise LabError(f"нет модуля {args.module}")
    demo = mods[0] / "demo.sql"
    require_seed()
    reset_db()
    os.execvp("psql", ["psql", "-X", "-a", "-P", "pager=off", "-f", str(demo)])


def cmd_psql(args):
    os.execvp("psql", ["psql"] + args.rest)


def cmd_selftest(args):
    tasks = all_tasks()
    if args.module is not None:
        tasks = module_tasks(args.module)
    if args.task:
        tasks = [find_task(args.task)]
    scale = require_seed()
    failures = 0
    print(f"selftest, масштаб {scale}, повторов {args.repeat}")
    for task in tasks:
        try:
            failures += selftest_task(task, args, scale)
        except LabError as e:
            failures += 1
            print("  " + red("FAIL") + f" {task['id']} {task['title']}: {e}")
    reset_db(quiet=True)
    print()
    print(green("selftest пройден") if failures == 0 else red(f"selftest: проблемных заданий {failures}"))
    return 0 if failures == 0 else 1


def selftest_task(task, args, scale):
    if True:
        sdir = solution_dir(task)
        checks = []
        # 1. эталон проходит (несколько раз подряд: план стабилен)
        files = {p.name: p for p in sdir.glob("*.sql")}
        override = None
        if task["type"] == "answers":
            reset_db(quiet=True)
            run_setup(task)
            exp = load_expected_answers(task)
            override = {}
            for k, spec in exp.items():
                v = compute_expected(spec, scale)
                override[k] = v[0] if isinstance(v, list) else v
        for i in range(args.repeat):
            res = check_task(task, source="reference", files=files, answers_override=override, show_baseline=False)
            checks.append(("эталон проходит" + (f" (прогон {i + 1})" if args.repeat > 1 else ""), res.passed, res))
        # 2. заготовка из задания не проходит
        if task["type"] != "answers":
            res = check_task(task, source="starter", show_baseline=False)
            checks.append(("заготовка не проходит", not res.passed, res))
        # 3. соблазнительные неверные решения не проходят
        wrong_dir = sdir / "wrong"
        if wrong_dir.exists():
            for w in sorted(wrong_dir.iterdir()):
                tag_file = w / "scales" if w.is_dir() else w
                head = tag_file.read_text(encoding="utf-8").splitlines()[:1] if tag_file.is_file() else []
                m = re.match(r"--\s*scales:\s*(.+)", head[0]) if head else None
                if m and scale not in m.group(1).replace(",", " ").split():
                    checks.append((f"неверное решение {w.name}: пропущено на масштабе {scale}", True, None))
                    continue
                if w.is_dir():
                    wfiles = {p.name: p for p in w.glob("*.sql")}
                    wfiles = {**files, **wfiles}
                    wanswers = None
                    if (w / "answers.yaml").exists():
                        wanswers = yaml.safe_load((w / "answers.yaml").read_text(encoding="utf-8"))
                    res = check_task(task, source="wrong", files=wfiles, answers_override=wanswers,
                                     show_baseline=False)
                else:
                    target = "indexes.sql" if task["type"] == "mixed" and w.name.startswith("idx") else "solution.sql"
                    res = check_task(task, source="wrong", files={**files, target: w}, show_baseline=False)
                checks.append((f"неверное решение {w.name} не проходит", not res.passed, res))
        # 4. эталон даёт тот же результат, что исходный запрос
        if task["type"] in ("query", "mixed") and (task["dir"] / "query.sql").exists() \
                and task.get("original_matches", True):
            try:
                reset_db(quiet=True)
                run_setup(task)
                if task["type"] == "mixed" and "indexes.sql" in files:
                    psql(None, file=files["indexes.sql"])
                orig = run_rows(read_query_file(task["dir"] / "query.sql"))
                ref = run_rows(read_query_file(sdir / "solution.sql"))
                checks.append(("эталон совпадает по результату с исходным запросом",
                               sorted(orig) == sorted(ref), None))
            except LabError as e:
                checks.append((f"сравнение с исходным запросом: {e}", False, None))
        ok_all = all(ok for _, ok, _ in checks)
        print(("  " + green("OK  ") if ok_all else "  " + red("FAIL")) + f" {task['id']} {task['title']}")
        if not ok_all or args.verbose:
            for text, ok, r in checks:
                print(f"        {'ok ' if ok else red('BAD')} {text}")
                if r is not None and (not ok or args.verbose):
                    for iok, itext in r.items:
                        print(dim(f"              {'+' if iok else '-'} {itext}"))
                    if r.error:
                        print(dim(f"              ! {r.error}"))
                    if not ok:
                        for label, _, after in r.plans:
                            print(dim(f"              план{(' ' + label) if label else ''}: {plan_summary(after)}"))
                            print(format_plan(after, indent="              "))
    return 0 if ok_all else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="lab", description="Index Lab: практикум по Use The Index, Luke")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seed", help="сгенерировать данные")
    s.add_argument("--scale", choices=SCALES, default="s")
    s.set_defaults(fn=cmd_seed)

    s = sub.add_parser("reset", help="вернуть базу к исходному состоянию")
    s.set_defaults(fn=cmd_reset)

    s = sub.add_parser("check", help="проверить задание")
    s.add_argument("task", nargs="?")
    s.add_argument("--module", type=int)
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("hint", help="следующая подсказка")
    s.add_argument("task")
    s.add_argument("level", nargs="?", type=int)
    s.set_defaults(fn=cmd_hint)

    s = sub.add_parser("status", help="прогресс по заданиям")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("demo", help="выполнить демо-скрипт модуля")
    s.add_argument("module")
    s.set_defaults(fn=cmd_demo)

    s = sub.add_parser("psql", help="открыть psql")
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_psql)

    s = sub.add_parser("selftest", help="для автора: эталоны проходят, заготовки и ловушки падают")
    s.add_argument("--module", type=int)
    s.add_argument("--task")
    s.add_argument("--repeat", type=int, default=1)
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_selftest)

    args = p.parse_args(argv)
    try:
        rc = args.fn(args)
    except LabError as e:
        print(red(f"Ошибка: {e}"), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
