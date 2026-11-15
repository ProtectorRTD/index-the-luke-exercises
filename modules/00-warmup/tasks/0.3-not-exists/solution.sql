-- Задание 0.3. Напишите запрос.
select count(*)
from customers c 
where c.id not in 
(select orders.customer_id 
	from orders)

-- SELECT count(*)
-- FROM customers c
-- WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);