-- Ловушка: Seq Scan получен условием не на created_at.
SELECT count(*), min(email) FROM customers WHERE country = 'SK';
