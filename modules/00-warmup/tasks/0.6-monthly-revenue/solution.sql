-- Задание 0.6. Напишите запрос.
SELECT date_trunc('month', created_at)::date AS month,
       sum(total) AS revenue
FROM orders
WHERE status = 'delivered'
  AND created_at >= '2025-01-01' AND created_at < '2026-01-01'
GROUP BY  date_trunc('month', created_at)::date
ORDER BY  date_trunc('month', created_at)::date;