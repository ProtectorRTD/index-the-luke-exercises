-- Ловушка: во втором индексе нет status, t5 отбрасывает сотни строк фильтром
CREATE INDEX tickets_status_assignee_priority_idx ON tickets (status, assignee_id, priority);
CREATE INDEX tickets_customer_id_idx ON tickets (customer_id);
