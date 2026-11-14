## 1

Заказ связан с клиентом колонкой `orders.customer_id`, она ссылается на `customers.id`.

## 2

В `WHERE` нужны условие на страну клиента и условие на статус заказа.

## 3

`JOIN customers c ON c.id = o.customer_id WHERE c.country = 'CZ' AND o.status = 'pending'`
