# 0.9. Читаем план: Hash Join

**Тип:** ответы. Ничего выполнять не нужно: план уже снят, его надо прочитать.

## Запрос

```sql
SELECT count(*) AS pending_orders
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.country = 'CZ' AND o.status = 'pending';
```

Это запрос из задания 0.1. Индексов, кроме первичных ключей, нет.

План снят на масштабе `s` командой `EXPLAIN (ANALYZE, BUFFERS)` и лежит в [plan.txt](plan.txt). Числа в плане фиксированы, на вашей базе они могут немного отличаться: отвечайте по файлу.

## Вопросы

Ответы впишите в `answers.yaml`. Названия узлов пишите как в плане, числа цифрами.

1. `join_node`: каким узлом соединяются таблицы.
2. `hash_table`: какая таблица (orders или customers) сложена в хеш-таблицу.
3. `orders_rows_removed`: сколько строк orders прочитано и отброшено фильтром.
4. `orders_buffers`: сколько страниц прочитал узел, читающий orders.
5. `total_buffers`: сколько страниц прочитал весь запрос.
6. `customers_estimated`: сколько строк из customers ожидал планировщик.
7. `customers_actual`: сколько строк из customers вернулось на самом деле.

Затем `lab check 0.9`.

Раздел 7 в [README модуля](../../README.md) объясняет, где что искать в плане.
