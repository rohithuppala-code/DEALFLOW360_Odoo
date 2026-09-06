import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, type ApiOk, type Page } from '../api/client'
import { Btn, ErrorState, PageHeader, Pagination, StatusBadge } from '../components/ui'
import { inr } from '../utils/format'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      {label}
      {children}
    </label>
  )
}

function parsePage<T>(data: unknown): { items: T[]; total: number; page: number; pages: number } {
  if (!data) return { items: [], total: 0, page: 1, pages: 1 }
  if (Array.isArray(data)) return { items: data as T[], total: data.length, page: 1, pages: 1 }
  if (typeof data === 'object' && 'items' in data) {
    const p = data as Page<T>
    return { items: p.items || [], total: p.total || 0, page: p.page || 1, pages: p.pages || 1 }
  }
  return { items: [], total: 0, page: 1, pages: 1 }
}

const TABS = [
  'Users',
  'Products',
  'Categories',
  'Tiers',
  'Price lists',
  'Discounts',
  'Approvals',
  'Warehouses',
  'Plans',
  'Recommendations',
  'Settings',
  'Audit',
]

const INITIAL_RULE_FORM = { name: '', field: 'discount_percent', operator: '>', value: '10', action_type: 'REQUIRE_APPROVAL', action_value: 'SALES_MANAGER', rule_type: 'APPROVAL' }
const INITIAL_USER_FORM = { name: '', email: '', password: '', role: 'SALES_REP', is_active: true, customer_id: '' }
const INITIAL_PROD_FORM = { sku: '', name: '', category_id: '', product_type: 'ONE_TIME', base_price: '', cost_price: '', description: '', is_active: true }
const INITIAL_TIER_FORM = { name: '', default_discount_limit: '10', risk_multiplier: '1', description: '' }
const INITIAL_DISC_FORM = { name: '', customer_tier_id: '', category_id: '', max_discount_percent: '10', requires_approval: true, is_active: true, severity: 'MEDIUM' }
const INITIAL_APPR_FORM = { condition_type: 'DISCOUNT_EXCEEDS_TIER', condition_value: '0', required_role: 'SALES_MANAGER', sequence: '1' }
const INITIAL_WH_FORM = { name: '', code: '', city: '', handling_cost: '150', reliability_score: '90', avg_lead_days: '3', shipping_zone: 'WEST' }
const INITIAL_INV_FORM = { warehouse_id: '', product_id: '', available_qty: '0', reorder_level: '5' }
const INITIAL_PLAN_FORM = { name: '', billing_interval: 'MONTHLY', price: '', setup_fee: '0', trial_days: '0', cost: '0' }
const INITIAL_REC_FORM = { product_id: '', recommended_product_id: '', recommendation_type: 'CROSS_SELL', reason: '', priority: '70' }
const INITIAL_PLIST_FORM = { name: '', currency: 'INR', customer_tier_id: '', is_active: true }
const INITIAL_PITEM_FORM = { list_id: '', product_id: '', unit_price: '', min_quantity: '1' }
const INITIAL_CAT_FORM = { name: '', kind: 'HARDWARE', description: '' }
const INITIAL_CUST_FORM = { name: '', code: '', email: '', customer_tier_id: '', city: '', payment_terms: '30' }

export default function AdminPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState('Users')

  // Pagination states
  const [usersPage, setUsersPage] = useState(1)
  const [usersPageSize, setUsersPageSize] = useState(10)

  const [prodPage, setProdPage] = useState(1)
  const [prodPageSize, setProdPageSize] = useState(10)

  const [whPage, setWhPage] = useState(1)
  const [whPageSize, setWhPageSize] = useState(10)

  const [invPage, setInvPage] = useState(1)
  const [invPageSize, setInvPageSize] = useState(10)

  const [plansPage, setPlansPage] = useState(1)
  const [plansPageSize, setPlansPageSize] = useState(10)

  const [auditPage, setAuditPage] = useState(1)
  const [auditPageSize, setAuditPageSize] = useState(20)

  const users = useQuery({
    queryKey: ['admin', 'users', usersPage, usersPageSize],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/admin/users', { params: { page: usersPage, page_size: usersPageSize } })).data.data,
  })
  const products = useQuery({
    queryKey: ['admin', 'products', prodPage, prodPageSize],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/admin/products', { params: { page: prodPage, page_size: prodPageSize } })).data.data,
  })
  const cats = useQuery({ queryKey: ['admin', 'cats'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/products/categories')).data.data })
  const tiers = useQuery({ queryKey: ['admin', 'tiers'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/tiers')).data.data })
  const rules = useQuery({ queryKey: ['admin', 'drules'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/discount-rules')).data.data })
  const brules = useQuery({ queryKey: ['admin', 'brules'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/rules')).data.data })
  const chains = useQuery({ queryKey: ['admin', 'chains'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/approval-chains')).data.data })
  const warehouses = useQuery({
    queryKey: ['admin', 'wh', whPage, whPageSize],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/admin/warehouses', { params: { page: whPage, page_size: whPageSize } })).data.data,
  })
  const inventory = useQuery({
    queryKey: ['admin', 'inv', invPage, invPageSize],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/admin/inventory', { params: { page: invPage, page_size: invPageSize } })).data.data,
  })
  const plans = useQuery({
    queryKey: ['admin', 'plans', plansPage, plansPageSize],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/admin/subscription-plans', { params: { page: plansPage, page_size: plansPageSize } })).data.data,
  })
  const recs = useQuery({ queryKey: ['admin', 'recs'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/recommendations')).data.data })
  const prices = useQuery({ queryKey: ['admin', 'plist'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/price-lists')).data.data })
  const settings = useQuery({ queryKey: ['admin', 'settings'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/settings')).data.data })
  const audit = useQuery({
    queryKey: ['admin', 'audit', auditPage, auditPageSize],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/admin/audit', { params: { page: auditPage, page_size: auditPageSize } })).data.data,
  })
  const customers = useQuery({ queryKey: ['admin', 'customers'], queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/admin/customers')).data.data })

  const parsedUsers = parsePage<Record<string, unknown>>(users.data)
  const parsedProducts = parsePage<Record<string, unknown>>(products.data)
  const parsedWarehouses = parsePage<Record<string, unknown>>(warehouses.data)
  const parsedInventory = parsePage<Record<string, unknown>>(inventory.data)
  const parsedPlans = parsePage<Record<string, unknown>>(plans.data)
  const parsedAudit = parsePage<Record<string, unknown>>(audit.data)

  const [form, setForm] = useState(INITIAL_RULE_FORM)
  const [userForm, setUserForm] = useState(INITIAL_USER_FORM)
  const [prodForm, setProdForm] = useState(INITIAL_PROD_FORM)
  const [tierForm, setTierForm] = useState(INITIAL_TIER_FORM)
  const [discForm, setDiscForm] = useState(INITIAL_DISC_FORM)
  const [apprForm, setApprForm] = useState(INITIAL_APPR_FORM)
  const [whForm, setWhForm] = useState(INITIAL_WH_FORM)
  const [invForm, setInvForm] = useState(INITIAL_INV_FORM)
  const [planForm, setPlanForm] = useState(INITIAL_PLAN_FORM)
  const [recForm, setRecForm] = useState(INITIAL_REC_FORM)
  const [plistForm, setPlistForm] = useState(INITIAL_PLIST_FORM)
  const [pitemForm, setPitemForm] = useState(INITIAL_PITEM_FORM)
  const [catForm, setCatForm] = useState(INITIAL_CAT_FORM)
  const [custForm, setCustForm] = useState(INITIAL_CUST_FORM)
  const [tax, setTax] = useState('18')
  const [riskThreshold, setRiskThreshold] = useState('70')
  const [minMargin, setMinMargin] = useState('0')
  const [proration, setProration] = useState({ monthly_days: '30', quarterly_days: '90', yearly_days: '365' })
  const [cancelCfg, setCancelCfg] = useState({ credit_unused: true, min_days: '0' })
  const [shipJson, setShipJson] = useState('')

  const invalidate = (...keys: string[]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: ['admin', k] }))

  useEffect(() => {
    for (const row of settings.data || []) {
      const key = String(row.key)
      const raw = row.value
      const val = raw && typeof raw === 'object' && raw !== null && 'value' in (raw as object) ? (raw as { value: unknown }).value : raw
      if (key === 'approvals.risk_threshold' && val != null) setRiskThreshold(String(val))
      if (key === 'billing.default_tax_percent' && val != null) setTax(String(val))
      if (key === 'recommendations.min_margin_percent' && val != null) setMinMargin(String(val))
    }
  }, [settings.data])

  const saveRule = useMutation({
    mutationFn: async () =>
      api.post('/admin/rules', {
        name: form.name || 'Custom rule',
        rule_type: form.rule_type,
        conditions: [{ field: form.field, operator: form.operator, value: form.value, logical_operator: 'AND' }],
        actions: [{ action_type: form.action_type, action_value: form.action_value }],
      }),
    onSuccess: () => {
      toast.success('Rule saved')
      setForm(INITIAL_RULE_FORM)
      invalidate('brules')
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to save rule')
    },
  })

  return (
    <div className="stack">
      <PageHeader
        kicker="Control plane"
        title="Admin"
        subtitle="Catalog, tiers, discount ceilings, approval chains, warehouses, plans, and recommendations — stored in the database and used by every workflow."
      />
      <div className="tabs" role="tablist" aria-label="Admin sections">
        {TABS.map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {users.isError ? <ErrorState title="We couldn't load admin data." onRetry={() => users.refetch()} /> : null}

      {tab === 'Users' && (
        <div className="stack">
          <div className="card card-pad grid-2">
            <Field label="Name"><input className="input" value={userForm.name} onChange={(e) => setUserForm({ ...userForm, name: e.target.value })} /></Field>
            <Field label="Email"><input className="input" type="email" value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} /></Field>
            <Field label="Password"><input className="input" type="password" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} /></Field>
            <Field label="Role">
              <select className="input" value={userForm.role} onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}>
                {['SALES_REP', 'SALES_MANAGER', 'FINANCE', 'OPERATIONS', 'ADMIN', 'CUSTOMER'].map((r) => <option key={r}>{r}</option>)}
              </select>
            </Field>
            {userForm.role === 'CUSTOMER' ? (
              <Field label="Company / Customer Account">
                <select
                  className="input"
                  value={userForm.customer_id}
                  onChange={(e) => setUserForm({ ...userForm, customer_id: e.target.value })}
                >
                  <option value="">(Auto-create new company profile)</option>
                  {(customers.data || []).map((c) => (
                    <option key={String(c.id)} value={String(c.id)}>
                      {String(c.name)} ({String(c.code)})
                    </option>
                  ))}
                </select>
              </Field>
            ) : null}
            <Btn onClick={async () => {
              try {
                const payload = {
                  ...userForm,
                  customer_id: userForm.customer_id ? Number(userForm.customer_id) : undefined,
                }
                await api.post('/admin/users', payload)
                toast.success('User created')
                setUserForm(INITIAL_USER_FORM)
                invalidate('users')
                invalidate('customers')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to create user')
              }
            }}>Create user</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Company / Account</th><th>Active</th><th></th></tr></thead>
              <tbody>
                {parsedUsers.items.map((u) => (
                  <tr key={String(u.id)}>
                    <td>{String(u.name)}</td>
                    <td>{String(u.email)}</td>
                    <td><StatusBadge value={String(u.role)} /></td>
                    <td>{String(u.customer_name || '—')}</td>
                    <td>{String(u.is_active)}</td>
                    <td>
                      <Btn kind="ghost" onClick={async () => {
                        try {
                          await api.put(`/admin/users/${u.id}`, { name: u.name, email: u.email, role: u.role, is_active: !u.is_active })
                          toast.success('Updated')
                          invalidate('users')
                          invalidate('customers')
                        } catch (err: any) {
                          toast.error(err?.response?.data?.detail || 'Failed to update user')
                        }
                      }}>{u.is_active ? 'Deactivate' : 'Activate'}</Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={parsedUsers.page}
              pages={parsedUsers.pages}
              total={parsedUsers.total}
              pageSize={usersPageSize}
              onPageChange={setUsersPage}
              onPageSizeChange={(ps) => {
                setUsersPageSize(ps)
                setUsersPage(1)
              }}
            />
          </div>
        </div>
      )}

      {tab === 'Products' && (
        <div className="stack">
          <div className="card card-pad grid-2">
            <Field label="SKU"><input className="input" value={prodForm.sku} onChange={(e) => setProdForm({ ...prodForm, sku: e.target.value })} /></Field>
            <Field label="Name"><input className="input" value={prodForm.name} onChange={(e) => setProdForm({ ...prodForm, name: e.target.value })} /></Field>
            <Field label="Category">
              <select className="input" value={prodForm.category_id} onChange={(e) => setProdForm({ ...prodForm, category_id: e.target.value })}>
                <option value="">Select category</option>
                {(cats.data || []).map((c) => <option key={String(c.id)} value={String(c.id)}>{String(c.name)}</option>)}
              </select>
            </Field>
            <Field label="Type">
              <select className="input" value={prodForm.product_type} onChange={(e) => setProdForm({ ...prodForm, product_type: e.target.value })}>
                {['ONE_TIME', 'SERVICE', 'SUBSCRIPTION'].map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="List price"><input className="input" value={prodForm.base_price} onChange={(e) => setProdForm({ ...prodForm, base_price: e.target.value })} /></Field>
            <Field label="Cost"><input className="input" value={prodForm.cost_price} onChange={(e) => setProdForm({ ...prodForm, cost_price: e.target.value })} /></Field>
            <Field label="Description"><input className="input" value={prodForm.description} onChange={(e) => setProdForm({ ...prodForm, description: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/products', { ...prodForm, category_id: Number(prodForm.category_id), base_price: Number(prodForm.base_price), cost_price: Number(prodForm.cost_price) })
                toast.success('Product saved')
                setProdForm(INITIAL_PROD_FORM)
                invalidate('products')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to create product')
              }
            }}>Create product</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>SKU</th><th>Name</th><th>Type</th><th className="num">Price</th><th className="num">Cost</th><th>Active</th><th></th></tr></thead>
              <tbody>
                {parsedProducts.items.map((p) => (
                  <tr key={String(p.id)}>
                    <td className="mono">{String(p.sku)}</td>
                    <td>{String(p.name)}</td>
                    <td>{String(p.product_type)}</td>
                    <td className="num mono">{inr(Number(p.base_price))}</td>
                    <td className="num mono">{inr(Number(p.cost_price))}</td>
                    <td>{String(p.is_active)}</td>
                    <td>
                      <Btn kind="ghost" onClick={async () => {
                        try {
                          await api.put(`/admin/products/${p.id}`, {
                            sku: p.sku, name: p.name, category_id: (p.category as { id?: number } | undefined)?.id, product_type: p.product_type,
                            base_price: p.base_price, cost_price: p.cost_price, description: p.description, is_active: !p.is_active,
                          })
                          toast.success('Product updated')
                          invalidate('products')
                        } catch (err: any) {
                          toast.error(err?.response?.data?.detail || 'Failed to update product')
                        }
                      }}>{p.is_active ? 'Deactivate' : 'Activate'}</Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={parsedProducts.page}
              pages={parsedProducts.pages}
              total={parsedProducts.total}
              pageSize={prodPageSize}
              onPageChange={setProdPage}
              onPageSizeChange={(ps) => {
                setProdPageSize(ps)
                setProdPage(1)
              }}
            />
          </div>
        </div>
      )}

      {tab === 'Categories' && (
        <div className="stack">
          <div className="card card-pad grid-2">
            <Field label="Name"><input className="input" value={catForm.name} onChange={(e) => setCatForm({ ...catForm, name: e.target.value })} /></Field>
            <Field label="Kind">
              <select className="input" value={catForm.kind} onChange={(e) => setCatForm({ ...catForm, kind: e.target.value })}>
                {['HARDWARE', 'SERVICE', 'SUBSCRIPTION', 'SOFTWARE', 'ACCESSORY'].map((k) => <option key={k}>{k}</option>)}
              </select>
            </Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/categories', catForm)
                toast.success('Category saved')
                setCatForm(INITIAL_CAT_FORM)
                qc.invalidateQueries({ queryKey: ['admin', 'cats'] })
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to create category')
              }
            }}>Create</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>Kind</th></tr></thead>
              <tbody>{(cats.data || []).map((c) => <tr key={String(c.id)}><td>{String(c.name)}</td><td>{String(c.kind)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'Tiers' && (
        <div className="stack">
          <p className="muted">Default discount ceilings per customer tier. Used by the discount engine when no category rule matches.</p>
          <div className="card card-pad grid-2">
            <Field label="Name"><input className="input" value={tierForm.name} onChange={(e) => setTierForm({ ...tierForm, name: e.target.value })} /></Field>
            <Field label="Discount ceiling %"><input className="input" value={tierForm.default_discount_limit} onChange={(e) => setTierForm({ ...tierForm, default_discount_limit: e.target.value })} /></Field>
            <Field label="Risk multiplier"><input className="input" value={tierForm.risk_multiplier} onChange={(e) => setTierForm({ ...tierForm, risk_multiplier: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/tiers', { ...tierForm, default_discount_limit: Number(tierForm.default_discount_limit), risk_multiplier: Number(tierForm.risk_multiplier) })
                toast.success('Tier saved')
                setTierForm(INITIAL_TIER_FORM)
                invalidate('tiers')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to create tier')
              }
            }}>Create tier</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Tier</th><th>Ceiling %</th><th>Risk ×</th><th></th></tr></thead>
              <tbody>
                {(tiers.data || []).map((t) => (
                  <tr key={String(t.id)}>
                    <td>{String(t.name)}</td>
                    <td>
                      <input className="input" style={{ maxWidth: 90 }} defaultValue={String(t.default_discount_limit)}
                        onBlur={async (e) => {
                          try {
                            await api.put(`/admin/tiers/${t.id}`, { name: t.name, description: t.description, default_discount_limit: Number(e.target.value), risk_multiplier: t.risk_multiplier })
                            toast.success('Ceiling updated')
                            invalidate('tiers')
                          } catch (err: any) {
                            toast.error(err?.response?.data?.detail || 'Failed to update ceiling')
                          }
                        }} />
                    </td>
                    <td className="mono">{String(t.risk_multiplier)}</td>
                    <td className="muted">{String(t.description || '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card card-pad">
            <h3>Customers</h3>
            <div className="grid-2" style={{ marginTop: 8 }}>
              <Field label="Name"><input className="input" value={custForm.name} onChange={(e) => setCustForm({ ...custForm, name: e.target.value })} /></Field>
              <Field label="Code"><input className="input" value={custForm.code} onChange={(e) => setCustForm({ ...custForm, code: e.target.value })} /></Field>
              <Field label="Email"><input className="input" type="email" value={custForm.email} onChange={(e) => setCustForm({ ...custForm, email: e.target.value })} /></Field>
              <Field label="Tier">
                <select className="input" value={custForm.customer_tier_id} onChange={(e) => setCustForm({ ...custForm, customer_tier_id: e.target.value })}>
                  <option value="">Select tier</option>
                  {(tiers.data || []).map((t) => <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>)}
                </select>
              </Field>
              <Btn onClick={async () => {
                try {
                  await api.post('/customers', { ...custForm, customer_tier_id: custForm.customer_tier_id ? Number(custForm.customer_tier_id) : undefined, payment_terms: Number(custForm.payment_terms) })
                  toast.success('Customer created')
                  setCustForm(INITIAL_CUST_FORM)
                  invalidate('customers')
                } catch (err: any) {
                  toast.error(err?.response?.data?.detail || 'Failed to create customer')
                }
              }}>Create customer</Btn>
            </div>
            <div className="muted" style={{ marginTop: 8 }}>{(customers.data || []).length} customers in the database.</div>
          </div>
        </div>
      )}

      {tab === 'Price lists' && (
        <div className="stack">
          <p className="muted">Tier- and currency-specific unit prices. The quote engine uses the active list for the customer’s tier.</p>
          <div className="card card-pad grid-2">
            <Field label="List name"><input className="input" value={plistForm.name} onChange={(e) => setPlistForm({ ...plistForm, name: e.target.value })} /></Field>
            <Field label="Currency"><input className="input" value={plistForm.currency} onChange={(e) => setPlistForm({ ...plistForm, currency: e.target.value })} /></Field>
            <Field label="Tier">
              <select className="input" value={plistForm.customer_tier_id} onChange={(e) => setPlistForm({ ...plistForm, customer_tier_id: e.target.value })}>
                <option value="">Any tier</option>
                {(tiers.data || []).map((t) => <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>)}
              </select>
            </Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/price-lists', { ...plistForm, customer_tier_id: plistForm.customer_tier_id ? Number(plistForm.customer_tier_id) : null })
                toast.success('Price list created')
                setPlistForm(INITIAL_PLIST_FORM)
                invalidate('plist')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to create price list')
              }
            }}>Create list</Btn>
          </div>
          <div className="card card-pad grid-2">
            <Field label="Price list">
              <select className="input" value={pitemForm.list_id} onChange={(e) => setPitemForm({ ...pitemForm, list_id: e.target.value })}>
                <option value="">Select list</option>
                {(prices.data || []).map((p) => <option key={String(p.id)} value={String(p.id)}>{String(p.name)}</option>)}
              </select>
            </Field>
            <Field label="Product">
              <select className="input" value={pitemForm.product_id} onChange={(e) => setPitemForm({ ...pitemForm, product_id: e.target.value })}>
                <option value="">Select product</option>
                {parsedProducts.items.map((p) => <option key={String(p.id)} value={String(p.id)}>{String(p.name)}</option>)}
              </select>
            </Field>
            <Field label="Unit price"><input className="input" value={pitemForm.unit_price} onChange={(e) => setPitemForm({ ...pitemForm, unit_price: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post(`/admin/price-lists/${pitemForm.list_id}/items`, { product_id: Number(pitemForm.product_id), unit_price: Number(pitemForm.unit_price), min_quantity: Number(pitemForm.min_quantity) })
                toast.success('Price saved')
                setPitemForm(INITIAL_PITEM_FORM)
                invalidate('plist')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to add price')
              }
            }}>Add price</Btn>
          </div>
          {(prices.data || []).map((p) => (
            <div className="card card-pad" key={String(p.id)}>
              <strong>{String(p.name)}</strong> <span className="muted">{String(p.currency)} · active {String(p.is_active)}</span>
              {((p.items as Record<string, unknown>[]) || []).map((i) => (
                <div className="factor" key={String(i.id)}><span>{String(i.product)}</span><span className="mono">{String(i.unit_price)}</span></div>
              ))}
            </div>
          ))}
        </div>
      )}

      {tab === 'Discounts' && (
        <div className="stack">
          <p className="muted">Category- and tier-specific discount ceilings. The discount engine evaluates these on every quote line.</p>
          <div className="card card-pad grid-2">
            <Field label="Rule name"><input className="input" value={discForm.name} onChange={(e) => setDiscForm({ ...discForm, name: e.target.value })} /></Field>
            <Field label="Tier">
              <select className="input" value={discForm.customer_tier_id} onChange={(e) => setDiscForm({ ...discForm, customer_tier_id: e.target.value })}>
                <option value="">Select tier</option>
                {(tiers.data || []).map((t) => <option key={String(t.id)} value={String(t.id)}>{String(t.name)}</option>)}
              </select>
            </Field>
            <Field label="Category">
              <select className="input" value={discForm.category_id} onChange={(e) => setDiscForm({ ...discForm, category_id: e.target.value })}>
                <option value="">Optional</option>
                {(cats.data || []).map((c) => <option key={String(c.id)} value={String(c.id)}>{String(c.name)}</option>)}
              </select>
            </Field>
            <Field label="Max %"><input className="input" value={discForm.max_discount_percent} onChange={(e) => setDiscForm({ ...discForm, max_discount_percent: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/discount-rules', {
                  name: discForm.name,
                  customer_tier_id: discForm.customer_tier_id ? Number(discForm.customer_tier_id) : null,
                  category_id: discForm.category_id ? Number(discForm.category_id) : null,
                  max_discount_percent: Number(discForm.max_discount_percent),
                  requires_approval: discForm.requires_approval,
                  is_active: true,
                  severity: discForm.severity,
                })
                toast.success('Discount rule saved')
                setDiscForm(INITIAL_DISC_FORM)
                invalidate('drules')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to save discount rule')
              }
            }}>Save ceiling</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>Tier</th><th>Category</th><th>Max %</th><th>Active</th></tr></thead>
              <tbody>
                {(rules.data || []).map((r) => (
                  <tr key={String(r.id)}>
                    <td>{String(r.name)}</td>
                    <td>{String(r.tier)}</td>
                    <td>{String(r.category)}</td>
                    <td>
                      <input className="input" style={{ maxWidth: 80 }} defaultValue={String(r.max_discount_percent)}
                        onBlur={async (e) => {
                          try {
                            await api.put(`/admin/discount-rules/${r.id}`, {
                              name: r.name, customer_tier_id: r.customer_tier_id, category_id: r.category_id, product_id: r.product_id,
                              max_discount_percent: Number(e.target.value), severity: r.severity, requires_approval: r.requires_approval, is_active: r.is_active,
                            })
                            toast.success('Ceiling updated')
                            invalidate('drules')
                          } catch (err: any) {
                            toast.error(err?.response?.data?.detail || 'Failed to update ceiling')
                          }
                        }} />
                    </td>
                    <td>{String(r.is_active)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'Approvals' && (
        <div className="stack">
          <p className="muted">Configure which discount/risk conditions require Sales Manager, and which also require Finance (higher sequence).</p>
          {(chains.data || []).map((c) => (
            <div className="card card-pad" key={String(c.id)}>
              <h3>{String(c.name)}</h3>
              <div className="muted">{String(c.description || '')}</div>
              {((c.rules as Record<string, unknown>[]) || []).map((r) => (
                <div className="factor" key={String(r.id)}>
                  <span>{String(r.condition_type)} {String(r.condition_value)} → {String(r.required_role)} (seq {String(r.sequence)})</span>
                  <Btn kind="ghost" onClick={async () => {
                    try {
                      await api.delete(`/admin/approval-chains/${c.id}/rules/${r.id}`)
                      toast.success('Removed')
                      invalidate('chains')
                    } catch (err: any) {
                      toast.error(err?.response?.data?.detail || 'Failed to remove rule')
                    }
                  }}>Remove</Btn>
                </div>
              ))}
              <div className="grid-2" style={{ marginTop: 10 }}>
                <Field label="Condition">
                  <select className="input" value={apprForm.condition_type} onChange={(e) => setApprForm({ ...apprForm, condition_type: e.target.value })}>
                    {['DISCOUNT_EXCEEDS_TIER', 'MARGIN_BELOW', 'RISK_ABOVE', 'DEAL_VALUE_ABOVE', 'PAYMENT_TERMS_ABOVE', 'CATEGORY_DISCOUNT_ABOVE'].map((x) => <option key={x}>{x}</option>)}
                  </select>
                </Field>
                <Field label="Threshold"><input className="input" value={apprForm.condition_value} onChange={(e) => setApprForm({ ...apprForm, condition_value: e.target.value })} /></Field>
                <Field label="Required role">
                  <select className="input" value={apprForm.required_role} onChange={(e) => setApprForm({ ...apprForm, required_role: e.target.value })}>
                    <option>SALES_MANAGER</option>
                    <option>FINANCE</option>
                  </select>
                </Field>
                <Field label="Sequence"><input className="input" value={apprForm.sequence} onChange={(e) => setApprForm({ ...apprForm, sequence: e.target.value })} /></Field>
                <Btn onClick={async () => {
                  try {
                    await api.post(`/admin/approval-chains/${c.id}/rules`, { ...apprForm, sequence: Number(apprForm.sequence) })
                    toast.success('Approval rule saved')
                    setApprForm(INITIAL_APPR_FORM)
                    invalidate('chains')
                  } catch (err: any) {
                    toast.error(err?.response?.data?.detail || 'Failed to save approval rule')
                  }
                }}>Add rule</Btn>
              </div>
            </div>
          ))}
          <div className="grid-2">
            <div className="card card-pad stack">
              <h3>WHEN / THEN builder</h3>
              <Field label="Rule name"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <div className="grid-3">
                <Field label="Field"><input className="input" value={form.field} onChange={(e) => setForm({ ...form, field: e.target.value })} /></Field>
                <Field label="Operator">
                  <select className="input" value={form.operator} onChange={(e) => setForm({ ...form, operator: e.target.value })}>
                    {['=', '!=', '>', '<', '>=', '<=', 'IN', 'NOT_IN'].map((o) => <option key={o}>{o}</option>)}
                  </select>
                </Field>
                <Field label="Value"><input className="input" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} /></Field>
              </div>
              <Field label="Action">
                <select className="input" value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
                  {['REQUIRE_APPROVAL', 'RAISE_RISK', 'RECOMMEND_PRODUCT', 'BLOCK_QUOTE', 'REQUIRE_FINANCE', 'FLAG_ANOMALY'].map((o) => <option key={o}>{o}</option>)}
                </select>
              </Field>
              <Field label="Action value"><input className="input" value={form.action_value} onChange={(e) => setForm({ ...form, action_value: e.target.value })} /></Field>
              <Btn onClick={() => saveRule.mutate()}>Save rule</Btn>
            </div>
            <div className="card card-pad">
              <h3>Active rules</h3>
              {(brules.data || []).map((r) => (
                <div key={String(r.id)} className="factor"><div><strong>{String(r.name)}</strong><div className="muted">{String(r.rule_type)}</div></div></div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'Warehouses' && (
        <div className="stack">
          <p className="muted">Handling cost is the shipping-cost weight used when splitting warehouses. Inventory and reorder levels are used at allocation time.</p>
          <div className="card card-pad grid-2">
            <Field label="Name"><input className="input" value={whForm.name} onChange={(e) => setWhForm({ ...whForm, name: e.target.value })} /></Field>
            <Field label="Code"><input className="input" value={whForm.code} onChange={(e) => setWhForm({ ...whForm, code: e.target.value })} /></Field>
            <Field label="City"><input className="input" value={whForm.city} onChange={(e) => setWhForm({ ...whForm, city: e.target.value })} /></Field>
            <Field label="Handling cost"><input className="input" value={whForm.handling_cost} onChange={(e) => setWhForm({ ...whForm, handling_cost: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/warehouses', { ...whForm, handling_cost: Number(whForm.handling_cost), reliability_score: Number(whForm.reliability_score), avg_lead_days: Number(whForm.avg_lead_days) })
                toast.success('Warehouse saved')
                setWhForm(INITIAL_WH_FORM)
                invalidate('wh')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to save warehouse')
              }
            }}>Create warehouse</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>City</th><th>Handling</th><th>Lead days</th></tr></thead>
              <tbody>
                {parsedWarehouses.items.map((w) => (
                  <tr key={String(w.id)}>
                    <td>{String(w.name)}</td>
                    <td>{String(w.city)}</td>
                    <td>
                      <input className="input" style={{ maxWidth: 90 }} defaultValue={String(w.handling_cost)}
                        onBlur={async (e) => {
                          try {
                            await api.put(`/admin/warehouses/${w.id}`, { ...w, handling_cost: Number(e.target.value) })
                            toast.success('Shipping weight updated')
                            invalidate('wh')
                          } catch (err: any) {
                            toast.error(err?.response?.data?.detail || 'Failed to update warehouse')
                          }
                        }} />
                    </td>
                    <td className="mono">{String(w.avg_lead_days)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={parsedWarehouses.page}
              pages={parsedWarehouses.pages}
              total={parsedWarehouses.total}
              pageSize={whPageSize}
              onPageChange={setWhPage}
              onPageSizeChange={(ps) => {
                setWhPageSize(ps)
                setWhPage(1)
              }}
            />
          </div>
          <div className="card card-pad">
            <h3>Stock / replenishment</h3>
            <div className="grid-2" style={{ marginTop: 8 }}>
              <Field label="Warehouse">
                <select className="input" value={invForm.warehouse_id} onChange={(e) => setInvForm({ ...invForm, warehouse_id: e.target.value })}>
                  <option value="">Select warehouse</option>
                  {parsedWarehouses.items.map((w) => <option key={String(w.id)} value={String(w.id)}>{String(w.name)}</option>)}
                </select>
              </Field>
              <Field label="Product">
                <select className="input" value={invForm.product_id} onChange={(e) => setInvForm({ ...invForm, product_id: e.target.value })}>
                  <option value="">Select product</option>
                  {parsedProducts.items.map((p) => <option key={String(p.id)} value={String(p.id)}>{String(p.name)}</option>)}
                </select>
              </Field>
              <Field label="Available qty"><input className="input" value={invForm.available_qty} onChange={(e) => setInvForm({ ...invForm, available_qty: e.target.value })} /></Field>
              <Field label="Reorder level"><input className="input" value={invForm.reorder_level} onChange={(e) => setInvForm({ ...invForm, reorder_level: e.target.value })} /></Field>
              <Btn onClick={async () => {
                try {
                  await api.post('/admin/inventory', { warehouse_id: Number(invForm.warehouse_id), product_id: Number(invForm.product_id), available_qty: Number(invForm.available_qty), reorder_level: Number(invForm.reorder_level) })
                  toast.success('Inventory saved')
                  setInvForm(INITIAL_INV_FORM)
                  invalidate('inv')
                } catch (err: any) {
                  toast.error(err?.response?.data?.detail || 'Failed to save inventory')
                }
              }}>Save stock</Btn>
            </div>
            <div className="card table-wrap" style={{ marginTop: 12 }}>
              <table className="table">
                <thead><tr><th>Product</th><th>Warehouse</th><th>Available</th><th>Reorder Level</th></tr></thead>
                <tbody>
                  {parsedInventory.items.map((i) => (
                    <tr key={String(i.id)}>
                      <td>{String(i.product_name || i.product_id)}</td>
                      <td>{String(i.warehouse_name || i.warehouse_id)}</td>
                      <td className="mono">{String(i.available_qty)}</td>
                      <td className="mono">{String(i.reorder_level)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={parsedInventory.page}
                pages={parsedInventory.pages}
                total={parsedInventory.total}
                pageSize={invPageSize}
                onPageChange={setInvPage}
                onPageSizeChange={(ps) => {
                  setInvPageSize(ps)
                  setInvPage(1)
                }}
              />
            </div>
          </div>
        </div>
      )}

      {tab === 'Plans' && (
        <div className="stack">
          <p className="muted">Monthly, quarterly, and yearly plans. Proration and cancellation rules are in Settings.</p>
          <div className="card card-pad grid-2">
            <Field label="Name"><input className="input" value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} /></Field>
            <Field label="Interval">
              <select className="input" value={planForm.billing_interval} onChange={(e) => setPlanForm({ ...planForm, billing_interval: e.target.value })}>
                <option>MONTHLY</option><option>QUARTERLY</option><option>YEARLY</option>
              </select>
            </Field>
            <Field label="Price"><input className="input" value={planForm.price} onChange={(e) => setPlanForm({ ...planForm, price: e.target.value })} /></Field>
            <Field label="Setup fee"><input className="input" value={planForm.setup_fee} onChange={(e) => setPlanForm({ ...planForm, setup_fee: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/subscription-plans', { ...planForm, price: Number(planForm.price), setup_fee: Number(planForm.setup_fee), trial_days: Number(planForm.trial_days), cost: Number(planForm.cost) })
                toast.success('Plan saved')
                setPlanForm(INITIAL_PLAN_FORM)
                invalidate('plans')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to save plan')
              }
            }}>Create plan</Btn>
          </div>
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>Interval</th><th className="num">Price</th><th>Trial</th></tr></thead>
              <tbody>
                {parsedPlans.items.map((p) => (
                  <tr key={String(p.id)}>
                    <td>{String(p.name)}</td>
                    <td>{String(p.billing_interval)}</td>
                    <td className="num mono">{inr(Number(p.price))}</td>
                    <td>{String(p.trial_days)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={parsedPlans.page}
              pages={parsedPlans.pages}
              total={parsedPlans.total}
              pageSize={plansPageSize}
              onPageChange={setPlansPage}
              onPageSizeChange={(ps) => {
                setPlansPageSize(ps)
                setPlansPage(1)
              }}
            />
          </div>
        </div>
      )}

      {tab === 'Recommendations' && (
        <div className="stack">
          <p className="muted">Product pairings for upsell/cross-sell. Minimum margin is in Settings and is applied by the recommendation engine.</p>
          <div className="card card-pad grid-2">
            <Field label="Source product">
              <select className="input" value={recForm.product_id} onChange={(e) => setRecForm({ ...recForm, product_id: e.target.value })}>
                <option value="">Select product</option>
                {parsedProducts.items.map((p) => <option key={String(p.id)} value={String(p.id)}>{String(p.name)}</option>)}
              </select>
            </Field>
            <Field label="Recommended product">
              <select className="input" value={recForm.recommended_product_id} onChange={(e) => setRecForm({ ...recForm, recommended_product_id: e.target.value })}>
                <option value="">Select product</option>
                {parsedProducts.items.map((p) => <option key={String(p.id)} value={String(p.id)}>{String(p.name)}</option>)}
              </select>
            </Field>
            <Field label="Type">
              <select className="input" value={recForm.recommendation_type} onChange={(e) => setRecForm({ ...recForm, recommendation_type: e.target.value })}>
                {['UPSELL', 'CROSS_SELL', 'BUNDLE', 'ALTERNATIVE'].map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Reason"><input className="input" value={recForm.reason} onChange={(e) => setRecForm({ ...recForm, reason: e.target.value })} /></Field>
            <Btn onClick={async () => {
              try {
                await api.post('/admin/recommendations', { ...recForm, product_id: Number(recForm.product_id), recommended_product_id: Number(recForm.recommended_product_id), priority: Number(recForm.priority) })
                toast.success('Pairing saved')
                setRecForm(INITIAL_REC_FORM)
                invalidate('recs')
              } catch (err: any) {
                toast.error(err?.response?.data?.detail || 'Failed to save pairing')
              }
            }}>Save pairing</Btn>
          </div>
          {(recs.data || []).map((r) => (
            <div className="card card-pad" key={String(r.id)}>
              <div className="spread">
                <div><strong>{String(r.product)}</strong> → {String(r.recommended)} <span className="badge">{String(r.recommendation_type)}</span>
                  <div className="muted">{String(r.reason)}</div>
                </div>
                <Btn kind="ghost" onClick={async () => {
                  try {
                    await api.put(`/admin/recommendations/${r.id}`, { ...r, is_active: !r.is_active })
                    toast.success('Updated')
                    invalidate('recs')
                  } catch (err: any) {
                    toast.error(err?.response?.data?.detail || 'Failed to update pairing')
                  }
                }}>{r.is_active ? 'Deactivate' : 'Activate'}</Btn>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'Settings' && (
        <div className="card card-pad stack">
          <h3>Tax, proration, cancellation, recommendations, shipping</h3>
          <label className="field">Default tax %
            <input className="input" value={tax} onChange={(e) => setTax(e.target.value)} />
          </label>
          <label className="field">Negotiation risk threshold (Finance is required when blended risk is above this)
            <input className="input" type="number" min={0} max={100} value={riskThreshold} onChange={(e) => setRiskThreshold(e.target.value)} />
            <span className="muted">Discount over the customer tier/category ceiling always goes to the Sales Manager. Risk above this value also sends the deal to Finance after the manager.</span>
          </label>
          <label className="field">Recommendation minimum margin %
            <input className="input" value={minMargin} onChange={(e) => setMinMargin(e.target.value)} />
          </label>
          <div className="grid-3">
            <label className="field">Monthly proration days<input className="input" value={proration.monthly_days} onChange={(e) => setProration({ ...proration, monthly_days: e.target.value })} /></label>
            <label className="field">Quarterly days<input className="input" value={proration.quarterly_days} onChange={(e) => setProration({ ...proration, quarterly_days: e.target.value })} /></label>
            <label className="field">Yearly days<input className="input" value={proration.yearly_days} onChange={(e) => setProration({ ...proration, yearly_days: e.target.value })} /></label>
          </div>
          <label className="row"><input type="checkbox" checked={cancelCfg.credit_unused} onChange={(e) => setCancelCfg({ ...cancelCfg, credit_unused: e.target.checked })} /> Credit unused days on cancellation</label>
          <label className="field">Shipping matrix JSON (CityA|CityB → cost)
            <textarea className="input" rows={5} value={shipJson} onChange={(e) => setShipJson(e.target.value)} placeholder='{"Ahmedabad|Mumbai":250}' />
          </label>
          <Btn onClick={async () => {
            try {
              await api.put('/admin/settings/billing.default_tax_percent', { value: Number(tax) })
              await api.put('/admin/settings/approvals.risk_threshold', { value: Number(riskThreshold) })
              await api.put('/admin/settings/recommendations.min_margin_percent', { value: Number(minMargin) })
              await api.put('/admin/settings/billing.proration', { value: { monthly_days: Number(proration.monthly_days), quarterly_days: Number(proration.quarterly_days), yearly_days: Number(proration.yearly_days) } })
              await api.put('/admin/settings/billing.cancellation', { value: { credit_unused: cancelCfg.credit_unused, min_days: Number(cancelCfg.min_days) } })
              if (shipJson.trim()) await api.put('/admin/settings/shipping_matrix', { value: JSON.parse(shipJson) })
              toast.success('Settings stored — engines will use them on the next quote')
              invalidate('settings')
            } catch (err: any) {
              toast.error(err?.response?.data?.detail || 'Failed to save settings')
            }
          }}>Save settings</Btn>
          <div className="muted">{(settings.data || []).map((s) => `${s.key}`).join(' · ') || 'No rows yet — save to create them.'}</div>
        </div>
      )}

      {tab === 'Audit' && (
        <div className="card card-pad stack">
          <h3>System activity</h3>
          <div className="timeline" style={{ marginTop: 10 }}>
            {parsedAudit.items.map((e) => (
              <div className="t-item" key={String(e.id)}>
                <div>{String(e.action)} · {String(e.entity_type)} {e.entity_id ? `#${e.entity_id}` : ''}</div>
                <time>{e.created_at ? new Date(String(e.created_at)).toLocaleString() : ''} · {String(e.user || '')}</time>
              </div>
            ))}
          </div>
          <Pagination
            page={parsedAudit.page}
            pages={parsedAudit.pages}
            total={parsedAudit.total}
            pageSize={auditPageSize}
            onPageChange={setAuditPage}
            onPageSizeChange={(ps) => {
              setAuditPageSize(ps)
              setAuditPage(1)
            }}
          />
        </div>
      )}
    </div>
  )
}

