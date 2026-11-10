from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text

from src.database.connection import get_engine

LIVE_STATUSES = ("placed", "preparing", "out_for_delivery")

ORDER_COLUMNS = """order_id, user_id, restaurant_name, order_status, total_amount,
               placed_at, eta_minutes, delivery_partner_name, delivery_partner_phone,
               cancellation_reason"""


def _clean(value: Any) -> Any:
    """Makes DB values JSON / prompt friendly (Decimal -> float, datetime -> string)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def _row(row: Any) -> Dict[str, Any]:
    return {k: _clean(v) for k, v in dict(row).items()}


def _attach_items(conn, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Adds an 'items' list to every order using a single query."""
    if not orders:
        return orders
    query = text("""
        SELECT item_id, order_id, item_name, quantity, unit_price
        FROM order_items
        WHERE order_id IN :ids
        ORDER BY item_id
    """).bindparams(bindparam("ids", expanding=True))
    rows = conn.execute(query, {"ids": [o["order_id"] for o in orders]}).mappings().all()

    by_order: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        item = _row(r)
        by_order.setdefault(item["order_id"], []).append(item)
    for o in orders:
        o["items"] = by_order.get(o["order_id"], [])
    return orders


def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches user information for authentication and greeting."""
    query = text("SELECT user_id, name, phone FROM users WHERE user_id = :user_id")
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(query, {"user_id": user_id}).mappings().first()
        return _row(row) if row else None


def get_user_orders(user_id: int, limit: int = 3, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves orders for a user ordered by most recent first."""
    query = text(f"""
        SELECT {ORDER_COLUMNS}
        FROM orders
        WHERE user_id = :user_id
        ORDER BY placed_at DESC
        LIMIT :limit OFFSET :offset
    """)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(query, {"user_id": user_id, "limit": limit, "offset": offset}).mappings().all()
        return [_row(r) for r in rows]


def get_user_orders_with_items(user_id: int, limit: int = 4, offset: int = 0) -> List[Dict[str, Any]]:
    """Same as get_user_orders, but every order also carries its items."""
    query = text(f"""
        SELECT {ORDER_COLUMNS}
        FROM orders
        WHERE user_id = :user_id
        ORDER BY placed_at DESC
        LIMIT :limit OFFSET :offset
    """)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(query, {"user_id": user_id, "limit": limit, "offset": offset}).mappings().all()
        return _attach_items(conn, [_row(r) for r in rows])


def get_live_orders(user_id: int) -> List[Dict[str, Any]]:
    """Orders that are still in progress (placed / preparing / out_for_delivery), newest first."""
    query = text(f"""
        SELECT {ORDER_COLUMNS}
        FROM orders
        WHERE user_id = :user_id
          AND order_status IN ('placed', 'preparing', 'out_for_delivery')
        ORDER BY placed_at DESC
    """)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(query, {"user_id": user_id}).mappings().all()
        return _attach_items(conn, [_row(r) for r in rows])


def get_order_details(order_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a single order along with its item breakdown."""
    order_query = text(f"""
        SELECT {ORDER_COLUMNS}
        FROM orders
        WHERE order_id = :order_id
    """)
    engine = get_engine()
    with engine.connect() as conn:
        order_row = conn.execute(order_query, {"order_id": order_id}).mappings().first()
        if not order_row:
            return None
        order = _row(order_row)
        _attach_items(conn, [order])
        return order


def get_open_tickets(user_id: int) -> List[Dict[str, Any]]:
    """Unresolved support tickets for a user, with the restaurant name of the related order."""
    query = text("""
        SELECT t.ticket_id, t.order_id, t.issue_type, t.ticket_status, t.refund_amount,
               t.bot_summary, t.created_at, o.restaurant_name, o.order_status
        FROM support_tickets t
        LEFT JOIN orders o ON o.order_id = t.order_id
        WHERE t.user_id = :user_id AND t.ticket_status IN ('open', 'escalated_to_agent')
        ORDER BY t.created_at DESC
    """)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(query, {"user_id": user_id}).mappings().all()
        return [_row(r) for r in rows]


def get_tickets_for_order(order_id: int, user_id: int) -> List[Dict[str, Any]]:
    """All tickets (open or closed) raised for one order of this user, newest first."""
    query = text("""
        SELECT ticket_id, order_id, issue_type, ticket_status, refund_amount, bot_summary, created_at
        FROM support_tickets
        WHERE order_id = :order_id AND user_id = :user_id
        ORDER BY created_at DESC
    """)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(query, {"order_id": order_id, "user_id": user_id}).mappings().all()
        return [_row(r) for r in rows]


if __name__ == "__main__":
    sample_user = get_user_profile(1964)
    print(f"[TEST] Profile: {sample_user}")
    sample_orders = get_user_orders_with_items(1964, limit=3)
    print(f"[TEST] Found {len(sample_orders)} orders:")
    for o in sample_orders:
        item_summary = ", ".join(f"{it['quantity']}x {it['item_name']}" for it in o.get("items", []))
        print(f"  - Order #{o['order_id']} | {o['restaurant_name']} | Status: {o['order_status']} | ₹{o['total_amount']} | Items: {item_summary}")
    print(f"[TEST] Live orders: {[o['order_id'] for o in get_live_orders(1964)]}")
    print(f"[TEST] Open tickets: {[t['ticket_id'] for t in get_open_tickets(1964)]}")