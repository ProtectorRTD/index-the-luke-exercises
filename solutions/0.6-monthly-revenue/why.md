# Разбор 0.6

```sql
SELECT date_trunc('month', created_at)::date AS month, sum(total) AS revenue
FROM orders
WHERE status = 'delivered'
  AND created_at >= '2025-01-01' AND created_at < '2026-01-01'
GROUP BY 1
ORDER BY 1;
```

`GROUP BY 1` и `ORDER BY 1` значат «по первой колонке из `SELECT`». Удобно, когда выражение длинное.

Почему год задан диапазоном, а не `extract(year FROM created_at) = 2025`: результат одинаковый, но условие на саму колонку может использовать индекс, а условие на функцию от колонки — нет. Плюс по функции планировщик плохо оценивает число строк (задание 0.11). Подробно это модуль 3.
