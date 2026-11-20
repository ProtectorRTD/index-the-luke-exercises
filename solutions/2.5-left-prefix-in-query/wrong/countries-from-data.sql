-- scales: s
-- Ловушка: перечислены только страны, где такие клиенты есть сейчас, а не все страны.
SELECT id, email
FROM customers
WHERE country IN ('AT', 'BG', 'CZ', 'ES', 'FI', 'FR', 'HR', 'HU', 'IT', 'NL',
                  'PL', 'PT', 'RO', 'SE', 'SI', 'SK', 'UA')
  AND last_name = 'novak' AND first_name = 'jana';
