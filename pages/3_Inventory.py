import streamlit as st
from db import get_session
from models import Purchase

st.set_page_config(page_title="Inventory – FoodApp", page_icon="🛒", layout="wide")
st.title("🛒 Market Purchases")

session = get_session()

# ── Record new purchase ────────────────────────────────────────────────────────
with st.expander("➕ Record Market Purchase", expanded=False):
    with st.form("add_purchase_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        item_name = c1.text_input("Item Name *", placeholder="e.g. Tomatoes")
        category  = c2.text_input("Category *",  placeholder="e.g. Vegetables, Meat, Spices")

        c3, c4, c5 = st.columns(3)
        quantity  = c3.number_input("Quantity *", min_value=0.01, step=0.5, format="%.2f")
        unit      = c4.text_input("Unit *", placeholder="kg / litre / piece")
        unit_cost = c5.number_input("Unit Cost ($) *", min_value=0.0, step=0.1, format="%.2f")

        c6, c7 = st.columns(2)
        supplier = c6.text_input("Supplier", placeholder="Market or supplier name")
        notes    = c7.text_input("Notes")

        submitted = st.form_submit_button("Record Purchase", type="primary")
        if submitted:
            if not item_name or not category or not unit or unit_cost <= 0:
                st.error("Item name, category, unit, and unit cost are required.")
            else:
                session.add(Purchase(
                    item_name=item_name, category=category,
                    quantity=quantity, unit=unit,
                    unit_cost=unit_cost, total_cost=quantity * unit_cost,
                    supplier=supplier, notes=notes,
                ))
                session.commit()
                st.success(f"Recorded: {quantity} {unit} of {item_name} — ${quantity * unit_cost:,.2f}")
                st.rerun()

st.divider()

# ── Filter & list purchases ────────────────────────────────────────────────────
all_purchases = session.query(Purchase).order_by(Purchase.purchased_at.desc()).all()
categories = ["All"] + sorted({p.category for p in all_purchases})
cat_filter = st.selectbox("Filter by category", categories)

purchases = [p for p in all_purchases if cat_filter == "All" or p.category == cat_filter]

if not purchases:
    st.info("No purchases recorded yet.")
else:
    # Summary metric
    total_spend = sum(p.total_cost for p in purchases)
    st.metric("Total spend (filtered)", f"${total_spend:,.2f}")

    data = [
        {
            "Item":      p.item_name,
            "Category":  p.category,
            "Quantity":  f"{p.quantity} {p.unit}",
            "Unit Cost": f"${p.unit_cost:.2f}",
            "Total":     f"${p.total_cost:,.2f}",
            "Supplier":  p.supplier or "—",
            "Date":      p.purchased_at.strftime("%Y-%m-%d"),
        }
        for p in purchases
    ]
    st.dataframe(data, use_container_width=True, hide_index=True)

    st.markdown("**Delete a record**")
    del_options = {f"#{p.id} — {p.item_name} ({p.purchased_at.strftime('%b %d')})": p for p in purchases}
    to_delete = st.selectbox("Select purchase to delete", ["—"] + list(del_options.keys()))
    if st.button("🗑 Delete selected", type="secondary") and to_delete != "—":
        session.delete(del_options[to_delete])
        session.commit()
        st.rerun()

session.close()
