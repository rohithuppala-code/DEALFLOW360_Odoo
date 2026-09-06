import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { api, type ApiOk } from '../api/client'
import { Empty, ErrorState, PageHeader, RiskBadge, SkeletonGrid, StatusBadge } from '../components/ui'
import { inr } from '../utils/format'

type Row = {
  id: number
  reason: string
  risk_score: number
  is_reapproval: boolean
  quote?: { id: number; quote_number: string; customer: string; sales_rep?: string; total: number; margin: number; status: string }
}

type Nego = {
  id: number
  quote_id: number
  quote_number?: string
  customer?: string
  sales_rep?: string
  total: number
  quote_status?: string
  approval_id?: number | null
  exceeds_policy?: boolean
  comment?: string
  requests: { id: number; category?: string; requested_value?: string; reason?: string; current_discount?: string; status: string }[]
}

export default function ApprovalsPage() {
  const nav = useNavigate()
  const q = useQuery({
    queryKey: ['approvals'],
    queryFn: async () => (await api.get<ApiOk<Row[]>>('/approvals')).data.data,
    refetchInterval: 10000,
  })
  const nego = useQuery({
    queryKey: ['negotiations', 'inbox'],
    queryFn: async () => (await api.get<ApiOk<Nego[]>>('/negotiations', { params: { status: 'open' } })).data.data,
    refetchInterval: 10000,
  })
  const rows = q.data || []
  const negotiations = nego.data || []

  if (q.isError) return <ErrorState title="We couldn't load approvals." onRetry={() => q.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Governance"
        title="Approval Center"
        subtitle={`${rows.length} approval${rows.length === 1 ? '' : 's'} and ${negotiations.length} negotiation${negotiations.length === 1 ? '' : 's'} waiting.`}
      />

      {q.isLoading ? <SkeletonGrid n={4} /> : null}

      <section className="stack">
        <div className="kicker">Policy approvals</div>
        {rows.length === 0 && !q.isLoading ? (
          <div className="card"><Empty title="No pending approvals" body="You're all caught up on policy reviews." /></div>
        ) : (
          <div className="approval-grid">
            {rows.map((r) => (
              <button key={r.id} type="button" className="approval-card" onClick={() => nav(`/approvals/${r.id}`)}>
                <div>
                  <div className="kicker">Approval{r.is_reapproval ? ' · Reapproval' : ''}</div>
                  <h3>Approve {r.quote?.quote_number}</h3>
                  <p className="muted">{r.reason}</p>
                  <div className="muted" style={{ marginTop: 8 }}>
                    {r.quote?.customer} · {inr(r.quote?.total, true)} · {r.quote?.sales_rep || 'Unassigned'}
                  </div>
                  <div style={{ marginTop: 8 }}><RiskBadge score={r.risk_score} /></div>
                </div>
                <ArrowRight size={18} aria-hidden />
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="stack">
        <div className="kicker">Customer negotiations</div>
        {negotiations.length === 0 && !nego.isLoading ? (
          <div className="card"><Empty title="No open negotiations" body="When a customer starts a discount request, it appears here for the sales manager." /></div>
        ) : (
          <div className="approval-grid">
            {negotiations.map((n) => (
              <button
                key={n.id}
                type="button"
                className="approval-card"
                onClick={() => nav(n.approval_id ? `/approvals/${n.approval_id}` : `/quotes/${n.quote_id}?tab=Negotiate`)}
              >
                <div>
                  <div className="kicker">Negotiation{n.exceeds_policy ? ' · Over policy' : ''}</div>
                  <h3>{n.quote_number}</h3>
                  <p className="muted">{n.comment || n.requests[0]?.reason || 'Customer requested a change'}</p>
                  <div className="muted" style={{ marginTop: 8 }}>
                    {n.customer} · {n.sales_rep || 'Unassigned'}
                  </div>
                  {n.requests.map((r) => (
                    <div key={r.id} className="muted">
                      {r.category || 'Discount'} {r.current_discount ? `${r.current_discount}% → ` : ''}{r.requested_value}%
                    </div>
                  ))}
                  <div style={{ marginTop: 8 }}><StatusBadge value={n.quote_status || 'NEGOTIATING'} /></div>
                </div>
                <ArrowRight size={18} aria-hidden />
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
