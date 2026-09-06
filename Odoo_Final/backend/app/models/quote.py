from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ApprovalStatus, NegotiationStatus, QuoteStatus


class Quote(TimestampMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        Index("ix_quotes_status_sales_rep", "status", "sales_rep_id"),
        Index("ix_quotes_customer_status", "customer_id", "status"),
        Index("ix_quotes_approval_status", "approval_status"),
        Index("ix_quotes_health_score", "deal_health_score"),
        Index("ix_quotes_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    sales_rep_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[QuoteStatus] = mapped_column(Enum(QuoteStatus), default=QuoteStatus.DRAFT, index=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cost_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gross_margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0, index=True)
    deal_health_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=100)
    approval_status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.NOT_REQUIRED)
    negotiation_status: Mapped[NegotiationStatus] = mapped_column(Enum(NegotiationStatus), default=NegotiationStatus.NONE)
    payment_terms: Mapped[int] = mapped_column(Integer, default=30)
    notes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[date | None] = mapped_column(Date)
    promised_delivery_date: Mapped[date | None] = mapped_column(Date)
    sent_to_customer_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_material_change_at: Mapped[datetime | None] = mapped_column(DateTime)
    shipment_count: Mapped[int] = mapped_column(Integer, default=0)
    delivery_risk_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=18)
    title: Mapped[str | None] = mapped_column(String(180))

    customer = relationship("Customer", back_populates="quotes")
    sales_rep = relationship("User")
    lines = relationship("QuoteLine", back_populates="quote", cascade="all, delete-orphan")
    risk_factors = relationship("RiskFactor", back_populates="quote", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="quote")
    events = relationship("DealEvent", back_populates="quote")
    simulations = relationship("DealSimulation", back_populates="quote")
    allocations = relationship("FulfillmentAllocation", back_populates="quote")
    backorders = relationship("Backorder", back_populates="quote")
    negotiations = relationship("Negotiation", back_populates="quote")
    orders = relationship("Order", back_populates="quote")


class QuoteLine(Base):
    __tablename__ = "quote_lines"
    __table_args__ = (
        Index("ix_quote_lines_product_id", "product_id"),
        Index("ix_quote_lines_warehouse_id", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    delivery_date: Mapped[date | None] = mapped_column(Date)
    subscription_plan_id: Mapped[int | None] = mapped_column(ForeignKey("subscription_plans.id"))
    is_freebie: Mapped[bool] = mapped_column(Boolean, default=False)
    source_recommendation_id: Mapped[int | None] = mapped_column(Integer)

    quote = relationship("Quote", back_populates="lines")
    product = relationship("Product")
    variant = relationship("ProductVariant")
    warehouse = relationship("Warehouse")
    subscription_plan = relationship("SubscriptionPlan")


class RiskFactor(Base):
    __tablename__ = "risk_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    factor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=1)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    quote = relationship("Quote", back_populates="risk_factors")


class DealSimulation(Base):
    __tablename__ = "deal_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    revenue_delta: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    margin_delta: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    risk_delta: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    quote = relationship("Quote", back_populates="simulations")
    creator = relationship("User")
