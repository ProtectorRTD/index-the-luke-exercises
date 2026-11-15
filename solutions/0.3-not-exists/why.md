# Разбор 0.3

```sql
SELECT count(*) FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

Эквивалент через `LEFT JOIN`:

```sql
SELECT count(*) FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.id IS NULL;
```

У клиентов без заказов после `LEFT JOIN` правая часть заполнена `NULL`, это их и выделяет.

В плане `NOT EXISTS` превращается в anti join: «оставить клиентов, для которых в заказах пары нет». В Postgres 16 это узел `Hash Right Anti Join`: хеш-таблица строится по клиентам, а заказы проверяются по ней. Подзапрос не выполняется для каждого клиента отдельно, таблицы соединяются целиком.

**Про `NOT IN`.** `WHERE c.id NOT IN (SELECT customer_id FROM orders)` здесь даст тот же ответ, потому что `customer_id` не бывает `NULL`. Но если в подзапросе встретится хоть один `NULL`, `NOT IN` вернёт пустой результат. Привычка писать `NOT EXISTS` избавляет от этой ловушки.
