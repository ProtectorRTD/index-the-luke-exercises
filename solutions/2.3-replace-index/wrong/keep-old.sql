-- Ловушка: старый индекс оставлен, индексов на events стало два
CREATE INDEX events_user_id_type_idx ON events (user_id, type);
