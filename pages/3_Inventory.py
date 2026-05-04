import streamlit as st
from datetime import datetime
from db import get_session
from models import Ingredient, Purchase

st.set_page_config(page_title="Inventory – FoodApp", page_icon="🛒", layout="wide")
st.title("🛒 Inventory")

session = get_session()

tab_stock, tab_purchases = st.tabs(["📦 Stock Levels", "🧾 Market Purchases"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Stock Levels
# ══════════════════════════════════════════════════════════════════════════════
with tab_stock:
    with st.expander("➕ Add New Ingredient", expanded=False):
        with st.form("add_ingredient_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ing_name  = c1.text_input("Ingredient Name *", placeholder="e.g. Tomatoes")
            category  = c2.text_input("Category *", placeholder="e.g. Vegetables, Meat")
            c3, c4, c5 = st.columns(3)
            qty_stock = c3.number_input("Initial Stock *", min_value=0.0, step=0.5, format="%.2f")
            unit      = c4.text_input("Unit *", placeholder="kg / litre / piece")
            threshold = c5.number_input("Low Stock Alert At", min_value=0.0, step=0.1, format="%.2f",
                                        help="Get a dashboard alert when stock drops to this level.")
            if st.form_submit_button("Add Ingredient", type="primary"):
                if not ing_name or not category or not unit:
                    st.error("Name, category, and unit are required.")
                else:
                    session.add(Ingredient(
                        name=ing_name, category=category,
                        quantity_in_stock=qty_stock, unit=unit,
                        low_stock_threshold=threshold,
                    ))
                    session.commit()
                    st.success(f"'{ing_name}' added to ingredients.")
                    st.rerun()

    st.divider()

    ingredients = session.query(Ingredient).order_by(Ingredient.category, Ingredient.name).all()
    if not ingredients:
        st.info("No ingredients yet. Add one above, then link dishes to them in the **Menu** page.")
    else:
        # Summary metrics
        low_count = sum(1 for i in ingredients if i.is_low)
        m1, m2 = st.columns(2)
        m1.metric("Total Ingredients", len(ingredients))
        m2.metric("⚠️ Low Stock", low_count, delta=None if low_count == 0 else f"{low_count} need restocking",
                  delta_color="inverse")

        categories = sorted({i.category for i in ingredients})
        for cat in categories:
            st.subheader(cat)
            cat_ings = [i for i in ingredients if i.category == cat]
            for ing in cat_ings:
                status = "🔴 LOW" if ing.is_low else "🟢 OK"
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 2])
                    c1.markdown(f"**{ing.name}**")
                    c2.metric("In Stock", f"{ing.quantity_in_stock:.2f} {ing.unit}", label_visibility="collapsed")
                    c3.caption(f"Alert at: {ing.low_stock_threshold} {ing.unit}")
                    c4.markdown(status)

                    with c5:
                        adj_col, del_col = st.columns(2)
                        if adj_col.button("Adjust", key=f"adj_{ing.id}"):
                            st.session_state[f"adjusting_{ing.id}"] = True
                        if del_col.button("Delete", key=f"deling_{ing.id}"):
                            session.delete(ing)
                            session.commit()
                            st.rerun()

                    if st.session_state.get(f"adjusting_{ing.id}"):
                        with st.form(f"adj_form_{ing.id}"):
                            new_qty  = st.number_input("New stock quantity", value=ing.quantity_in_stock,
                                                       step=0.1, format="%.2f")
                            new_thr  = st.number_input("Low stock threshold", value=ing.low_stock_threshold,
                                                       step=0.1, format="%.2f")
                            s1, s2 = st.columns(2)
                            if s1.form_submit_button("Save", type="primary"):
                                ing.quantity_in_stock   = new_qty
                                ing.low_stock_threshold = new_thr
                                ing.updated_at = datetime.utcnow()
                                session.commit()
                                st.session_state.pop(f"adjusting_{ing.id}", None)
                                st.rerun()
                            if s2.form_submit_button("Cancel"):
                                st.session_state.pop(f"adjusting_{ing.id}", None)
                                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Market Purchases
# ══════════════════════════════════════════════════════════════════════════════
with tab_purchases:
    ingredients = session.query(Ingredient).order_by(Ingredient.name).all()

    with st.expander("➕ Record Market Purchase", expanded=False):
        with st.form("add_purchase_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            item_name = c1.text_input("Item Name *", placeholder="e.g. Tomatoes")
            category  = c2.text_input("Category *",  placeholder="e.g. Vegetables")

            c3, c4, c5 = st.columns(3)
            quantity  = c3.number_input("Quantity *", min_value=0.01, step=0.5, format="%.2f")
            unit      = c4.text_input("Unit *", placeholder="kg / litre / piece")
            unit_cost = c5.number_input("Unit Cost ($) *", min_value=0.0, step=0.1, format="%.2f")

            c6, c7 = st.columns(2)
            supplier  = c6.text_input("Supplier")
            notes     = c7.text_input("Notes")

            # Optional: link to an ingredient to restock it
            ing_options = {"— Don't restock (record only) —": None}
            ing_options.update({f"{i.name} ({i.unit})": i for i in ingredients})
            restock_label = st.selectbox(
                "Restock ingredient",
                list(ing_options.keys()),
                help="If selected, this purchase will add to that ingredient's stock.",
            )

            if st.form_submit_button("Record Purchase", type="primary"):
                if not item_name or not category or not unit or unit_cost <= 0:
                    st.error("Item name, category, unit, and unit cost are required.")
                else:
                    chosen_ing = ing_options[restock_label]
                    purchase = Purchase(
                        item_name=item_name, category=category,
                        quantity=quantity, unit=unit,
                        unit_cost=unit_cost, total_cost=quantity * unit_cost,
                        supplier=supplier, notes=notes,
                        ingredient_id=chosen_ing.id if chosen_ing else None,
                    )
                    session.add(purchase)
                    if chosen_ing:
                        chosen_ing.quantity_in_stock += quantity
                        chosen_ing.updated_at = datetime.utcnow()
                    session.commit()
                    msg = f"Recorded: {quantity} {unit} of {item_name} — ${quantity * unit_cost:,.2f}"
                    if chosen_ing:
                        msg += f" | {chosen_ing.name} stock → {chosen_ing.quantity_in_stock:.2f} {chosen_ing.unit}"
                    st.success(msg)
                    st.rerun()

    st.divider()

    all_purchases = session.query(Purchase).order_by(Purchase.purchased_at.desc()).all()
    categories    = ["All"] + sorted({p.category for p in all_purchases})
    cat_filter    = st.selectbox("Filter by category", categories)
    purchases     = [p for p in all_purchases if cat_filter == "All" or p.category == cat_filter]

    if not purchases:
        st.info("No purchases recorded yet.")
    else:
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
                "Restocked": p.ingredient.name if p.ingredient else "—",
                "Date":      p.purchased_at.strftime("%Y-%m-%d"),
            }
            for p in purchases
        ]
        st.dataframe(data, use_container_width=True, hide_index=True)

        st.markdown("**Delete a record**")
        del_options = {f"#{p.id} — {p.item_name} ({p.purchased_at.strftime('%b %d')})": p for p in purchases}
        to_delete   = st.selectbox("Select purchase to delete", ["—"] + list(del_options.keys()))
        if st.button("🗑 Delete selected", type="secondary") and to_delete != "—":
            session.delete(del_options[to_delete])
            session.commit()
            st.rerun()

session.close()
