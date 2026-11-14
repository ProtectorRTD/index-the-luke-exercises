## 1

Сначала посчитайте помесячную выручку в CTE (это запрос из 0.6), а оконные функции примените уже к его 12 строкам.

## 2

`sum(revenue) OVER (ORDER BY month)` — нарастающий итог. `lag(revenue) OVER (ORDER BY month)` — выручка предыдущего месяца, для первой строки `NULL`.

## 3

`round(100 * (revenue - lag(revenue) OVER (ORDER BY month)) / lag(revenue) OVER (ORDER BY month), 1)`
