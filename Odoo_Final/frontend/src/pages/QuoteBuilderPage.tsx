import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { api, type ApiOk, type Page } from '../api/client'
import type { Customer, Product } from '../types'
import { Btn, PageHeader, RiskBadge } from '../components/ui'
import { inr, pct } from '../utils/format'

type Line = { product_id: number; name: string; quantity: number; discount_percent: number; category?: string }

type Rec = {
  id: number
  recommendation_type: string
  product_name: string
  reason: string
  recommended_product_id: number
  additional_revenue?: number
  additional_profit?: number
  unit_price?: number
  product_type?: string
}

const GROUPS: { id: string; label: string; kinds: string[] }[] = [
  { id: 'HARDWARE', label: 'Hardware', kinds: ['HARDWARE', 'ACCESSORY'] },
  { id: 'SERVICE', label: 'Services', kinds: ['SERVICE'] },
  { id: 'SUBSCRIPTION', label: 'Subscriptions', kinds: ['SUBSCRIPTION', 'SOFTWARE'] },
]

function productKind(p: Product) {
  return (p.category?.kind || p.product_type || '').toUpperCase()
}

export default function QuoteBuilderPage() {
  const nav = useNavigate()
  const [customerId, setCustomerId] = useState<number | ''>('')
  const [customerQ, setCustomerQ] = useState('')
  const [lines, setLines] = useState<Line[]>([])
  const [title, setTitle] = useState('Enterprise Hardware + Support')
  const [orderDiscount, setOrderDiscount] = useState(0)
  const [group, setGroup] = useState('HARDWARE')
  const [search, setSearch] = useState('')
  const [dismissed, setDismissed] = useState<number[]>([])

  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: async () => (await api.get<ApiOk<Page<Customer>>>('/customers', { params: { page_size: 100 } })).data.data.items,
  })
  const products = useQuery({
    queryKey: ['products', 'builder'],
    queryFn: async () => (await api.get<ApiOk<Page<Product>>>('/products', { params: { page_size: 100 } })).data.data.items,
  })
  const preview = useQuery({
    queryKey: ['preview', customerId, lines, orderDiscount, title],
    enabled: Boolean(customerId) && lines.length > 0,
    queryFn: async () =>
      (
        await api.post<ApiOk<Record<string, unknown>>>('/quotes/preview', {
          customer_id: customerId,
          title,
          order_discount_percent: orderDiscount,
          lines: lines.map((l) => ({ product_id: l.product_id, quantity: l.quantity, discount_percent: l.discount_percent })),
        })
      ).data.data,
  })
  const create = useMutation({
    mutationFn: async () =>
      (
        await api.post<ApiOk<{ id: number }>>('/quotes', {
          customer_id: customerId,
          title,
          order_discount_percent: orderDiscount,
          lines: lines.map((l) => ({ product_id: l.product_id, quantity: l.quantity, discount_percent: l.discount_percent })),
        })
      ).data.data,
    onSuccess: (q) => {
      toast.success('Quote saved')
      nav(`/quotes/${q.id}`)
    },
  })

  const totals = (preview.data?.totals || {}) as {
    net_revenue?: number
    gross_margin_percent?: number
    total?: number
    gross_profit?: number
    subtotal?: number
    discount_total?: number
    tax_total?: number
  }
  const risk = (preview.data?.risk || {}) as { score?: number; level?: string; factors?: { type: string; message: string; severity: number }[] }
  const approval = (preview.data?.approval_preview || {}) as { required?: boolean; reasons?: string[]; roles?: string[] }
  const recs = ((preview.data?.recommendations as Rec[]) || []).filter((r) => !dismissed.includes(r.id) && !lines.some((l) => l.product_id === r.recommended_product_id))
  const dirty = Boolean(customerId || lines.length)

  useEffect(() => {
    if (!dirty) return
    const onLeave = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', onLeave)
    return () => window.removeEventListener('beforeunload', onLeave)
  }, [dirty])

  function addProduct(p: Product) {
    setLines((prev) => {
      const hit = prev.find((l) => l.product_id === p.id)
      if (hit) return prev.map((l) => (l.product_id === p.id ? { ...l, quantity: l.quantity + 1 } : l))
      return [...prev, { product_id: p.id, name: p.name, quantity: 1, discount_percent: 0, category: p.category?.name }]
    })
  }

  function addRec(r: Rec) {
    const catalog = products.data || []
    const p = catalog.find((x) => x.id === r.recommended_product_id)
    if (p) addProduct(p)
    else {
      setLines((prev) => {
        if (prev.some((l) => l.product_id === r.recommended_product_id)) return prev
        return [...prev, { product_id: r.recommended_product_id, name: r.product_name, quantity: 1, discount_percent: 0, category: r.product_type }]
      })
    }
  }

  const customer = useMemo(() => (customers.data || []).find((c) => c.id === customerId), [customers.data, customerId])
  const customerOptions = useMemo(() => {
    const q = customerQ.trim().toLowerCase()
    const rows = customers.data || []
    if (!q) return rows
    return rows.filter((c) => c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q) || c.code.toLowerCase().includes(q))
  }, [customers.data, customerQ])
  const catalog = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (products.data || []).filter((p) => {
      const kind = productKind(p)
      const g = GROUPS.find((x) => x.id === group)
      if (g && !g.kinds.includes(kind) && p.category?.name?.toUpperCase() !== group) return false
      if (!q) return true
      return p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q)
    })
  }, [products.data, group, search])

  const canSave = Boolean(customerId) && lines.length > 0 && !create.isPending

  return (
    <div className="stack">
      <PageHeader
        kicker="Quote builder"
        title="New quote"
        subtitle="Pick the customer, add Hardware / Services / Subscriptions, then review live margin and policy."
      />

      <div className="deal-grid">
        <div className="stack">
          <div className="card card-pad stack">
            <h3>Customer</h3>
            <label className="field">
              Search
              <input className="input" placeholder="Name, code, or email" value={customerQ} onChange={(e) => setCustomerQ(e.target.value)} />
            </label>
            <label className="field">
              Account
              <select className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">Select the customer this quote is for</option>
                {customerOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} · {c.email} · {c.tier?.name}{c.has_portal ? ' · Portal login' : ''}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted">The selected customer is the only account that will see this quotation in the Customer Portal after you send it.</p>
            <label className="field">
              Deal title
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            {customer?.has_portal ? <div className="badge teal">This customer has a portal login and will receive the quote there.</div> : customer ? <div className="badge gold">No portal login yet — they can sign up with {customer.email} to review the quote.</div> : null}
          </div>

          <div className="card card-pad">
            <h3>Catalog</h3>
            <div className="tabs" style={{ marginTop: 10 }} role="tablist" aria-label="Product type">
              {GROUPS.map((g) => (
                <button key={g.id} type="button" role="tab" aria-selected={group === g.id} className={`tab ${group === g.id ? 'active' : ''}`} onClick={() => setGroup(g.id)}>{g.label}</button>
              ))}
            </div>
            <label className="field" style={{ marginTop: 10 }}>
              Search catalog
              <input className="input" placeholder="SKU or name" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <div className="stack catalog-list" style={{ marginTop: 10 }}>
              {catalog.length === 0 ? <p className="muted">No products in this category.</p> : null}
              {catalog.map((p) => (
                <div className="spread" key={p.id}>
                  <div>
                    <strong>{p.name}</strong>
                    <div className="muted">{p.sku} · {p.category?.name || p.product_type} · {inr(p.base_price)}</div>
                  </div>
                  <Btn kind="ghost" onClick={() => addProduct(p)}>Add</Btn>
                </div>
              ))}
            </div>
          </div>

          <div className="card card-pad">
            <h3>Line items</h3>
            {lines.length === 0 ? <p className="muted">Add Hardware, Services, and Subscriptions from the catalog.</p> : null}
            {lines.map((l) => (
              <div key={l.product_id} className="stack" style={{ marginTop: 10, paddingBottom: 10, borderBottom: '1px solid var(--line)' }}>
                <div className="spread">
                  <div>
                    <strong>{l.name}</strong>
                    {l.category ? <div className="muted">{l.category}</div> : null}
                  </div>
                  <button className="btn ghost sm" type="button" onClick={() => setLines(lines.filter((x) => x.product_id !== l.product_id))}>Remove</button>
                </div>
                <div className="grid-2">
                  <label className="field">Qty
                    <input className="input" type="number" min={1} value={l.quantity} onChange={(e) => setLines(lines.map((x) => x.product_id === l.product_id ? { ...x, quantity: Math.max(1, Number(e.target.value) || 1) } : x))} />
                  </label>
                  <label className="field">Line discount %
                    <input className="input" type="number" min={0} max={100} value={l.discount_percent} onChange={(e) => setLines(lines.map((x) => x.product_id === l.product_id ? { ...x, discount_percent: Number(e.target.value) } : x))} />
                  </label>
                </div>
              </div>
            ))}
            <label className="field" style={{ marginTop: 12 }}>
              Order-level discount %
              <input className="input" type="number" min={0} max={100} value={orderDiscount} onChange={(e) => setOrderDiscount(Number(e.target.value) || 0)} />
              <span className="muted">Applied on top of every line discount when pricing this quote.</span>
            </label>
            {recs.length > 0 ? (
              <div className="stack" style={{ marginTop: 16 }}>
                <h3>Recommended for this deal</h3>
                {recs.map((r) => (
                  <div className="card card-pad" key={r.id}>
                    <div className="badge gold">{r.recommendation_type.replaceAll('_', ' ')}</div>
                    <strong style={{ display: 'block', marginTop: 6 }}>{r.product_name}</strong>
                    <p className="muted">{r.reason}</p>
                    <div className="muted">Revenue {inr(Number(r.additional_revenue))} · Profit {inr(Number(r.additional_profit))}</div>
                    <div className="row" style={{ marginTop: 8 }}>
                      <Btn kind="accent" onClick={() => addRec(r)}>Add</Btn>
                      <Btn kind="ghost" onClick={() => setDismissed((d) => [...d, r.id])}>Dismiss</Btn>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <aside className="intel-rail">
          <div className="card card-pad stack">
            <h3>Summary</h3>
            {!customerId || lines.length === 0 ? (
              <p className="muted">Select a customer and add products to see live totals from pricing policy.</p>
            ) : preview.isFetching && !preview.data ? (
              <p className="muted">Calculating…</p>
            ) : (
              <>
                <div className="factor"><span>Subtotal</span><span className="mono">{inr(totals.subtotal)}</span></div>
                <div className="factor"><span>Discount</span><span className="mono">{inr(totals.discount_total)}</span></div>
                <div className="factor"><span>Tax</span><span className="mono">{inr(totals.tax_total)}</span></div>
                <div className="factor"><strong>Grand total</strong><strong className="mono">{inr(totals.total)}</strong></div>
                <div className="factor"><span>Margin</span><span className="mono">{pct(totals.gross_margin_percent)}</span></div>
                <div className="factor">
                  <span>{risk.level ? `${risk.level.replaceAll('_', ' ')} risk` : 'Risk'}</span>
                  <RiskBadge score={risk.score} level={risk.level} />
                </div>
                {(risk.factors || []).slice(0, 4).map((f) => (
                  <p key={f.type + f.message} className="muted" style={{ margin: 0 }}>{f.message}</p>
                ))}
                <div className="factor">
                  <span>Approval</span>
                  <strong>{approval.required ? 'Required' : 'Clear'}</strong>
                </div>
                {(approval.reasons || []).map((r) => <p key={r} className="muted" style={{ margin: 0 }}>{r}</p>)}
              </>
            )}
            <Btn disabled={!canSave} onClick={() => create.mutate()}>
              {create.isPending ? 'Saving…' : 'Save draft'}
            </Btn>
          </div>
        </aside>
      </div>
    </div>
  )
}
