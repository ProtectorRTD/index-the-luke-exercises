-- Ловушка: среднее не округлено
SELECT status, count(*), avg(total) FROM orders GROUP BY status HAVING count(*) > 20000;
