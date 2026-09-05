"""Internal users and customer-portal users."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin, pg_enum


class User(Base, TimestampMixin):
    """A login identity.

    Internal staff (ADMIN / SALES_REP / SALES_MANAGER / FINANCE) have
    ``customer_id`` NULL. A portal user has role CUSTOMER and is bound to
    exactly one customer record, which is what every ownership check keys off.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="portal_users")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_role", "role"),
        Index("ix_users_customer_id", "customer_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
