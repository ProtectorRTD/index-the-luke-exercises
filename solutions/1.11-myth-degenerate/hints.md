## 1

`SELECT tree_level, leaf_pages, avg_leaf_density FROM pgstatindex('sessions_churned_user_idx');` и то же для `sessions_fresh_user_idx`.

## 2

Страницы для диапазона берите из `EXPLAIN (ANALYZE, BUFFERS)`, второй прогон. Обратите внимание на тип узла: `Index Only Scan` читает только индекс.

## 3

После `REINDEX INDEX sessions_churned_user_idx;` снова вызовите `pgstatindex`. Чтобы повторить эксперимент с начала, выполните `lab reset` и `setup.sql` заново.
