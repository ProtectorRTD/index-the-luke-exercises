-- Ловушка: три индекса при бюджете в два
CREATE INDEX tickets_customer_id_idx ON tickets (customer_id);
CREATE INDEX tickets_created_at_idx ON tickets (created_at);
CREATE INDEX tickets_assignee_id_idx ON tickets (assignee_id);
