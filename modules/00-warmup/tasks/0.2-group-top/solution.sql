-- Задание 0.2. Замените ___ на нужные выражения.
SELECT country, count(*) AS customers_count
FROM customers
GROUP BY ___
ORDER BY ___ DESC, ___
LIMIT ___;
