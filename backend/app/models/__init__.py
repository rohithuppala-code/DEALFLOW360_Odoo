"""ORM model package.

Importing this package registers every table on ``Base.metadata``, which is
what Alembic autogenerate and the health check rely on.
"""

from app.models.alerts import DealAlert
from app.models.approval import Approval
from app.models.audit import AuditLog
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.customer import Customer
from app.models.fulfillment import Backorder, FulfillmentSplit
from app.models.negotiation import Negotiation, NegotiationComment
from app.models.pricing import PriceList, PriceListItem
from app.models.product import Product, ProductVariant
from app.models.quotation import Quotation, QuotationItem
from app.models.rules import (
    ApprovalRule,
    BusinessSetting,
    DiscountRule,
    RecommendationRule,
)
from app.models.subscription import BillingSchedule, Subscription, SubscriptionPlan
from app.models.user import User
from app.models.warehouse import Inventory, Warehouse

__all__ = [
    "Approval",
    "ApprovalRule",
    "AuditLog",
    "Backorder",
    "BillingSchedule",
    "BusinessSetting",
    "Customer",
    "DealAlert",
    "DiscountRule",
    "FulfillmentSplit",
    "Inventory",
    "Invoice",
    "InvoiceItem",
    "Negotiation",
    "NegotiationComment",
    "Payment",
    "PriceList",
    "PriceListItem",
    "Product",
    "ProductVariant",
    "Quotation",
    "QuotationItem",
    "RecommendationRule",
    "Subscription",
    "SubscriptionPlan",
    "User",
    "Warehouse",
]
