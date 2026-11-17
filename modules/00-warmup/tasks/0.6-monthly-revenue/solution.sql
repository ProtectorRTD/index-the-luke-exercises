-- Задание 0.6. Напишите запрос.
select date_trunc('month', created_at)::date as month, sum(total)
from orders
where
    created_at >= '2025-01-01' and
    created_at < '2026-01-01' and
    status = 'delivered'
group by month
order by month