## 1

Шаг 1: соединить `order_items`, `orders`, `products`, отфильтровать заказы и посчитать `sum(quantity)` по товару.

## 2

Шаг 2: `row_number() OVER (PARTITION BY category_id ORDER BY units DESC, product_id)`. Шаг 3: снаружи `WHERE rank <= 3` и `JOIN categories` за названием.

## 3

Нумерацию нельзя отфильтровать в том же `SELECT`, где она считается: оконные функции вычисляются после `WHERE`. Нужен подзапрос или ещё один CTE.
