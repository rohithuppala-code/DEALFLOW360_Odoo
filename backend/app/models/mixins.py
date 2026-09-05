"""Reusable column mixins and enum helper."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column


def pg_enum(enum_cls: type[PyEnum], name: str) -> SAEnum:
    """Build a native PostgreSQL enum type that stores the member *values*."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda e: [member.value for member in e],
    )


class TimestampMixin:
    """created_at / updated_at maintained by the database server clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
