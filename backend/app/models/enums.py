"""Enumerations shared by the ORM models.

These describe *states and shapes* the application understands. They are not
business configuration: every configurable threshold (discount ceilings,
approval routing, stalled-deal windows) lives in PostgreSQL tables instead.
"""

import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SALES_REP = "SALES_REP"
    SALES_MANAGER = "SALES_MANAGER"
    FINANCE = "FINANCE"
    CUSTOMER = "CUSTOMER"


class CustomerTier(str, enum.Enum):
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"


class ProductType(str, enum.Enum):
    ONE_TIME = "ONE_TIME"
    RECURRING = "RECURRING"
    SERVICE = "SERVICE"


class BillingType(str, enum.Enum):
    """How a single order/quotation line is billed."""

    ONE_TIME = "ONE_TIME"
    RECURRING = "RECURRING"


class DiscountRuleScope(str, enum.Enum):
    """A discount ceiling applies either to a customer tier or a product category."""

    CUSTOMER_TIER = "CUSTOMER_TIER"
    PRODUCT_CATEGORY = "PRODUCT_CATEGORY"


class RiskLevel(str, enum.Enum):
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class QuotationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    SENT = "SENT"
    UNDER_NEGOTIATION = "UNDER_NEGOTIATION"
    CONFIRMED = "CONFIRMED"
    FULFILLMENT = "FULFILLMENT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"
    SKIPPED = "SKIPPED"


class RecommendationType(str, enum.Enum):
    UPSELL = "UPSELL"
    CROSS_SELL = "CROSS_SELL"


class FulfillmentStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RESERVED = "RESERVED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class BackorderStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIALLY_ALLOCATED = "PARTIALLY_ALLOCATED"
    ALLOCATED = "ALLOCATED"
    CANCELLED = "CANCELLED"


class BillingFrequency(str, enum.Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"


class CancellationRule(str, enum.Enum):
    IMMEDIATE = "IMMEDIATE"
    END_OF_PERIOD = "END_OF_PERIOD"


class RefundRule(str, enum.Enum):
    NONE = "NONE"
    PRORATED = "PRORATED"
    FULL = "FULL"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class BillingScheduleStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    INVOICED = "INVOICED"
    PAID = "PAID"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class NegotiationType(str, enum.Enum):
    COMMENT = "COMMENT"
    CHANGE_REQUEST = "CHANGE_REQUEST"
    COUNTER_DISCOUNT = "COUNTER_DISCOUNT"


class NegotiationStatus(str, enum.Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, enum.Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    UPI = "UPI"
    OTHER = "OTHER"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class AlertType(str, enum.Enum):
    STALLED_DEAL = "STALLED_DEAL"
    DISCOUNT_ANOMALY = "DISCOUNT_ANOMALY"
    DELIVERY_SLIPPAGE = "DELIVERY_SLIPPAGE"


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
