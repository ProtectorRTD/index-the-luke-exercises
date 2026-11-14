-- Ловушка: месяц остался timestamptz
SELECT date_trunc('month', created_at) AS month, sum(total) FROM orders
WHERE status = 'delivered' AND created_at >= '2025-01-01' AND created_at < '2026-01-01'
GROUP BY 1 ORDER BY 1;
