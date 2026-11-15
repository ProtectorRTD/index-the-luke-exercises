## 1

`SELECT relpages, reltuples FROM pg_class WHERE relname = 'customers';` и три команды `SHOW`. Дальше арифметика.

## 2

В `WHERE` одно условие, значит `cpu_operator_cost` учитывается один раз на строку. Долю `'SK'` смотрите так: `SELECT most_common_vals, most_common_freqs FROM pg_stats WHERE tablename = 'customers' AND attname = 'country';`

## 3

Для `'UA'` меняется только оценка числа строк. Страниц и строк в таблице столько же, условие одно, значит стоимость та же.
