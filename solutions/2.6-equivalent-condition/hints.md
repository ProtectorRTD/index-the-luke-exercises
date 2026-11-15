## 1

В исходном плане `customer_id` в `Index Cond`, а `shipped_at IS NULL` в `Filter`: прочитаны все заказы клиента. `shipped_at` в индексе нет.

## 2

По бизнес-правилу «не отправлен» значит «статус один из трёх». А `status` в индексе есть, второй колонкой.

## 3

`WHERE customer_id = 17 AND status IN ('pending', 'processing', 'cancelled')`
