-- Генератор данных Index Lab.
-- Запускается через `lab seed --scale s|m`, который передаёт размеры как переменные psql.
-- Данные детерминированы: setseed перед каждой таблицей, параллельность выключена,
-- поэтому на любой машине получаются одинаковые строки и одинаковые планы.

\set ON_ERROR_STOP on
SET client_min_messages = warning;
SET synchronize_seqscans = off;
SET max_parallel_workers_per_gather = 0;
SET maintenance_work_mem = '256MB';
SET work_mem = '256MB';
SET TIME ZONE 'UTC';

DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
DROP SCHEMA IF EXISTS lab_meta CASCADE;
CREATE SCHEMA lab_meta;
DO $$ BEGIN EXECUTE format('ALTER DATABASE %I SET timezone TO ''UTC''', current_database()); END $$;

CREATE EXTENSION IF NOT EXISTS pageinspect SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgstattuple SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements SCHEMA public;

-- ---------------------------------------------------------------------------
-- categories: 20 строк
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    id   int  PRIMARY KEY,
    name text NOT NULL
);
INSERT INTO categories (id, name)
SELECT i, n
FROM unnest(ARRAY[
    'Electronics','Books','Toys','Garden','Kitchen','Sports','Clothing','Shoes',
    'Beauty','Health','Office','Pets','Music','Games','Tools','Auto',
    'Baby','Jewelry','Food','Furniture']) WITH ORDINALITY AS t(n, i);

-- ---------------------------------------------------------------------------
-- customers
-- ---------------------------------------------------------------------------
SELECT setseed(0.11);
CREATE TABLE customers AS
SELECT
    g::bigint AS id,
    initcap(fn) || '.' || initcap(ln) || lpad(g::text, 7, '0') || '@' || dom AS email,
    fn AS first_name,
    ln AS last_name,
    country,
    '421' || lpad((floor(r_phone * 1e9))::bigint::text, 9, '0') AS phone,
    date_trunc('second', timestamptz '2020-01-01 00:00:00+00'
        + make_interval(secs => 189302400 * r_created)) AS created_at,
    CASE WHEN r_deleted < 0.01
         THEN timestamptz '2025-06-01 00:00:00+00' + make_interval(secs => 15768000 * r_deleted * 100)
    END AS deleted_at
FROM (
    SELECT g,
        (ARRAY['jana','peter','martin','lucia','tomas','eva','michal','zuzana','jan','maria',
               'lukas','katarina','marek','monika','jakub','simona','filip','petra','adam','veronika',
               'david','barbora','samuel','natalia','matej','kristina','andrej','lenka','pavol','ivana'])
            [1 + floor(random() * 30)::int] AS fn,
        (ARRAY['novak','novakova','novotny','horvath','horvathova','kovac','kovacova','varga','vargova','toth',
               'nagy','balaz','balazova','molnar','szabo','kral','kralova','lukac','simko','simkova',
               'polak','polakova','urban','urbanova','gajdos','kollar','kollarova','oravec','sloboda','slobodova',
               'hudak','hudakova','krajci','marko','markova','blaho','cerny','cerna','novy','nova'])
            [1 + floor(random() * 40)::int] AS ln,
        CASE WHEN random() < 0.6 THEN 'SK'
             ELSE (ARRAY['CZ','AT','HU','PL','DE','UA','IT','FR','ES','NL',
                         'BE','SI','HR','RO','BG','SE','DK','FI','IE','PT'])[1 + floor(random() * 20)::int]
        END AS country,
        (ARRAY['example.sk','example.cz','mail.example','post.example'])[1 + floor(random() * 4)::int] AS dom,
        random() AS r_phone,
        random() AS r_created,
        random() AS r_deleted
    FROM generate_series(1, :n_customers) g
) s;

-- ---------------------------------------------------------------------------
-- products
-- ---------------------------------------------------------------------------
SELECT setseed(0.22);
CREATE TABLE products AS
SELECT
    g::bigint AS id,
    'SKU-' || lpad(g::text, 7, '0') AS sku,
    initcap(adj) || ' ' || noun || ' ' || g AS name,
    category_id,
    round((1 + 499 * pow(r_price, 2))::numeric, 2) AS price
FROM (
    SELECT g,
        (ARRAY['basic','smart','mini','pro','eco','classic','ultra','compact','deluxe','travel'])
            [1 + floor(random() * 10)::int] AS adj,
        (ARRAY['Widget','Lamp','Bottle','Charger','Notebook','Backpack','Mug','Speaker','Blanket','Kit'])
            [1 + floor(random() * 10)::int] AS noun,
        1 + floor(random() * 20)::int AS category_id,
        random() AS r_price
    FROM generate_series(1, :n_products) g
) s;

-- ---------------------------------------------------------------------------
-- orders: 1% клиентов делают половину заказов, 90% delivered, рост к концу периода.
-- Строки лежат на диске в порядке created_at, как в живой системе.
-- ---------------------------------------------------------------------------
SELECT setseed(0.33);
CREATE TEMP TABLE orders_raw AS
SELECT
    g AS rn,
    CASE WHEN r_heavy < 0.5
         THEN 1 + floor(r_cust * (:n_customers / 100))::bigint
         ELSE 1 + floor(r_cust * :n_customers)::bigint
    END AS customer_id,
    CASE
        WHEN r_status < 0.900 THEN 'delivered'
        WHEN r_status < 0.940 THEN 'shipped'
        WHEN r_status < 0.970 THEN 'cancelled'
        WHEN r_status < 0.985 THEN 'returned'
        WHEN r_status < 0.995 THEN 'processing'
        ELSE 'pending'
    END AS status,
    date_trunc('second', timestamptz '2021-01-01 00:00:00+00'
        + make_interval(secs => 157766400 * sqrt(r_created))) AS created_at,
    r_ship,
    1 + floor(r_items * 5)::int AS n_items
FROM (
    SELECT g, random() AS r_heavy, random() AS r_cust, random() AS r_status,
           random() AS r_created, random() AS r_ship, random() AS r_items
    FROM generate_series(1, :n_orders) g
) s;

CREATE TEMP TABLE orders_sorted AS
SELECT row_number() OVER (ORDER BY created_at, rn)::bigint AS id,
       customer_id, status, created_at,
       CASE WHEN status IN ('delivered', 'shipped', 'returned')
            THEN date_trunc('second', created_at + make_interval(secs => 86400 + 345600 * r_ship))
       END AS shipped_at,
       n_items
FROM orders_raw;
DROP TABLE orders_raw;

-- ---------------------------------------------------------------------------
-- order_items: в среднем 3 позиции на заказ, популярность товаров сильно перекошена
-- ---------------------------------------------------------------------------
SELECT setseed(0.44);
CREATE TABLE order_items AS
SELECT
    row_number() OVER (ORDER BY o.id, i)::bigint AS id,
    o.id AS order_id,
    1 + floor(pow(random(), 3) * :n_products)::bigint AS product_id,
    1 + floor(pow(random(), 2) * 4)::int AS quantity
FROM (SELECT id, n_items FROM orders_sorted ORDER BY id) o,
     generate_series(1, o.n_items) i;

CREATE TABLE order_items_final AS
SELECT oi.id, oi.order_id, oi.product_id, oi.quantity, p.price AS unit_price
FROM order_items oi JOIN products p ON p.id = oi.product_id
ORDER BY oi.id;
DROP TABLE order_items;
ALTER TABLE order_items_final RENAME TO order_items;

CREATE TABLE orders AS
SELECT o.id, o.customer_id, o.status, o.created_at, o.shipped_at,
       t.total::numeric(12,2) AS total
FROM orders_sorted o
JOIN (SELECT order_id, sum(quantity * unit_price) AS total
      FROM order_items GROUP BY order_id) t ON t.order_id = o.id
ORDER BY o.id;
DROP TABLE orders_sorted;

-- ---------------------------------------------------------------------------
-- events: журнал за 2025 год, только вставка, id растёт вместе со временем.
-- Время округлено до минуты, поэтому у части событий одинаковый created_at.
-- ---------------------------------------------------------------------------
SELECT setseed(0.55);
CREATE TABLE events AS
SELECT
    g::bigint AS id,
    CASE WHEN random() < 0.5
         THEN 1 + floor(random() * (:n_customers / 100))::bigint
         ELSE 1 + floor(random() * :n_customers)::bigint
    END AS user_id,
    CASE
        WHEN r_type < 0.70 THEN 'page_view'
        WHEN r_type < 0.85 THEN 'add_to_cart'
        WHEN r_type < 0.95 THEN 'search'
        ELSE 'purchase'
    END AS type,
    date_trunc('minute', timestamptz '2025-01-01 00:00:00+00'
        + make_interval(secs => 31536000.0 * g / :n_events)) AS created_at,
    jsonb_build_object('page', '/p/' || (1 + floor(r_page * 1000))::int) AS payload
FROM (SELECT g, random() AS r_type, random() AS r_page
      FROM generate_series(1, :n_events) g) s;

-- ---------------------------------------------------------------------------
-- tickets: обращения в поддержку. Много колонок с малым числом значений,
-- редкий статус open, 3% обращений без исполнителя (assignee_id IS NULL).
-- Строки лежат на диске в порядке created_at.
-- ---------------------------------------------------------------------------
SELECT setseed(0.66);
CREATE TEMP TABLE tickets_raw AS
SELECT
    g AS rn,
    CASE WHEN r_heavy < 0.5
         THEN 1 + floor(r_cust * (:n_customers / 100))::bigint
         ELSE 1 + floor(r_cust * :n_customers)::bigint
    END AS customer_id,
    CASE WHEN r_unassigned < 0.03 THEN NULL
         ELSE 1 + floor(pow(r_assignee, 2) * 40)::int
    END AS assignee_id,
    CASE
        WHEN r_status < 0.80 THEN 'closed'
        WHEN r_status < 0.94 THEN 'solved'
        WHEN r_status < 0.98 THEN 'pending'
        ELSE 'open'
    END AS status,
    CASE
        WHEN r_priority < 0.30 THEN 'low'
        WHEN r_priority < 0.85 THEN 'normal'
        WHEN r_priority < 0.97 THEN 'high'
        ELSE 'urgent'
    END AS priority,
    CASE
        WHEN r_channel < 0.50 THEN 'email'
        WHEN r_channel < 0.80 THEN 'web'
        WHEN r_channel < 0.95 THEN 'chat'
        ELSE 'phone'
    END AS channel,
    1 + floor(r_category * 30)::int AS category_id,
    (ARRAY['Refund request','Delivery delay','Wrong item','Payment failed','Account access',
           'Invoice question','Damaged package','Change address','Cancel order','Product question'])
        [1 + floor(r_subject * 10)::int] || ' #' || g AS subject,
    date_trunc('second', timestamptz '2021-01-01 00:00:00+00'
        + make_interval(secs => 157766400 * sqrt(r_created))) AS created_at,
    r_closed
FROM (
    SELECT g, random() AS r_heavy, random() AS r_cust, random() AS r_unassigned, random() AS r_assignee,
           random() AS r_status, random() AS r_priority, random() AS r_channel, random() AS r_category,
           random() AS r_subject, random() AS r_created, random() AS r_closed
    FROM generate_series(1, :n_tickets) g
) s;

CREATE TABLE tickets AS
SELECT row_number() OVER (ORDER BY created_at, rn)::bigint AS id,
       customer_id, assignee_id, status, priority, channel, category_id, subject, created_at,
       CASE WHEN status IN ('solved', 'closed')
            THEN date_trunc('second', created_at + make_interval(secs => 3600 + 2592000 * r_closed))
       END AS closed_at
FROM tickets_raw
ORDER BY 1;
DROP TABLE tickets_raw;

-- ---------------------------------------------------------------------------
-- tags и ticket_tags: связь «многие ко многим». У таблицы связей только первичный ключ.
-- ---------------------------------------------------------------------------
CREATE TABLE tags (
    id   int  PRIMARY KEY,
    name text NOT NULL
);
INSERT INTO tags (id, name)
SELECT i, n
FROM unnest(ARRAY[
    'vip','refund','delivery','payment','bug','feature','complaint','praise','fraud','legal',
    'b2b','first-contact','escalated','waiting-customer','waiting-vendor','duplicate','spam',
    'follow-up','survey','other']) WITH ORDINALITY AS t(n, i);

SELECT setseed(0.77);
CREATE TABLE ticket_tags AS
SELECT DISTINCT tag_id, ticket_id
FROM (
    SELECT 1 + floor(pow(random(), 2) * 20)::int AS tag_id, t.id AS ticket_id
    FROM (SELECT id FROM tickets ORDER BY id) t,
         generate_series(1, 1 + (t.id % 3)::int) n
) s
ORDER BY ticket_id, tag_id;

-- ---------------------------------------------------------------------------
-- Ограничения: только первичные ключи и NOT NULL. Индексов на внешних ключах нет.
-- ---------------------------------------------------------------------------
ALTER TABLE customers   ALTER COLUMN email SET NOT NULL,
                        ALTER COLUMN country SET NOT NULL,
                        ALTER COLUMN created_at SET NOT NULL,
                        ADD PRIMARY KEY (id);
ALTER TABLE products    ALTER COLUMN sku SET NOT NULL,
                        ALTER COLUMN category_id SET NOT NULL,
                        ALTER COLUMN price SET NOT NULL,
                        ADD PRIMARY KEY (id);
ALTER TABLE orders      ALTER COLUMN customer_id SET NOT NULL,
                        ALTER COLUMN status SET NOT NULL,
                        ALTER COLUMN created_at SET NOT NULL,
                        ALTER COLUMN total SET NOT NULL,
                        ADD PRIMARY KEY (id);
ALTER TABLE order_items ALTER COLUMN order_id SET NOT NULL,
                        ALTER COLUMN product_id SET NOT NULL,
                        ALTER COLUMN quantity SET NOT NULL,
                        ALTER COLUMN unit_price SET NOT NULL,
                        ADD PRIMARY KEY (id);
ALTER TABLE events      ALTER COLUMN user_id SET NOT NULL,
                        ALTER COLUMN type SET NOT NULL,
                        ALTER COLUMN created_at SET NOT NULL,
                        ADD PRIMARY KEY (id);
ALTER TABLE tickets     ALTER COLUMN customer_id SET NOT NULL,
                        ALTER COLUMN status SET NOT NULL,
                        ALTER COLUMN priority SET NOT NULL,
                        ALTER COLUMN channel SET NOT NULL,
                        ALTER COLUMN category_id SET NOT NULL,
                        ALTER COLUMN subject SET NOT NULL,
                        ALTER COLUMN created_at SET NOT NULL,
                        ADD PRIMARY KEY (id);
ALTER TABLE ticket_tags ALTER COLUMN tag_id SET NOT NULL,
                        ALTER COLUMN ticket_id SET NOT NULL,
                        ADD PRIMARY KEY (tag_id, ticket_id);

VACUUM (ANALYZE, FREEZE);
CHECKPOINT;
