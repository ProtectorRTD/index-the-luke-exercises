-- Ловушка: забыли LIMIT
SELECT country, count(*) FROM customers GROUP BY country ORDER BY 2 DESC, 1;
