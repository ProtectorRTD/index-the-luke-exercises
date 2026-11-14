-- Точное время регистрации клиента 4242: планировщик ждёт одну строку.
SELECT count(*), min(email) FROM customers WHERE created_at = '2023-07-12 12:02:31+00';
