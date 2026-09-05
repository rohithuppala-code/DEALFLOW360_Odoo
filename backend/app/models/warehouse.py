"""Warehouses and per-warehouse stock."""

from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Warehouse(Base, TimestampMixin):
    """A stocking location.

    ``shipping_cost_weight`` is the relative cost the split engine uses when it
    decides which warehouses to draw from and how to keep shipment count down.
    """

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    shipping_cost_weight: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    inventory_records: Mapped[list["Inventory"]] = relationship(
        back_populates="warehouse", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("shipping_cost_weight >= 0", name="ck_warehouses_weight_non_negative"),
        Index("ix_warehouses_active", "is_active"),
    )


class Inventory(Base, TimestampMixin):
    """Stock of one product in one warehouse.

    ``available_quantity`` is physical stock and ``reserved_quantity`` is the
    part already committed to accepted fulfilment splits; free-to-allocate
    stock is the difference between the two.
    """

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    warehouse: Mapped["Warehouse"] = relationship(back_populates="inventory_records")
    product: Mapped["Product"] = relationship(back_populates="inventory_records")

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_inventory_warehouse_product"),
        CheckConstraint("available_quantity >= 0", name="ck_inventory_available_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_non_negative"),
        CheckConstraint(
            "reserved_quantity <= available_quantity",
            name="ck_inventory_reserved_within_available",
        ),
        Index("ix_inventory_product_id", "product_id"),
    )
