WITH units AS (
    SELECT p.category_id, p.id AS product_id, p.name AS product_name, sum(oi.quantity) AS units
    FROM order_items oi
    JOIN orders o   ON o.id = oi.order_id
    JOIN products p ON p.id = oi.product_id
    WHERE o.status = 'delivered'
      AND o.created_at >= '2025-01-01' AND o.created_at < '2026-01-01'
    GROUP BY p.category_id, p.id, p.name
),
ranked AS (
    SELECT u.*, row_number() OVER (PARTITION BY u.category_id ORDER BY u.units DESC, u.product_id) AS rank
    FROM units u
)
SELECT c.name AS category, r.product_id, r.product_name, r.units, r.rank
FROM ranked r
JOIN categories c ON c.id = r.category_id
WHERE r.rank <= 3
ORDER BY c.name, r.rank;
