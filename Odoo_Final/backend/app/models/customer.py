from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import CustomerStatus


class CustomerTier(Base):
    __tablename__ = "customer_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    default_discount_limit: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    risk_multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=1)

    customers = relationship("Customer", back_populates="tier")


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_status", "status"),
        Index("ix_customers_name", "name"),
        Index("ix_customers_sales_rep_id", "sales_rep_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(180), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    industry: Mapped[str | None] = mapped_column(String(80))
    customer_tier_id: Mapped[int] = mapped_column(ForeignKey("customer_tiers.id"), nullable=False, index=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    payment_terms: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE)
    city: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    sales_rep_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", use_alter=True, name="fk_customers_sales_rep_id_users")
    )
    avg_accept_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=2)
    historical_avg_discount: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=8)

    tier = relationship("CustomerTier", back_populates="customers")
    sales_rep = relationship("User", foreign_keys=[sales_rep_id])
    portal_users = relationship("User", back_populates="customer", foreign_keys="User.customer_id")
    quotes = relationship("Quote", back_populates="customer")
