## 1

Группируем по стране, в каждой группе считаем строки.

## 2

В `ORDER BY` можно писать псевдоним из `SELECT`: `customers_count`. Второй ключ сортировки нужен, чтобы порядок при равенстве был однозначным.

## 3

`GROUP BY country ORDER BY customers_count DESC, country LIMIT 5`
