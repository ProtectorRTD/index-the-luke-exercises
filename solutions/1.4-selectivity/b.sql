-- Один месяц: около 1,4% клиентов.
SELECT count(*), min(email) FROM customers
WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';
