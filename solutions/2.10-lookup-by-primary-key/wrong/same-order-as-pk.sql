-- Ловушка: «индекс по обеим колонкам» в том же порядке, что первичный ключ
CREATE INDEX ticket_tags_tag_ticket_idx ON ticket_tags (tag_id, ticket_id);
