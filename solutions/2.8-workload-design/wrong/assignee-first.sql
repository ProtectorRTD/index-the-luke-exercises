-- Ловушка: первой стоит колонка, которой нет в t3: он читает весь индекс
CREATE INDEX tickets_assignee_status_priority_idx ON tickets (assignee_id, status, priority);
CREATE INDEX tickets_customer_id_status_idx ON tickets (customer_id, status);
