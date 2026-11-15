-- ===========================================================================
-- Демо модуля 2. Запуск: lab demo 2
-- ===========================================================================

\pset pager off

-- Шаг 1. Поиск по первичному ключу: одна строка, несколько страниц.
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT * FROM orders WHERE id = 500000;

-- Шаг 2. Индекс по одной колонке и условие на две.
-- status стоит в Filter: прочитаны все заказы клиента, почти все выброшены.
CREATE INDEX demo_customer_idx ON orders (customer_id);
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, total FROM orders WHERE customer_id = 17 AND status = 'cancelled';

-- Шаг 3. Составной индекс: обе колонки в Index Cond, страниц на порядок меньше.
CREATE INDEX demo_customer_status_idx ON orders (customer_id, status);
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, total FROM orders WHERE customer_id = 17 AND status = 'cancelled';

-- Шаг 4. Тот же составной индекс подходит и для условия только на первую колонку.
DROP INDEX demo_customer_idx;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT count(*), sum(total) FROM orders WHERE customer_id = 17;

-- Шаг 5. Обратный порядок колонок. Запрос по обеим колонкам по-прежнему быстрый...
DROP INDEX demo_customer_status_idx;
CREATE INDEX demo_status_customer_idx ON orders (status, customer_id);
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, total FROM orders WHERE customer_id = 17 AND status = 'cancelled';

-- Шаг 6. ...а запрос только по customer_id — нет. Посмотрите внимательно:
-- в плане есть Index Cond: (customer_id = 17), но Buffers — больше тысячи.
-- Postgres прочитал ВЕСЬ индекс и проверил customer_id на каждой записи.
-- Сравните с шагом 4.
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT count(*), sum(total) FROM orders WHERE customer_id = 17;

-- Размер этого индекса в страницах: примерно столько и прочитано.
SELECT pg_relation_size('demo_status_customer_idx') / 8192 AS index_pages;

-- Шаг 7. Два отдельных индекса и BitmapAnd: Postgres пересекает две битовые карты.
-- Работает, но индекс по status приходится читать по всему условию на статус.
DROP INDEX demo_status_customer_idx;
CREATE INDEX demo_customer_idx ON orders (customer_id);
CREATE INDEX demo_status_idx ON orders (status);
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, total FROM orders WHERE customer_id = 17 AND status = 'pending';

-- Уборка.
DROP INDEX demo_customer_idx;
DROP INDEX demo_status_idx;
