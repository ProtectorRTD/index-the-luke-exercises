## 1

Посмотрите на `Buffers` у `b.sql`: тысячи страниц ради десятка строк. Условие на `user_id` есть, но `user_id` — вторая колонка индекса.

## 2

Нужен один индекс, где `user_id` первый. Старый индекс тогда станет лишним, его можно удалить в том же `solution.sql`.

## 3

`DROP INDEX events_type_user_id_idx;` и `CREATE INDEX events_user_id_type_idx ON events (user_id, type);`
