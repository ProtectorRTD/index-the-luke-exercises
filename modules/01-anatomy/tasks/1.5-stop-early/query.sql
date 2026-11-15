SELECT count(*) > 0 AS has_delivered
FROM orders
WHERE customer_id = 17 AND status = 'delivered';
