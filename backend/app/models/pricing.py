"""Price lists used by the backend pricing service."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import CustomerTier
from app.models.mixins import TimestampMixin, pg_enum


class PriceList(Base, TimestampMixin):
    """A named set of prices.

    A list may target a customer tier, a single customer, or neither (a global
    fallback). ``priority`` breaks ties when several lists match: the pricing
    service resolves the most specific, highest-priority, currently-effective
    list for a given customer and product.
    """

    __tablename__ = "price_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    customer_tier: Mapped[Optional[CustomerTier]] = mapped_column(
        pg_enum(CustomerTier, "customer_tier"), nullable=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True
    )
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["PriceListItem"]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_price_lists_tier", "customer_tier"),
        Index("ix_price_lists_customer_id", "customer_id"),
        Index("ix_price_lists_active", "is_active"),
    )


class PriceListItem(Base, TimestampMixin):
    """One product price inside a price list, optionally quantity-banded."""

    __tablename__ = "price_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    price_list_id: Mapped[int] = mapped_column(
        ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    product_variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    price_list: Mapped["PriceList"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="price_list_items")

    __table_args__ = (
        UniqueConstraint(
            "price_list_id",
            "product_id",
            "product_variant_id",
            "min_quantity",
            name="uq_price_list_item_scope",
        ),
        CheckConstraint("unit_price >= 0", name="ck_price_list_items_price_non_negative"),
        CheckConstraint("min_quantity >= 1", name="ck_price_list_items_min_quantity"),
        Index("ix_price_list_items_product_id", "product_id"),
    )
