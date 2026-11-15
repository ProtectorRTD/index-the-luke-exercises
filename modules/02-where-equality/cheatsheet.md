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

## Посмотреть план с конкретным индексом

```sql
BEGIN;
DROP INDEX orders_sc_idx;                 -- спрятать другой индекс
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
ROLLBACK;                                 -- индекс возвращается
```

Удаление индекса внутри транзакции мгновенное и откатывается целиком. На рабочей базе так делать нельзя: таблица заблокирована до конца транзакции.

## Статистика

```sql
ANALYZE refunds;                          -- пересобрать статистику по таблице

-- когда её собирали и сколько строк изменилось с тех пор
SELECT last_analyze, last_autoanalyze, n_mod_since_analyze
FROM pg_stat_user_tables WHERE relname = 'refunds';

-- что планировщик знает о значениях колонки
SELECT most_common_vals, most_common_freqs FROM pg_stats
WHERE tablename = 'refunds' AND attname = 'status';
```

## Описание таблицы и её ключей

```
\d ticket_tags
```

В разделе `Indexes` видно, из каких колонок и в каком порядке состоит первичный ключ.
