import streamlit as st
from datetime import datetime, timedelta
from sqlalchemy import func
from db import get_session
from models import Order, Purchase, Ingredient

st.set_page_config(page_title="FoodApp", page_icon="🍽", layout="wide")
st.title("🍽 FoodApp — Dashboard")

session = get_session()
today = datetime.utcnow().date()
week_ago = datetime.utcnow() - timedelta(days=7)

# ── KPI metrics ────────────────────────────────────────────────────────────────
sales_today = session.query(func.sum(Order.total)).filter(
    func.date(Order.created_at) == today, Order.status == "completed"
).scalar() or 0

sales_week = session.query(func.sum(Order.total)).filter(
    Order.created_at >= week_ago, Order.status == "completed"
).scalar() or 0

orders_today = session.query(Order).filter(func.date(Order.created_at) == today).count()
pending      = session.query(Order).filter_by(status="pending").count()
spend_week   = session.query(func.sum(Purchase.total_cost)).filter(
    Purchase.purchased_at >= week_ago
).scalar() or 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Sales Today",       f"${sales_today:,.2f}")
c2.metric("📈 Sales This Week",   f"${sales_week:,.2f}")
c3.metric("🧾 Orders Today",      orders_today)
c4.metric("⏳ Pending Orders",    pending)
c5.metric("🛒 Market Spend (7d)", f"${spend_week:,.2f}")

# ── Low stock alerts ───────────────────────────────────────────────────────────
low_stock = [i for i in session.query(Ingredient).all() if i.is_low]
if low_stock:
    st.divider()
    st.subheader("⚠️ Low Stock Alerts")
    cols = st.columns(min(len(low_stock), 4))
    for idx, ing in enumerate(low_stock):
        cols[idx % 4].warning(
            f"**{ing.name}**\n\n"
            f"{ing.quantity_in_stock:.2f} {ing.unit} remaining\n\n"
            f"_(threshold: {ing.low_stock_threshold} {ing.unit})_"
        )

st.divider()

# ── Recent activity ────────────────────────────────────────────────────────────
col_orders, col_purchases = st.columns(2)

with col_orders:
    st.subheader("Recent Orders")
    recent_orders = session.query(Order).order_by(Order.created_at.desc()).limit(8).all()
    if recent_orders:
        st.dataframe(
            [{"ID": o.id, "Customer": o.customer_name, "Total": f"${o.total:,.2f}",
              "Status": o.status.capitalize(), "Time": o.created_at.strftime("%b %d, %H:%M")}
             for o in recent_orders],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No orders yet. Go to **Orders** to create one.")

with col_purchases:
    st.subheader("Recent Purchases")
    recent_purchases = session.query(Purchase).order_by(Purchase.purchased_at.desc()).limit(8).all()
    if recent_purchases:
        st.dataframe(
            [{"Item": p.item_name, "Qty": f"{p.quantity} {p.unit}",
              "Cost": f"${p.total_cost:,.2f}", "Date": p.purchased_at.strftime("%b %d")}
             for p in recent_purchases],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No purchases yet. Go to **Inventory** to record one.")

session.close()
