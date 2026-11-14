## 1

Нужны клиенты, для которых в `orders` **нет** ни одной строки с их `id`.

## 2

Подзапрос внутри `NOT EXISTS` должен ссылаться на клиента из внешнего запроса: `o.customer_id = c.id`.

## 3

`SELECT count(*) FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);`
