"""Approval steps created by the automatic routing service."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ApprovalStatus, RiskLevel, UserRole
from app.models.mixins import TimestampMixin, pg_enum


class Approval(Base, TimestampMixin):
    """One step in a quotation's approval chain.

    Rows are created by FastAPI when the blended risk evaluation demands them -
    a sales rep never requests approval by hand. ``cycle`` increments each time
    the quote re-enters approval (for example after a customer counter-offer),
    so the full history of every round is preserved.
    """

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    approval_rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("approval_rules.id", ondelete="SET NULL"), nullable=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        pg_enum(ApprovalStatus, "approval_status"),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )

    acted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot of the evaluation that produced this step, for the audit trail.
    risk_score_snapshot: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False, default=0)
    risk_level_snapshot: Mapped[RiskLevel] = mapped_column(
        pg_enum(RiskLevel, "risk_level"), nullable=False, default=RiskLevel.NORMAL
    )

    quotation: Mapped["Quotation"] = relationship(back_populates="approvals")
    acted_by: Mapped[Optional["User"]] = relationship(foreign_keys=[acted_by_id])

    __table_args__ = (
        UniqueConstraint("quotation_id", "cycle", "step_order", name="uq_approval_step_per_cycle"),
        CheckConstraint("step_order >= 1", name="ck_approvals_step_order"),
        CheckConstraint("cycle >= 1", name="ck_approvals_cycle"),
        Index("ix_approvals_quotation_id", "quotation_id"),
        Index("ix_approvals_status", "status"),
        Index("ix_approvals_required_role", "required_role"),
    )
