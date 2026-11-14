# Шпаргалка к модулю 1

Все примеры на нашей схеме, их можно выполнять в `lab psql`.

## EXPLAIN

```sql
-- только план, запрос не выполняется
EXPLAIN SELECT * FROM orders WHERE id = 42;

-- выполнить и показать фактические строки, время и страницы
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE id = 42;

-- то же без cost: короче читать
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) SELECT * FROM orders WHERE id = 42;
```

Осторожно: `EXPLAIN ANALYZE` для `UPDATE` и `DELETE` реально меняет данные. В этом модуле только `SELECT`.

## Индексы

```sql
CREATE INDEX customers_country_idx ON customers (country);  -- имя, таблица, колонка
DROP INDEX customers_country_idx;
```

В psql:

```
\d customers        -- колонки и индексы таблицы
\di+                -- все индексы с размерами
```

Размер объекта:

```sql
SELECT pg_size_pretty(pg_relation_size('customers'));          -- только таблица
SELECT pg_size_pretty(pg_relation_size('customers_pkey'));     -- индекс
SELECT pg_relation_size('customers') / 8192 AS pages;          -- в страницах
```

## Сколько строк подходит под условие

```sql
SELECT count(*) FROM orders WHERE total BETWEEN 1000 AND 1100;

-- доля от всей таблицы, в процентах
SELECT round(100.0 * count(*) FILTER (WHERE total BETWEEN 1000 AND 1100) / count(*), 2)
FROM orders;
```

`FILTER (WHERE …)` считает агрегат только по строкам, подходящим под условие.

## «Есть ли хоть одна строка»

```sql
-- считает ВСЕ подходящие строки, потом сравнивает с нулём
SELECT count(*) > 0 FROM orders WHERE customer_id = 42;

-- останавливается на первой найденной
SELECT EXISTS (SELECT 1 FROM orders WHERE customer_id = 42);
```

`EXISTS (подзапрос)` возвращает `true`, как только подзапрос нашёл первую строку. Что именно выбирает подзапрос, неважно, поэтому пишут `SELECT 1`.

## pageinspect

```sql
SELECT root, level FROM bt_metap('orders_pkey');
SELECT type, live_items FROM bt_page_stats('orders_pkey', 1);
SELECT itemoffset, ctid, data FROM bt_page_items('orders_pkey', 1) LIMIT 5;

-- обход всех страниц индекса (страница 0 — служебная, её пропускаем)
SELECT s.type, count(*)
FROM generate_series(1, (pg_relation_size('orders_pkey') / 8192)::int - 1) AS b,
     bt_page_stats('orders_pkey', b) AS s
GROUP BY s.type;
```

`generate_series(a, b)` выдаёт числа от a до b. Здесь она перебирает номера страниц, и для каждой вызывается `bt_page_stats`.

## Подсмотреть альтернативный план (только в psql, не в решениях)

```sql
SET enable_seqscan = off;     -- «запретить» Seq Scan в этой сессии
SET enable_bitmapscan = off;  -- и Bitmap Heap Scan
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
RESET ALL;                    -- вернуть как было
```

Это не запрет, а очень высокая стоимость: если других вариантов нет, Postgres всё равно сделает Seq Scan. В `solution.sql` такие команды запрещены, проверка их отклонит.
