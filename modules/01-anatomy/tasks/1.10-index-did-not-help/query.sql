SELECT id, created_at, total
FROM orders
WHERE status = 'delivered' AND customer_id = 54321;
