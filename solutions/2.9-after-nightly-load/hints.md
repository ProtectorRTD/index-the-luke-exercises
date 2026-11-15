## 1

Снимите `EXPLAIN (ANALYZE, BUFFERS)`. Какой индекс выбран? Сравните `rows` в первых и во вторых скобках, как в задании 0.11, и посмотрите на `Rows Removed by Filter`.

## 2

Планировщик ожидает одну строку со статусом `new`, а их сто тысяч. Откуда он берёт оценку? Загляните в `pg_stats` для `refunds.status`: есть ли там значение `new`? Когда собиралась статистика: `SELECT last_analyze, last_autoanalyze FROM pg_stat_user_tables WHERE relname = 'refunds';`

## 3

Статистика собрана до загрузки. Её нужно пересобрать: `ANALYZE refunds;`
