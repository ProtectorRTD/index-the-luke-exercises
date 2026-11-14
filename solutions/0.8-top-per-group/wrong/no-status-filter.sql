-- Ловушка: забыли условие на статус заказа
WITH units AS (
    SELECT p.category_id, p.id AS product_id, p.name AS product_name, sum(oi.quantity) AS units
    FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN products p ON p.id = oi.product_id
    WHERE o.created_at >= '2025-01-01' AND o.created_at < '2026-01-01'
    GROUP BY 1, 2, 3),
ranked AS (SELECT u.*, row_number() OVER (PARTITION BY category_id ORDER BY units DESC, product_id) AS rank FROM units u)
SELECT c.name, r.product_id, r.product_name, r.units, r.rank FROM ranked r JOIN categories c ON c.id = r.category_id
WHERE rank <= 3 ORDER BY c.name, rank;
