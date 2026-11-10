import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from src.agents.prompts import (
    LIVE_STATUSES,
    SYSTEM_PROMPT,
    build_order_context,
    build_ticket_context,
)
from src.database.queries import get_tickets_for_order
from src.tools.sql_query_tool import execute_readonly_sql
from src.tools.ticket_actions import create_support_ticket, process_cancellation_refund


# --- Wrap functions as LangChain Tools ---
@tool
def query_database(query: str) -> str:
    """Executes a read-only SQL SELECT query to retrieve order details, user records, or past tickets."""
    result = execute_readonly_sql(query)
    return str(result)


@tool
def raise_support_ticket(
    order_id: int,
    user_id: int,
    issue_type: str,
    ticket_status: str = "open",
    bot_summary: str = "",
    refund_amount: float = 0.0,
) -> str:
    """Creates a new support ticket. issue_type must be: order_delay, missing_item, food_quality, or agent_escalation.
    missing_item and food_quality are only allowed once the order is delivered. order_delay only while it is still in progress.
    For agent_escalation use ticket_status 'escalated_to_agent'."""
    res = create_support_ticket(
        order_id=order_id,
        user_id=user_id,
        issue_type=issue_type,
        ticket_status=ticket_status,
        bot_summary=bot_summary,
        refund_amount=refund_amount,
    )
    return str(res)


@tool
def cancel_and_refund_order(order_id: int, user_id: int, refund_amount: float, reason: str) -> str:
    """Cancels an order and refunds the full amount. Only works while the order status is 'placed' or 'preparing'."""
    res = process_cancellation_refund(order_id, user_id, refund_amount, reason)
    return str(res)


def _query_allowed(query: str, user_id: Any, order_id: Any) -> bool:
    """Read-only queries must be scoped to the current customer (their user_id or the selected order_id)."""
    body = query.strip().rstrip(";")
    if ";" in body:
        return False
    numbers = set(re.findall(r"\d+", body))
    return str(user_id) in numbers or (order_id is not None and str(order_id) in numbers)


class SupportAgent:
    def __init__(self):
        settings.validate()
        self.llm = ChatGoogleGenerativeAI(
            model=settings.MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            max_retries=2,
            timeout=30,
        )
        self.tools = {
            "query_database": query_database,
            "raise_support_ticket": raise_support_ticket,
            "cancel_and_refund_order": cancel_and_refund_order,
        }
        self.llm_with_tools = self.llm.bind_tools(list(self.tools.values()))

    def _guard_tool_call(self, name: str, args: Dict[str, Any], user_id: Any, order_id: Any) -> Optional[str]:
        """
        Pins every tool call to the logged-in customer and the selected order.
        Returns a rejection message, or None when the call is fine (args may be rewritten in place).
        """
        if name in ("raise_support_ticket", "cancel_and_refund_order"):
            if order_id is None:
                return "Rejected: no order is selected, so no action can be taken."
            if str(args.get("order_id")) != str(order_id):
                return "Rejected: actions are only allowed on the order the customer selected."
            args["order_id"] = order_id
            args["user_id"] = user_id  # never trust a user id supplied by the model
        elif name == "query_database":
            if not _query_allowed(str(args.get("query", "")), user_id, order_id):
                return "Rejected: queries must be limited to this customer's own user_id or selected order_id."
        return None

    def chat(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]],
        user_profile: Dict[str, Any],
        active_order: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Processes a user message, handles tool execution loops, and returns final answer."""
        now = datetime.now()
        current_time_str = now.strftime("%I:%M %p")
        user_id = user_profile.get("user_id")
        order_id = active_order.get("order_id") if active_order else None

        eta_minutes = (active_order.get("eta_minutes") or 0) if active_order else 0
        is_live = bool(active_order) and active_order.get("order_status") in LIVE_STATUSES
        expected_delivery = (
            (now + timedelta(minutes=int(eta_minutes))).strftime("%I:%M %p")
            if eta_minutes and is_live
            else "N/A"
        )

        # Tickets already raised for this order (so the agent never duplicates them)
        tickets: List[Dict[str, Any]] = []
        if order_id is not None and user_id is not None:
            try:
                tickets = get_tickets_for_order(order_id, user_id)
            except Exception as exc:
                print(f"[WARN] Could not load tickets: {exc}")

        formatted_system_prompt = SYSTEM_PROMPT.format(
            user_name=user_profile.get("name", "Valued Customer"),
            user_phone=user_profile.get("phone", "N/A"),
            user_id=user_id if user_id is not None else "N/A",
            current_time=current_time_str,
            active_order_context=build_order_context(active_order, expected_delivery_time=expected_delivery),
            open_tickets_context=build_ticket_context(tickets),
            delivery_partner_name=(
                (active_order.get("delivery_partner_name") or "Not assigned yet") if active_order else "N/A"
            ),
            delivery_partner_phone=(
                (active_order.get("delivery_partner_phone") or "N/A") if active_order else "N/A"
            ),
            eta_minutes=eta_minutes,
        )

        messages = [SystemMessage(content=formatted_system_prompt)]

        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_message))

        # Initial LLM call
        print("[DEBUG] Sending message to Gemini...")
        ai_response = self.llm_with_tools.invoke(messages)
        messages.append(ai_response)

        # Handle tool calls requested by the model, with a max iteration guard
        iteration = 0
        max_iterations = 5

        while ai_response.tool_calls and iteration < max_iterations:
            iteration += 1
            print(f"[DEBUG] Tool call detected (Iteration {iteration}): {[tc['name'] for tc in ai_response.tool_calls]}")

            for tool_call in ai_response.tool_calls:
                selected_tool = self.tools.get(tool_call["name"])
                if not selected_tool:
                    tool_output = f"Tool {tool_call['name']} not found."
                else:
                    args = dict(tool_call["args"])
                    rejection = self._guard_tool_call(tool_call["name"], args, user_id, order_id)
                    if rejection:
                        print(f"[DEBUG] Tool call rejected: {tool_call['name']} {args} -> {rejection}")
                        tool_output = rejection
                    else:
                        print(f"[DEBUG] Executing tool: {tool_call['name']} with args: {args}")
                        try:
                            tool_output = selected_tool.invoke(args)
                        except Exception as exc:
                            print(f"[ERROR] Tool {tool_call['name']} failed: {exc}")
                            tool_output = f"Tool error: {exc}"

                messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))

            print("[DEBUG] Returning tool results back to Gemini...")
            ai_response = self.llm_with_tools.invoke(messages)
            messages.append(ai_response)

        # Extract clean text string
        if isinstance(ai_response.content, str):
            return ai_response.content
        elif isinstance(ai_response.content, list):
            text_parts = [
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in ai_response.content
            ]
            return "".join(text_parts).strip()

        return str(ai_response.content)


if __name__ == "__main__":
    print("[INFO] Testing SupportAgent with Gemini Flash...")
    agent = SupportAgent()
    mock_user = {"user_id": 1964, "name": "Neha Das", "phone": "+916985066310"}
    mock_order = {
        "order_id": 6547,
        "restaurant_name": "KFC",
        "order_status": "out_for_delivery",
        "total_amount": 79.64,
        "placed_at": "2026-11-09 15:30:00",
        "eta_minutes": 10,
        "delivery_partner_name": "Suresh Kumar",
        "delivery_partner_phone": "+919876543210",
        "items": [{"item_name": "Chicken Boneless Biryani", "quantity": 1, "unit_price": 79.64}],
    }

    test_reply = agent.chat(
        user_message="Where is my food right now?",
        chat_history=[],
        user_profile=mock_user,
        active_order=mock_order,
    )
    print(f"\nAgent Reply:\n{test_reply}")