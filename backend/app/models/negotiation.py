"""Customer-portal negotiation requests and their comment threads."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import NegotiationStatus, NegotiationType
from app.models.mixins import TimestampMixin, pg_enum


class Negotiation(Base, TimestampMixin):
    """A change request raised by a customer against a live quotation.

    A COUNTER_DISCOUNT carries ``requested_discount_percent``, which is fed
    back through the same discount governance service used at quote creation;
    ``triggered_reapproval`` records whether that evaluation forced a new
    approval round.
    """

    __tablename__ = "negotiations"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    quotation_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotation_items.id", ondelete="CASCADE"), nullable=True
    )
    raised_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    negotiation_type: Mapped[NegotiationType] = mapped_column(
        pg_enum(NegotiationType, "negotiation_type"), nullable=False
    )
    status: Mapped[NegotiationStatus] = mapped_column(
        pg_enum(NegotiationStatus, "negotiation_status"),
        nullable=False,
        default=NegotiationStatus.OPEN,
    )
    requested_discount_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_reapproval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    quotation: Mapped["Quotation"] = relationship(back_populates="negotiations")
    raised_by: Mapped["User"] = relationship(foreign_keys=[raised_by_id])
    resolved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[resolved_by_id])
    comments: Mapped[list["NegotiationComment"]] = relationship(
        back_populates="negotiation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "requested_discount_percent IS NULL"
            " OR (requested_discount_percent >= 0 AND requested_discount_percent <= 100)",
            name="ck_negotiations_discount_range",
        ),
        Index("ix_negotiations_quotation_id", "quotation_id"),
        Index("ix_negotiations_customer_id", "customer_id"),
        Index("ix_negotiations_status", "status"),
    )


class NegotiationComment(Base, TimestampMixin):
    """A message on a negotiation thread.

    ``is_internal`` marks notes that must never be serialised to the customer
    portal, keeping internal risk discussion out of the customer's view.
    """

    __tablename__ = "negotiation_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    negotiation_id: Mapped[int] = mapped_column(
        ForeignKey("negotiations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    negotiation: Mapped["Negotiation"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_negotiation_comments_negotiation_id", "negotiation_id"),
    )
