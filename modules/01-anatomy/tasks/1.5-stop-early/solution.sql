-- Задание 1.5. Перепишите запрос так, чтобы чтение остановилось на первой подходящей строке.
-- Сейчас здесь исходный запрос: проверка его не пропустит.
select EXISTS(SELECT * FROM orders
WHERE customer_id = 17
  AND status = 'delivered') AS has_delivered