CREATE INDEX orders_created_at_idx ON orders (created_at);

-- explain (analyse, buffers) select * from orders where created_at = '2021-02-06 19:03:20.000000 +00:00';
--
-- select * from bt_metap('orders_created_at_idx');
--
-- select * from bt_page_stats('orders_created_at_idx', 290);
--
-- SELECT s.type, count(*), avg(s.live_items)
-- FROM generate_series(1, (pg_relation_size('orders_created_at_idx') / 8192)::int - 1) AS b,
--      bt_page_stats('orders_created_at_idx', b) AS s
-- GROUP BY s.type;