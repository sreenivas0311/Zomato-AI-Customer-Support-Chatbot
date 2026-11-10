from src.agents.support_agent import SupportAgent

agent = SupportAgent()

mock_user = {
    "user_id": 1964,
    "name": "Neha Das",
    "phone": "+916985066310"
}

mock_order = {
    "order_id": 6547,
    "restaurant_name": "KFC",
    "order_status": "delivered",
    "total_amount": 79.64,
    "placed_at": "2026-11-09 15:30:00",
    "eta_minutes": 0,
    "delivery_partner_name": "Suresh Kumar",
    "delivery_partner_phone": "+919876543210",
    "items": [
        {"item_name": "Chicken Boneless Biryani", "quantity": 1, "unit_price": 79.64}
    ]
}

print("=" * 60)
print("TEST 1: Missing Item / Quality Issue")
print("=" * 60)

chat_history = []
user_msg_1 = "I opened my order and the Biryani was completely missing from the bag!"
print(f"User: {user_msg_1}\n")

reply_1 = agent.chat(
    user_message=user_msg_1,
    chat_history=chat_history,
    user_profile=mock_user,
    active_order=mock_order
)
print(f"Agent:\n{reply_1}\n")

chat_history.append({"role": "user", "content": user_msg_1})
chat_history.append({"role": "assistant", "content": reply_1})

print("=" * 60)
print("TEST 2: Cancellation & Refund Query")
print("=" * 60)

mock_active_order = {
    "order_id": 6548,
    "restaurant_name": "Burger King",
    "order_status": "placed",
    "total_amount": 34.50,
    "placed_at": "2026-11-09 16:35:00",
    "eta_minutes": 30,
    "delivery_partner_name": "Ramesh",
    "delivery_partner_phone": "+919811223344",
    "items": [
        {"item_name": "Whopper", "quantity": 1, "unit_price": 34.50}
    ]
}

user_msg_2 = "I just placed this order by mistake 2 minutes ago. Can you cancel it and refund me?"
print(f"User: {user_msg_2}\n")

reply_2 = agent.chat(
    user_message=user_msg_2,
    chat_history=[],
    user_profile=mock_user,
    active_order=mock_active_order
)
print(f"Agent:\n{reply_2}\n")