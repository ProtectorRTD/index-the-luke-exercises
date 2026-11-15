-- Ловушка: по индексу на группу запросов, бюджет превышен
CREATE INDEX i1 ON tickets (assignee_id, status, priority);
CREATE INDEX i2 ON tickets (status, priority);
CREATE INDEX i3 ON tickets (customer_id, status);
