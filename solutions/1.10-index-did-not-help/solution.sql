DROP INDEX orders_status_idx;
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
