-- Половина клиентов: читать таблицу целиком дешевле.
SELECT count(*), min(email) FROM customers WHERE created_at >= '2023-01-01';
