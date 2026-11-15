SELECT country, count(*) AS customers_count
FROM customers
GROUP BY country
ORDER BY count(*) DESC
LIMIT 5;