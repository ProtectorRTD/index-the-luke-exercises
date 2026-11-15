SELECT status, count(*) AS orders_count, round(avg(total), 2) AS avg_total
FROM orders
GROUP BY status
HAVING count(*) > 20000;
