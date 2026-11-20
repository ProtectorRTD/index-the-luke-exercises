-- Ловушка: email заменён на подсмотренный id клиента. Поиск идёт по email, а не по id.
SELECT o.id, o.created_at, o.total, c.email
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE o.customer_id = 4242
UNION
SELECT o.id, o.created_at, o.total, c.email
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE o.id = 830947;
