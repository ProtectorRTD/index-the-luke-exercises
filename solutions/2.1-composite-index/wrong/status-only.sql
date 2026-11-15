-- Ловушка: индекс по статусу, клиент остаётся фильтром
CREATE INDEX orders_status_idx ON orders (status);
