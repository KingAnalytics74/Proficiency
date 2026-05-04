import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from models import db, MenuItem, Order, OrderItem, Purchase

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///foodapp.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    today = datetime.utcnow().date()
    week_ago = datetime.utcnow() - timedelta(days=7)

    total_sales_today = (
        db.session.query(db.func.sum(Order.total))
        .filter(
            db.func.date(Order.created_at) == today,
            Order.status == "completed",
        )
        .scalar() or 0
    )
    total_sales_week = (
        db.session.query(db.func.sum(Order.total))
        .filter(Order.created_at >= week_ago, Order.status == "completed")
        .scalar() or 0
    )
    orders_today = Order.query.filter(
        db.func.date(Order.created_at) == today
    ).count()
    pending_orders = Order.query.filter_by(status="pending").count()
    total_purchases_week = (
        db.session.query(db.func.sum(Purchase.total_cost))
        .filter(Purchase.purchased_at >= week_ago)
        .scalar() or 0
    )

    recent_orders = (
        Order.query.order_by(Order.created_at.desc()).limit(5).all()
    )
    recent_purchases = (
        Purchase.query.order_by(Purchase.purchased_at.desc()).limit(5).all()
    )

    return render_template(
        "dashboard.html",
        total_sales_today=total_sales_today,
        total_sales_week=total_sales_week,
        orders_today=orders_today,
        pending_orders=pending_orders,
        total_purchases_week=total_purchases_week,
        recent_orders=recent_orders,
        recent_purchases=recent_purchases,
    )


# ─── Menu ─────────────────────────────────────────────────────────────────────

@app.route("/menu")
def menu():
    items = MenuItem.query.order_by(MenuItem.category, MenuItem.name).all()
    categories = sorted({i.category for i in items})
    return render_template("menu.html", items=items, categories=categories)


@app.route("/menu/add", methods=["POST"])
def add_menu_item():
    item = MenuItem(
        name=request.form["name"],
        description=request.form.get("description", ""),
        price=float(request.form["price"]),
        category=request.form["category"],
        available=request.form.get("available") == "on",
    )
    db.session.add(item)
    db.session.commit()
    flash("Menu item added.", "success")
    return redirect(url_for("menu"))


@app.route("/menu/<int:item_id>/edit", methods=["POST"])
def edit_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.name = request.form["name"]
    item.description = request.form.get("description", "")
    item.price = float(request.form["price"])
    item.category = request.form["category"]
    item.available = request.form.get("available") == "on"
    db.session.commit()
    flash("Menu item updated.", "success")
    return redirect(url_for("menu"))


@app.route("/menu/<int:item_id>/delete", methods=["POST"])
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Menu item deleted.", "success")
    return redirect(url_for("menu"))


@app.route("/api/menu")
def api_menu():
    items = MenuItem.query.filter_by(available=True).all()
    return jsonify([i.to_dict() for i in items])


# ─── Orders ───────────────────────────────────────────────────────────────────

@app.route("/orders")
def orders():
    status_filter = request.args.get("status", "all")
    query = Order.query.order_by(Order.created_at.desc())
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    all_orders = query.all()
    menu_items = MenuItem.query.filter_by(available=True).all()
    return render_template("orders.html", orders=all_orders, menu_items=menu_items, status_filter=status_filter)


@app.route("/orders/new", methods=["POST"])
def new_order():
    customer = request.form.get("customer_name", "").strip()
    notes = request.form.get("notes", "")
    item_ids = request.form.getlist("item_id[]")
    quantities = request.form.getlist("quantity[]")

    if not customer or not item_ids:
        flash("Customer name and at least one item are required.", "error")
        return redirect(url_for("orders"))

    order = Order(customer_name=customer, notes=notes)
    db.session.add(order)
    db.session.flush()

    for item_id, qty in zip(item_ids, quantities):
        menu_item = MenuItem.query.get(int(item_id))
        if not menu_item:
            continue
        oi = OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=int(qty),
            unit_price=menu_item.price,
        )
        db.session.add(oi)

    db.session.flush()
    order.calc_total()
    db.session.commit()
    flash(f"Order #{order.id} created.", "success")
    return redirect(url_for("orders"))


@app.route("/orders/<int:order_id>/status", methods=["POST"])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = request.form["status"]
    db.session.commit()
    flash(f"Order #{order_id} marked as {order.status}.", "success")
    return redirect(url_for("orders"))


@app.route("/orders/<int:order_id>/delete", methods=["POST"])
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    flash(f"Order #{order_id} deleted.", "success")
    return redirect(url_for("orders"))


# ─── Purchases / Inventory ────────────────────────────────────────────────────

@app.route("/inventory")
def inventory():
    category_filter = request.args.get("category", "all")
    query = Purchase.query.order_by(Purchase.purchased_at.desc())
    if category_filter != "all":
        query = query.filter_by(category=category_filter)
    purchases = query.all()
    categories = sorted({p.category for p in Purchase.query.all()})
    return render_template(
        "inventory.html", purchases=purchases, categories=categories, category_filter=category_filter
    )


@app.route("/inventory/add", methods=["POST"])
def add_purchase():
    qty = float(request.form["quantity"])
    unit_cost = float(request.form["unit_cost"])
    purchase = Purchase(
        item_name=request.form["item_name"],
        category=request.form["category"],
        quantity=qty,
        unit=request.form["unit"],
        unit_cost=unit_cost,
        total_cost=qty * unit_cost,
        supplier=request.form.get("supplier", ""),
        notes=request.form.get("notes", ""),
    )
    db.session.add(purchase)
    db.session.commit()
    flash("Purchase recorded.", "success")
    return redirect(url_for("inventory"))


@app.route("/inventory/<int:purchase_id>/delete", methods=["POST"])
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    flash("Purchase deleted.", "success")
    return redirect(url_for("inventory"))


# ─── Reports ──────────────────────────────────────────────────────────────────

@app.route("/reports")
def reports():
    # Sales by day for the last 14 days
    days = []
    for i in range(13, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).date()
        sales = (
            db.session.query(db.func.sum(Order.total))
            .filter(db.func.date(Order.created_at) == d, Order.status == "completed")
            .scalar() or 0
        )
        spend = (
            db.session.query(db.func.sum(Purchase.total_cost))
            .filter(db.func.date(Purchase.purchased_at) == d)
            .scalar() or 0
        )
        days.append({"date": d.strftime("%b %d"), "sales": round(sales, 2), "spend": round(spend, 2)})

    # Top selling items
    top_items = (
        db.session.query(MenuItem.name, db.func.sum(OrderItem.quantity).label("sold"))
        .join(OrderItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status == "completed")
        .group_by(MenuItem.name)
        .order_by(db.desc("sold"))
        .limit(5)
        .all()
    )

    # Spend by category
    spend_by_cat = (
        db.session.query(Purchase.category, db.func.sum(Purchase.total_cost).label("total"))
        .group_by(Purchase.category)
        .all()
    )

    return render_template(
        "reports.html",
        days=days,
        top_items=top_items,
        spend_by_cat=spend_by_cat,
    )


if __name__ == "__main__":
    app.run(debug=True)
