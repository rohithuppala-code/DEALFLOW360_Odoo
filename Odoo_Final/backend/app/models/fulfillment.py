from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReservationStatus


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    shipping_zone: Mapped[str] = mapped_column(String(40), default="WEST")
    handling_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=150)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=90)
    avg_lead_days: Mapped[int] = mapped_column(Integer, default=3)

    inventory = relationship("Inventory", back_populates="warehouse")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("warehouse_id", "product_id", "variant_id", name="uq_inventory_wh_prod_var"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    available_qty: Mapped[int] = mapped_column(Integer, default=0)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)
    expected_replenishment: Mapped[date | None] = mapped_column(Date)

    warehouse = relationship("Warehouse", back_populates="inventory")
    product = relationship("Product")
    variant = relationship("ProductVariant")


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus), default=ReservationStatus.RESERVED)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    warehouse = relationship("Warehouse")
    product = relationship("Product")


class FulfillmentAllocation(Base):
    __tablename__ = "fulfillment_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    quote_line_id: Mapped[int | None] = mapped_column(ForeignKey("quote_lines.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    delivery_days: Mapped[int] = mapped_column(Integer, default=3)
    is_backorder: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)

    quote = relationship("Quote", back_populates="allocations")
    warehouse = relationship("Warehouse")
    product = relationship("Product")
    line = relationship("QuoteLine")


class Backorder(Base):
    __tablename__ = "backorders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    quote_line_id: Mapped[int | None] = mapped_column(ForeignKey("quote_lines.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    requested_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    available_qty: Mapped[int] = mapped_column(Integer, default=0)
    backorder_qty: Mapped[int] = mapped_column(Integer, default=0)
    expected_replenishment: Mapped[date | None] = mapped_column(Date)
    substitute_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    alternative_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))

    quote = relationship("Quote", back_populates="backorders")
    product = relationship("Product", foreign_keys=[product_id])
