from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import OrderStatus


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)

    quote = relationship("Quote", back_populates="orders")
    customer = relationship("Customer")
    invoices = relationship("Invoice", back_populates="order")
