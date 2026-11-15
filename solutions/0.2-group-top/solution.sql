SELECT country, count(*) AS customers_count
FROM customers
GROUP BY country
ORDER BY customers_count DESC, country
LIMIT 5;
