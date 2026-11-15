# 2.6. Эквивалентное условие

**Тип:** запросы. Индексы даны, переписать нужно запрос.

## Сценарий

`setup.sql` создаёт индекс:

```sql
CREATE INDEX orders_customer_id_status_idx ON orders (customer_id, status);
```

Менеджер хочет видеть заказы клиента, которые так и не были отправлены (`query.sql`):

```sql
SELECT id, status, created_at
FROM orders
WHERE customer_id = 17 AND shipped_at IS NULL;
```

Бизнес-правило системы: `shipped_at` заполняется ровно тогда, когда заказ переходит в статус `shipped`, а потом в `delivered` или `returned`. У заказов в статусах `pending`, `processing` и `cancelled` дата отправки всегда пустая, у остальных всегда заполнена.

## Что сделать

1. Заполните `prediction.md`.
2. Убедитесь в правиле на данных:
   ```sql
   SELECT status, count(*) FILTER (WHERE shipped_at IS NULL) AS not_shipped, count(*)
   FROM orders GROUP BY status;
   ```
3. `lab reset`, в `lab psql` выполните `\i modules/02-where-equality/tasks/2.6-equivalent-condition/setup.sql` и посмотрите исходный план. Что в `Index Cond`, а что в `Filter`?
4. Перепишите запрос в `solution.sql` так, чтобы результат остался тем же, а фильтром не отбрасывалось ни одной строки.
5. `lab check 2.6`.

## Как проверяется

- результат совпадает с эталоном, порядок строк не важен;
- `customer_id` и `status` стоят в `Index Cond`;
- фильтром не отброшено ни одной строки;
- запрос трогает не больше 60 страниц.
