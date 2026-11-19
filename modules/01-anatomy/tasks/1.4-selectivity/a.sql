-- Задание 1.4, файл a.sql. Замените ___ на условие по created_at.
SELECT count(*), min(email)
FROM customers
WHERE created_at = '2020-01-01'
