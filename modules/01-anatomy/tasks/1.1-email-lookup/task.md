# 1.1. Поиск клиента по email

**Тип:** индексы. Запрос менять нельзя, можно только создавать индексы.

## Сценарий

Служба поддержки ищет клиента по email, который он назвал по телефону. Запрос в `query.sql`:

```sql
SELECT id, first_name, last_name, country
FROM customers
WHERE email = 'Peter.Oravec0004242@example.cz';
```

Сейчас Postgres читает всю таблицу клиентов ради одной строки.

## Что сделать

1. Заполните `prediction.md`.
2. Посмотрите исходный план: `lab psql`, затем `EXPLAIN (ANALYZE, BUFFERS)` для запроса из `query.sql`. Найдите в плане `Rows Removed by Filter` и `Buffers`.
3. В `solution.sql` создайте индекс, после которого поиск станет точечным.
4. Запустите `lab check 1.1`.

## Как проверяется

- в плане нет `Seq Scan` по `customers`;
- есть `Index Scan` или `Index Only Scan` по `customers`;
- запрос трогает не больше 6 страниц на масштабе `s` (7 на `m`);
- создан ровно один новый индекс.

После PASS ответьте себе: из каких страниц сложилось число в `Buffers`?
