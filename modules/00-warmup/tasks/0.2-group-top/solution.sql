-- Задание 0.2. Замените ___ на нужные выражения.
SELECT country, count(*) AS customers_count
FROM customers
GROUP BY country
ORDER BY count(*) DESC, country
LIMIT 5;
