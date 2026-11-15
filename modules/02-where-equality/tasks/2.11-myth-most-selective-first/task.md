# 2.11. Миф: самая селективная колонка первой

**Уровень:** эксперимент. Проверяем утверждение на базе.

## Миф

«В составном индексе первой нужно ставить колонку с наибольшим числом разных значений: так индекс быстрее отсекает лишнее».

В книге это [Most Selective First](https://use-the-index-luke.com/sql/myth-directory/most-selective-first).

## Сценарий

`setup.sql` создаёт на `orders` два индекса с одними и теми же колонками в разном порядке:

```sql
CREATE INDEX orders_cs_idx ON orders (customer_id, status);   -- по мифу: правильный
CREATE INDEX orders_sc_idx ON orders (status, customer_id);   -- по мифу: неправильный
```

У `customer_id` десятки тысяч разных значений, у `status` шесть.

Нагрузка состоит из двух запросов:

```sql
-- both: счётчик на странице клиента
SELECT count(*) FROM orders WHERE status = 'cancelled' AND customer_id = 17;

-- queue: счётчик очереди необработанных заказов
SELECT count(*) FROM orders WHERE status = 'pending';
```

## Как измерить запрос с конкретным индексом

Когда индексов два, выбирает планировщик. Чтобы посмотреть план с одним из них, второй можно «спрятать» внутри транзакции:

```sql
BEGIN;
DROP INDEX orders_sc_idx;
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;   -- берите второй прогон
ROLLBACK;                                -- индекс возвращается
```

`DROP INDEX` внутри транзакции мгновенный и полностью откатывается. На рабочей базе так делать нельзя: до конца транзакции таблица заблокирована для всех остальных.

## Что сделать

1. `lab reset`, в `lab psql` выполните `\i modules/02-where-equality/tasks/2.11-myth-most-selective-first/setup.sql`.
2. До измерений запишите прогноз: сколько страниц прочитает каждый запрос с каждым индексом.
3. Измерьте и впишите в `answers.yaml`:

| Ответ | Что это | Допуск |
| --- | --- | --- |
| `cs_pages`, `sc_pages` | размер каждого индекса в страницах | точно |
| `both_via_cs`, `both_via_sc` | страниц на запрос both с каждым индексом | 1 страница |
| `queue_via_cs`, `queue_via_sc` | страниц на запрос queue с каждым индексом | 5% |
| `leading_column` | какая колонка должна быть первой для этой нагрузки | имя колонки |

4. `lab check 2.11`.

После PASS сформулируйте правило, которым нужно заменить миф.
