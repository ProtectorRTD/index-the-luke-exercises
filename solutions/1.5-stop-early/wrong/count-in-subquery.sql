-- Ловушка: подзапрос ничего не ограничивает, count всё равно перебирает все строки.
SELECT count(*) > 0 AS has_delivered
FROM (SELECT 1 FROM orders WHERE customer_id = 17 AND status = 'delivered') t;
