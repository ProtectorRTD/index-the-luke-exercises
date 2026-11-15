-- Ловушка: q2 выбрасывает почти все строки фильтром
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
