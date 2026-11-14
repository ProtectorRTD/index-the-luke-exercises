# Index Lab

Практикум к книге Маркуса Винанда [«Use The Index, Luke»](https://use-the-index-luke.com/) на PostgreSQL. Каждая глава книги — модуль: объяснение, демо и задания с автоматической проверкой по плану запроса.

Нужен только Docker Desktop. Java, Maven и локальный Postgres не нужны.

## Установка за пять минут

```bash
git clone https://github.com/ProtectorRTD/index-the-luke-exercises
cd index-the-luke-exercises

./lab up                # поднять базу и собрать контейнер с проверкой
./lab seed --scale s    # сгенерировать данные, около минуты
./lab check 1.1         # убедиться, что проверка работает (будет FAIL: задание не решено)
```

На Windows в cmd или PowerShell вместо `./lab` пишите `.\lab.cmd`: `.\lab.cmd up`, `.\lab.cmd check 1.1`. В Git Bash работает и `./lab`.

Если `./lab` пишет `Permission denied`, выполните `chmod +x lab`.

## Команды

| Команда | Что делает |
| --- | --- |
| `lab up` | Поднимает базу |
| `lab down` | Останавливает базу, данные сохраняются |
| `lab seed --scale s` | Генерирует данные. `s` — около 1 млн заказов, `m` — около 10 млн (нужен для модуля 5, около 10 ГБ на диске) |
| `lab psql` | Открывает psql в базе |
| `lab demo 1` | Выполняет демо-скрипт модуля 1 с комментариями |
| `lab check 1.3` | Проверяет задание: PASS или FAIL с отчётом и планом «было / стало» |
| `lab check --module 1` | Проверяет все задания модуля |
| `lab hint 1.3` | Показывает следующую подсказку (их три уровня) |
| `lab reset` | Убирает всё, что вы создали в базе: индексы, представления, таблицы |
| `lab status` | Прогресс по всем заданиям |

Подключиться из IDE тоже можно: `localhost:5432`, база `lab`, пользователь `lab`, пароль `lab`.

## Карта модулей

| Модуль | Глава книги | Статус |
| --- | --- | --- |
| [0. Разминка: SQL и EXPLAIN](modules/00-warmup/README.md) | нет в книге | готов |
| [1. Анатомия индекса](modules/01-anatomy/README.md) | [Anatomy of an Index](https://use-the-index-luke.com/sql/anatomy) | готов |
| 2. Where: равенство | [The Equals Operator](https://use-the-index-luke.com/sql/where-clause/the-equals-operator) | в работе |
| 3. Where: функции и замаскированные условия | [Functions](https://use-the-index-luke.com/sql/where-clause/functions), [Bind Variables](https://use-the-index-luke.com/sql/where-clause/bind-parameters), [Obfuscated Conditions](https://use-the-index-luke.com/sql/where-clause/obfuscation) | в работе |
| 4. Where: диапазоны, LIKE, частичные индексы, NULL | [Searching for Ranges](https://use-the-index-luke.com/sql/where-clause/searching-for-ranges), [Partial Indexes](https://use-the-index-luke.com/sql/where-clause/partial-and-filtered-indexes), [NULL](https://use-the-index-luke.com/sql/where-clause/null) | в работе |
| 5. Производительность и масштабируемость | [Testing and Scalability](https://use-the-index-luke.com/sql/testing-scalability) | в работе |
| 6. Join | [The Join Operation](https://use-the-index-luke.com/sql/join) | в работе |
| 7. Кластеризация данных | [Clustering Data](https://use-the-index-luke.com/sql/clustering) | в работе |
| 8. Сортировка и группировка | [Sorting and Grouping](https://use-the-index-luke.com/sql/sorting-grouping) | в работе |
| 9. Top-N и пагинация | [Partial Results](https://use-the-index-luke.com/sql/partial-results) | в работе |
| 10. Изменение данных | [Insert, Delete and Update](https://use-the-index-luke.com/sql/dml) | в работе |
| 11. Финальный босс | всё вместе | в работе |

## Как устроен модуль

```
modules/01-anatomy/
  README.md        идея главы, как это выглядит в Postgres, как читать план
  demo.sql         пошаговая демонстрация: lab demo 1
  cheatsheet.md    SQL, который понадобится в заданиях
  tasks/
    1.1-email-lookup/
      task.md        сценарий, цель, критерии проверки
      prediction.md  прогноз до первого EXPLAIN
      query.sql      исходный запрос
      solution.sql   ваше решение
      check.yaml     правила проверки
```

Типы заданий:

- **индексы** — запрос менять нельзя, в `solution.sql` только `CREATE INDEX`, `DROP INDEX`, `ANALYZE`, `VACUUM`;
- **запросы** — индексы даны, нужно переписать запрос так, чтобы результат остался тем же, а план стал нужным;
- **ответы** — нужно измерить или прочитать план и записать числа в `answers.yaml`;
- **индексы и запросы** — с модуля 4, можно менять и то и другое.

## Порядок работы над заданием

1. Прочитать `task.md`.
2. Заполнить `prediction.md`: какой будет план и почему. Строки, начинающиеся с `>`, должны быть заполнены, иначе проверка не пройдёт.
3. Посмотреть исходный план: `lab psql`, затем `EXPLAIN (ANALYZE, BUFFERS) ...`.
4. Написать решение, запустить `lab check <номер>`.
5. После PASS сравнить с эталоном в `solutions/<задание>/` и с решением напарника.

## Как проверяется

Проверка жёсткая: PASS, только если выполнены все правила из `check.yaml`.

- Перед проверкой база сбрасывается в исходное состояние, затем выполняется `setup.sql` задания, если он есть.
- Результат вашего запроса сравнивается с эталонным.
- План снимается через `EXPLAIN (ANALYZE, BUFFERS)`, запрос выполняется дважды, берётся второй прогон.
- Проверяются узлы плана и число прочитанных страниц (buffers). Время показывается в отчёте, но на результат не влияет: оно скачет от машины к машине, а число страниц нет.
- `SET enable_*`, хинты и прочие обходы планировщика в решениях запрещены.

## Работа в паре

- У каждого своя ветка: `git switch -c yehor`, `git switch -c <имя напарника>`. Решения коммитятся в свою ветку.
- `solutions/` не открывать до PASS. Подсказки через `lab hint` открываются по одной.
- Прогресс (`lab status`, использованные подсказки) хранится локально в `.lab/` и в git не попадает.
- После модуля: сравнить решения и планы друг друга, обсудить, почему решения разные.

## Данные

Интернет-магазин: `customers`, `orders`, `order_items`, `products`, `categories`, `events`. Схема — в README модуля 0.

Данные генерируются детерминированно: у обоих участников одинаковые строки и одинаковые планы. Перекосы заложены специально: 60% клиентов из одной страны, 90% заказов в одном статусе, 1% клиентов делает половину заказов. Без перекосов многие эффекты из книги не видны.

**Не меняйте данные в базовых таблицах** (`UPDATE`, `DELETE` по `orders` и т.п.). Если всё-таки изменили, `lab reset` предупредит, а исправит только `lab seed`.

Настройки Postgres зафиксированы в `docker-compose.yml` (параллельные запросы и JIT выключены, `random_page_cost = 4`). От них зависят планы и пороги проверок, менять их не нужно.

## Для автора заданий

`lab selftest` проверяет каждое задание: эталон проходит, заготовка и «соблазнительные, но неверные» решения из `solutions/<задание>/wrong/` падают. Опции: `--module 1`, `--task 1.3`, `--repeat 10` (стабильность плана), `-v`.
