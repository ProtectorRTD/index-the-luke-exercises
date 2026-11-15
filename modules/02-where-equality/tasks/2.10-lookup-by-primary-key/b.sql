SELECT t.id, t.subject, tt.tag_id
FROM tickets t
JOIN ticket_tags tt ON tt.ticket_id = t.id
WHERE t.customer_id = 17;
