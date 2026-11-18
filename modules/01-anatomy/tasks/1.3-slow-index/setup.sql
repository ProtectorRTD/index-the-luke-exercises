CREATE INDEX orders_customer_id_idx ON orders (customer_id);

-- explain (analyze, buffers)
-- SELECT sum(total) FROM orders WHERE customer_id = 54321;
--
-- SET enable_seqscan = off;
-- SET enable_bitmapscan = off;
-- explain (analyze, buffers)
-- SELECT sum(total) FROM orders WHERE customer_id <= 1000;