-- Задание 0.7. Напишите запрос. Удобно начать с запроса из 0.6, обернув его в WITH.
with stat (month, total)
as (
    select date_trunc('month', created_at)::date as month, sum(total) as total
    from orders
    where created_at >= '2025-01-01'
      and created_at < '2026-01-01'
      and status = 'delivered'
    group by month
    order by month
)
select month, total
from stat