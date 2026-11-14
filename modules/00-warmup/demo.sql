-- ===========================================================================
-- Демо модуля 0. Запуск: lab demo 0
-- ===========================================================================

\pset pager off

-- Шаг 1. Сколько строк в таблицах.
SELECT 'customers' AS t, count(*) FROM customers
UNION ALL SELECT 'orders', count(*) FROM orders
UNION ALL SELECT 'order_items', count(*) FROM order_items
UNION ALL SELECT 'products', count(*) FROM products;

-- Шаг 2. Перекосы в данных: статусы заказов.
SELECT status, count(*), round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM orders GROUP BY status ORDER BY 2 DESC;

-- Шаг 3. JOIN размножает строки. У клиента 17 сотни заказов,
-- поэтому после соединения он встречается сотни раз.
SELECT c.id, count(*) AS rows_after_join
FROM customers c JOIN orders o ON o.customer_id = c.id
WHERE c.id IN (17, 54321)
GROUP BY c.id;

-- Шаг 4. EXISTS не размножает: каждый клиент один раз.
SELECT c.id FROM customers c
WHERE c.id IN (17, 54321)
  AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);

-- Шаг 5. Оконная функция: три самых дорогих заказа клиента 17.
SELECT * FROM (
    SELECT id, total, row_number() OVER (ORDER BY total DESC, id) AS rn
    FROM orders WHERE customer_id = 17
) t WHERE rn <= 3;

-- Шаг 6. План запроса. Читайте снизу вверх:
-- два Seq Scan читают таблицы, Hash строит хеш-таблицу по клиентам из CZ,
-- Hash Join проверяет по ней заказы, Aggregate считает.
-- Найдите Rows Removed by Filter и Buffers у каждого узла.
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*)
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE c.country = 'CZ' AND o.status = 'pending';

-- Шаг 7. Ошибка оценки. Функция над колонкой: планировщик не знает,
-- сколько строк даст extract(year ...) = 2025, и берёт стандартную оценку 0,5%.
-- Сравните rows в первых и во вторых скобках у Seq Scan on orders.
EXPLAIN (ANALYZE)
SELECT count(*) FROM orders WHERE extract(year FROM created_at) = 2025;

-- Шаг 8. То же условие диапазоном по самой колонке: оценка почти точная.
EXPLAIN (ANALYZE)
SELECT count(*) FROM orders WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01';
