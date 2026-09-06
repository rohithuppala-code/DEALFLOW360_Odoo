import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { api, type ApiOk, type Page } from '../api/client'
import type { Quote, QuoteLine } from '../types'
import { Btn, Card, Empty, ErrorState, PageHeader, StatusBadge } from '../components/ui'
import { inr, pct } from '../utils/format'

function lineGross(ln: QuoteLine) {
  return ln.quantity * ln.unit_price
}

function groupCategories(lines: QuoteLine[]) {
  const map = new Map<string, { name: string; category_id?: number; gross: number; net: number; discountAmt: number }>()
  for (const ln of lines) {
    const name = ln.product?.category || 'Other'
    const slot = map.get(name) || { name, category_id: ln.product?.category_id, gross: 0, net: 0, discountAmt: 0 }
    slot.gross += lineGross(ln)
    slot.net += ln.net_amount
    slot.discountAmt += ln.discount_amount || lineGross(ln) - ln.net_amount
    if (!slot.category_id && ln.product?.category_id) slot.category_id = ln.product.category_id
    map.set(name, slot)
  }
  return [...map.values()].map((s) => ({
    ...s,
    currentDiscount: s.gross ? (s.discountAmt / s.gross) * 100 : 0,
  }))
}

export function CustomerHome() {
  const nav = useNavigate()
  const q = useQuery({
    queryKey: ['cquotes'],
    queryFn: async () => (await api.get<ApiOk<Page<Quote>>>('/quotes', { params: { page_size: 50 } })).data.data,
    refetchInterval: 10000,
  })
  const items = q.data?.items || []
  if (q.isError) return <ErrorState title="We couldn't load your offers." onRetry={() => q.refetch()} />
  return (
    <div className="stack" style={{ gap: 20 }}>
      <PageHeader
        kicker="Customer portal"
        title="Your offers"
        subtitle="Review pricing, accept as presented, or request a different discount."
      />
      {items.length === 0 && !q.isLoading ? (
        <Empty title="No quotes shared yet" body="When a quote is sent to you, it will appear here." />
      ) : (
        <div className="stack" style={{ gap: 14 }}>
          {items.map((qt) => (
            <button
              key={qt.id}
              type="button"
              className="offer-card"
              onClick={() => nav(`/portal/quotes/${qt.id}`)}
            >
              <div>
                <div className="mono muted">{qt.quote_number}</div>
                <h3 className="offer-title">{qt.title}</h3>
                <StatusBadge value={qt.status} />
              </div>
              <div className="offer-side">
                <div className="offer-amount">{inr(qt.total)}</div>
                <span className="btn">Review</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function CustomerQuote() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [comment, setComment] = useState('')
  const q = useQuery({
    queryKey: ['cquote', id],
    queryFn: async () => (await api.get<ApiOk<Quote>>(`/quotes/${id}`)).data.data,
  })
  const nego = useQuery({
    queryKey: ['cnego', id],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown> | null>>(`/quotes/${id}/negotiation`)).data.data,
  })
  const qt = q.data
  const categories = useMemo(() => groupCategories(qt?.lines || []), [qt?.lines])
  const [requested, setRequested] = useState<Record<string, string>>({})

  const request = useMutation({
    mutationFn: async () =>
      (
        await api.post<ApiOk<Record<string, unknown>>>(`/quotes/${id}/negotiation`, {
          request_type: 'DISCOUNT',
          reason: comment,
          category_discounts: categories.map((c) => ({
            category_id: c.category_id,
            category: c.name,
            requested_percent: Number(requested[c.name] ?? c.currentDiscount.toFixed(1)),
          })),
        })
      ).data.data,
    onSuccess: () => {
      toast.success('Negotiation started — your request is with the sales manager')
      qc.invalidateQueries({ queryKey: ['cnego', id] })
      qc.invalidateQueries({ queryKey: ['cquote', id] })
    },
  })
  const accept = useMutation({
    mutationFn: async () => {
      const n = nego.data as { id?: number } | null
      if (n?.id) return api.post(`/negotiations/${n.id}/accept`)
      return api.post(`/quotes/${id}/negotiation`, { request_type: 'COMMENT', requested_value: 'accept', reason: 'Accepted as presented' })
    },
    onSuccess: () => toast.success('Accepted'),
  })
  if (q.isError) return <ErrorState title="We couldn't load this offer." onRetry={() => q.refetch()} />
  if (!qt) return <div className="card card-pad"><div className="skeleton" style={{ height: 28 }} /><div className="skeleton" style={{ marginTop: 12, height: 80 }} /></div>
  const analysis = (request.data?.analysis || {}) as { counteroffer?: Record<string, unknown>; requested_discount?: number }
  const pending = ((nego.data as { requests?: { id: number; category?: string; requested_value?: string; reason?: string; status: string; current_discount?: string }[] } | null)?.requests || []).filter((r) => r.status === 'PENDING')
  const subtotal = qt.lines.reduce((s, ln) => s + lineGross(ln), 0)
  const afterDiscount = qt.lines.reduce((s, ln) => s + ln.net_amount, 0)

  return (
    <div className="stack" style={{ gap: 20 }}>
      <PageHeader
        kicker="Commercial offer"
        title={qt.quote_number}
        subtitle={qt.title}
        actions={
          <div className="row">
            <StatusBadge value={qt.status} />
            <Btn kind="ghost" onClick={() => nav('/portal')}>All offers</Btn>
          </div>
        }
      />
      <div className="card card-pad">
        <div className="offer-amount">{inr(qt.total)}</div>
        <div className="muted">Valid until {qt.expires_at || '—'}</div>
      </div>
      <Card>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Item</th>
                <th className="num">Quantity</th>
                <th className="num">Price</th>
                <th className="num">Discount</th>
                <th className="num">Amount</th>
                <th className="num">After discount</th>
              </tr>
            </thead>
            <tbody>
              {qt.lines.map((ln) => (
                <tr key={ln.id}>
                  <td>
                    {ln.product?.name || ln.description}
                    <div className="muted">{ln.product?.category}</div>
                  </td>
                  <td className="num">{ln.quantity}</td>
                  <td className="num mono">{inr(ln.unit_price)}</td>
                  <td className="num mono">{pct(ln.discount_percent)}</td>
                  <td className="num mono">{inr(lineGross(ln))}</td>
                  <td className="num mono">{inr(ln.net_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card-pad" style={{ borderTop: '1px solid var(--line)' }}>
          <div className="factor"><span>Order subtotal</span><span className="mono">{inr(subtotal)}</span></div>
          <div className="factor"><span>Discount</span><span className="mono">{inr(subtotal - afterDiscount)}</span></div>
          <div className="factor"><span>Amount after discount</span><span className="mono">{inr(afterDiscount)}</span></div>
          <div className="factor"><strong>Order total (incl. tax/shipping)</strong><strong className="mono">{inr(qt.total)}</strong></div>
        </div>
      </Card>

      {categories.length > 0 ? (
        <Card className="card-pad">
          <h3>Category discounts</h3>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="num">Current discount</th>
                  <th className="num">Amount</th>
                  <th className="num">After discount</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((c) => (
                  <tr key={c.name}>
                    <td>{c.name}</td>
                    <td className="num mono">{pct(c.currentDiscount)}</td>
                    <td className="num mono">{inr(c.gross)}</td>
                    <td className="num mono">{inr(c.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      <Card className="card-pad stack">
        <h3>Your actions</h3>
        <div className="row">
          <Btn kind="accent" disabled={accept.isPending} onClick={() => accept.mutate()}>
            {accept.isPending ? 'Confirming…' : 'Confirm'}
          </Btn>
        </div>
        {categories.map((c) => (
          <label className="field" key={c.name}>
            {c.name} — requested discount %
            <input
              className="input"
              type="number"
              min={0}
              max={100}
              value={requested[c.name] ?? c.currentDiscount.toFixed(1)}
              onChange={(e) => setRequested({ ...requested, [c.name]: e.target.value })}
            />
            <span className="muted">Current {pct(c.currentDiscount)}</span>
          </label>
        ))}
        <label className="field">
          Comment / reason
          <textarea className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Tell the sales manager why you need a different discount" required />
        </label>
        <Btn kind="ghost" disabled={!comment.trim() || request.isPending} onClick={() => request.mutate()}>
          {request.isPending ? 'Sending…' : 'Propose discount'}
        </Btn>
        {pending.length > 0 ? (
          <div className="card card-pad">
            <h3>Submitted to sales manager</h3>
            {pending.map((r) => (
              <div className="factor" key={r.id}>
                <div>
                  <strong>{r.category || 'Discount'} → {r.requested_value}%</strong>
                  <div className="muted">{r.reason}</div>
                </div>
                <StatusBadge value={r.status} />
              </div>
            ))}
          </div>
        ) : null}
        {analysis.counteroffer && (
          <div className="card card-pad">
            <h3>Suggested counteroffer</h3>
            <p>{String(analysis.counteroffer.offer)}</p>
            {nego.data && (nego.data as { id?: number }).id ? (
              <Btn onClick={() => accept.mutate()}>Confirm</Btn>
            ) : null}
          </div>
        )}
      </Card>
    </div>
  )
}

export function CustomerInvoices() {
  const q = useQuery({
    queryKey: ['cinv'],
    queryFn: async () => (await api.get<ApiOk<Page<Record<string, unknown>>>>('/invoices')).data.data,
  })
  const items = q.data?.items || []
  if (q.isError) return <ErrorState title="We couldn't load invoices." onRetry={() => q.refetch()} />
  return (
    <div className="stack" style={{ gap: 20 }}>
      <PageHeader kicker="Accounts" title="Invoices" subtitle="Balances and payment status for your account." />
      <div className="card">
        {items.length === 0 && !q.isLoading ? (
          <Empty title="No invoices yet" body="Invoices appear here after an offer is confirmed." />
        ) : (
          <div className="table-wrap stack-sm">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th className="num">Total</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((inv) => (
                  <tr key={String(inv.id)}>
                    <td className="mono" data-label="#">{String(inv.invoice_number)}</td>
                    <td className="num mono" data-label="Total">{inr(Number(inv.total))}</td>
                    <td className="num mono" data-label="Balance">{inr(Number(inv.balance_due))}</td>
                    <td data-label="Status"><StatusBadge value={String(inv.status)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
