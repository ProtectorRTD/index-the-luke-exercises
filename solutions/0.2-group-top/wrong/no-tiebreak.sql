-- Ловушка: нет второго ключа сортировки. При равном числе клиентов порядок и состав топа случайны.
SELECT country, count(*) AS customers_count
FROM customers
GROUP BY country
ORDER BY customers_count DESC
LIMIT 5;
