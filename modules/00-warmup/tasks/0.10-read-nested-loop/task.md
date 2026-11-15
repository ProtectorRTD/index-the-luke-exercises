# 0.10. Читаем план: Nested Loop

**Тип:** ответы. Ничего выполнять не нужно: план уже снят, его надо прочитать.

## Запрос

```sql
SELECT c.email, o.id, o.total
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE c.id BETWEEN 100 AND 109;
```

Перед снятием плана был создан индекс `CREATE INDEX orders_customer_id_idx ON orders (customer_id);`. Клиенты 100–109 — оптовики, у каждого сотни заказов.

План снят на масштабе `s` командой `EXPLAIN (ANALYZE, BUFFERS)` и лежит в [plan.txt](plan.txt). Числа в плане фиксированы, на вашей базе они могут немного отличаться: отвечайте по файлу.

## Вопросы

Ответы впишите в `answers.yaml`. Названия узлов пишите как в плане, числа цифрами.

1. `join_node`: каким узлом соединяются таблицы.
2. `outer_table`: какая таблица читается во внешнем цикле (orders или customers).
3. `inner_loops`: сколько раз выполнился узел, читающий orders.
4. `inner_rows_per_loop`: сколько строк orders он возвращал за одно выполнение (как в плане).
5. `inner_rows_total`: сколько строк orders он вернул за все выполнения вместе.
6. `inner_expected_per_loop`: сколько строк за одно выполнение ожидал планировщик.

Затем `lab check 0.10`.

Раздел 7 в [README модуля](../../README.md) объясняет, где что искать в плане.
