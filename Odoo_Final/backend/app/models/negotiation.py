from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import NegotiationRequestType, NegotiationStatus, RequestStatus


class Negotiation(TimestampMixin, Base):
    __tablename__ = "negotiations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    status: Mapped[NegotiationStatus] = mapped_column(Enum(NegotiationStatus), default=NegotiationStatus.OPEN, index=True)
    last_counteroffer_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)

    quote = relationship("Quote", back_populates="negotiations")
    customer = relationship("Customer")
    requests = relationship("NegotiationRequest", back_populates="negotiation", cascade="all, delete-orphan")


class NegotiationRequest(Base):
    __tablename__ = "negotiation_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    negotiation_id: Mapped[int] = mapped_column(ForeignKey("negotiations.id"), nullable=False, index=True)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("quote_lines.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True, index=True)
    request_type: Mapped[NegotiationRequestType] = mapped_column(Enum(NegotiationRequestType), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(255))
    requested_value: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.PENDING)
    margin_impact: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    risk_impact: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    exception_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    counteroffer_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    negotiation = relationship("Negotiation", back_populates="requests")
    line = relationship("QuoteLine")
    category = relationship("ProductCategory")
