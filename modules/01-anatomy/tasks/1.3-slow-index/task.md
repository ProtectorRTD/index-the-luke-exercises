# 1.3. Медленный индекс

**Тип:** ответы. Нужно выполнить запросы, посмотреть планы и записать числа в `answers.yaml`.

## Сценарий

`setup.sql` создаёт индекс по клиенту:

```sql
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

В наших данных есть перекос: первый 1% клиентов («оптовики») делает половину всех заказов. На масштабе `s` это клиенты с id от 1 до 1 000, на масштабе `m` от 1 до 10 000.

Два отчёта используют один и тот же индекс:

```sql
-- обычный клиент
SELECT sum(total) FROM orders WHERE customer_id = 54321;

-- все оптовики (на масштабе m: <= 10000)
SELECT sum(total) FROM orders WHERE customer_id <= 1000;
```

## Что сделать

1. `lab reset`, затем в `lab psql` выполните `\i modules/01-anatomy/tasks/1.3-slow-index/setup.sql`.
2. Снимите `EXPLAIN (ANALYZE, BUFFERS)` для обоих запросов.
3. Для запроса по оптовикам «запретите» планировщику полное чтение таблицы и bitmap и снимите план ещё раз:

   ```sql
   SET enable_seqscan = off;
   SET enable_bitmapscan = off;
   EXPLAIN (ANALYZE, BUFFERS) SELECT sum(total) FROM orders WHERE customer_id <= 1000;
   RESET ALL;
   ```

4. Заполните `answers.yaml`. Названия узлов пишите как в плане, например `Seq Scan`. Для `buffers` берите сумму `shared hit + read` верхнего узла из второго прогона подряд: первое обращение к индексу в сессии читает на несколько страниц больше. Допускается погрешность 2%.
5. `lab check 1.3`.

После PASS ответьте себе: во сколько раз «индексный» план для оптовиков прочитал больше страниц, чем `Seq Scan`, и почему почти каждая строка стоила отдельной страницы?
