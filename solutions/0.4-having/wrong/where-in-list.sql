-- scales: s
-- Ловушка: крупные статусы выписаны руками вместо HAVING. Появится новый крупный статус, и его не будет.
SELECT status, count(*) AS orders_count, round(avg(total), 2) AS avg_total
FROM orders
WHERE status IN ('delivered', 'shipped', 'cancelled')
GROUP BY status;
