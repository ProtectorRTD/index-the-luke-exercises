-- Ловушка: обратный порядок колонок, q1 читает весь индекс
CREATE INDEX orders_status_customer_id_idx ON orders (status, customer_id);
