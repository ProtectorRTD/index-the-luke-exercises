CREATE INDEX tickets_status_assignee_priority_idx ON tickets (status, assignee_id, priority);
CREATE INDEX tickets_customer_id_status_idx ON tickets (customer_id, status);
