# Разбор 0.5

```sql
SELECT c.id, c.email
FROM customers c
WHERE c.country = 'AT'
  AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.total > 3000)
ORDER BY c.id;
```

Вариант с `IN` даёт тот же результат:

```sql
WHERE c.country = 'AT'
  AND c.id IN (SELECT customer_id FROM orders WHERE total > 3000)
```

Ловушка — `JOIN`: у оптовиков бывает несколько крупных заказов, и они попадут в результат несколько раз. `JOIN ... ` с `DISTINCT` исправит результат, но заставит базу сначала размножить строки, а потом убрать дубли.

Postgres переписывает `EXISTS` и `IN` в semi join: «оставить строку слева, если справа есть хотя бы одна пара». Здесь он выбрал такой способ: сначала собрать уникальные `customer_id` из крупных заказов (`HashAggregate`), потом обычный `Hash Join` с клиентами. Дублей не будет, потому что каждый `customer_id` справа встречается один раз.
