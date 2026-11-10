from typing import Any, Dict

from sqlalchemy import text

from src.database.connection import get_engine

ISSUE_TYPES = {"order_delay", "missing_item", "food_quality", "cancellation", "agent_escalation"}
TICKET_STATUSES = {"open", "resolved_bot", "escalated_to_agent"}

LIVE_STATUSES = ("placed", "preparing", "out_for_delivery")
CANCELLABLE_STATUSES = ("placed", "preparing")

# Which order statuses each issue type is allowed for.
# 'cancellation' is intentionally absent: it is only created through process_cancellation_refund().
ALLOWED_STATUS_FOR_ISSUE = {
    "missing_item": ("delivered",),
    "food_quality": ("delivered",),
    "order_delay": LIVE_STATUSES,
}

REFUND_ISSUES = {"missing_item", "cancellation"}


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "error": message}


def _fetch_order(conn, order_id: int):
    return conn.execute(
        text("SELECT order_id, user_id, order_status, total_amount FROM orders WHERE order_id = :order_id"),
        {"order_id": order_id},
    ).mappings().first()


def _insert_ticket(
    conn,
    order_id: int,
    user_id: int,
    issue_type: str,
    ticket_status: str,
    bot_summary: str,
    refund_amount: float,
) -> int:
    result = conn.execute(
        text("""
            INSERT INTO support_tickets (order_id, user_id, issue_type, ticket_status, bot_summary, refund_amount, created_at)
            VALUES (:order_id, :user_id, :issue_type, :ticket_status, :bot_summary, :refund_amount, NOW())
        """),
        {
            "order_id": order_id,
            "user_id": user_id,
            "issue_type": issue_type,
            "ticket_status": ticket_status,
            "bot_summary": bot_summary,
            "refund_amount": refund_amount,
        },
    )
    return result.lastrowid


def create_support_ticket(
    order_id: int,
    user_id: int,
    issue_type: str,
    ticket_status: str = "open",
    bot_summary: str = "",
    refund_amount: float = 0.0,
) -> Dict[str, Any]:
    """
    Inserts a new support ticket after validating it against the real order in the database.
    issue_type must be one of:
      'order_delay', 'missing_item', 'food_quality', 'agent_escalation'
      ('cancellation' tickets are created only by process_cancellation_refund)
    ticket_status must be one of:
      'open', 'resolved_bot', 'escalated_to_agent'

    Rules enforced here (not left to the language model):
      * the order must exist and belong to the user
      * missing_item / food_quality only for DELIVERED orders
      * order_delay only for orders that are still LIVE
      * no duplicate open ticket of the same type for the same order
      * refund can never exceed the order total
    """
    if issue_type not in ISSUE_TYPES or issue_type == "cancellation":
        return _fail(f"Invalid issue_type '{issue_type}'.")
    if ticket_status not in TICKET_STATUSES:
        return _fail(f"Invalid ticket_status '{ticket_status}'.")

    try:
        refund_amount = float(refund_amount or 0.0)
    except (TypeError, ValueError):
        return _fail("refund_amount must be a number.")
    if refund_amount < 0:
        return _fail("refund_amount cannot be negative.")

    engine = get_engine()
    with engine.begin() as conn:
        order = _fetch_order(conn, order_id)
        if not order or int(order["user_id"]) != int(user_id):
            return _fail("Order not found for this customer.")

        status = order["order_status"]
        allowed = ALLOWED_STATUS_FOR_ISSUE.get(issue_type)
        if allowed and status not in allowed:
            if issue_type in ("missing_item", "food_quality"):
                reason = (
                    f"This order is '{status}', not delivered yet, so a {issue_type.replace('_', ' ')} "
                    "ticket cannot be raised. Offer order tracking instead."
                    if status in LIVE_STATUSES
                    else f"This order is '{status}', so a {issue_type.replace('_', ' ')} ticket cannot be raised."
                )
            else:
                reason = f"This order is '{status}', so an order delay ticket does not apply."
            return _fail(reason)

        if issue_type not in REFUND_ISSUES:
            refund_amount = 0.0
        elif refund_amount > float(order["total_amount"]):
            return _fail("Refund amount cannot exceed the order total.")

        duplicate = conn.execute(
            text("""
                SELECT ticket_id, ticket_status FROM support_tickets
                WHERE order_id = :order_id AND issue_type = :issue_type
                  AND ticket_status IN ('open', 'escalated_to_agent')
                LIMIT 1
            """),
            {"order_id": order_id, "issue_type": issue_type},
        ).mappings().first()
        if duplicate:
            return _fail(
                f"A ticket for this issue already exists (ticket #{duplicate['ticket_id']}, "
                f"status: {duplicate['ticket_status']}). Do not raise another one."
            )

        new_ticket_id = _insert_ticket(conn, order_id, user_id, issue_type, ticket_status, bot_summary, refund_amount)

    return {
        "success": True,
        "ticket_id": new_ticket_id,
        "order_id": order_id,
        "issue_type": issue_type,
        "ticket_status": ticket_status,
        "refund_amount": refund_amount,
    }


def process_cancellation_refund(order_id: int, user_id: int, refund_amount: float, reason: str) -> Dict[str, Any]:
    """
    Cancels an order and records the refund ticket, in one transaction.
    Allowed only while the order is 'placed' or 'preparing'. The refund is always the full order total.
    """
    engine = get_engine()
    with engine.begin() as conn:
        order = _fetch_order(conn, order_id)
        if not order or int(order["user_id"]) != int(user_id):
            return _fail("Order not found for this customer.")

        status = order["order_status"]
        if status not in CANCELLABLE_STATUSES:
            if status == "out_for_delivery":
                return _fail("The order is already out for delivery and can no longer be cancelled.")
            if status == "delivered":
                return _fail("The order has already been delivered and cannot be cancelled.")
            if status == "cancelled":
                return _fail("The order is already cancelled.")
            return _fail(f"The order is '{status}' and cannot be cancelled.")

        full_refund = float(order["total_amount"])

        # The WHERE clause re-checks the status so two requests cannot both cancel the order.
        updated = conn.execute(
            text("""
                UPDATE orders SET order_status = 'cancelled', cancellation_reason = :reason
                WHERE order_id = :order_id AND order_status IN ('placed', 'preparing')
            """),
            {"reason": reason, "order_id": order_id},
        )
        if updated.rowcount != 1:
            return _fail("The order status changed just now and it can no longer be cancelled.")

        ticket_id = _insert_ticket(
            conn,
            order_id,
            user_id,
            "cancellation",
            "resolved_bot",
            f"Automated bot refund processed: ₹{full_refund}. Reason: {reason}",
            full_refund,
        )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "order_id": order_id,
        "issue_type": "cancellation",
        "ticket_status": "resolved_bot",
        "refund_amount": full_refund,
    }


if __name__ == "__main__":
    print("[INFO] ticket_actions module loaded successfully.")