-- Ловушка: «открытых всего 2%, значит индекс поможет»
CREATE INDEX tickets_customer_id_idx ON tickets (customer_id);
CREATE INDEX tickets_status_idx ON tickets (status);
