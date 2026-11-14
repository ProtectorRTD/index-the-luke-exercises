-- Ловушка: OR вместо AND
SELECT count(*) FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE c.country = 'CZ' OR o.status = 'pending';
