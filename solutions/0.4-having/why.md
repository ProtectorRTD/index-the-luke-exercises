# Разбор 0.4

```sql
SELECT status, count(*) AS orders_count, round(avg(total), 2) AS avg_total
FROM orders
GROUP BY status
HAVING count(*) > 20000;
```

`WHERE` фильтрует строки до группировки, `HAVING` — группы после неё. Написать `WHERE count(*) > 20000` нельзя: на этапе `WHERE` групп ещё нет.

В плане это `HashAggregate` с `Filter: (count(*) > 20000)`: условие проверяется уже над готовыми группами.
