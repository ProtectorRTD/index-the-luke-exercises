SELECT id, status, created_at
FROM orders
WHERE customer_id = 17 AND status IN ('pending', 'processing', 'cancelled');
