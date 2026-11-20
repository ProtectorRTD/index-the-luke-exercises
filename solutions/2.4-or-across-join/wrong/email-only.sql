-- scales: s
-- Ловушка: на масштабе s заказ 830947 принадлежит этому же клиенту, поэтому поиск только по email
-- случайно даёт тот же результат.
SELECT o.id, o.created_at, o.total, c.email
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE c.email = 'Peter.Oravec0004242@example.cz';
