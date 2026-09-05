"""Recurring plans, live subscriptions and their billing schedules."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (
    BillingFrequency,
    BillingScheduleStatus,
    CancellationRule,
    RefundRule,
    SubscriptionStatus,
)
from app.models.mixins import TimestampMixin, pg_enum


class SubscriptionPlan(Base, TimestampMixin):
    """Admin-configured recurring plan attached to recurring products."""

    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    billing_frequency: Mapped[BillingFrequency] = mapped_column(
        pg_enum(BillingFrequency, "billing_frequency"), nullable=False
    )
    billing_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proration_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cancellation_rule: Mapped[CancellationRule] = mapped_column(
        pg_enum(CancellationRule, "cancellation_rule"),
        nullable=False,
        default=CancellationRule.END_OF_PERIOD,
    )
    refund_rule: Mapped[RefundRule] = mapped_column(
        pg_enum(RefundRule, "refund_rule"), nullable=False, default=RefundRule.PRORATED
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")
    products: Mapped[list["Product"]] = relationship(back_populates="default_subscription_plan")

    __table_args__ = (
        CheckConstraint("billing_interval >= 1", name="ck_subscription_plans_interval"),
        Index("ix_subscription_plans_active", "is_active"),
    )


class Subscription(Base, TimestampMixin):
    """A recurring quotation line that became a live commitment."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    quotation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True
    )
    quotation_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotation_items.id", ondelete="SET NULL"), nullable=True
    )
    subscription_plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        pg_enum(SubscriptionStatus, "subscription_status"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")
    quotation: Mapped[Optional["Quotation"]] = relationship(back_populates="subscriptions")
    billing_schedules: Mapped[list["BillingSchedule"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_subscriptions_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_subscriptions_unit_price"),
        Index("ix_subscriptions_customer_id", "customer_id"),
        Index("ix_subscriptions_status", "status"),
    )


class BillingSchedule(Base, TimestampMixin):
    """One future or past charge generated for a subscription."""

    __tablename__ = "billing_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    billing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_proration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[BillingScheduleStatus] = mapped_column(
        pg_enum(BillingScheduleStatus, "billing_schedule_status"),
        nullable=False,
        default=BillingScheduleStatus.SCHEDULED,
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="billing_schedules")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="billing_schedules")

    __table_args__ = (
        Index("ix_billing_schedules_subscription_id", "subscription_id"),
        Index("ix_billing_schedules_billing_date", "billing_date"),
        Index("ix_billing_schedules_status", "status"),
    )
