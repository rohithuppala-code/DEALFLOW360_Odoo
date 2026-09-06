from decimal import Decimal

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import CategoryKind, ProductType


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    kind: Mapped[CategoryKind] = mapped_column(Enum(CategoryKind), default=CategoryKind.HARDWARE)

    products = relationship("Product", back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("product_categories.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    product_type: Mapped[ProductType] = mapped_column(Enum(ProductType), nullable=False, index=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    subscription_plan_id: Mapped[int | None] = mapped_column(ForeignKey("subscription_plans.id"))
    perceived_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    category = relationship("ProductCategory", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    subscription_plan = relationship("SubscriptionPlan")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    attributes_json: Mapped[dict | None] = mapped_column(JSON)
    price_adjustment: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cost_adjustment: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product = relationship("Product", back_populates="variants")


class PriceList(Base):
    __tablename__ = "price_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    customer_tier_id: Mapped[int | None] = mapped_column(ForeignKey("customer_tiers.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    items = relationship("PriceListItem", back_populates="price_list", cascade="all, delete-orphan")
    tier = relationship("CustomerTier")


class PriceListItem(Base):
    __tablename__ = "price_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_list_id: Mapped[int] = mapped_column(ForeignKey("price_lists.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    max_quantity: Mapped[int | None] = mapped_column(Integer)

    price_list = relationship("PriceList", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")
