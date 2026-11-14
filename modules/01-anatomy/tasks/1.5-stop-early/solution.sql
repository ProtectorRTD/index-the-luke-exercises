-- Задание 1.5. Перепишите запрос так, чтобы чтение остановилось на первой подходящей строке.
-- Сейчас здесь исходный запрос: проверка его не пропустит.
SELECT count(*) > 0 AS has_delivered
FROM orders
WHERE customer_id = 17 AND status = 'delivered';
