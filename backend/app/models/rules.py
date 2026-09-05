"""Admin-configurable business rules.

Nothing in this module encodes a threshold in Python: the ceilings, the
approval routing bands and the recommendation pairings are all rows that an
Admin edits at runtime, and the services read them fresh on every evaluation.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import CustomerTier, DiscountRuleScope, RecommendationType, UserRole
from app.models.mixins import TimestampMixin, pg_enum


class DiscountRule(Base, TimestampMixin):
    """A discount ceiling for either a customer tier or a product category.

    The discount engine takes the *stricter* of the two applicable ceilings for
    each quotation line, so a Gold customer still cannot exceed a thin-margin
    Service category limit.
    """

    __tablename__ = "discount_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[DiscountRuleScope] = mapped_column(
        pg_enum(DiscountRuleScope, "discount_rule_scope"), nullable=False
    )
    customer_tier: Mapped[Optional[CustomerTier]] = mapped_column(
        pg_enum(CustomerTier, "customer_tier"), nullable=True
    )
    product_category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    max_discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "max_discount_percent >= 0 AND max_discount_percent <= 100",
            name="ck_discount_rules_percent_range",
        ),
        CheckConstraint(
            "(scope = 'CUSTOMER_TIER' AND customer_tier IS NOT NULL AND product_category IS NULL)"
            " OR (scope = 'PRODUCT_CATEGORY' AND product_category IS NOT NULL AND customer_tier IS NULL)",
            name="ck_discount_rules_scope_target",
        ),
        UniqueConstraint("scope", "customer_tier", "product_category", name="uq_discount_rule_target"),
        Index("ix_discount_rules_active", "is_active"),
    )


class ApprovalRule(Base, TimestampMixin):
    """One step of the approval chain, selected by blended risk score band.

    Several rules may match the same score; the routing service orders them by
    ``approval_order`` to build a multi-level chain (e.g. Manager then Finance).
    """

    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    min_risk_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    max_risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    required_role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    approval_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("min_risk_score >= 0", name="ck_approval_rules_min_score"),
        CheckConstraint(
            "max_risk_score IS NULL OR max_risk_score >= min_risk_score",
            name="ck_approval_rules_score_band",
        ),
        CheckConstraint("approval_order >= 1", name="ck_approval_rules_order"),
        UniqueConstraint("min_risk_score", "required_role", "approval_order", name="uq_approval_rule_step"),
        Index("ix_approval_rules_active", "is_active"),
    )


class RecommendationRule(Base, TimestampMixin):
    """An admin-defined upsell / cross-sell pairing."""

    __tablename__ = "recommendation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    recommended_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    recommendation_type: Mapped[RecommendationType] = mapped_column(
        pg_enum(RecommendationType, "recommendation_type"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promotion_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_margin_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    source_product: Mapped["Product"] = relationship(foreign_keys=[source_product_id])
    recommended_product: Mapped["Product"] = relationship(foreign_keys=[recommended_product_id])

    __table_args__ = (
        CheckConstraint(
            "source_product_id <> recommended_product_id", name="ck_recommendation_distinct_products"
        ),
        UniqueConstraint(
            "source_product_id",
            "recommended_product_id",
            "recommendation_type",
            name="uq_recommendation_pair",
        ),
        Index("ix_recommendation_rules_source", "source_product_id"),
    )


class BusinessSetting(Base, TimestampMixin):
    """Key/value store for the remaining tunable thresholds.

    Used for values that are single numbers rather than rule rows - the risk
    band cut-offs, the stalled-deal day count, the discount-anomaly multiplier.
    Keeping them here means changing behaviour never means changing code.
    """

    __tablename__ = "business_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_business_settings_key", "key", unique=True),)
