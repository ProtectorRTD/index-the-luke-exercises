# 2.4. OR через JOIN

**Тип:** запросы. Индексы даны, переписать нужно запрос.

## Сценарий

В админке поддержки одно поле поиска: туда вводят либо email клиента, либо номер заказа. Бэкенд ищет сразу по обоим (`query.sql`):

```sql
SELECT o.id, o.created_at, o.total, c.email
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.email = 'Peter.Oravec0004242@example.cz'
   OR o.id = 830947;
```

`setup.sql` создаёт индексы, нужные для обоих поисков по отдельности:

```sql
CREATE INDEX customers_email_idx ON customers (email);
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

Каждый поиск по отдельности занимает несколько страниц. Вместе они читают обе таблицы целиком.

## Что сделать

1. Заполните `prediction.md`.
2. `lab reset`, в `lab psql` выполните `\i modules/02-where-equality/tasks/2.4-or-across-join/setup.sql` и посмотрите план. Где стоит условие с `OR`?
3. Перепишите запрос в `solution.sql`. Результат должен остаться тем же, **без дублей**: если заказ 830947 принадлежит тому же клиенту, он должен попасть в результат один раз.
4. `lab check 2.4`.

## Как проверяется

- результат совпадает с эталоном, порядок строк не важен;
- в плане нет `Seq Scan` ни по `orders`, ни по `customers`;
- запрос трогает не больше 60 страниц на масштабе `s` (на `m` клиент 4242 оказывается оптовиком с сотнями заказов, там порог 800).
