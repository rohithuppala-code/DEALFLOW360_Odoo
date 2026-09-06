from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ApprovalStatus, ApprovalStepStatus, ConditionType, Severity, UserRole


class DiscountRule(Base):
    __tablename__ = "discount_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_tier_id: Mapped[int | None] = mapped_column(ForeignKey("customer_tiers.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    max_discount_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.MEDIUM)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tier = relationship("CustomerTier")
    category = relationship("ProductCategory")
    product = relationship("Product")


class ApprovalChain(Base):
    __tablename__ = "approval_chains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules = relationship("ApprovalRule", back_populates="chain", cascade="all, delete-orphan")


class ApprovalRule(Base):
    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_chain_id: Mapped[int] = mapped_column(ForeignKey("approval_chains.id"), nullable=False, index=True)
    condition_type: Mapped[ConditionType] = mapped_column(Enum(ConditionType), nullable=False)
    condition_value: Mapped[str] = mapped_column(String(80), nullable=False)
    required_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1)

    chain = relationship("ApprovalChain", back_populates="rules")


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), nullable=False, index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    reason: Mapped[str | None] = mapped_column(Text)
    is_reapproval: Mapped[bool] = mapped_column(Boolean, default=False)

    quote = relationship("Quote", back_populates="approval_requests")
    requester = relationship("User", foreign_keys=[requested_by])
    steps = relationship("ApprovalStep", back_populates="request", cascade="all, delete-orphan")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    __table_args__ = (Index("ix_approval_steps_status_role", "status", "role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_request_id: Mapped[int] = mapped_column(ForeignKey("approval_requests.id"), nullable=False, index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ApprovalStepStatus] = mapped_column(Enum(ApprovalStepStatus), default=ApprovalStepStatus.PENDING)
    comment: Mapped[str | None] = mapped_column(Text)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime)

    request = relationship("ApprovalRequest", back_populates="steps")
    approver = relationship("User")
