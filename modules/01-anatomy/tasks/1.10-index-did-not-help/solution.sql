-- Задание 1.10. Разрешены только CREATE INDEX, DROP INDEX, ANALYZE, VACUUM.
DROP INDEX IF EXISTS orders_status_idx;
CREATE INDEX orders_status_idx ON orders (customer_id);
-- CREATE INDEX orders_status_idx ON orders (status, customer_id); this is better, imo
