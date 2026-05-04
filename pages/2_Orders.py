import streamlit as st
from db import get_session
from models import MenuItem, Order, OrderItem

st.set_page_config(page_title="Orders – FoodApp", page_icon="🧾", layout="wide")
st.title("🧾 Orders")

session = get_session()
menu_items = session.query(MenuItem).filter_by(available=True).order_by(MenuItem.category, MenuItem.name).all()

# ── New order form ─────────────────────────────────────────────────────────────
with st.expander("➕ New Order", expanded=False):
    if not menu_items:
        st.warning("No available menu items. Add dishes in the **Menu** page first.")
    else:
        with st.form("new_order_form", clear_on_submit=True):
            customer = st.text_input("Customer Name *")
            notes    = st.text_input("Notes / Special instructions")

            st.markdown("**Select Items**")
            item_options = {f"{m.name} — ${m.price:.2f}": m for m in menu_items}
            selected_labels = st.multiselect("Dishes *", options=list(item_options.keys()))

            quantities = {}
            if selected_labels:
                cols = st.columns(min(len(selected_labels), 4))
                for idx, label in enumerate(selected_labels):
                    quantities[label] = cols[idx % 4].number_input(
                        label, min_value=1, value=1, step=1, key=f"qty_{label}"
                    )

            submitted = st.form_submit_button("Place Order", type="primary")
            if submitted:
                if not customer:
                    st.error("Customer name is required.")
                elif not selected_labels:
                    st.error("Select at least one dish.")
                else:
                    order = Order(customer_name=customer.strip(), notes=notes)
                    session.add(order)
                    session.flush()
                    for label in selected_labels:
                        m = item_options[label]
                        session.add(OrderItem(
                            order_id=order.id,
                            menu_item_id=m.id,
                            quantity=quantities[label],
                            unit_price=m.price,
                        ))
                    session.flush()
                    order.calc_total()
                    session.commit()
                    st.success(f"Order #{order.id} placed for {customer} — ${order.total:,.2f}")
                    st.rerun()

st.divider()

# ── Filter & list orders ───────────────────────────────────────────────────────
status_filter = st.selectbox("Filter by status", ["All", "Pending", "Completed", "Cancelled"], index=0)

query = session.query(Order).order_by(Order.created_at.desc())
if status_filter != "All":
    query = query.filter_by(status=status_filter.lower())
orders = query.all()

if not orders:
    st.info("No orders found.")
else:
    for o in orders:
        status_icon = {"pending": "⏳", "completed": "✅", "cancelled": "❌"}.get(o.status, "•")
        label = f"{status_icon} Order #{o.id} — {o.customer_name} — **${o.total:,.2f}** — {o.created_at.strftime('%b %d, %H:%M')}"
        with st.expander(label):
            item_lines = "\n".join(
                f"- {oi.quantity}× {oi.menu_item.name}  (${oi.unit_price:.2f} each)"
                for oi in o.items
            )
            st.markdown(item_lines or "_No items_")
            if o.notes:
                st.caption(f"Notes: {o.notes}")

            ac1, ac2, ac3 = st.columns(3)
            if o.status == "pending":
                if ac1.button("✅ Mark Completed", key=f"comp_{o.id}"):
                    o.status = "completed"
                    session.commit()
                    st.rerun()
                if ac2.button("❌ Cancel Order", key=f"cancel_{o.id}"):
                    o.status = "cancelled"
                    session.commit()
                    st.rerun()
            if ac3.button("🗑 Delete", key=f"del_{o.id}"):
                session.delete(o)
                session.commit()
                st.rerun()

session.close()
