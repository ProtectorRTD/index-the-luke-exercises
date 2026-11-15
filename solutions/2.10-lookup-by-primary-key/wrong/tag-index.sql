-- Ловушка: индекс по колонке, которая и так первая в первичном ключе
CREATE INDEX ticket_tags_tag_id_idx ON ticket_tags (tag_id);
