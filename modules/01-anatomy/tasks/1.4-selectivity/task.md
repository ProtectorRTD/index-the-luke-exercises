# 1.4. Три плана одного запроса

**Тип:** запросы. Индекс дан, писать нужно условия.

## Сценарий

`setup.sql` создаёт индекс по дате регистрации клиента:

```sql
CREATE INDEX customers_created_at_idx ON customers (created_at);
```

Клиенты регистрировались равномерно с 2020 по 2025 год, и порядок строк в таблице с датой регистрации никак не связан.

Маркетинг считает клиентов за разные периоды. Запрос всегда одной формы, меняется только условие на `created_at`:

```sql
SELECT count(*), min(email) FROM customers WHERE ___;
```

## Что сделать

Допишите условие в трёх файлах так, чтобы планировщик выбрал разные способы чтения таблицы:

| Файл | Нужный узел по `customers` |
| --- | --- |
| `a.sql` | `Index Scan using customers_created_at_idx` |
| `b.sql` | `Bitmap Heap Scan` поверх `Bitmap Index Scan on customers_created_at_idx` |
| `c.sql` | `Seq Scan` |

Порядок работы:

1. В `prediction.md` прикиньте, какая доля строк нужна для каждого плана.
2. `lab reset`, затем в `lab psql` выполните `\i modules/01-anatomy/tasks/1.4-selectivity/setup.sql`.
3. Подбирайте условия, проверяя `EXPLAIN`. Сколько строк попадает под условие, считайте через `count(*)`.
4. `lab check 1.4`.

## Как проверяется

- запрос в каждом файле имеет вид `SELECT count(*), min(email) FROM customers WHERE <условие на created_at>`;
- в плане `a.sql` есть `Index Scan` через `customers_created_at_idx`;
- в плане `b.sql` есть `Bitmap Heap Scan` по `customers` и `Bitmap Index Scan` через `customers_created_at_idx`;
- в плане `c.sql` есть `Seq Scan` по `customers`.

## Какой SQL понадобится

Сравнения `=`, `<`, `>=`, `BETWEEN` для дат: `created_at >= '2024-01-01' AND created_at < '2024-02-01'`. Как посчитать долю строк, есть в [cheatsheet.md](../../cheatsheet.md).

После PASS запишите в `prediction.md` настоящие доли строк, при которых менялся план. Совпало с прогнозом?
