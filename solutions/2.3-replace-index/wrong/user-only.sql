-- Ловушка: type в a.sql остаётся фильтром
DROP INDEX events_type_user_id_idx;
CREATE INDEX events_user_id_idx ON events (user_id);
