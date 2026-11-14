# Шпаргалка к модулю 0

Все примеры на нашей схеме, их можно выполнять в `lab psql`.

## Фильтры и соединения

```sql
-- заказы клиентов из Австрии дороже 1000
SELECT o.id, o.total, c.email
FROM orders o
JOIN customers c ON c.id = o.customer_id     -- условие соединения
WHERE c.country = 'AT' AND o.total > 1000;   -- фильтр

-- все клиенты и число их заказов, включая клиентов без заказов
SELECT c.id, count(o.id) AS orders_count     -- count(o.id) не считает NULL
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id;
```

`count(*)` считает строки, `count(колонка)` — строки, где колонка не `NULL`. После `LEFT JOIN` у клиента без заказов будет одна строка с `o.id = NULL`: `count(*)` даст 1, `count(o.id)` даст 0.

## Группировка

```sql
SELECT status, count(*) AS n, round(avg(total), 2) AS avg_total
FROM orders
GROUP BY status
HAVING count(*) > 10000      -- фильтр по группам
ORDER BY n DESC;             -- можно ссылаться на псевдоним из SELECT
```

Каждая колонка в `SELECT` должна быть либо в `GROUP BY`, либо внутри агрегата (`count`, `sum`, `avg`, `min`, `max`).

## Сортировка и ограничение

```sql
SELECT id, total FROM orders
ORDER BY total DESC, id      -- при равных total порядок по id: результат однозначный
LIMIT 10;
```

Без второго ключа сортировки строки с одинаковым `total` могут прийти в любом порядке.

## EXISTS и NOT EXISTS

```sql
-- клиенты, у которых есть отменённый заказ
SELECT c.id FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.status = 'cancelled');

-- клиенты без единого заказа
SELECT c.id FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

## Даты

```sql
-- заказы за 2025 год: полуоткрытый интервал, без функций над колонкой
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01'

-- начало месяца: 2025-03-17 14:05 → 2025-03-01 00:00
date_trunc('month', created_at)

-- привести к дате без времени
date_trunc('month', created_at)::date

-- выделить часть даты
extract(year FROM created_at)
```

## CTE

```sql
WITH big_orders AS (
    SELECT customer_id, count(*) AS n
    FROM orders
    WHERE total > 3000
    GROUP BY customer_id
)
SELECT c.country, sum(b.n)
FROM big_orders b
JOIN customers c ON c.id = b.customer_id
GROUP BY c.country;
```

## Оконные функции

```sql
SELECT id, customer_id, total,
       row_number() OVER (PARTITION BY customer_id ORDER BY total DESC, id) AS rn,   -- номер внутри клиента
       sum(total)   OVER (PARTITION BY customer_id ORDER BY id)             AS running, -- нарастающий итог
       lag(total)   OVER (PARTITION BY customer_id ORDER BY id)             AS prev     -- предыдущее значение
FROM orders
WHERE customer_id = 17;
```

Отфильтровать по оконной функции можно только снаружи:

```sql
SELECT * FROM (
    SELECT id, customer_id,
           row_number() OVER (PARTITION BY customer_id ORDER BY created_at DESC) AS rn
    FROM orders
    WHERE customer_id IN (17, 18)
) t
WHERE rn <= 2;
```

## Округление и деление

```sql
round(x, 2)                 -- до двух знаков
100.0 * a / b               -- 100.0, а не 100: иначе деление целых отбросит дробную часть
round(100 * (a - b) / b, 1) -- процент изменения
```

Если `b` равно `NULL`, результат тоже `NULL`. Это нормально для «изменения к прошлому месяцу» у первого месяца.

## EXPLAIN

```sql
EXPLAIN SELECT ...;                         -- только план
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;      -- выполнить и показать факт и страницы
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) ...;  -- без оценок стоимости, короче
```

## psql

```
\d               список таблиц
\d orders        колонки и индексы таблицы
\x auto          широкие строки показывать вертикально
\timing on       время каждого запроса
\i путь/файл.sql выполнить файл
\q               выйти
```
