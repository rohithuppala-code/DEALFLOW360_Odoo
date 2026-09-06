import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { api, type ApiOk } from '../api/client'
import { Btn, Card, ConfirmDialog, ErrorState, Metric, PageHeader, RiskBadge, StatusBadge } from '../components/ui'
import { inr, pct } from '../utils/format'

type LineRow = {
  line_id: number
  product: string
  sku?: string
  category?: string
  quantity: number
  unit_price: number
  gross_amount: number
  net_amount: number
  margin_percent: number
  current_discount: number
  requested_discount: number
  allowed_discount: number
  excess_discount: number
  rule_name?: string
}

type NegoReq = {
  id: number
  category?: string
  current_discount?: string
  requested_value?: string
  reason?: string
  status: string
  exception_percent?: number
}

export default function ApprovalDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [comment, setComment] = useState('')
  const [confirm, setConfirm] = useState<null | 'reject' | 'request-changes'>(null)
  const q = useQuery({
    queryKey: ['approval', id],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown>>>(`/approvals/${id}`)).data.data,
  })
  const act = useMutation({
    mutationFn: async (path: string) => api.post(`/approvals/${id}/${path}`, { comment }),
    onSuccess: (_, path) => {
      toast.success(path === 'approve' ? 'Approved' : path === 'reject' ? 'Rejected' : 'Returned to sales rep')
      qc.invalidateQueries({ queryKey: ['approvals'] })
      qc.invalidateQueries({ queryKey: ['negotiations'] })
      nav('/approvals')
    },
  })
  const d = q.data
  const quote = (d?.quote || {}) as {
    id?: number
    quote_number?: string
    title?: string
    customer?: string
    sales_rep?: string
    total?: number
    subtotal?: number
    discount_total?: number
    margin?: number
    gross_profit?: number
    risk?: number
    tier?: string
    status?: string
    approval_status?: string
  }
  const why = (d?.why || {}) as { reasons?: string[]; factors?: { message: string; severity: number; type: string }[] }
  const steps = (d?.steps || []) as { id: number; role: string; status: string; comment?: string; sequence: number; approver?: string }[]
  const lines = (d?.lines || []) as LineRow[]
  const blended = (d?.blended || {}) as { deal_discount_percent?: number; has_exceptions?: boolean; max_exception_points?: number; risk_level?: string; exception_count?: number }
  const nego = (d?.negotiation || {}) as { id?: number; status?: string; comment?: string; requests?: NegoReq[] }
  const timeline = (d?.timeline || []) as { id: number; description: string; created_at?: string; actor?: string; type: string }[]
  const canAct = Boolean(d?.can_act)

  function run(path: string) {
    if (path !== 'approve' && !comment.trim()) {
      toast.error('Add a reason for the sales rep')
      return
    }
    if (path === 'reject' || path === 'request-changes') {
      setConfirm(path)
      return
    }
    act.mutate(path)
  }

  if (q.isError) return <ErrorState title="We couldn't load this approval." onRetry={() => q.refetch()} />
  if (!d) return <div className="card card-pad"><div className="skeleton" style={{ height: 28 }} /><div className="skeleton" style={{ marginTop: 12, height: 80 }} /></div>
  return (
    <div className="stack">
      <PageHeader
        kicker="Why this needs approval"
        title={quote.quote_number || 'Approval'}
        subtitle={`${quote.customer || ''}${quote.tier ? ` · ${quote.tier}` : ''} · Rep ${quote.sales_rep || '—'}`}
        actions={
          <>
            <StatusBadge value={quote.status} />
            <Btn kind="ghost" onClick={() => quote.id && nav(`/quotes/${quote.id}`)}>Open deal</Btn>
          </>
        }
      />
      <div className="grid-4">
        <Metric label="Value" value={inr(quote.total, true)} />
        <Metric label="Margin" value={pct(quote.margin)} hint={quote.gross_profit != null ? `Profit ${inr(quote.gross_profit, true)}` : undefined} />
        <Metric label="Risk" value={<RiskBadge score={quote.risk} level={blended.risk_level} />} />
        <Metric label="Deal discount" value={pct(blended.deal_discount_percent)} hint={blended.has_exceptions ? `${blended.exception_count || 0} line(s) over policy` : 'Within policy'} />
      </div>

      <Card>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Allowed %</th>
                <th>Requested %</th>
                <th>Excess %</th>
                <th>Net</th>
                <th>Margin</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((ln) => (
                <tr key={ln.line_id} className={ln.excess_discount > 0 ? 'row-warn' : undefined}>
                  <td>
                    {ln.product}
                    <div className="muted">{ln.sku} · {ln.category}</div>
                  </td>
                  <td>{ln.quantity}</td>
                  <td className="mono">{inr(ln.unit_price)}</td>
                  <td className="mono">{pct(ln.allowed_discount)}</td>
                  <td className="mono">{pct(ln.requested_discount)}</td>
                  <td className="mono">{ln.excess_discount > 0 ? pct(ln.excess_discount) : '—'}</td>
                  <td className="mono">{inr(ln.net_amount)}</td>
                  <td className="mono">{pct(ln.margin_percent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card-pad" style={{ borderTop: '1px solid var(--line)' }}>
          <div className="factor"><span>Subtotal</span><span className="mono">{inr(quote.subtotal)}</span></div>
          <div className="factor"><span>Discount</span><span className="mono">{inr(quote.discount_total)}</span></div>
          <div className="factor"><strong>Total</strong><strong className="mono">{inr(quote.total)}</strong></div>
        </div>
      </Card>

      {(nego.requests || []).length > 0 ? (
        <Card className="card-pad">
          <h3>Customer negotiation</h3>
          {nego.comment ? <p style={{ marginTop: 8 }}><strong>Customer comment:</strong> {nego.comment}</p> : null}
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Current discount</th>
                  <th>Requested discount</th>
                  <th>Comment</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(nego.requests || []).map((r) => (
                  <tr key={r.id}>
                    <td>{r.category || 'Discount'}</td>
                    <td className="mono">{r.current_discount ? `${r.current_discount}%` : '—'}</td>
                    <td className="mono">{r.requested_value}%</td>
                    <td>{r.reason || '—'}</td>
                    <td><StatusBadge value={r.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      <div className="grid-2">
        <Card className="card-pad">
          <h3>Policy reasons</h3>
          {(why.reasons || []).map((r) => <p key={r}>• {r}</p>)}
          {(why.factors || []).map((f) => (
            <div className="factor" key={f.type + f.message}>
              <div><strong>{f.type.replaceAll('_', ' ')}</strong><div className="muted">{f.message}</div></div>
              <span className="mono">+{Math.round(f.severity)}</span>
            </div>
          ))}
          {blended.max_exception_points ? (
            <p className="muted" style={{ marginTop: 8 }}>Blended excess over policy: {pct(blended.max_exception_points)} (max line).</p>
          ) : null}
          {canAct ? (
            <>
              <label className="field" style={{ marginTop: 12 }}>
                Reason / comment
                <textarea className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Stored on the approval and sent to the sales rep" />
              </label>
              <div className="row" style={{ marginTop: 12, flexWrap: 'wrap' }}>
                <Btn kind="accent" disabled={act.isPending} onClick={() => run('approve')}>Approve</Btn>
                <Btn kind="danger" disabled={act.isPending} onClick={() => run('reject')}>Reject</Btn>
                <Btn kind="ghost" disabled={act.isPending} onClick={() => run('request-changes')}>Return for revision</Btn>
              </div>
            </>
          ) : (
            <p className="muted" style={{ marginTop: 12 }}>Waiting for the current approver in the chain.</p>
          )}
        </Card>
        <Card className="card-pad">
          <h3>Approval chain</h3>
          {steps.map((s) => (
            <div className="factor" key={s.id}>
              <div>
                <strong>{s.role.replaceAll('_', ' ')}</strong>
                <div className="muted">{s.approver ? `${s.approver} · ` : ''}{s.comment || 'No comment yet'}</div>
              </div>
              <StatusBadge value={s.status} />
            </div>
          ))}
        </Card>
      </div>

      <Card className="card-pad">
        <h3>Audit trail</h3>
        <div className="timeline" style={{ marginTop: 10 }}>
          {timeline.length === 0 ? <p className="muted">No events recorded yet.</p> : timeline.map((e) => (
            <div className="t-item" key={e.id}>
              <div>{e.description}</div>
              <time>{e.created_at ? new Date(e.created_at).toLocaleString() : ''} · {e.actor || e.type}</time>
            </div>
          ))}
        </div>
      </Card>
      <ConfirmDialog
        open={confirm === 'reject'}
        title="Reject this deal?"
        body="The sales representative will be notified. A reason is required."
        confirmLabel="Reject"
        danger
        busy={act.isPending}
        onClose={() => setConfirm(null)}
        onConfirm={() => {
          act.mutate('reject')
          setConfirm(null)
        }}
      />
      <ConfirmDialog
        open={confirm === 'request-changes'}
        title="Return for revision?"
        body="The quote goes back to the sales representative with your instructions."
        confirmLabel="Return for revision"
        busy={act.isPending}
        onClose={() => setConfirm(null)}
        onConfirm={() => {
          act.mutate('request-changes')
          setConfirm(null)
        }}
      />
    </div>
  )
}
