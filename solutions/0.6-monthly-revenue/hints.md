## 1

Месяц заказа: `date_trunc('month', created_at)`. Это `timestamptz`, а нужен `date`: добавьте `::date`.

## 2

Год задайте диапазоном: `created_at >= '2025-01-01' AND created_at < '2026-01-01'`.

## 3

`SELECT date_trunc('month', created_at)::date AS month, sum(total) ... GROUP BY 1 ORDER BY 1`
