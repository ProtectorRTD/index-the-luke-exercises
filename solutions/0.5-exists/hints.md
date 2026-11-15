## 1

Если соединить клиентов с заказами через `JOIN`, клиент с тремя крупными заказами появится трижды.

## 2

Подойдёт `EXISTS`: он только проверяет наличие и не размножает строки.

## 3

`WHERE c.country = 'AT' AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.total > 3000) ORDER BY c.id`
