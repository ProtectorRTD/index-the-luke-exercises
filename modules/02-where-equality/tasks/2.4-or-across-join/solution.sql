-- Задание 2.4. Перепишите запрос. Сейчас здесь исходный: проверка его не пропустит.
SELECT o.id, o.created_at, o.total, c.email
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.email = 'Peter.Oravec0004242@example.cz'
   OR o.id = 830947;
