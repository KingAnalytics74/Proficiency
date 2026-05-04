from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    quantity_in_stock = Column(Float, default=0.0)
    unit = Column(String(20), nullable=False)
    low_stock_threshold = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    menu_links = relationship("MenuItemIngredient", back_populates="ingredient", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="ingredient")

    @property
    def is_low(self):
        return self.low_stock_threshold > 0 and self.quantity_in_stock <= self.low_stock_threshold


class MenuItemIngredient(Base):
    """How much of an ingredient is consumed per serving of a dish."""
    __tablename__ = "menu_item_ingredients"
    id = Column(Integer, primary_key=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    quantity_per_serving = Column(Float, nullable=False)

    menu_item = relationship("MenuItem", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="menu_links")


class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(300), default="")
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order_items = relationship("OrderItem", back_populates="menu_item")
    ingredients = relationship("MenuItemIngredient", back_populates="menu_item", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_name = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")  # pending | completed | cancelled
    total = Column(Float, default=0.0)
    notes = Column(String(300), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def calc_total(self):
        self.total = sum(i.quantity * i.unit_price for i in self.items)


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")


class Purchase(Base):
    """Market purchase — optionally linked to an ingredient to restock it."""
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    item_name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    supplier = Column(String(100), default="")
    notes = Column(String(300), default="")
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=True)
    purchased_at = Column(DateTime, default=datetime.utcnow)

    ingredient = relationship("Ingredient", back_populates="purchases")
