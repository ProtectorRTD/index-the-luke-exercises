-- Задание 1.4, файл c.sql. Замените ___ на условие по created_at.
SELECT count(*), min(email)
FROM customers
WHERE EXTRACT(YEAR FROM created_at) >= 2020 and EXTRACT(YEAR FROM created_at) <= 2025
