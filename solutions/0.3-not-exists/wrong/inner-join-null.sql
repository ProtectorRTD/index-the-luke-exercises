-- Ловушка: обычный JOIN выбрасывает клиентов без заказов ещё до WHERE
SELECT count(*) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL;
