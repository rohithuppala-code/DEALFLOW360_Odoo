"""Customer master data."""

from typing import Optional

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import CustomerTier
from app.models.mixins import TimestampMixin, pg_enum


class Customer(Base, TimestampMixin):
    """A buying organisation.

    ``customer_tier`` is assigned by an Admin and is one of the two inputs to
    the discount ceiling lookup (the other being the product category).
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_tier: Mapped[CustomerTier] = mapped_column(
        pg_enum(CustomerTier, "customer_tier"), nullable=False, default=CustomerTier.BRONZE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    portal_users: Mapped[list["User"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    quotations: Mapped[list["Quotation"]] = relationship(back_populates="customer")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="customer")

    __table_args__ = (
        Index("ix_customers_email", "email", unique=True),
        Index("ix_customers_tier", "customer_tier"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Customer id={self.id} name={self.name!r} tier={self.customer_tier}>"
