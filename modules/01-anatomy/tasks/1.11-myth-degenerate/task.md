# 1.11. Миф: индексы вырождаются

**Уровень:** эксперимент. Проверяем утверждение на базе.

## Миф

«Со временем, после множества вставок и удалений, B-дерево становится несбалансированным и глубоким, поиск по нему замедляется. Поэтому индексы нужно регулярно перестраивать».

В книге это первый пункт справочника мифов: [Indexes Can Degenerate](https://use-the-index-luke.com/sql/myth-directory/indexes-can-degenerate).

## Сценарий

`setup.sql` создаёт две одинаковые таблицы сессий по 400 000 строк с индексом по `user_id`:

- `sessions_fresh` — нетронутая;
- `sessions_churned` — после чистки: 90% строк удалены в случайном порядке, затем выполнен `VACUUM`.

Оптовики — пользователи с id от 1 до 1 000 на масштабе `s` и от 1 до 10 000 на масштабе `m`. Запрос по диапазону:

```sql
SELECT count(*) FROM sessions_fresh   WHERE user_id BETWEEN 1 AND 1000;   -- на m: 10000
SELECT count(*) FROM sessions_churned WHERE user_id BETWEEN 1 AND 1000;
```

## Что сделать

1. `lab reset`, в `lab psql` выполните `\i modules/01-anatomy/tasks/1.11-myth-degenerate/setup.sql`.
2. До измерений ответьте себе: что изменится в индексе после удаления 90% строк? Глубина? Число листьев? Цена поиска одной строки? Цена чтения диапазона?
3. Измерьте и впишите в `answers.yaml`. Пригодится `pgstatindex('имя_индекса')`: он возвращает `tree_level`, `leaf_pages`, `avg_leaf_density`.

| Ответ | Что это |
| --- | --- |
| `level_fresh`, `level_churned` | уровней над листьями у каждого индекса |
| `leaf_pages_fresh`, `leaf_pages_churned` | листовых страниц |
| `density_churned` | средняя заполненность листа в процентах, допуск 10% |
| `range_rows_fresh`, `range_rows_churned` | сколько строк вернул диапазонный запрос (значение `count`) |
| `range_buffers_fresh`, `range_buffers_churned` | сколько страниц он прочитал, допуск 10% |
| `leaf_pages_rebuilt` | листовых страниц у индекса `sessions_churned` после `REINDEX INDEX sessions_churned_user_idx`, допуск 5% |
| `depth_grew` | выросла ли глубина дерева после удалений: `yes` или `no` |

4. `lab check 1.11`.

После PASS сформулируйте: какая часть мифа неверна, а какая описывает реальную проблему под неверным названием?
