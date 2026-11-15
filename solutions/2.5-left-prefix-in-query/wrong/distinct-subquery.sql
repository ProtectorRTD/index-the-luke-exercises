-- Ловушка: список стран считается в том же запросе, а для этого читается весь индекс
SELECT id, email FROM customers
WHERE country = ANY (ARRAY(SELECT DISTINCT country FROM customers))
  AND last_name = 'novak' AND first_name = 'jana';
