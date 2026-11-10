INSERT INTO support_tickets (
    order_id,
    user_id,
    issue_type,
    ticket_status,
    refund_amount,
    bot_summary,
    created_at
)
SELECT 
    o.order_id,
    o.user_id,
    -- Match issue_type ENUM
    ELT(1 + (ROW_NUMBER() OVER () % 5), 
        'order_delay', 
        'missing_item', 
        'food_quality', 
        'cancellation', 
        'agent_escalation'
    ) AS issue_type,
    -- Match ticket_status ENUM
    ELT(1 + (ROW_NUMBER() OVER () % 3), 
        'open', 
        'resolved_bot', 
        'escalated_to_agent'
    ) AS ticket_status,
    -- Refund amount logic based on status
    CASE 
        WHEN (ROW_NUMBER() OVER () % 3) = 1 THEN ROUND(120.00 + (ROW_NUMBER() OVER () * 4.5), 2)
        WHEN (ROW_NUMBER() OVER () % 5) = 1 THEN ROUND(50.00 + (ROW_NUMBER() OVER () * 2.0), 2)
        ELSE 0.00 
    END AS refund_amount,
    -- Realistic contextual chatbot summary
    CASE (ROW_NUMBER() OVER () % 5)
        WHEN 0 THEN 'Customer reported delivery delayed past estimated arrival time. Bot tracked rider and issued coupon.'
        WHEN 1 THEN 'Customer flagged missing beverages. Validated item list and issued partial refund to source account.'
        WHEN 2 THEN 'Packaging compromised upon handover. Customer provided photo evidence. Ticket processed for compensation.'
        WHEN 3 THEN 'Order cancelled prior to restaurant food preparation stage per user request. Automated waiver applied.'
        ELSE 'User requested human operator regarding repeated transaction failure on payment gateway.'
    END AS bot_summary,
    -- Timestamp spread across recent hours/days
    NOW() - INTERVAL (ROW_NUMBER() OVER () * 7) HOUR AS created_at
FROM orders o
ORDER BY o.order_id ASC
LIMIT 75;