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
import traceback
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("LAB_ROOT") or Path(__file__).resolve().parent.parent)
MODULES = ROOT / "modules"
SOLUTIONS = ROOT / "solutions"
STATE_FILE = ROOT / ".lab" / "state.json"

SCALES = {
    "s": dict(n_customers=100_000, n_products=10_000, n_orders=1_000_000, n_events=2_000_000, n_tickets=500_000),
    "m": dict(n_customers=1_000_000, n_products=50_000, n_orders=10_000_000, n_events=20_000_000, n_tickets=5_000_000),
}
# Подстановки в эталонах ответов: «оптовики» — первый 1% клиентов, они делают половину заказов.
SCALE_VARS = {"s": {"heavy": "1000"}, "m": {"heavy": "10000"}}
BASE_TABLES = ["categories", "customers", "products", "orders", "order_items", "events", "tickets", "tags", "ticket_tags"]

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
    "answers": "ответы",
}

LEVEL_NAMES = {
    "base": "база",
    "calc": "расчёт",
    "design": "проектирование",
    "investigate": "расследование",
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
    """Сбой не по вине решения: база, setup.sql, эталон, сам lab.py. В отчёте — ERROR."""


class SolutionError(LabError):
    """Ошибка в файлах решения: запрещённая команда, синтаксис, таймаут, пустой файл. В отчёте — FAILED."""


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


FULL_STATS_SQL = """
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.relname, a.attname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = 1
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname IN (SELECT name FROM lab_meta.manifest WHERE kind = 'r')
    LOOP
        EXECUTE format('ALTER TABLE public.%I ALTER COLUMN %I SET STATISTICS 10000', r.relname, r.attname);
        EXECUTE format('ANALYZE public.%I', r.relname);
    END LOOP;
END $$;
INSERT INTO lab_meta.settings VALUES ('stats', 'full') ON CONFLICT (key) DO UPDATE SET value = 'full';
"""


def require_seed():
    scale = current_scale()
    if not scale:
        raise LabError("База пустая. Сначала запустите: lab seed --scale s")
    if scalar("SELECT count(*) FROM lab_meta.settings WHERE key = 'stats'") == "0":
        # База сгенерирована до того, как статистику стали собирать по всей таблице.
        # Обновляем один раз, данные не меняются.
        print("Обновляю статистику планировщика (один раз, около минуты)...", flush=True)
        psql(FULL_STATS_SQL, timeout=3600)
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


def read_query_file(path, allow=QUERY_ALLOWED, err=LabError):
    """Читает файл с одним запросом. err=SolutionError для файлов, которые пишет человек."""
    if not path.exists():
        raise err(f"нет файла {path.relative_to(ROOT)}")
    stmts = split_sql(path.read_text(encoding="utf-8"))
    if not stmts:
        raise err(f"{path.name}: нет решения")
    if len(stmts) != 1:
        raise err(f"{path.name} должен содержать ровно один запрос, а в нём {len(stmts)}")
    q = stmts[0]
    if "___" in q:
        raise err(f"в {path.name} остались пропуски ___: заполните их")
    if not allow.match(q):
        raise err(f"{path.name}: ожидается запрос SELECT/WITH, а не «{q.split()[0]}»")
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


def base_table_changes():
    """Счётчики изменённых строк по базовым таблицам (включая откатившиеся транзакции)."""
    psql("SELECT pg_stat_force_next_flush();")
    rows = psql("""
        SELECT relname, n_tup_upd + n_tup_del + n_tup_ins FROM pg_stat_user_tables
        WHERE schemaname = 'public' AND relname IN (SELECT name FROM lab_meta.manifest WHERE kind = 'r')
    """, csv_out=True)
    return {r[0]: int(r[1]) for r in csv.reader(io.StringIO(rows))}


def modified_base_tables():
    """Базовые таблицы, в которых менялись данные после генерации."""
    psql("SELECT pg_stat_force_next_flush();")
    return psql("""
        SELECT s.relname FROM pg_stat_user_tables s
        JOIN lab_meta.table_stats t USING (relname)
        WHERE s.schemaname = 'public' AND s.n_tup_upd + s.n_tup_del + s.n_tup_ins > t.changes
    """).split()


def reset_db(quiet=False):
    require_seed()
    psql(RESET_SQL)
    changed = modified_base_tables()
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


def run_rows(query, *, writes=False, settings=None, timeout_s=300, pre=None):
    """pre: изменение данных перед запросом (вариант данных). Всё откатывается,
    а сам запрос после изменения выполняется в режиме только чтения."""
    block = ""
    if pre:
        block = pre.rstrip().rstrip(";") + ";\n"
        if not writes:
            block += "SET LOCAL transaction_read_only = on;\n"
    script = (tx_begin(writes or bool(pre)) + f"\nSET LOCAL statement_timeout = '{timeout_s}s';\n"
              + settings_sql(settings) + block + query + ";\nROLLBACK;\n")
    out = psql(script, csv_out=True, timeout=timeout_s + 30)
    return [tuple(normalize_value(x) for x in row) for row in csv.reader(io.StringIO(out))]


def explain(query, *, writes=False, settings=None, runs=2, timeout_s=300, pre=None):
    """Снимает план. Все прогоны идут в одной сессии, возвращается последний:
    первое обращение к таблице или индексу в сессии читает на несколько страниц больше."""
    block = (tx_begin(writes or bool(pre)) + f"\nSET LOCAL statement_timeout = '{timeout_s}s';\n"
             + settings_sql(settings) + (pre.rstrip().rstrip(";") + ";\n" if pre else "")
             + f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query};\nROLLBACK;\n")
    out = psql(block * runs, timeout=(timeout_s + 30) * runs)
    decoder, pos, plans = json.JSONDecoder(), 0, []
    while True:
        while pos < len(out) and out[pos].isspace():
            pos += 1
        if pos >= len(out):
            break
        doc, pos = decoder.raw_decode(out, pos)
        plans.append(doc[0])
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


def row_misestimate(plan):
    """Во сколько раз оценка числа строк расходится с фактом, максимум по узлам плана."""
    worst = 1.0
    for node, _ in walk(plan["Plan"]):
        if float(node.get("Actual Loops", 1)) == 0:
            continue
        est = max(float(node.get("Plan Rows", 1)), 1.0)
        act = max(float(node.get("Actual Rows", 0)), 1.0)
        worst = max(worst, est / act, act / est)
    return worst


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
    if name == "max_row_misestimate":
        got = row_misestimate(plan)
        return got <= arg, f"оценка числа строк расходится с фактом не больше чем в {arg} раз (сейчас в {got:.0f})"
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
              "min_buffers", "max_rows_removed_by_filter", "heap_fetches_zero", "max_row_misestimate"}


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


def first_error_line(e):
    for line in str(e).splitlines():
        line = line.strip()
        if line:
            return re.sub(r"^psql:[^:]*:\d+:\s*", "", line)
    return ""


class Result:
    def __init__(self):
        self.items = []  # (ok, text)
        self.error = None
        self.error_kind = None  # "failure" — ошибка в решении, "error" — сбой проверки
        self.plans = []  # (title, before, after)
        self.score = []  # строки со счётом для заданий на проектирование
        self.headline = []  # строки в начало подробного отчёта
        self.notes = []  # дополнительные строки отчёта
        self.metrics = {}  # числа для <properties> в JUnit
        self.wrong_answers = []  # ключи неверных ответов (без эталонных значений)
        self.answers_total = 0
        self.total_fail = None  # сообщение о превышении общего лимита страниц

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
        raise SolutionError(f"нет файла {path.relative_to(ROOT)}")
    stmts = split_sql(path.read_text(encoding="utf-8"))
    if not stmts:
        raise SolutionError(f"{path.name}: нет решения")
    extra = [re.compile(p, re.I) for p in task.get("allowed_sql", [])]
    bad = [s for s in stmts if not INDEX_TASK_ALLOWED.match(s) and not any(p.match(s) for p in extra)]
    if bad:
        raise SolutionError("в этом задании разрешены только CREATE INDEX, DROP INDEX, ANALYZE, VACUUM. "
                            f"Лишнее: «{short(bad[0], 50)}»")
    problems = check_forbidden(stmts, task.get("forbidden_sql", []))
    if problems:
        raise SolutionError("; ".join(problems))
    before = list_indexes()
    try:
        psql(";\n".join(stmts) + ";\n")
    except LabError as e:
        raise SolutionError(f"ошибка при выполнении {path.name}:\n{e}")
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
    for chk in task.get("post_checks", []):
        res.add(scalar(f"SELECT ({chk['sql']})::boolean") == "t", chk["message"])
    if new:
        res.notes.append("Новые индексы: " + ", ".join(
            f"{name} на {table}, {size / 1024 / 1024:.1f} МБ" for name, (table, size) in new.items()))
    return new


def compare_rows(res, prefix, exp_rows, got_rows, ordered, variant=None):
    if not ordered:
        exp_rows, got_rows = sorted(exp_rows), sorted(got_rows)
    ok = exp_rows == got_rows
    where = f" на изменённых данных ({variant})" if variant else ""
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
        if variant:
            res.headline.append(f"{prefix}результат не совпадает с эталоном{where}")
        else:
            res.headline.append(f"{prefix}результат не совпадает с эталоном: получено строк {len(got_rows)}, "
                                f"ожидалось {len(exp_rows)}")
    res.add(ok, prefix + "результат совпадает с эталоном" + ("" if not ordered else ", включая порядок")
            + where + detail)


def evaluate_query(task, spec, query, res, scale, *, label="", reference=None, baseline=None,
                   force_plan=False):
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
        ordered = spec.get("ordered", task.get("ordered", False))
        # Сначала исходные данные, потом варианты: те же запросы на изменённых данных
        # (изменение откатывается). Так ловится запрос, который совпал с эталоном случайно.
        for variant in [None] + list(spec.get("variants") or []):
            pre = variant["sql"] if variant else None
            exp_rows = run_rows(reference, writes=writes, settings=settings, pre=pre)
            try:
                got_rows = run_rows(query, writes=writes, settings=settings, pre=pre)
            except SolutionError:
                raise
            except LabError as e:
                where = f" на изменённых данных ({variant['name']})" if variant else ""
                raise SolutionError(f"{prefix}запрос не выполнился{where}: {first_error_line(e)}\n{e}")
            compare_rows(res, prefix, exp_rows, got_rows, ordered, variant["name"] if variant else None)
    plan_rules = [r for r in rules if rule_label(r)[0] in PLAN_RULES]
    if not plan_rules and not force_plan:
        return
    try:
        plan = explain(query, writes=writes, settings=settings)
    except SolutionError:
        raise
    except LabError as e:
        raise SolutionError(f"{prefix}запрос не выполнился: {first_error_line(e)}\n{e}")
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
        plan = explain(subst(p["query"], scale), settings=p.get("settings"),
                       pre=subst(p["pre"], scale) if p.get("pre") else None)
        what = p["extract"]
        if what == "buffers":
            return total_buffers(plan)
        if what == "total_cost":
            return plan["Plan"]["Total Cost"]
        if what == "plan_rows":
            return plan["Plan"]["Plan Rows"]
        if what == "actual_rows":
            return plan["Plan"]["Actual Rows"]
        if what.startswith("scan_node:"):
            return scan_node_type(plan, what.split(":", 1)[1])
        if what == "rows_removed":
            return rows_removed(plan)
        raise LabError(f"неизвестный extract {what}")
    raise LabError(f"не понимаю эталон {spec}")


def norm_text(v):
    return re.sub(r"\s+", " ", str(v).strip().lower())


def answer_matches(got, expected, spec):
    if isinstance(got, bool):  # YAML читает yes/no как логические значения
        got = "yes" if got else "no"
    tolerance = spec.get("tolerance", 0) if isinstance(spec, dict) else 0
    slack = spec.get("abs", 0) if isinstance(spec, dict) else 0
    alts = expected if isinstance(expected, list) else [expected]
    for exp in alts:
        try:
            g, e = float(str(got).replace(",", ".")), float(exp)
            if abs(g - e) <= max(abs(e) * tolerance, slack) + 1e-9:
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
            raise SolutionError("нет файла answers.yaml")
        try:
            got = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise SolutionError(f"answers.yaml не разбирается: {e}")
        if not isinstance(got, dict):
            raise SolutionError("answers.yaml должен состоять из строк вида «ключ: значение»")
    res.answers_total = len(expected)
    for key, spec in expected.items():
        exp = compute_expected(spec, scale)
        value = got.get(key)
        question = spec.get("label", key) if isinstance(spec, dict) else key
        tol = spec.get("tolerance") if isinstance(spec, dict) else None
        tol_text = f", допуск ±{tol * 100:g}%" if tol else ""
        if value is None or str(value).strip() == "":
            res.add(False, f"{question}: нет ответа")
            res.wrong_answers.append(key)
            continue
        ok = answer_matches(value, exp, spec)
        res.add(ok, f"{question}: ответ «{value}»{tol_text}")
        if not ok:
            res.wrong_answers.append(key)
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
        if ttype == "answers":
            check_answers(task, res, scale, answers_override)
            return res
        limits = task.get("limits", {})
        reference_path = solution_dir(task) / "solution.sql"
        baseline_path = task["dir"] / "query.sql"
        baseline = read_query_file(baseline_path) if baseline_path.exists() and show_baseline else None

        if ttype not in ("index", "mixed", "query"):
            raise LabError(f"неизвестный тип задания {ttype}")
        if ttype == "index":
            parts = task.get("parts") or [dict(task, file="query.sql", label="")]
            queries = [read_query_file(task["dir"] / p["file"]) for p in parts]
            befores = [explain(q, runs=1) if show_baseline else None for q in queries]
            new_indexes = apply_index_solution(task, files.get("solution.sql", task["dir"] / "solution.sql"),
                                               res, limits)
            total = task.get("total") or {}
            for part, query, before in zip(parts, queries, befores):
                label = part.get("label", part["file"]) if task.get("parts") else ""
                n_plans = len(res.plans)
                evaluate_query(task, part, query, res, scale, label=label, reference=query, force_plan=True)
                if len(res.plans) > n_plans:
                    res.plans[-1] = (label, before, res.plans[-1][2])
            if total:
                pages = sum(total_buffers(p[2]) for p in res.plans)
                if "max_total_buffers" in total:
                    limit = total["max_total_buffers"][scale]
                    res.add(pages <= limit, f"все запросы вместе читают не больше {limit} страниц (сейчас {pages})")
                    if pages > limit:
                        res.total_fail = f"все запросы читают {pages} страниц, лимит {limit}"
                size_mb = sum(v[1] for v in new_indexes.values()) / 1024 / 1024
                res.score.append(f"страниц на все запросы: {pages} · новых индексов: {len(new_indexes)} "
                                 f"· их размер: {size_mb:.1f} МБ")
                res.metrics.update(total_buffers=pages, new_indexes=len(new_indexes),
                                   index_size_mb=f"{size_mb:.1f}")
        elif ttype == "mixed":
            apply_index_solution(task, files.get("indexes.sql", task["dir"] / "indexes.sql"), res, limits)
            sol = files.get("solution.sql", task["dir"] / "solution.sql")
            query = read_query_file(sol, err=SolutionError)
            problems = check_forbidden([query], task.get("forbidden_sql", []))
            if problems:
                raise SolutionError("; ".join(problems))
            reference = read_query_file(reference_path)
            evaluate_query(task, task, query, res, scale, reference=reference, baseline=baseline,
                           force_plan=True)
        elif ttype == "query":
            if task.get("parts"):
                for part in task["parts"]:
                    path = files.get(part["file"], task["dir"] / part["file"])
                    if source == "student" and untouched_reason(task, part["file"]):
                        res.add(False, f"{part['file']}: нет решения")
                        continue
                    try:
                        q = read_query_file(path, err=SolutionError)
                    except SolutionError as e:
                        res.add(False, f"{part['file']}: {e}")
                        continue
                    problems = check_forbidden([q], task.get("forbidden_sql", []))
                    if problems:
                        res.add(False, f"{part['file']}: " + "; ".join(problems))
                        continue
                    ref = None
                    if any(rule_label(r)[0] == "results_equal" for r in part.get("rules", [])):
                        ref = read_query_file(solution_dir(task) / part["file"])
                    evaluate_query(task, part, q, res, scale, label=part["file"], reference=ref, force_plan=True)
            else:
                sol = files.get("solution.sql", task["dir"] / "solution.sql")
                query = read_query_file(sol, err=SolutionError)
                problems = check_forbidden([query], task.get("forbidden_sql", []))
                if problems:
                    raise SolutionError("; ".join(problems))
                reference = read_query_file(reference_path)
                evaluate_query(task, task, query, res, scale, reference=reference, baseline=baseline,
                               force_plan=True)
    except LabError as e:
        res.error = str(e)
        res.error_kind = "failure" if isinstance(e, SolutionError) else "error"
    if res.plans:
        res.metrics.setdefault("buffers", sum(total_buffers(p[2]) for p in res.plans))
        res.metrics.setdefault("execution_ms", f"{sum(p[2].get('Execution Time', 0) for p in res.plans):.2f}")
    return res


def render_result(task, res, verbose_plan=True):
    """Текст отчёта по заданию. Цвета — только если включены для терминала."""
    out = ["", bold(f"Задание {task['id']}. {task['title']}")
           + dim(f"  [{LEVEL_NAMES.get(task.get('level', 'base'), task.get('level'))} · "
                 f"{TYPE_NAMES.get(task['type'], task['type'])}]")]
    for line in res.headline:
        out.append(red("  ! ") + line)
    for ok, text in res.items:
        mark = green("  [OK]  ") if ok else red("  [FAIL]")
        out.append(f"{mark} {text}")
    if res.error:
        label = "  [FAIL]  " if res.error_kind == "failure" else "  [ERROR] "
        out.append(red(label) + res.error.replace("\n", "\n          "))
    for line in res.notes:
        out.append(dim("  " + line))
    if verbose_plan:
        for label, before, after in res.plans:
            if before is not None:
                out.append(dim(f"\n  Было{(' (' + label + ')') if label else ''}: {plan_summary(before)}"))
                out.append(format_plan(before))
            out.append(f"\n  {'Стало' if before is not None else 'План'}"
                       f"{(' (' + label + ')') if label else ''}: {plan_summary(after)}")
            out.append(format_plan(after))
    for line in res.score:
        out.append(bold("\n  Счёт: ") + line)
    out.append("")
    out.append(bold("  ИТОГ: ") + (green(bold("PASS")) if res.passed else red(bold("FAIL"))))
    out.append("")
    return "\n".join(out)


def print_result(task, res, verbose_plan=True):
    print(render_result(task, res, verbose_plan))


# ---------------------------------------------------------------------------
# «Не начато», статусы и JUnit-отчёт
# ---------------------------------------------------------------------------

def solution_files(task):
    """Файлы, которые заполняет человек. None — тип задания неизвестен."""
    ttype = task.get("type")
    if ttype == "answers":
        return ["answers.yaml"]
    if ttype == "index":
        return ["solution.sql"]
    if ttype == "mixed":
        return ["indexes.sql", "solution.sql"]
    if ttype == "query":
        return [p["file"] for p in task["parts"]] if task.get("parts") else ["solution.sql"]
    return None


def normalized_sql(text):
    return re.sub(r"\s+", " ", " ; ".join(split_sql(text))).strip().lower()


def untouched_reason(task, name):
    """Почему файл решения выглядит как нетронутая заготовка. None — файл заполнен."""
    path = task["dir"] / name
    if not path.exists():
        return f"нет файла {name}"
    text = path.read_text(encoding="utf-8")
    if name.endswith(".yaml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            return None  # что-то написано, пусть проверка покажет ошибку разбора
        if not data or (isinstance(data, dict) and all(v is None or str(v).strip() == "" for v in data.values())):
            return f"{name} не заполнен"
        return None
    norm = normalized_sql(text)
    if not norm:
        return f"{name} пустой"
    if "___" in norm:
        return f"в {name} заготовка с пропусками ___"
    original = task["dir"] / "query.sql"
    if task.get("type") in ("query", "mixed") and original.exists() \
            and norm == normalized_sql(original.read_text(encoding="utf-8")):
        return f"{name} совпадает с исходным запросом"
    return None


def not_started_reason(task):
    """Если все файлы решения нетронуты — причина для SKIPPED, иначе None."""
    names = solution_files(task)
    if names is None:
        return None
    reasons = [untouched_reason(task, n) for n in names]
    if all(reasons):
        return "; ".join(reasons)
    return None


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
XML_BAD_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def plain(text):
    """Текст для XML: без ANSI-кодов и управляющих символов."""
    return XML_BAD_CHARS.sub("", ANSI_RE.sub("", text or ""))


class Outcome:
    def __init__(self, task, status, message="", details="", properties=None):
        self.task = task
        self.status = status  # passed | failed | error | skipped
        self.message = message
        self.details = details
        self.properties = properties or {}
        self.time = 0.0


def failure_message(res):
    if res.answers_total and (res.wrong_answers or not res.error):
        n = len(res.wrong_answers)
        msg = f"неверно {n} из {res.answers_total}: " + ", ".join(res.wrong_answers)
    elif res.error:
        msg = res.error.strip().splitlines()[0]
    elif res.total_fail:
        msg = res.total_fail
        rest = sum(1 for ok, t in res.items if not ok and not t.startswith("все запросы вместе"))
        if rest:
            msg += f" (и ещё {rest})"
    else:
        failed = [t for ok, t in res.items if not ok]
        if not failed:
            return "задание не прошло проверку"
        if res.headline:
            msg = res.headline[0]
        elif failed[0].endswith(("нет решения", "нет ответа")):
            msg = failed[0]
        else:
            msg = f"{failed[0]} — не выполнено"
        if len(failed) > 1:
            msg += f" (и ещё {len(failed) - 1})"
    return msg if len(msg) <= 200 else msg[:199] + "…"


def outcome_from_result(task, res):
    props = {"level": task.get("level", "base"), "type": task["type"]}
    props.update(res.metrics)
    if res.passed:
        return Outcome(task, "passed", properties=props)
    details = plain(render_result(task, res, verbose_plan=True)).strip("\n")
    if res.score:
        details = "Счёт: " + res.score[0] + "\n\n" + details
    if res.error and res.error_kind == "error":
        return Outcome(task, "error", plain(first_error_line(res.error)), details, props)
    return Outcome(task, "failed", plain(failure_message(res)), details, props)


def write_junit(path, outcomes, suite_props):
    def fmt(t):
        return f"{t:.3f}"

    def counts(items):
        return dict(tests=str(len(items)),
                    failures=str(sum(o.status == "failed" for o in items)),
                    errors=str(sum(o.status == "error" for o in items)),
                    skipped=str(sum(o.status == "skipped" for o in items)),
                    time=fmt(sum(o.time for o in items)))

    root = ET.Element("testsuites", dict(name="Index Lab", **counts(outcomes),
                                         timestamp=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    modules = []
    for o in outcomes:
        name = o.task["module_dir"].name
        if name not in modules:
            modules.append(name)
    for module in modules:
        items = [o for o in outcomes if o.task["module_dir"].name == module]
        suite = ET.SubElement(root, "testsuite", dict(name=module, **counts(items)))
        props = ET.SubElement(suite, "properties")
        for k, v in suite_props.items():
            ET.SubElement(props, "property", name=k, value=plain(str(v)))
        for o in items:
            case = ET.SubElement(suite, "testcase", classname=module,
                                 name=plain(f"{o.task['id']} {o.task['title']}"), time=fmt(o.time))
            if o.properties:
                cprops = ET.SubElement(case, "properties")
                for k, v in o.properties.items():
                    ET.SubElement(cprops, "property", name=k, value=plain(str(v)))
            if o.status == "failed":
                el = ET.SubElement(case, "failure", message=plain(o.message), type="AssertionError")
                el.text = plain(o.details)
            elif o.status == "error":
                el = ET.SubElement(case, "error", message=plain(o.message), type="LabError")
                el.text = plain(o.details)
            elif o.status == "skipped":
                ET.SubElement(case, "skipped", message=plain(o.message))
    ET.indent(root)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        ET.ElementTree(root).write(f, encoding="UTF-8", xml_declaration=False)


def suite_properties():
    props = {"scale": current_scale()}
    try:
        props["postgres"] = scalar("SHOW server_version").split()[0]
    except LabError:
        pass
    try:
        if modified_base_tables():
            props["data_modified"] = "true"
    except LabError:
        pass
    return props


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
            ('seeded_at', now()::text), ('stats', 'full');
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
    if args.all:
        tasks = all_tasks()
    elif args.module is not None:
        tasks = module_tasks(args.module)
    elif args.task:
        tasks = [find_task(args.task)]
    else:
        raise LabError("укажите задание (lab check 1.1), модуль (lab check --module 1) или все (lab check --all)")
    require_seed()  # без базы проверять нечего: код возврата 2, отчёт не пишется
    single = len(tasks) == 1
    outcomes = []
    try:
        for task in tasks:
            t0 = time.monotonic()
            try:
                reason = not_started_reason(task)
                if reason:
                    outcome = Outcome(task, "skipped", f"не начато: {reason}",
                                      properties={"level": task.get("level", "base"), "type": task["type"]})
                    print(f"\n{bold('Задание ' + str(task['id']) + '. ' + task['title'])}  "
                          + dim(f"не начато: {reason}"))
                else:
                    res = check_task(task)
                    print_result(task, res, verbose_plan=single)
                    outcome = outcome_from_result(task, res)
                    state["results"][str(task["id"])] = {
                        "status": {"passed": "PASS", "failed": "FAIL", "error": "ERROR"}[outcome.status],
                        "at": dt.datetime.now().isoformat(timespec="seconds"), "scale": current_scale()}
            except Exception as e:  # сбой в самом lab.py не должен ронять весь прогон
                outcome = Outcome(task, "error", plain(f"{type(e).__name__}: {e}"),
                                  plain(traceback.format_exc()))
                print(red(f"\nЗадание {task['id']}: ERROR {type(e).__name__}: {e}"))
            outcome.time = time.monotonic() - t0
            outcomes.append(outcome)
    finally:
        save_state(state)
        if args.junit:
            write_junit(args.junit, outcomes, suite_properties())
            print(dim(f"JUnit-отчёт: {args.junit}"))
    if len(outcomes) > 1:
        names = {"passed": green("PASS"), "failed": red("FAIL"), "error": red("ERROR"), "skipped": dim("SKIP")}
        print(bold("\nСводка: ") + "  ".join(f"{o.task['id']} {names[o.status]}" for o in outcomes))
        print(dim("пройдено {p}, не пройдено {f}, ошибок {e}, не начато {s}".format(
            p=sum(o.status == "passed" for o in outcomes), f=sum(o.status == "failed" for o in outcomes),
            e=sum(o.status == "error" for o in outcomes), s=sum(o.status == "skipped" for o in outcomes))))
    return 1 if any(o.status in ("failed", "error") for o in outcomes) else 0


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
    print(bold("Задание  Уровень         Тип                 Статус  Подсказок  Название"))
    current = None
    for t in all_tasks():
        mod = t["module_dir"].name
        if mod != current:
            current = mod
            print(dim(f"-- {mod}"))
        r = state["results"].get(str(t["id"]))
        s = r["status"] if r else "-"
        s_col = green(s.ljust(6)) if s == "PASS" else red(s.ljust(6)) if s in ("FAIL", "ERROR") else s.ljust(6)
        hints = state["hints"].get(str(t["id"]), 0)
        print(f"{str(t['id']).ljust(8)} {LEVEL_NAMES.get(t.get('level', 'base'), str(t.get('level'))).ljust(15)} "
              f"{TYPE_NAMES.get(t['type'], t['type']).ljust(19)} {s_col}  {str(hints).ljust(9)}  {t['title']}")
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


def cmd_expected(args):
    """Для автора: показать эталонные значения задания с ответами."""
    task = find_task(args.task)
    scale = require_seed()
    reset_db(quiet=True)
    run_setup(task)
    for key, spec in load_expected_answers(task).items():
        print(f"{key}: {compute_expected(spec, scale)}")
    reset_db(quiet=True)


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
        changes_before = base_table_changes()
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
        # 5. проверка не трогает данные базовых таблиц: варианты данных только подменяют
        #    таблицы временными представлениями, даже откатившийся UPDATE оставил бы мусор в таблице
        changes_after = base_table_changes()
        touched = sorted(t for t, n in changes_after.items() if n > changes_before.get(t, 0))
        if touched:
            checks.append(("проверка меняет данные базовых таблиц: " + ", ".join(touched), False, None))
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
    s.add_argument("--all", action="store_true", help="все задания")
    s.add_argument("--junit", metavar="PATH", help="записать отчёт в формате JUnit XML")
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

    s = sub.add_parser("expected", help="для автора: эталонные ответы задания")
    s.add_argument("task")
    s.set_defaults(fn=cmd_expected)

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
