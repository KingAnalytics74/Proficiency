import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func
from db import get_session
from models import Order, OrderItem, MenuItem, Purchase

st.set_page_config(page_title="Reports – FoodApp", page_icon="📊", layout="wide")
st.title("📊 Reports")

session = get_session()

# ── Date range selector ────────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
end_date   = col_a.date_input("To",   value=datetime.utcnow().date())
start_date = col_b.date_input("From", value=(datetime.utcnow() - timedelta(days=13)).date())

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt   = datetime.combine(end_date,   datetime.max.time())

st.divider()

# ── Daily sales vs spend chart ─────────────────────────────────────────────────
st.subheader("Daily Sales vs Market Spend")

days = []
d = start_date
while d <= end_date:
    sales = session.query(func.sum(Order.total)).filter(
        func.date(Order.created_at) == d, Order.status == "completed"
    ).scalar() or 0
    spend = session.query(func.sum(Purchase.total_cost)).filter(
        func.date(Purchase.purchased_at) == d
    ).scalar() or 0
    days.append({"Date": d.strftime("%b %d"), "Sales ($)": round(sales, 2), "Market Spend ($)": round(spend, 2)})
    d += timedelta(days=1)

df_days = pd.DataFrame(days).set_index("Date")
st.bar_chart(df_days, use_container_width=True)

st.divider()

# ── Top items & spend by category ─────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Top Selling Dishes")
    top_items = (
        session.query(MenuItem.name, func.sum(OrderItem.quantity).label("sold"))
        .join(OrderItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status == "completed", Order.created_at.between(start_dt, end_dt))
        .group_by(MenuItem.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
        .all()
    )
    if top_items:
        df_items = pd.DataFrame(top_items, columns=["Dish", "Units Sold"]).set_index("Dish")
        st.bar_chart(df_items, use_container_width=True)
    else:
        st.info("No completed orders in this date range.")

with col2:
    st.subheader("Market Spend by Category")
    spend_by_cat = (
        session.query(Purchase.category, func.sum(Purchase.total_cost).label("total"))
        .filter(Purchase.purchased_at.between(start_dt, end_dt))
        .group_by(Purchase.category)
        .order_by(func.sum(Purchase.total_cost).desc())
        .all()
    )
    if spend_by_cat:
        df_cat = pd.DataFrame(spend_by_cat, columns=["Category", "Total ($)"]).set_index("Category")
        st.bar_chart(df_cat, use_container_width=True)
    else:
        st.info("No purchases in this date range.")

st.divider()

# ── Daily breakdown table ──────────────────────────────────────────────────────
st.subheader("Daily Breakdown")
df_table = pd.DataFrame(days)
df_table["Net ($)"] = df_table["Sales ($)"] - df_table["Market Spend ($)"]
st.dataframe(df_table, use_container_width=True, hide_index=True)

total_sales = df_table["Sales ($)"].sum()
total_spend = df_table["Market Spend ($)"].sum()
net         = total_sales - total_spend

m1, m2, m3 = st.columns(3)
m1.metric("Total Sales",        f"${total_sales:,.2f}")
m2.metric("Total Market Spend", f"${total_spend:,.2f}")
m3.metric("Net",                f"${net:,.2f}", delta=f"${net:,.2f}")

session.close()
