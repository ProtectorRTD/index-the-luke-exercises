-- ===========================================================================
-- Демо модуля 1. Запуск: lab demo 1
-- Каждая команда печатается перед выполнением. Читайте комментарии по ходу.
-- ===========================================================================

\pset pager off
\timing off

-- Шаг 1. Сколько места занимает таблица клиентов и сколько в ней страниц.
SELECT pg_size_pretty(pg_relation_size('customers')) AS size,
       pg_relation_size('customers') / 8192        AS pages,
       (SELECT count(*) FROM customers)             AS row_count;

-- Шаг 2. Ищем клиента по email. Индекса по email нет.
-- Смотрите на узел Seq Scan: он читает ВСЕ страницы таблицы (Buffers ≈ pages из шага 1)
-- и отбрасывает почти все строки (Rows Removed by Filter).
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, first_name, last_name FROM customers
WHERE email = 'Jana.Balazova0001000@example.sk';

-- Шаг 3. Создаём индекс по email.
CREATE INDEX demo_customers_email_idx ON customers (email);

-- Шаг 4. Тот же запрос. Теперь Index Scan: Index Cond вместо Filter,
-- и всего несколько страниц: спуск по дереву плюс одна страница таблицы.
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, first_name, last_name FROM customers
WHERE email = 'Jana.Balazova0001000@example.sk';

-- Шаг 5. Сколько уровней у дерева? level — уровни НАД листьями.
-- Глубина спуска = level + 1. Сравните с Buffers из шага 4.
SELECT root, level FROM bt_metap('demo_customers_email_idx');

-- Шаг 6. Типы страниц индекса: r — корень, i — внутренние, l — листья.
-- Листьев сотни, а внутренних страниц единицы: дерево очень широкое.
SELECT s.type, count(*) AS pages, sum(s.live_items) AS items
FROM generate_series(1, (pg_relation_size('demo_customers_email_idx') / 8192)::int - 1) AS b,
     bt_page_stats('demo_customers_email_idx', b) AS s
GROUP BY s.type ORDER BY s.type;

-- Шаг 7. Заглянем в корень. Каждая запись — «ключ-разделитель» и ссылка на страницу ниже.
-- В data ключ лежит в шестнадцатеричном виде, это нормально.
SELECT itemoffset, ctid, left(data, 40) AS data_prefix
FROM bt_page_items('demo_customers_email_idx', (SELECT root FROM bt_metap('demo_customers_email_idx')))
LIMIT 5;

-- Шаг 8. Лист индекса: здесь ctid — уже адрес строки в таблице (страница, позиция).
-- btpo_prev / btpo_next — соседние листья: это и есть двусвязный список.
SELECT type, live_items, btpo_prev, btpo_next
FROM bt_page_stats('demo_customers_email_idx', 1);

-- Шаг 9. Обратная сторона: индекс не помогает, когда строк много.
-- Индекс по стране, а 60% клиентов из SK. Планировщик выбирает Seq Scan.
CREATE INDEX demo_customers_country_idx ON customers (country);
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT count(*), max(created_at) FROM customers WHERE country = 'SK';

-- Шаг 10. Для редкой страны (около 2% клиентов) тот же индекс уже используется:
-- Bitmap Heap Scan. Но посмотрите на Heap Blocks: задета большая часть страниц таблицы,
-- потому что эти 2% строк разбросаны по всей таблице. Вот почему индекс выгоден только
-- для действительно редких значений.
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT count(*), max(created_at) FROM customers WHERE country = 'UA';

-- Уборка: удаляем индексы демо, база возвращается в исходное состояние.
DROP INDEX demo_customers_email_idx;
DROP INDEX demo_customers_country_idx;
