SELECT id, amount, created_at
FROM refunds
WHERE status = 'new' AND customer_id = 4242;
