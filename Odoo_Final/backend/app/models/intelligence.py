from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Priority, RecommendationType, RuleActionType, RuleType


class RecommendationRule(Base):
    __tablename__ = "recommendation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    recommended_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    recommendation_type: Mapped[RecommendationType] = mapped_column(Enum(RecommendationType), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    reason: Mapped[str] = mapped_column(String(400), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[int] = mapped_column(Integer, default=80)

    product = relationship("Product", foreign_keys=[product_id])
    recommended_product = relationship("Product", foreign_keys=[recommended_product_id])


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)

    conditions = relationship("RuleCondition", back_populates="rule", cascade="all, delete-orphan")
    actions = relationship("RuleAction", back_populates="rule", cascade="all, delete-orphan")


class RuleCondition(Base):
    __tablename__ = "rule_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rule_definitions.id"), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(80), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    logical_operator: Mapped[str] = mapped_column(String(8), default="AND")

    rule = relationship("RuleDefinition", back_populates="conditions")


class RuleAction(Base):
    __tablename__ = "rule_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rule_definitions.id"), nullable=False, index=True)
    action_type: Mapped[RuleActionType] = mapped_column(Enum(RuleActionType), nullable=False)
    action_value: Mapped[str] = mapped_column(String(255), nullable=False)

    rule = relationship("RuleDefinition", back_populates="actions")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
