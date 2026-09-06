from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, ser_json_bytes="utf8")


class LoginIn(BaseModel):
    email: str
    password: str


class SignupIn(BaseModel):
    name: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=6)
    role: str
    company: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class IdIn(BaseModel):
    id: int


class PageQuery(BaseModel):
    page: int = 1
    page_size: int = 20


class QuoteLineIn(BaseModel):
    id: int | None = None
    product_id: int
    variant_id: int | None = None
    quantity: int = Field(ge=1)
    discount_percent: float = Field(default=0, ge=0, le=100)
    unit_price: float | None = None
    warehouse_id: int | None = None
    delivery_date: str | None = None
    subscription_plan_id: int | None = None
    description: str | None = None
    is_freebie: bool = False
    source_recommendation_id: int | None = None


class QuoteCreateIn(BaseModel):
    customer_id: int
    title: str | None = None
    notes: str | None = None
    payment_terms: int | None = None
    lines: list[QuoteLineIn] = []
    quote_number: str | None = None
    sales_rep_id: int | None = None
    order_discount_percent: float = Field(default=0, ge=0, le=100)


class QuoteUpdateIn(BaseModel):
    title: str | None = None
    notes: str | None = None
    payment_terms: int | None = None
    expires_at: str | None = None
    promised_delivery_date: str | None = None
    lines: list[QuoteLineIn] | None = None
    order_discount_percent: float | None = Field(default=None, ge=0, le=100)


class DiscountPatchIn(BaseModel):
    discount_percent: float = Field(ge=0, le=100)


class QuoteLinePatchIn(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    discount_percent: float | None = Field(default=None, ge=0, le=100)


class CommentIn(BaseModel):
    comment: str | None = None


class CategoryDiscountIn(BaseModel):
    category_id: int | None = None
    category: str | None = None
    requested_percent: float = Field(ge=0, le=100)


class NegotiationIn(BaseModel):
    request_type: str
    line_id: int | None = None
    requested_value: str | None = None
    old_value: str | None = None
    reason: str | None = None
    category_discounts: list[CategoryDiscountIn] | None = None


class SimulateIn(BaseModel):
    name: str | None = None
    line_discounts: dict[str, float] | None = None
    line_quantities: dict[str, int] | None = None
    add_product_ids: list[int] | None = None
    consolidate_warehouse: bool = False
    payment_terms: int | None = None
    add_premium_support: bool = False


class PaymentIn(BaseModel):
    amount: float
    payment_method: str = "BANK_TRANSFER"


class CustomerIn(BaseModel):
    name: str
    code: str
    email: str
    phone: str | None = None
    industry: str | None = None
    customer_tier_id: int
    credit_limit: float = 0
    payment_terms: int = 30
    city: str | None = None
    status: str | None = None
    sales_rep_id: int | None = None


class UserIn(BaseModel):
    name: str
    email: str
    password: str | None = None
    role: str
    is_active: bool = True
    customer_id: int | None = None


class DiscountRuleIn(BaseModel):
    name: str
    customer_tier_id: int | None = None
    category_id: int | None = None
    product_id: int | None = None
    max_discount_percent: float
    severity: str = "MEDIUM"
    requires_approval: bool = True
    is_active: bool = True


class RuleDefIn(BaseModel):
    name: str
    description: str | None = None
    rule_type: str
    is_active: bool = True
    priority: int = 100
    conditions: list[dict] = []
    actions: list[dict] = []


class ProrationIn(BaseModel):
    old_price: float
    new_price: float
    remaining_days: int
    period_days: int = 30


class FulfillmentAllocIn(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int = Field(ge=1)


class FulfillmentManualIn(BaseModel):
    allocations: list[FulfillmentAllocIn]


class SubscriptionChangeIn(BaseModel):
    plan_id: int | None = None
    quantity: int | None = Field(default=None, ge=1)
    remaining_days: int | None = None
    reason: str | None = None


class SubscriptionCancelIn(BaseModel):
    remaining_days: int | None = None
    reason: str | None = None


class ProductIn(BaseModel):
    sku: str
    name: str
    description: str | None = None
    category_id: int
    product_type: str
    base_price: float
    cost_price: float
    weight: float = 0
    is_active: bool = True
    subscription_plan_id: int | None = None
    perceived_value: float = 0


class CategoryIn(BaseModel):
    name: str
    kind: str = "HARDWARE"
    description: str | None = None


class VariantIn(BaseModel):
    sku: str
    name: str
    price_adjustment: float = 0
    cost_adjustment: float = 0
    is_active: bool = True
    attributes_json: dict | None = None


class TierIn(BaseModel):
    name: str
    description: str | None = None
    default_discount_limit: float
    risk_multiplier: float = 1


class WarehouseIn(BaseModel):
    name: str
    code: str
    city: str
    address: str | None = None
    shipping_zone: str = "WEST"
    handling_cost: float = 150
    reliability_score: float = 90
    avg_lead_days: int = 3


class InventoryIn(BaseModel):
    warehouse_id: int
    product_id: int
    available_qty: int = 0
    reserved_qty: int = 0
    reorder_level: int = 5
    expected_replenishment: str | None = None


class PriceListIn(BaseModel):
    name: str
    currency: str = "INR"
    customer_tier_id: int | None = None
    is_active: bool = True


class PriceListItemIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    unit_price: float
    min_quantity: int = 1
    max_quantity: int | None = None


class ApprovalRuleWriteIn(BaseModel):
    condition_type: str
    condition_value: str
    required_role: str
    sequence: int = 1


class RecRuleIn(BaseModel):
    product_id: int
    recommended_product_id: int
    recommendation_type: str
    reason: str
    priority: int = 50
    confidence: int = 80
    is_active: bool = True


class PlanIn(BaseModel):
    name: str
    description: str | None = None
    billing_interval: str
    price: float
    setup_fee: float = 0
    trial_days: int = 0
    cost: float = 0
