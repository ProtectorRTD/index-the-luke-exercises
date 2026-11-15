# Шпаргалка к модулю 2

## Составной индекс

```sql
CREATE INDEX orders_customer_id_status_idx ON orders (customer_id, status);
DROP INDEX orders_customer_id_status_idx;
```

Порядок колонок в скобках — это порядок сортировки в индексе. `(a, b)` и `(b, a)` — разные индексы.

Какие индексы есть на таблице и из каких колонок они состоят:

```
\d orders
```

или запросом:

```sql
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'orders';
```

## Сколько строк под условием и как они распределены

```sql
SELECT status, count(*) FROM orders WHERE customer_id = 17 GROUP BY status;
SELECT count(DISTINCT country) FROM customers;   -- сколько разных значений
```

## IN и ANY

```sql
WHERE status IN ('pending', 'processing', 'cancelled')
-- то же самое, в плане Postgres покажет так:
WHERE status = ANY ('{pending,processing,cancelled}'::text[])
```

`IN` со списком значений работает как несколько равенств сразу. Если колонка в индексе, условие попадает в `Index Cond`.

## UNION и UNION ALL

```sql
SELECT id FROM orders WHERE customer_id = 17
UNION ALL                                     -- склеить результаты как есть
SELECT id FROM orders WHERE status = 'pending';

SELECT id FROM orders WHERE customer_id = 17
UNION                                         -- склеить и убрать дубли
SELECT id FROM orders WHERE status = 'pending';
```

Обе части должны возвращать одинаковое число колонок совместимых типов. `UNION` убирает дубли, но для этого сортирует или хеширует весь результат. `UNION ALL` дешевле, но тогда дубли нужно исключить самим, условием во второй части:

```sql
SELECT id FROM orders WHERE customer_id = 17
UNION ALL
SELECT id FROM orders WHERE status = 'pending' AND customer_id <> 17;
```

Осторожно с `NULL`: `a <> b` не выполняется, если `a` или `b` равно `NULL`. Для колонок, где бывает `NULL`, пишут `a IS DISTINCT FROM b`.

## Строки, где колонка пустая

```sql
WHERE shipped_at IS NULL       -- правильно
WHERE shipped_at = NULL        -- никогда не выполняется: сравнение с NULL даёт NULL
```

## Сравнить два запроса по результату

```sql
-- строки, которые есть в первом и нет во втором (должно быть пусто в обе стороны)
(SELECT ... первый запрос ...) EXCEPT ALL (SELECT ... второй запрос ...);
```

## Объединение индексов (только посмотреть)

```sql
CREATE INDEX tmp_customer ON orders (customer_id);
CREATE INDEX tmp_status   ON orders (status);
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders WHERE customer_id = 17 AND status = 'cancelled';
-- возможен BitmapAnd: два Bitmap Index Scan и их пересечение
DROP INDEX tmp_customer, tmp_status;
```
