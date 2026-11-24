-- Задание 1.9. Разрешены только CREATE INDEX, DROP INDEX, ANALYZE, VACUUM.
CREATE INDEX if not exists IDX_CUSTOMER_ID on tickets (customer_id);
CREATE INDEX if not exists IDX_CREATED_AT on tickets (created_at);
