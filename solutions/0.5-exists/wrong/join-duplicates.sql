-- Ловушка: JOIN размножает клиентов с несколькими крупными заказами
SELECT c.id, c.email FROM customers c JOIN orders o ON o.customer_id = c.id
WHERE c.country = 'AT' AND o.total > 3000 ORDER BY c.id;
