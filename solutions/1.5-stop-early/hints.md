## 1

`count(*)` по определению должен увидеть все подходящие строки. Нужна конструкция, которой достаточно одной.

## 2

`EXISTS (подзапрос)` возвращает `true`, как только подзапрос нашёл первую строку. Обёрнутый в `SELECT`, он даёт ровно одну строку с `true` или `false`.

## 3

```sql
SELECT EXISTS (SELECT 1 FROM orders WHERE customer_id = 17 AND status = 'delivered') AS has_delivered;
```
