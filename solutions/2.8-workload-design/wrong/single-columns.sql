-- Ловушка: по одной колонке на индекс
CREATE INDEX tickets_assignee_id_idx ON tickets (assignee_id);
CREATE INDEX tickets_customer_id_idx ON tickets (customer_id);
