-- Ловушка: конец года задан как 23:59:59. Заказы в последнюю долю секунды года теряются.
SELECT date_trunc('month', created_at)::date AS month, sum(total) AS revenue
FROM orders
WHERE status = 'delivered'
  AND created_at BETWEEN '2025-01-01 00:00:00' AND '2025-12-31 23:59:59'
GROUP BY 1
ORDER BY 1;
