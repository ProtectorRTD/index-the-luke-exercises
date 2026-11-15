SELECT id, status, created_at
FROM orders
WHERE customer_id = 17 AND shipped_at IS NULL;
