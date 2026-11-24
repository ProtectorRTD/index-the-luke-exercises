-- Ловушка: BETWEEN включает обе границы, заказ ровно в полночь 1 января 2026 даёт тринадцатый месяц.
SELECT date_trunc('month', created_at)::date AS month, sum(total) AS revenue
FROM orders
WHERE status = 'delivered'
  AND created_at BETWEEN '2025-01-01' AND '2026-01-01'
GROUP BY 1
ORDER BY 1;
