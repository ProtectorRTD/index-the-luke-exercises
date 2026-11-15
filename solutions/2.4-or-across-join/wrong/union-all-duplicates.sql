-- scales: s
-- Ловушка: без исключения во второй части заказ 830947 попадает в результат дважды.
-- На масштабе s он принадлежит клиенту 4242, на m — другому клиенту, поэтому проверяется только на s.
SELECT o.id, o.created_at, o.total, c.email
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE c.email = 'Peter.Oravec0004242@example.cz'
UNION ALL
SELECT o.id, o.created_at, o.total, c.email
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE o.id = 830947;
