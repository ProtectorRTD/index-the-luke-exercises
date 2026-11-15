CREATE INDEX orders_cs_idx ON orders (customer_id, status);
CREATE INDEX orders_sc_idx ON orders (status, customer_id);
