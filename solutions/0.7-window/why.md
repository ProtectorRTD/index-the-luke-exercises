# Разбор 0.7

```sql
WITH monthly AS (
    SELECT date_trunc('month', created_at)::date AS month, sum(total) AS revenue
    FROM orders
    WHERE status = 'delivered'
      AND created_at >= '2025-01-01' AND created_at < '2026-01-01'
    GROUP BY 1
)
SELECT month,
       revenue,
       sum(revenue) OVER (ORDER BY month) AS running_total,
       round(100 * (revenue - lag(revenue) OVER (ORDER BY month))
             / lag(revenue) OVER (ORDER BY month), 1) AS change_pct
FROM monthly
ORDER BY month;
```

Оконные функции не схлопывают строки: на выходе те же 12 месяцев, к каждому добавлены значения, посчитанные по «окну» соседних строк.

`sum(...) OVER (ORDER BY month)` по умолчанию суммирует от первой строки до текущей, это и есть нарастающий итог.

Если повторять `lag(...)` дважды не хочется, есть именованное окно: `WINDOW w AS (ORDER BY month)` и `lag(revenue) OVER w`.
