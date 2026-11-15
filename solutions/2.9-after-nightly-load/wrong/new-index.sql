-- Ловушка: составной индекс лечит этот запрос, но запрещён условием и не устраняет причину
CREATE INDEX refunds_customer_id_status_idx ON refunds (customer_id, status);
