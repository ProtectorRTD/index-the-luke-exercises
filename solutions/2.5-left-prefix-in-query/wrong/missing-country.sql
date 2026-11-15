-- Ловушка: в списке не хватает одной страны, часть клиентов потеряна
SELECT id, email FROM customers
WHERE country IN ('AT', 'BE', 'BG', 'CZ', 'DE', 'DK', 'ES', 'FI', 'FR', 'HR', 'HU',
                  'IE', 'IT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'UA')
  AND last_name = 'novak' AND first_name = 'jana';
