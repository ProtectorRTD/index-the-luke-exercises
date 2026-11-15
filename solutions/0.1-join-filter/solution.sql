SELECT count(*) AS pending_orders
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.country = 'CZ' AND o.status = 'pending';
