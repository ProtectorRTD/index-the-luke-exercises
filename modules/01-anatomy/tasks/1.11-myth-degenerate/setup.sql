SELECT setseed(0.61);
CREATE TABLE sessions_fresh AS
SELECT id, user_id, created_at FROM events WHERE id <= 400000;
CREATE TABLE sessions_churned AS
SELECT * FROM sessions_fresh;
CREATE INDEX sessions_fresh_user_idx ON sessions_fresh (user_id);
CREATE INDEX sessions_churned_user_idx ON sessions_churned (user_id);
-- Чистка: 90% строк удалены в случайном порядке.
DELETE FROM sessions_churned WHERE random() < 0.9;
VACUUM (ANALYZE) sessions_fresh;
VACUUM (ANALYZE) sessions_churned;
