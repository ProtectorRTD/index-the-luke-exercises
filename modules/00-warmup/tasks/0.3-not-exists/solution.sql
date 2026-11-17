-- Задание 0.3. Напишите запрос.
select count(*)
from customers c
where not exists(
    select o.id
    from orders o
    where o.customer_id = c.id
)