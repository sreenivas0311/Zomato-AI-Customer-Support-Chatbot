-- Check total volume
SELECT COUNT(*) AS total_users FROM users;
SELECT COUNT(*) AS total_orders FROM orders;
SELECT COUNT(*) AS total_order_items FROM order_items;

-- Check distribution of order statuses
SELECT order_status, COUNT(*) AS count 
FROM orders 
GROUP BY order_status;

-- Verify users with no orders vs high orders
SELECT 
    CASE 
        WHEN order_count = 0 THEN '0 Orders (New User)'
        WHEN order_count BETWEEN 1 AND 3 THEN '1-3 Orders (Casual)'
        ELSE '4+ Orders (Frequent)'
    END AS user_segment,
    COUNT(*) AS total_customers
FROM (
    SELECT u.user_id, COUNT(o.order_id) AS order_count
    FROM users u
    LEFT JOIN orders o ON u.user_id = o.user_id
    GROUP BY u.user_id
) sub
GROUP BY user_segment;
