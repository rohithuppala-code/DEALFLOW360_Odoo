"""Deal health and anomaly alerts."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.models.mixins import TimestampMixin, pg_enum


class DealAlert(Base, TimestampMixin):
    """A stalled deal, discount anomaly or delivery slippage flag.

    ``details`` carries the numbers behind the flag - for a discount anomaly,
    the current discount, the rep's historical average and the difference - so
    the dashboard can explain the alert rather than just assert it.
    """

    __tablename__ = "deal_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[AlertType] = mapped_column(pg_enum(AlertType, "alert_type"), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        pg_enum(AlertSeverity, "alert_severity"), nullable=False, default=AlertSeverity.MEDIUM
    )
    status: Mapped[AlertStatus] = mapped_column(
        pg_enum(AlertStatus, "alert_status"), nullable=False, default=AlertStatus.OPEN
    )

    quotation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True
    )
    sales_rep_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    quotation: Mapped[Optional["Quotation"]] = relationship(back_populates="alerts")
    sales_rep: Mapped[Optional["User"]] = relationship(foreign_keys=[sales_rep_id])
    acknowledged_by: Mapped[Optional["User"]] = relationship(foreign_keys=[acknowledged_by_id])

    __table_args__ = (
        Index("ix_deal_alerts_type", "alert_type"),
        Index("ix_deal_alerts_status", "status"),
        Index("ix_deal_alerts_quotation_id", "quotation_id"),
    )
