-- Ловушка: если доставленных заказов нет, запрос вернёт ноль строк, а не false.
SELECT true AS has_delivered
FROM orders
WHERE customer_id = 17 AND status = 'delivered'
LIMIT 1;
