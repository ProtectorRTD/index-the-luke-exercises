-- Ловушка: начало года через >, заказ ровно в полночь 1 января 2025 теряется.
WITH monthly AS (
    SELECT date_trunc('month', created_at)::date AS month, sum(total) AS revenue
    FROM orders
    WHERE status = 'delivered' AND created_at > '2025-01-01' AND created_at < '2026-01-01'
    GROUP BY 1
)
SELECT month, revenue,
       sum(revenue) OVER (ORDER BY month) AS running_total,
       round(100 * (revenue - lag(revenue) OVER (ORDER BY month)) / lag(revenue) OVER (ORDER BY month), 1) AS change_pct
FROM monthly
ORDER BY month;
