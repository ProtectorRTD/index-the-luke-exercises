DROP INDEX events_type_user_id_idx;
CREATE INDEX events_user_id_type_idx ON events (user_id, type);
