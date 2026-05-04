import streamlit as st
from db import get_session
from models import MenuItem, Ingredient, MenuItemIngredient

st.set_page_config(page_title="Menu – FoodApp", page_icon="🍽", layout="wide")
st.title("🥘 Menu Management")

session = get_session()

# ── Add new item ───────────────────────────────────────────────────────────────
with st.expander("➕ Add New Menu Item", expanded=False):
    with st.form("add_item_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name      = c1.text_input("Dish Name *")
        category  = c2.text_input("Category *", placeholder="e.g. Main Course, Drinks")
        desc      = st.text_input("Description")
        c3, c4    = st.columns(2)
        price     = c3.number_input("Price ($) *", min_value=0.0, step=0.5, format="%.2f")
        available = c4.checkbox("Available for order", value=True)
        if st.form_submit_button("Add Item", type="primary"):
            if not name or not category or price <= 0:
                st.error("Name, category, and a price greater than 0 are required.")
            else:
                session.add(MenuItem(name=name, description=desc, price=price,
                                     category=category, available=available))
                session.commit()
                st.success(f"'{name}' added to the menu.")
                st.rerun()

st.divider()

# ── Display items grouped by category ─────────────────────────────────────────
items = session.query(MenuItem).order_by(MenuItem.category, MenuItem.name).all()
all_ingredients = session.query(Ingredient).order_by(Ingredient.name).all()

if not items:
    st.info("No menu items yet. Add your first dish above.")
else:
    categories = sorted({i.category for i in items})
    for cat in categories:
        st.subheader(cat)
        for item in [i for i in items if i.category == cat]:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                c1.markdown(f"**{item.name}**  \n<small>{item.description or '—'}</small>",
                            unsafe_allow_html=True)
                c2.markdown(f"**${item.price:,.2f}**")
                c3.markdown("🟢 Available" if item.available else "🔴 Unavailable")

                with c4:
                    ec, dc = st.columns(2)
                    if ec.button("Edit", key=f"edit_{item.id}"):
                        st.session_state[f"editing_{item.id}"] = True
                    if dc.button("Delete", key=f"del_{item.id}"):
                        session.delete(item)
                        session.commit()
                        st.rerun()

                # ── Recipe / ingredient links ──────────────────────────────
                if item.ingredients:
                    recipe_lines = "  \n".join(
                        f"• {link.quantity_per_serving} {link.ingredient.unit} **{link.ingredient.name}**"
                        for link in item.ingredients
                    )
                    st.caption(f"**Recipe:** {recipe_lines}")
                else:
                    st.caption("_No ingredients linked yet._")

                if st.button("🧪 Manage Recipe", key=f"recipe_{item.id}"):
                    st.session_state[f"recipe_{item.id}"] = not st.session_state.get(f"recipe_{item.id}", False)

                if st.session_state.get(f"recipe_{item.id}"):
                    st.markdown("**Link an ingredient to this dish:**")
                    if not all_ingredients:
                        st.warning("No ingredients in stock yet. Add them in the **Inventory** page first.")
                    else:
                        ing_options = {f"{ing.name} ({ing.unit})": ing for ing in all_ingredients}
                        with st.form(f"recipe_form_{item.id}", clear_on_submit=True):
                            rc1, rc2 = st.columns(2)
                            sel_label = rc1.selectbox("Ingredient", list(ing_options.keys()))
                            qty_per   = rc2.number_input("Qty per serving", min_value=0.001, step=0.1, format="%.3f")
                            if st.form_submit_button("Add to Recipe"):
                                chosen = ing_options[sel_label]
                                existing = next(
                                    (l for l in item.ingredients if l.ingredient_id == chosen.id), None
                                )
                                if existing:
                                    existing.quantity_per_serving = qty_per
                                else:
                                    session.add(MenuItemIngredient(
                                        menu_item_id=item.id,
                                        ingredient_id=chosen.id,
                                        quantity_per_serving=qty_per,
                                    ))
                                session.commit()
                                st.rerun()

                    if item.ingredients:
                        st.markdown("**Remove ingredient from recipe:**")
                        rem_opts = {link.ingredient.name: link for link in item.ingredients}
                        rem_sel  = st.selectbox("Select", list(rem_opts.keys()), key=f"rem_{item.id}")
                        if st.button("Remove", key=f"remb_{item.id}"):
                            session.delete(rem_opts[rem_sel])
                            session.commit()
                            st.rerun()

                # ── Edit form ──────────────────────────────────────────────
                if st.session_state.get(f"editing_{item.id}"):
                    with st.form(f"edit_form_{item.id}"):
                        ec1, ec2  = st.columns(2)
                        new_name  = ec1.text_input("Name", value=item.name)
                        new_cat   = ec2.text_input("Category", value=item.category)
                        new_desc  = st.text_input("Description", value=item.description)
                        ec3, ec4  = st.columns(2)
                        new_price = ec3.number_input("Price ($)", value=item.price, step=0.5, format="%.2f")
                        new_avail = ec4.checkbox("Available", value=item.available)
                        sc1, sc2  = st.columns(2)
                        if sc1.form_submit_button("Save", type="primary"):
                            item.name, item.description = new_name, new_desc
                            item.price, item.category   = new_price, new_cat
                            item.available = new_avail
                            session.commit()
                            st.session_state.pop(f"editing_{item.id}", None)
                            st.rerun()
                        if sc2.form_submit_button("Cancel"):
                            st.session_state.pop(f"editing_{item.id}", None)
                            st.rerun()

session.close()
