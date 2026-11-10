\about
USE zomato_support;

-- Temporarily increase recursion/statement boundaries for bulk generation
SET autocommit = 0;

DELIMITER $$

DROP PROCEDURE IF EXISTS GenerateZomatoMockData$$

CREATE PROCEDURE GenerateZomatoMockData()
BEGIN
    DECLARE i INT DEFAULT 1;
    DECLARE j INT DEFAULT 1;
    DECLARE k INT DEFAULT 1;
    DECLARE v_user_id INT;
    DECLARE v_order_id INT;
    DECLARE v_order_count INT;
    DECLARE v_item_count INT;
    DECLARE v_status VARCHAR(30);
    DECLARE v_rider_name VARCHAR(100);
    DECLARE v_rider_phone VARCHAR(20);
    DECLARE v_restaurant VARCHAR(120);
    DECLARE v_total_bill DECIMAL(10, 2);
    DECLARE v_item_price DECIMAL(10, 2);
    DECLARE v_item_name VARCHAR(150);
    DECLARE v_created_ago_minutes INT;

    -- 1. Insert 2,000 Customers
    WHILE i <= 2000 DO
        INSERT INTO users (user_id, name, phone)
        VALUES (
            i,
            CONCAT(
                ELT(FLOOR(1 + RAND() * 15), 'Aarav', 'Rahul', 'Rohan', 'Priya', 'Ananya', 'Sneha', 'Vikram', 'Neha', 'Aditya', 'Kavita', 'Suresh', 'Deepak', 'Pooja', 'Manish', 'Divya'),
                ' ',
                ELT(FLOOR(1 + RAND() * 12), 'Sharma', 'Verma', 'Patel', 'Reddy', 'Iyer', 'Nair', 'Mehta', 'Kulkarni', 'Singh', 'Rao', 'Gowda', 'Das')
            ),
            CONCAT('+91', FLOOR(6000000000 + (RAND() * 3999999999)))
        );
        SET i = i + 1;
    END WHILE;
    COMMIT;

    -- 2. Generate Orders and Line Items for Users
    -- Distribution pattern:
    -- Users 1 to 300: 0 orders (inactive/new users)
    -- Users 301 to 1400: 1 to 3 orders (casual users)
    -- Users 1401 to 2000: 4 to 8 orders (frequent users)
    
    SET v_order_id = 1001;
    SET v_user_id = 301;

    WHILE v_user_id <= 2000 DO
        IF v_user_id <= 1400 THEN
            SET v_order_count = FLOOR(1 + (RAND() * 3));
        ELSE
            SET v_order_count = FLOOR(4 + (RAND() * 5));
        END IF;

        SET j = 1;
        WHILE j <= v_order_count DO
            -- Realistic restaurant list
            SET v_restaurant = ELT(FLOOR(1 + RAND() * 10), 
                'Meghana Foods', 'Truffles', 'Empire Restaurant', 'Empire Juices', 
                'A2B - Adyar Ananda Bhavan', 'Leon Grill', 'KFC', 'Domino\'s Pizza', 
                'Corner House Ice Cream', 'Behrouz Biryani');

            -- Status probability distribution
            SET v_status = ELT(
                FIELD(TRUE, 
                    RAND() < 0.05,  -- 5% placed
                    RAND() < 0.15,  -- 10% preparing
                    RAND() < 0.25,  -- 10% out_for_delivery
                    RAND() < 0.30,  -- 5% cancelled
                    TRUE            -- 70% delivered
                ),
                'placed', 'preparing', 'out_for_delivery', 'cancelled', 'delivered'
            );

            -- Assign delivery partner details only if out_for_delivery or delivered
            IF v_status IN ('out_for_delivery', 'delivered') THEN
                SET v_rider_name = CONCAT(
                    ELT(FLOOR(1 + RAND() * 6), 'Ramesh', 'Suresh', 'Murugan', 'Santosh', 'Mahesh', 'Ganesh'),
                    ' ',
                    ELT(FLOOR(1 + RAND() * 5), 'Kumar', 'Gowda', 'Yadav', 'Prasad', 'Swamy')
                );
                SET v_rider_phone = CONCAT('+91', FLOOR(9000000000 + (RAND() * 999999999)));
            ELSE
                SET v_rider_name = NULL;
                SET v_rider_phone = NULL;
            END IF;

            -- Timing logic
            IF v_status = 'delivered' THEN
                SET v_created_ago_minutes = FLOOR(60 + (RAND() * 43200)); -- Placed 1 hour to 30 days ago
            ELSE
                SET v_created_ago_minutes = FLOOR(5 + (RAND() * 45));    -- Placed 5 to 50 minutes ago
            END IF;

            -- Insert the base order
            INSERT INTO orders (
                order_id, user_id, restaurant_name, order_status, total_amount, 
                placed_at, eta_minutes, delivery_partner_name, delivery_partner_phone, cancellation_reason
            ) VALUES (
                v_order_id,
                v_user_id,
                v_restaurant,
                v_status,
                0.00, -- will update with real sum below
                NOW() - INTERVAL v_created_ago_minutes MINUTE,
                IF(v_status IN ('delivered', 'cancelled'), 0, FLOOR(5 + (RAND() * 35))),
                v_rider_name,
                v_rider_phone,
                IF(v_status = 'cancelled', 'Customer requested cancellation due to delay', NULL)
            );

            -- Insert 1 to 4 items for this specific order
            SET v_item_count = FLOOR(1 + (RAND() * 4));
            SET v_total_bill = 0.00;
            SET k = 1;

            WHILE k <= v_item_count DO
                SET v_item_name = ELT(FLOOR(1 + RAND() * 12),
                    'Chicken Boneless Biryani', 'Paneer Butter Masala', 'Butter Naan', 
                    'All American Veg Burger', 'Peri Peri Fries', 'Chicken Whopper', 
                    'Death By Chocolate', 'Mutton Rogan Josh', 'Cold Coffee', 
                    'Farmhouse Pizza (Medium)', 'Garlic Breadsticks', 'Ghee Rice'
                );
                SET v_item_price = ROUND(60.00 + (RAND() * 320.00), 2);

                INSERT INTO order_items (order_id, item_name, quantity, unit_price)
                VALUES (v_order_id, v_item_name, 1, v_item_price);

                SET v_total_bill = v_total_bill + v_item_price;
                SET k = k + 1;
            END WHILE;

            -- Update total_amount in orders with actual sum of items
            UPDATE orders SET total_amount = v_total_bill WHERE order_id = v_order_id;

            SET v_order_id = v_order_id + 1;
            SET j = j + 1;
        END WHILE;

        -- Commit every 100 users to keep buffer light
        IF MOD(v_user_id, 100) = 0 THEN
            COMMIT;
        END IF;

        SET v_user_id = v_user_id + 1;
    END WHILE;

    COMMIT;
END$$

DELIMITER ;

-- Execute the data generation procedure
CALL GenerateZomatoMockData();

-- Clean up the procedure after execution
DROP PROCEDURE IF EXISTS GenerateZomatoMockData;

SET autocommit = 1;
