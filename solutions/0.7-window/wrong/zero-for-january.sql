-- Ловушка: 0 вместо NULL для января
WITH monthly AS (
    SELECT date_trunc('month', created_at)::date AS month, sum(total) AS revenue
    FROM orders WHERE status = 'delivered' AND created_at >= '2025-01-01' AND created_at < '2026-01-01'
    GROUP BY 1)
SELECT month, revenue, sum(revenue) OVER (ORDER BY month),
       coalesce(round(100 * (revenue - lag(revenue) OVER (ORDER BY month)) / lag(revenue) OVER (ORDER BY month), 1), 0)
FROM monthly ORDER BY month;
