"""Product catalogue and variants."""

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ProductType
from app.models.mixins import TimestampMixin, pg_enum


class Product(Base, TimestampMixin):
    """A sellable item.

    ``cost_price`` is stored alongside ``price`` because every margin figure
    shown in the quotation builder is derived from the two, server-side.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="unit")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_type: Mapped[ProductType] = mapped_column(
        pg_enum(ProductType, "product_type"), nullable=False, default=ProductType.ONE_TIME
    )
    default_subscription_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    inventory_records: Mapped[list["Inventory"]] = relationship(back_populates="product")
    price_list_items: Mapped[list["PriceListItem"]] = relationship(back_populates="product")
    default_subscription_plan: Mapped[Optional["SubscriptionPlan"]] = relationship(
        back_populates="products"
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint("cost_price >= 0", name="ck_products_cost_non_negative"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_products_tax_rate_range"),
        Index("ix_products_category", "category"),
        Index("ix_products_active", "is_active"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Product id={self.id} sku={self.sku!r} category={self.category!r}>"


class ProductVariant(Base, TimestampMixin):
    """An attribute/value pair on a product that carries an extra price."""

    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    attribute: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[str] = mapped_column(String(80), nullable=False)
    extra_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sku: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped["Product"] = relationship(back_populates="variants")

    __table_args__ = (
        UniqueConstraint("product_id", "attribute", "value", name="uq_variant_product_attr_value"),
        Index("ix_product_variants_product_id", "product_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProductVariant id={self.id} {self.attribute}={self.value!r}>"
