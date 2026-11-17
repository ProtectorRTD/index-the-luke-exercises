-- Задание 0.4. Напишите запрос.
select status, count(*) as orders_count, round(avg(total), 2) as avg_total
from orders
group by status
having count(id) > 20000