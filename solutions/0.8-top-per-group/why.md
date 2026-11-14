# Разбор 0.8

```sql
WITH units AS (
    SELECT p.category_id, p.id AS product_id, p.name AS product_name, sum(oi.quantity) AS units
    FROM order_items oi
    JOIN orders o   ON o.id = oi.order_id
    JOIN products p ON p.id = oi.product_id
    WHERE o.status = 'delivered'
      AND o.created_at >= '2025-01-01' AND o.created_at < '2026-01-01'
    GROUP BY p.category_id, p.id, p.name
),
ranked AS (
    SELECT u.*, row_number() OVER (PARTITION BY u.category_id ORDER BY u.units DESC, u.product_id) AS rank
    FROM units u
)
SELECT c.name AS category, r.product_id, r.product_name, r.units, r.rank
FROM ranked r
JOIN categories c ON c.id = r.category_id
WHERE r.rank <= 3
ORDER BY c.name, r.rank;
```

Это классическая задача «топ-N в каждой группе». `row_number()` нумерует товары внутри категории, внешний запрос оставляет первые три.

`rank()` вместо `row_number()` при равенстве штук дал бы двум товарам один номер, и в категории могло бы оказаться больше трёх строк. Поэтому в условии задано правило для равенства и нужен `row_number()`.

Посмотрите план: самая дорогая часть — соединение 3 миллионов позиций с заказами. В модуле 6 это будет разбираться подробно. В модуле 9 вернётся «топ-N в каждой группе», но уже через `LATERAL` и индекс.
