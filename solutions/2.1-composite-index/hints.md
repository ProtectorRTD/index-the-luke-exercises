## 1

Посмотрите в план: какие условия из `WHERE` стоят в `Filter`? Их тоже нужно перенести в индекс.

## 2

Индекс может состоять из нескольких колонок: `CREATE INDEX ... ON orders (a, b);`.

## 3

`CREATE INDEX orders_customer_id_status_idx ON orders (customer_id, status);`
