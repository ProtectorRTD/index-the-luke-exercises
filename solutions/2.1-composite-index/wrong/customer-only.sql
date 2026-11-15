-- Ловушка: status остаётся фильтром
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
