export type Role = 'SALES_REP' | 'SALES_MANAGER' | 'FINANCE' | 'OPERATIONS' | 'CUSTOMER' | 'ADMIN'

export type User = {
  id: number
  name: string
  email: string
  role: Role
  is_active: boolean
  customer_id?: number | null
}

export type Customer = {
  id: number
  name: string
  code: string
  email: string
  industry?: string
  city?: string
  payment_terms: number
  credit_limit: number
  customer_tier_id: number
  tier?: { id: number; name: string; default_discount_limit: number }
  has_portal?: boolean
}

export type Product = {
  id: number
  sku: string
  name: string
  product_type: string
  base_price: number
  cost_price: number
  category?: { id: number; name: string; kind: string }
}

export type QuoteLine = {
  id: number
  product_id: number
  quantity: number
  unit_price: number
  discount_percent: number
  discount_amount: number
  net_amount: number
  unit_cost?: number
  total_cost?: number
  gross_profit?: number
  margin_percent?: number
  is_freebie?: boolean
  description?: string
  product?: { id: number; name: string; sku: string; product_type: string; category?: string; category_id?: number }
}

export type WorkflowStage = {
  key: string
  label: string
  hint: string
  state: 'done' | 'current' | 'todo' | 'blocked'
}

export type WorkflowAction = {
  id: string
  label: string
  reason: string
  tone: string
  can_act?: boolean
  approval_id?: number | null
}

export type Workflow = {
  current_key: string
  lost: boolean
  approval_required: boolean
  approval_reasons: string[]
  approval_roles: string[]
  stages: WorkflowStage[]
  next_action: WorkflowAction
  can_submit: boolean
  can_send: boolean
  can_confirm: boolean
  sent_to_customer: boolean
  can_approve?: boolean
  active_approval_id?: number | null
  active_approver_role?: string
}

export type ApprovalStepInfo = {
  id: number
  role: string
  sequence: number
  status: string
  comment?: string | null
}

export type CurrentApprovalInfo = {
  id: number
  status: string
  reason?: string | null
  can_act?: boolean
  steps: ApprovalStepInfo[]
}

export type Quote = {
  id: number
  quote_number: string
  customer_id?: number
  title?: string
  status: string
  subtotal: number
  discount_total: number
  tax_total: number
  shipping_total: number
  total: number
  cost_total?: number
  gross_profit?: number
  gross_margin_percent?: number
  risk_score?: number
  deal_health_score?: number
  approval_status: string
  negotiation_status: string
  payment_terms: number
  expires_at?: string
  promised_delivery_date?: string
  created_at?: string
  customer?: Customer
  sales_rep?: { id: number; name: string }
  lines: QuoteLine[]
  risk_factors?: { id: number; type: string; severity: number; message: string }[]
  shipment_count?: number
  intelligence?: Record<string, unknown>
  billing?: Record<string, unknown>
  workflow?: Workflow
  sent_to_customer_at?: string | null
  current_approval?: CurrentApprovalInfo | null
}
