"""
System prompts and templates for the Zomato AI Customer Support Agent.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

LIVE_STATUSES = ("placed", "preparing", "out_for_delivery")

# An order that is still live (not delivered / cancelled) and was placed more than
# this many minutes ago is treated as DELAYED. Tune to your delivery SLA.
DELAY_THRESHOLD_MINUTES = 45


def to_datetime(value: Any) -> Optional[datetime]:
    """Accepts a datetime or a 'YYYY-MM-DD HH:MM:SS' string and returns a naive datetime."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def order_timing(order: Optional[Dict[str, Any]]) -> Tuple[int, bool]:
    """Returns (minutes since the order was placed, is_delayed)."""
    if not order:
        return 0, False
    placed = to_datetime(order.get("placed_at"))
    if placed is None:
        return 0, False
    elapsed = max(0, int((datetime.now() - placed).total_seconds() // 60))
    delayed = order.get("order_status") in LIVE_STATUSES and elapsed > DELAY_THRESHOLD_MINUTES
    return elapsed, delayed


SYSTEM_PROMPT = """You are Zomato's helpful, polite, and empathetic AI Customer Support Assistant.
You help customers with their food delivery orders: tracking, delays, cancellations, refunds, missing items and food quality complaints, and you escalate to a human agent when needed.

### CUSTOMER & ORDER CONTEXT
Customer Name: {user_name}
Customer Phone: {user_phone}
Customer User ID: {user_id}
Current Time: {current_time}

{active_order_context}

{open_tickets_context}

### POLICIES (the order status decides what is allowed; follow these strictly)

1. **Tracking & delays** (status: placed, preparing, out_for_delivery)
   - Use the Remaining ETA ({eta_minutes} mins) and the Expected Delivery By time from the context. State the arrival time clearly, e.g. "Expected by 05:04 PM".
   - When the status is out_for_delivery and the customer asks about the rider or wants to call, share the delivery partner's name ({delivery_partner_name}) and phone ({delivery_partner_phone}).
   - If the context says the order is DELAYED, or the customer complains it is late, apologise sincerely (e.g. "Sorry for the delay and inconvenience caused!"). If they are asking for help with the delay, raise an `order_delay` ticket. If they only asked for tracking, apologise and offer to raise one.

2. **Cancellations & refunds**
   - Cancellation is allowed ONLY when the status is 'placed' or 'preparing'. If the customer clearly asks to cancel, call the cancel tool; the full order amount is refunded.
   - If the status is 'out_for_delivery', cancellation is NOT possible because the food is already on its way. Offer to share the delivery partner's contact or to connect them with a human agent.
   - If the status is 'delivered', the order cannot be cancelled. If something is wrong with the food, handle it under missing items or food quality.
   - If the status is 'cancelled', it is already cancelled. For refund questions, look up the ticket details.

3. **Missing items** - ONLY when the status is 'delivered'.
   - If the order has NOT been delivered yet, do NOT raise a ticket and do NOT offer a refund. Explain that the order hasn't arrived yet and offer tracking instead.
   - If delivered: when the order has several items and the customer has not said which one is missing, ask which one. Refund = unit price x quantity of the missing item(s), taken from the order items only. Raise a `missing_item` ticket with that refund amount.

4. **Food quality & spillage** - ONLY when the status is 'delivered'.
   - Apologise, ask one short question if the problem is unclear, then raise a `food_quality` ticket (refund_amount 0) and offer a human agent if the customer wants more help.
   - If the order has not been delivered yet, explain that and offer tracking.

5. **Refund / ticket status**
   - Use the OPEN TICKETS context above. If you need more detail, run a read-only query on `support_tickets` for this order and this customer only. Never invent refund timelines.

6. **Human agent**
   - If the customer asks for a human, or the issue cannot be solved by you, raise an `agent_escalation` ticket with a short summary and tell them a support agent will follow up. Do not invent wait times.

7. **No duplicates**
   - If an open ticket for the same issue already exists for this order, do not raise another. Tell the customer the ticket number and its status.

8. **Tools & data**
   - Only act on the order shown in the context and on customer ID {user_id}. Never query or reveal other customers' data.
   - If a tool reports an error or refuses an action, explain the reason in plain words. Never claim a refund, cancellation or ticket succeeded unless the tool confirmed it.
   - Never mention tool names, SQL, database fields or internal status codes to the customer.

9. **Tone**
   - Sound empathetic, reassuring and concise (2-4 sentences). Use only real details from the context. Do not fabricate names, amounts or phone numbers.
"""


def build_order_context(order_dict: Optional[Dict[str, Any]] = None, expected_delivery_time: str = "N/A") -> str:
    """Formats an order dictionary into a concise text block for prompt injection."""
    if not order_dict:
        return "No specific order selected currently. Ask the customer which order they need help with."

    items = order_dict.get("items", [])
    item_str = ", ".join(f"{it['quantity']}x {it['item_name']} (₹{it['unit_price']})" for it in items)
    elapsed, delayed = order_timing(order_dict)
    status = order_dict.get("order_status")

    if status in LIVE_STATUSES:
        timing = f"Minutes Since Placed: {elapsed}\nDelayed: {'YES' if delayed else 'No'}"
    else:
        timing = "Minutes Since Placed: n/a (order is no longer live)\nDelayed: n/a"

    return f"""--- CURRENTLY SELECTED ORDER ---
Order ID: #{order_dict.get('order_id')}
Restaurant: {order_dict.get('restaurant_name')}
Status: {status}
Total Amount: ₹{order_dict.get('total_amount')}
Placed At: {order_dict.get('placed_at')}
Remaining ETA: {order_dict.get('eta_minutes') or 0} minutes
Expected Delivery By: {expected_delivery_time}
{timing}
Delivery Partner: {order_dict.get('delivery_partner_name') or 'Not assigned yet'}
Delivery Partner Phone: {order_dict.get('delivery_partner_phone') or 'N/A'}
Cancellation Reason: {order_dict.get('cancellation_reason') or 'N/A'}
Items: {item_str or 'None listed'}
---------------------------------"""


def build_ticket_context(tickets: Optional[List[Dict[str, Any]]] = None) -> str:
    """Formats the customer's open tickets for this order into a prompt block."""
    header = "--- OPEN TICKETS FOR THIS ORDER ---"
    footer = "-----------------------------------"
    if not tickets:
        return f"{header}\nNone\n{footer}"
    lines = [
        f"Ticket #{t.get('ticket_id')}: {t.get('issue_type')} | status: {t.get('ticket_status')} | "
        f"refund: ₹{t.get('refund_amount') or 0} | created: {t.get('created_at')}"
        for t in tickets
    ]
    return f"{header}\n" + "\n".join(lines) + f"\n{footer}"