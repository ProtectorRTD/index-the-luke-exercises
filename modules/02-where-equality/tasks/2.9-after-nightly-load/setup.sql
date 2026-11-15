-- Заявки на возврат, состояние на вчерашний вечер.
CREATE TABLE refunds AS
SELECT g::bigint AS id,
       (1 + (g::bigint * 7919) % 5000)::bigint AS customer_id,
       CASE WHEN g % 10 = 0 THEN 'rejected' ELSE 'processed' END AS status,
       (10 + (g * 31) % 490)::numeric(10,2) AS amount,
       timestamptz '2025-01-01 00:00:00+00' + make_interval(secs => g * 100) AS created_at
FROM generate_series(1, 200000) g;
ALTER TABLE refunds ADD PRIMARY KEY (id);
CREATE INDEX refunds_status_idx ON refunds (status);
CREATE INDEX refunds_customer_id_idx ON refunds (customer_id);
ANALYZE refunds;

-- Ночная загрузка из старой системы: 100 000 новых заявок.
INSERT INTO refunds
SELECT g, 1 + (g::bigint * 7919) % 5000, 'new', 10 + (g * 31) % 490,
       timestamptz '2025-01-01 00:00:00+00' + make_interval(secs => g * 100)
FROM generate_series(200001, 300000) g;
