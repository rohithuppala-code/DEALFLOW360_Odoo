"""Quotations and their line items - the centre of the deal lifecycle."""

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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import BillingType, QuotationStatus, RiskLevel
from app.models.mixins import TimestampMixin, pg_enum


class Quotation(Base, TimestampMixin):
    """A deal document.

    Every monetary column here is written by the FastAPI pricing service after
    it recalculates from the persisted line items - totals arriving from the
    React client are never trusted or stored directly.
    """

    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    sales_rep_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[QuotationStatus] = mapped_column(
        pg_enum(QuotationStatus, "quotation_status"),
        nullable=False,
        default=QuotationStatus.DRAFT,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    # Totals, all recomputed server-side.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    cost_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    margin_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 3), nullable=False, default=0)
    recurring_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    one_time_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    # Order-level discount applied on top of line discounts.
    order_discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)

    # Output of the discount governance / blended risk engine.
    risk_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False, default=0)
    risk_level: Mapped[RiskLevel] = mapped_column(
        pg_enum(RiskLevel, "risk_level"), nullable=False, default=RiskLevel.NORMAL
    )
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Lifecycle timestamps; last_activity_at drives stalled-deal detection.
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    customer: Mapped["Customer"] = relationship(back_populates="quotations")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    sales_rep: Mapped["User"] = relationship(foreign_keys=[sales_rep_id])
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationItem.position",
    )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )
    fulfillment_splits: Mapped[list["FulfillmentSplit"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )
    backorders: Mapped[list["Backorder"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )
    negotiations: Mapped[list["Negotiation"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="quotation")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="quotation")
    alerts: Mapped[list["DealAlert"]] = relationship(back_populates="quotation")

    __table_args__ = (
        CheckConstraint(
            "order_discount_percent >= 0 AND order_discount_percent <= 100",
            name="ck_quotations_order_discount_range",
        ),
        CheckConstraint("risk_score >= 0", name="ck_quotations_risk_score_non_negative"),
        Index("ix_quotations_quote_number", "quote_number", unique=True),
        Index("ix_quotations_customer_id", "customer_id"),
        Index("ix_quotations_sales_rep_id", "sales_rep_id"),
        Index("ix_quotations_status", "status"),
        Index("ix_quotations_last_activity_at", "last_activity_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Quotation id={self.id} number={self.quote_number!r} status={self.status}>"


class QuotationItem(Base, TimestampMixin):
    """One priced line on a quotation.

    Both the requested discount and the ceiling the engine resolved for this
    specific line are stored, so the approval screen can explain *why* a line
    was flagged without recomputing history.
    """

    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    product_variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    subscription_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    product_category: Mapped[str] = mapped_column(String(80), nullable=False)
    billing_type: Mapped[BillingType] = mapped_column(
        pg_enum(BillingType, "billing_type"), nullable=False, default=BillingType.ONE_TIME
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)

    requested_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, default=0
    )
    allowed_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, default=0
    )
    excess_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, default=0
    )

    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_cost_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_margin_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 3), nullable=False, default=0)

    added_from_recommendation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    quotation: Mapped["Quotation"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
    variant: Mapped[Optional["ProductVariant"]] = relationship()

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_quotation_items_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_quotation_items_unit_price"),
        CheckConstraint(
            "requested_discount_percent >= 0 AND requested_discount_percent <= 100",
            name="ck_quotation_items_requested_discount_range",
        ),
        Index("ix_quotation_items_quotation_id", "quotation_id"),
        Index("ix_quotation_items_product_id", "product_id"),
    )
