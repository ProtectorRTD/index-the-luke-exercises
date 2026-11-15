-- Задание 0.5. Напишите запрос.
select c.id, c.email 
from customers c 
join orders o on o.customer_id  = c.id
where c.country = 'AT' and o.total > 3000
group by c.id, c.email 
order by id