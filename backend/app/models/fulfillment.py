"""Multi-warehouse fulfilment allocations and backorders."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import BackorderStatus, FulfillmentStatus
from app.models.mixins import TimestampMixin, pg_enum


class FulfillmentSplit(Base, TimestampMixin):
    """A quantity of one line allocated to one warehouse.

    ``is_manual_override`` records that a user replaced the engine's suggested
    split; the override is still validated against live stock before it is saved.
    """

    __tablename__ = "fulfillment_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    quotation_item_id: Mapped[int] = mapped_column(
        ForeignKey("quotation_items.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_shipping_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    status: Mapped[FulfillmentStatus] = mapped_column(
        pg_enum(FulfillmentStatus, "fulfillment_status"),
        nullable=False,
        default=FulfillmentStatus.PLANNED,
    )
    is_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    promised_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    quotation: Mapped["Quotation"] = relationship(back_populates="fulfillment_splits")
    quotation_item: Mapped["QuotationItem"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship()
    product: Mapped["Product"] = relationship()

    __table_args__ = (
        CheckConstraint("allocated_quantity >= 1", name="ck_fulfillment_splits_quantity"),
        Index("ix_fulfillment_splits_quotation_id", "quotation_id"),
        Index("ix_fulfillment_splits_warehouse_id", "warehouse_id"),
        Index("ix_fulfillment_splits_status", "status"),
    )


class Backorder(Base, TimestampMixin):
    """Quantity that could not be allocated from any warehouse."""

    __tablename__ = "backorders"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    quotation_item_id: Mapped[int] = mapped_column(
        ForeignKey("quotation_items.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[BackorderStatus] = mapped_column(
        pg_enum(BackorderStatus, "backorder_status"),
        nullable=False,
        default=BackorderStatus.OPEN,
    )
    expected_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    quotation: Mapped["Quotation"] = relationship(back_populates="backorders")
    quotation_item: Mapped["QuotationItem"] = relationship()
    product: Mapped["Product"] = relationship()

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_backorders_quantity"),
        CheckConstraint(
            "allocated_quantity >= 0 AND allocated_quantity <= quantity",
            name="ck_backorders_allocated_within_quantity",
        ),
        Index("ix_backorders_quotation_id", "quotation_id"),
        Index("ix_backorders_status", "status"),
    )
