select o.status, count(o.total), ROUND(AVG(o.total)::numeric, 2)
from orders o 
group by o.status
having count(o.total) > 20000