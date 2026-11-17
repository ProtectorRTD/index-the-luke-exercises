-- Задание 0.5. Напишите запрос.
select id, email
from customers c
where exists(
    select o.id
    from orders o
    where o.customer_id = c.id and o.total > 3000
) and country = 'AT'
order by id