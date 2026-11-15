-- Ловушка: выбраны две колонки с самой маленькой долей строк
CREATE INDEX tickets_customer_id_idx ON tickets (customer_id);
CREATE INDEX tickets_assignee_id_idx ON tickets (assignee_id);
