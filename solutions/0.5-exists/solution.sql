SELECT c.id, c.email
FROM customers c
WHERE c.country = 'AT'
  AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.total > 3000)
ORDER BY c.id;
