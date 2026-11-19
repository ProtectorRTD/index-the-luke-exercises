-- Задание 1.4, файл b.sql. Замените ___ на условие по created_at.
SELECT count(*), min(email)
FROM customers
WHERE created_at > '2024-01-01'

