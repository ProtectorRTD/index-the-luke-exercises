-- Ловушка: другое сравнение, та же работа.
SELECT count(*) >= 1 AS has_delivered
FROM orders
WHERE customer_id = 17 AND status = 'delivered';
