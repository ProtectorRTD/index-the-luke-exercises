-- Ловушка: месяц для a.sql. Строк уже слишком много для Index Scan.
SELECT count(*), min(email) FROM customers
WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';
