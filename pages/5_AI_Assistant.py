import os
import streamlit as st
import anthropic
from datetime import datetime, timedelta
from sqlalchemy import func
from db import get_session
from models import MenuItem, Order, OrderItem, Ingredient, Purchase

st.set_page_config(page_title="AI Assistant – FoodApp", page_icon="🤖", layout="wide")
st.title("🤖 AI Restaurant Assistant")
st.caption("Ask me anything about your restaurant — sales, inventory, menu, or business advice.")

# ── API key check ──────────────────────────────────────────────────────────────
if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("**ANTHROPIC_API_KEY is not set.** Add it to your environment before running.")
    st.code("export ANTHROPIC_API_KEY=sk-ant-...")
    st.stop()

client = anthropic.Anthropic()

# ── Static system prompt (cached — never changes within a session) ─────────────
_SYSTEM_ROLE = """You are an expert AI assistant embedded inside FoodApp, a restaurant management system.
You help restaurant owners and staff with:
- Sales performance analysis and revenue trends
- Inventory and ingredient stock management
- Menu pricing, availability, and recipe cost analysis
- Identifying low stock before it causes problems
- Acting on pending orders and operational questions
- General restaurant business advice

You are given a live snapshot of the restaurant's database every time the user sends a message.
Always ground your answers in this real data — cite specific numbers, dish names, or ingredient levels.
Be concise and practical. When you spot issues (low stock, many pending orders, low margin), flag them proactively.
Format currency as $X.XX. Use bullet points for lists. Keep responses focused and useful."""

# ── DB context builder ─────────────────────────────────────────────────────────
def _build_db_context() -> str:
    session = get_session()
    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)

    # KPIs
    sales_today = session.query(func.sum(Order.total)).filter(
        func.date(Order.created_at) == today, Order.status == "completed"
    ).scalar() or 0

    sales_week = session.query(func.sum(Order.total)).filter(
        Order.created_at >= week_ago, Order.status == "completed"
    ).scalar() or 0

    spend_week = session.query(func.sum(Purchase.total_cost)).filter(
        Purchase.purchased_at >= week_ago
    ).scalar() or 0

    orders_today = session.query(Order).filter(func.date(Order.created_at) == today).count()

    # Pending orders
    pending = session.query(Order).filter_by(status="pending").order_by(Order.created_at).all()

    # Menu
    menu_items = session.query(MenuItem).order_by(MenuItem.category, MenuItem.name).all()

    # Ingredients
    ingredients = session.query(Ingredient).order_by(Ingredient.name).all()
    low_stock = [i for i in ingredients if i.is_low]

    # Top sellers this week
    top = (
        session.query(MenuItem.name, func.sum(OrderItem.quantity).label("sold"))
        .join(OrderItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status == "completed", Order.created_at >= week_ago)
        .group_by(MenuItem.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(8)
        .all()
    )

    session.close()

    lines = [
        f"## Live Restaurant Snapshot — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "### Business Summary",
        f"- Sales today: ${sales_today:,.2f}  ({orders_today} orders)",
        f"- Sales this week: ${sales_week:,.2f}",
        f"- Market spend this week: ${spend_week:,.2f}",
        f"- Net this week: ${sales_week - spend_week:,.2f}",
        f"- Pending orders right now: {len(pending)}",
    ]

    # Pending orders detail
    if pending:
        lines += ["", f"### Pending Orders ({len(pending)})"]
        for o in pending[:15]:
            items_str = ", ".join(f"{oi.quantity}× {oi.menu_item.name}" for oi in o.items)
            lines.append(f"- #{o.id} | {o.customer_name} | {items_str} | ${o.total:.2f} | {o.created_at.strftime('%H:%M')}")

    # Menu
    lines += ["", "### Menu (✓ = available, ✗ = unavailable)"]
    current_cat = None
    for item in menu_items:
        if item.category != current_cat:
            lines.append(f"\n**{item.category}**")
            current_cat = item.category
        avail = "✓" if item.available else "✗"
        recipe_cost = 0.0
        recipe_note = ""
        if item.ingredients:
            parts = []
            for link in item.ingredients:
                parts.append(f"{link.quantity_per_serving}{link.ingredient.unit} {link.ingredient.name}")
            recipe_note = f" [recipe: {', '.join(parts)}]"
        lines.append(f"  {avail} {item.name} — ${item.price:.2f}{recipe_note}")

    # Ingredient stock
    if ingredients:
        lines += ["", "### Ingredient Stock"]
        for ing in ingredients:
            flag = " ⚠️ LOW" if ing.is_low else ""
            lines.append(
                f"- {ing.name}: {ing.quantity_in_stock:.2f} {ing.unit}"
                f" (alert ≤ {ing.low_stock_threshold}){flag}"
            )

    if low_stock:
        lines += ["", f"### ⚠️ Low Stock Summary ({len(low_stock)} items need restocking)"]
        for ing in low_stock:
            lines.append(f"- **{ing.name}**: {ing.quantity_in_stock:.2f} {ing.unit} remaining")

    # Top sellers
    if top:
        lines += ["", "### Top Sellers This Week"]
        for name, sold in top:
            lines.append(f"- {name}: {sold} portions")

    return "\n".join(lines)


# ── Streaming helper ───────────────────────────────────────────────────────────
def _stream_reply(history: list[dict], db_context: str):
    """Yield text chunks from Claude, streaming the response."""
    system = [
        # Static role — eligible for prompt caching across turns
        {
            "type": "text",
            "text": _SYSTEM_ROLE,
            "cache_control": {"type": "ephemeral"},
        },
        # Live DB snapshot — refreshed every turn, not cached
        {
            "type": "text",
            "text": db_context,
        },
    ]

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=system,
        messages=history,
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Sidebar controls ───────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Assistant Controls")
    if st.button("🗑 Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("**Suggested questions:**")
    suggestions = [
        "What are my sales like today?",
        "Which ingredients are running low?",
        "What are my best-selling dishes this week?",
        "Am I making a profit this week?",
        "What should I restock before tomorrow?",
        "Which menu items have the lowest profit margin?",
        "How many pending orders do I have?",
        "Give me a business summary.",
    ]
    for s in suggestions:
        if st.button(s, key=f"sug_{s}", use_container_width=True):
            st.session_state["_prefill"] = s
            st.rerun()

# ── Chat history ───────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Handle suggestion prefill ──────────────────────────────────────────────────
prefill = st.session_state.pop("_prefill", None)

# ── Chat input ─────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask about your sales, stock, menu...") or prefill

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    db_context = _build_db_context()

    api_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    with st.chat_message("assistant"):
        response_text = st.write_stream(_stream_reply(api_history, db_context))

    st.session_state.messages.append({"role": "assistant", "content": response_text})
