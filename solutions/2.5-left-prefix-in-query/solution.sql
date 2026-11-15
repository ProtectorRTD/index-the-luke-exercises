-- Список стран: SELECT DISTINCT country FROM customers ORDER BY 1;
SELECT id, email
FROM customers
WHERE country IN ('AT', 'BE', 'BG', 'CZ', 'DE', 'DK', 'ES', 'FI', 'FR', 'HR', 'HU',
                  'IE', 'IT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK', 'UA')
  AND last_name = 'novak' AND first_name = 'jana';
