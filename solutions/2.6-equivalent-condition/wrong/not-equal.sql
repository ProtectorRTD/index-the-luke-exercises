-- Ловушка: результат тот же, но <> не может быть access-предикатом
SELECT id, status, created_at FROM orders
WHERE customer_id = 17 AND status <> 'shipped' AND status <> 'delivered' AND status <> 'returned';
