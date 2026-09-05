"""Invoices, invoice lines and payments."""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import BillingType, InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.mixins import TimestampMixin, pg_enum


class Invoice(Base, TimestampMixin):
    """A billing document.

    ``paid_amount`` and ``balance_due`` are recalculated from the payment rows
    whenever a payment is recorded, inside the same transaction, so the status
    can never drift from the money actually received.
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    quotation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        pg_enum(InvoiceStatus, "invoice_status"), nullable=False, default=InvoiceStatus.DRAFT
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="invoices")
    quotation: Mapped[Optional["Quotation"]] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    billing_schedules: Mapped[list["BillingSchedule"]] = relationship(back_populates="invoice")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_invoices_total_non_negative"),
        CheckConstraint("paid_amount >= 0", name="ck_invoices_paid_non_negative"),
        Index("ix_invoices_invoice_number", "invoice_number", unique=True),
        Index("ix_invoices_customer_id", "customer_id"),
        Index("ix_invoices_quotation_id", "quotation_id"),
        Index("ix_invoices_status", "status"),
    )


class InvoiceItem(Base, TimestampMixin):
    """One billed line - either a one-time product or a recurring charge."""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    quotation_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotation_items.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    billing_schedule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("billing_schedules.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_type: Mapped[BillingType] = mapped_column(
        pg_enum(BillingType, "billing_type"), nullable=False, default=BillingType.ONE_TIME
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_invoice_items_quantity"),
        Index("ix_invoice_items_invoice_id", "invoice_id"),
    )


class Payment(Base, TimestampMixin):
    """Money received against an invoice."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        pg_enum(PaymentMethod, "payment_method"), nullable=False
    )
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), nullable=False, default=PaymentStatus.COMPLETED
    )
    recorded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
    recorded_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_payment_date", "payment_date"),
    )
