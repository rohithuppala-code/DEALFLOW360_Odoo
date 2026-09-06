/**
 * Shared vocabulary: roles, statuses and the colour each one reads as.
 *
 * Keeping the tone mapping here rather than in each component means a
 * PENDING_APPROVAL badge looks the same on the pipeline board, the list and the
 * detail header - which is what lets someone scan a screen without reading it.
 */

export const ROLES = {
  ADMIN: 'ADMIN',
  SALES_REP: 'SALES_REP',
  SALES_MANAGER: 'SALES_MANAGER',
  FINANCE: 'FINANCE',
  CUSTOMER: 'CUSTOMER',
}

export const INTERNAL_ROLES = [ROLES.ADMIN, ROLES.SALES_REP, ROLES.SALES_MANAGER, ROLES.FINANCE]
export const APPROVER_ROLES = [ROLES.SALES_MANAGER, ROLES.FINANCE, ROLES.ADMIN]
export const OVERSIGHT_ROLES = [ROLES.ADMIN, ROLES.SALES_MANAGER, ROLES.FINANCE]

export const ROLE_LABELS = {
  ADMIN: 'Administrator',
  SALES_REP: 'Sales Rep',
  SALES_MANAGER: 'Sales Manager',
  FINANCE: 'Finance',
  CUSTOMER: 'Customer',
}

export const QUOTATION_STATUSES = [
  'DRAFT',
  'PENDING_APPROVAL',
  'APPROVED',
  'REVISION_REQUIRED',
  'REJECTED',
  'SENT',
  'UNDER_NEGOTIATION',
  'CONFIRMED',
  'FULFILLMENT',
  'COMPLETED',
  'CANCELLED',
]

/** The columns of the Kanban pipeline: the statuses a deal is still live in. */
export const PIPELINE_STATUSES = [
  'DRAFT',
  'PENDING_APPROVAL',
  'APPROVED',
  'REVISION_REQUIRED',
  'SENT',
  'UNDER_NEGOTIATION',
]

export const STATUS_TONES = {
  DRAFT: 'slate',
  PENDING_APPROVAL: 'amber',
  APPROVED: 'emerald',
  REVISION_REQUIRED: 'orange',
  REJECTED: 'red',
  SENT: 'blue',
  UNDER_NEGOTIATION: 'violet',
  CONFIRMED: 'emerald',
  FULFILLMENT: 'cyan',
  COMPLETED: 'emerald',
  CANCELLED: 'slate',

  // Risk
  NORMAL: 'emerald',
  MODERATE: 'amber',
  HIGH: 'red',

  // Approvals
  PENDING: 'amber',
  RETURNED: 'orange',
  SKIPPED: 'slate',

  // Invoices and payments
  ISSUED: 'blue',
  PARTIALLY_PAID: 'amber',
  PAID: 'emerald',
  FAILED: 'red',
  REFUNDED: 'violet',

  // Fulfilment
  PLANNED: 'slate',
  RESERVED: 'blue',
  SHIPPED: 'cyan',
  DELIVERED: 'emerald',

  // Backorders
  OPEN: 'amber',
  PARTIALLY_ALLOCATED: 'blue',
  ALLOCATED: 'emerald',

  // Subscriptions and billing schedule
  ACTIVE: 'emerald',
  PAUSED: 'amber',
  EXPIRED: 'slate',
  SCHEDULED: 'slate',
  INVOICED: 'blue',

  // Alerts
  ACKNOWLEDGED: 'blue',
  ESCALATED: 'red',
  RESOLVED: 'emerald',
  LOW: 'slate',
  MEDIUM: 'amber',

  // Customer tiers
  BRONZE: 'orange',
  SILVER: 'slate',
  GOLD: 'amber',
}

export const statusTone = (value) => STATUS_TONES[value] ?? 'slate'

export const CUSTOMER_TIERS = ['BRONZE', 'SILVER', 'GOLD']
export const PRODUCT_TYPES = ['ONE_TIME', 'RECURRING', 'SERVICE']
export const BILLING_FREQUENCIES = ['MONTHLY', 'QUARTERLY', 'YEARLY']
export const CANCELLATION_RULES = ['IMMEDIATE', 'END_OF_PERIOD']
export const REFUND_RULES = ['NONE', 'PRORATED', 'FULL']
export const RECOMMENDATION_TYPES = ['UPSELL', 'CROSS_SELL']
export const PAYMENT_METHODS = ['BANK_TRANSFER', 'CARD', 'CASH', 'CHEQUE', 'UPI', 'OTHER']
export const INVOICE_STATUSES = ['DRAFT', 'ISSUED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED']
export const ALERT_TYPES = ['STALLED_DEAL', 'DISCOUNT_ANOMALY', 'DELIVERY_SLIPPAGE']
export const ALERT_SEVERITIES = ['LOW', 'MEDIUM', 'HIGH']
export const RISK_LEVELS = ['NORMAL', 'MODERATE', 'HIGH']

export const ALERT_TYPE_LABELS = {
  STALLED_DEAL: 'Stalled deal',
  DISCOUNT_ANOMALY: 'Discount anomaly',
  DELIVERY_SLIPPAGE: 'Delivery slippage',
}

/** Statuses in which a rep may still edit lines and discounts. */
export const EDITABLE_STATUSES = ['DRAFT', 'REVISION_REQUIRED', 'UNDER_NEGOTIATION']

export const isEditable = (status) => EDITABLE_STATUSES.includes(status)
