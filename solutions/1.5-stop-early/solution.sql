SELECT EXISTS (
    SELECT 1 FROM orders
    WHERE customer_id = 17 AND status = 'delivered'
) AS has_delivered;
