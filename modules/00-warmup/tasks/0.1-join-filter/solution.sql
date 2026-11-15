SELECT count(*) AS pending_orders
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'pending' and c.country = 'CZ'
