import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { api, type ApiOk } from '../api/client'
import { useAuth } from '../auth'
import type { Quote } from '../types'
import { Btn, Card, ConfirmDialog, ErrorState, HealthScore, Metric, Modal, PageHeader, Percent, RiskBadge, StatusBadge } from '../components/ui'
import { DealStepper, NextAction } from '../components/workflow'
import { inr, pct } from '../utils/format'

const TABS = ['Lines', 'Insights', 'Simulate', 'Fulfill', 'Negotiate', 'History'] as const

export default function DealCenterPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const qc = useQueryClient()
  const { user } = useAuth()
  const [approvalComment, setApprovalComment] = useState('')
  const [pendingAction, setPendingAction] = useState<null | 'reject' | 'revise'>(null)
  const urlTab = sp.get('tab')
  const [tab, setTab] = useState<(typeof TABS)[number]>(() =>
    urlTab && (TABS as readonly string[]).includes(urlTab) ? (urlTab as (typeof TABS)[number]) : 'Lines',
  )
  const [tabParam, setTabParam] = useState(urlTab)
  if (urlTab !== tabParam) {
    setTabParam(urlTab)
    if (urlTab && (TABS as readonly string[]).includes(urlTab)) setTab(urlTab as (typeof TABS)[number])
  }
  const [opt, setOpt] = useState<Record<string, unknown> | null>(null)
  const [dismissed, setDismissed] = useState<number[]>([])
  const [orderDisc, setOrderDisc] = useState('0')
  const quoteQ = useQuery({
    queryKey: ['quote', id, user?.id, user?.role],
    queryFn: async () => (await api.get<ApiOk<Quote>>(`/quotes/${id}`)).data.data,
  })
  const copilot = useQuery({
    queryKey: ['copilot', id],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown>>>(`/quotes/${id}/copilot`)).data.data,
  })
  const recs = useQuery({
    queryKey: ['recs', id],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>(`/quotes/${id}/recommendations`)).data.data,
  })
  const timeline = useQuery({
    queryKey: ['timeline', id],
    queryFn: async () => (await api.get<ApiOk<{ id: number; description: string; created_at: string; type: string }[]>>(`/quotes/${id}/timeline`)).data.data,
  })
  const fulfillment = useQuery({
    queryKey: ['fulfill', id],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown>>>(`/quotes/${id}/fulfillment`)).data.data,
  })
  const nego = useQuery({
    queryKey: ['nego', id],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown> | null>>(`/quotes/${id}/negotiation`)).data.data,
  })
  const q = quoteQ.data
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['quote', id] })
    qc.invalidateQueries({ queryKey: ['copilot', id] })
    qc.invalidateQueries({ queryKey: ['recs', id] })
    qc.invalidateQueries({ queryKey: ['fulfill', id] })
    qc.invalidateQueries({ queryKey: ['nego', id] })
    qc.invalidateQueries({ queryKey: ['timeline', id] })
    qc.invalidateQueries({ queryKey: ['approvals'] })
  }

  const patchLine = useMutation({
    mutationFn: async ({ lineId, quantity, discount }: { lineId: number; quantity?: number; discount?: number }) =>
      api.patch(`/quotes/${id}/lines/${lineId}`, { quantity, discount_percent: discount }),
    onSuccess: () => { toast.success('Line updated · pricing refreshed'); invalidate() },
  })
  const patchDisc = useMutation({
    mutationFn: async ({ lineId, discount }: { lineId: number; discount: number }) =>
      api.patch(`/quotes/${id}/lines/${lineId}/discount`, { discount_percent: discount }),
    onSuccess: () => { toast.success('Discount recalculated'); invalidate() },
  })
  const applyOrderDisc = useMutation({
    mutationFn: async () => api.put(`/quotes/${id}`, { order_discount_percent: Number(orderDisc) || 0 }),
    onSuccess: () => { toast.success('Order discount applied'); invalidate() },
  })
  const refresh = useMutation({
    mutationFn: async () => {
      await api.post(`/quotes/${id}/calculate`)
      await api.get(`/quotes/${id}/fulfillment`)
      await api.get(`/quotes/${id}/recommendations`)
    },
    onSuccess: () => { toast.success('Pricing, stock, and approval refreshed'); invalidate() },
  })
  const submit = useMutation({ mutationFn: async () => api.post(`/quotes/${id}/submit`), onSuccess: () => { toast.success('Submitted for approval'); invalidate() } })
  const send = useMutation({ mutationFn: async () => api.post(`/quotes/${id}/send`), onSuccess: () => { toast.success('Sent to customer'); invalidate() } })
  const confirm = useMutation({ mutationFn: async () => api.post(`/quotes/${id}/confirm`), onSuccess: () => { toast.success('Order confirmed'); invalidate() } })
  const approveDeal = useMutation({
    mutationFn: async (comment?: string) => {
      const approvalId = q?.current_approval?.id || q?.workflow?.active_approval_id
      try {
        return (await api.post(`/quotes/${id}/approve`, { comment })).data
      } catch (err: any) {
        if (err?.response?.status === 404 && approvalId) {
          return (await api.post(`/approvals/${approvalId}/approve`, { comment })).data
        }
        throw err
      }
    },
    onSuccess: () => {
      toast.success('Deal approved successfully')
      setApprovalComment('')
      invalidate()
    },
  })
  const rejectDeal = useMutation({
    mutationFn: async (comment?: string) => {
      const approvalId = q?.current_approval?.id || q?.workflow?.active_approval_id
      try {
        return (await api.post(`/quotes/${id}/reject`, { comment })).data
      } catch (err: any) {
        if (err?.response?.status === 404 && approvalId) {
          return (await api.post(`/approvals/${approvalId}/reject`, { comment })).data
        }
        throw err
      }
    },
    onSuccess: () => {
      toast.success('Deal rejected')
      setApprovalComment('')
      invalidate()
    },
  })
  const reviseDeal = useMutation({
    mutationFn: async (comment?: string) => {
      const approvalId = q?.current_approval?.id || q?.workflow?.active_approval_id
      try {
        return (await api.post(`/quotes/${id}/request-changes`, { comment })).data
      } catch (err: any) {
        if (err?.response?.status === 404 && approvalId) {
          return (await api.post(`/approvals/${approvalId}/request-changes`, { comment })).data
        }
        throw err
      }
    },
    onSuccess: () => {
      toast.success('Returned to sales rep for revision')
      setApprovalComment('')
      invalidate()
    },
  })
  const applyRec = useMutation({
    mutationFn: async (rid: number) => api.post(`/quotes/${id}/recommendations/${rid}/apply`),
    onSuccess: () => { toast.success('Added to quote'); invalidate(); qc.invalidateQueries({ queryKey: ['recs', id] }) },
  })
  const optMut = useMutation({
    mutationFn: async () => (await api.post<ApiOk<Record<string, unknown>>>(`/quotes/${id}/optimize`)).data.data,
    onSuccess: (d) => setOpt(d),
  })
  const applyOpt = useMutation({
    mutationFn: async () => api.post(`/quotes/${id}/optimize/apply`),
    onSuccess: () => { toast.success('Optimization applied'); setOpt(null); invalidate() },
  })
  const fulfillOpt = useMutation({
    mutationFn: async () => (await api.post<ApiOk<Record<string, unknown>>>(`/quotes/${id}/fulfillment/optimize`)).data.data,
    onSuccess: () => { toast.success('Optimized plan ready'); qc.invalidateQueries({ queryKey: ['fulfill', id] }) },
  })
  const fulfillApply = useMutation({
    mutationFn: async () => api.post(`/quotes/${id}/fulfillment/apply`),
    onSuccess: () => { toast.success('Fulfillment plan applied'); invalidate(); qc.invalidateQueries({ queryKey: ['fulfill', id] }) },
  })

  if (quoteQ.isError) return <ErrorState title="We couldn't load this deal." onRetry={() => quoteQ.refetch()} />
  if (!q) return <div className="card card-pad"><div className="skeleton" style={{ height: 28 }} /><div className="skeleton" style={{ marginTop: 12, height: 80 }} /></div>
  const intel = (q.intelligence || {}) as Record<string, unknown>
  const health = (intel.health || {}) as { score?: number; level?: string; strengths?: string[]; risks?: string[]; components?: { label: string; points: number }[] }
  const risk = (intel.risk || { factors: q.risk_factors }) as { score?: number; level?: string; factors?: { type: string; severity: number; message: string }[] }
  const guardian = (intel.margin_guardian || {}) as { customer_saving?: number; profit_lost?: number; recommendation?: { recommended: string } }
  const approval = (intel.approval_preview || {}) as { required?: boolean; reasons?: string[]; roles?: string[] }
  const busy = submit.isPending || send.isPending || confirm.isPending || approveDeal.isPending || rejectDeal.isPending || reviseDeal.isPending
  const canApprove = Boolean(
    q.workflow?.can_approve ||
    q.current_approval?.can_act ||
    user?.role === 'ADMIN' ||
    (user?.role === 'SALES_MANAGER' && q.status === 'PENDING_APPROVAL' && (!q.workflow?.active_approver_role || q.workflow?.active_approver_role === 'SALES_MANAGER')) ||
    (user?.role === 'FINANCE' && q.status === 'PENDING_APPROVAL' && q.workflow?.active_approver_role === 'FINANCE')
  )
  const isFinance = user?.role === 'FINANCE'
  const isWaitingOnManager = q.status === 'PENDING_APPROVAL' && !canApprove && isFinance && Boolean(q.current_approval?.steps?.some((s) => s.role === 'FINANCE'))

  return (
    <div className="stack">
      <PageHeader
        kicker={q.quote_number}
        title={q.title || 'Deal'}
        subtitle={`${q.customer?.name || 'Customer'}${q.customer?.tier?.name ? ` · ${q.customer.tier.name}` : ''} · ${q.sales_rep?.name || 'Unassigned'}`}
        actions={
          <>
            <HealthScore score={q.deal_health_score} />
            <Btn kind="ghost" disabled={refresh.isPending} onClick={() => refresh.mutate()}>{refresh.isPending ? 'Refreshing…' : 'Refresh'}</Btn>
            {canApprove ? (
              <Btn
                kind="accent"
                disabled={busy}
                onClick={() => {
                  const el = document.getElementById('approval-decision-card')
                  if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    const textarea = el.querySelector('textarea')
                    if (textarea) textarea.focus()
                  } else {
                    approveDeal.mutate(approvalComment || undefined)
                  }
                }}
              >
                Review & approve
              </Btn>
            ) : null}
            {q.workflow?.can_send && !q.sent_to_customer_at ? (
              <Btn kind="accent" disabled={send.isPending} onClick={() => send.mutate()}>{send.isPending ? 'Sending…' : 'Send to customer'}</Btn>
            ) : null}
            <Btn kind="ghost" onClick={() => optMut.mutate()}>Optimize</Btn>
          </>
        }
      />
      <div className="row" style={{ flexWrap: 'wrap' }}>
        <StatusBadge value={q.status} />
        <RiskBadge score={q.risk_score} level={risk.level} />
        <StatusBadge value={q.approval_status} />
        {q.sent_to_customer_at ? <span className="badge teal">Shared with customer</span> : null}
      </div>

      <DealStepper workflow={q.workflow} />
      <NextAction
        workflow={q.workflow}
        busy={busy}
        onSubmit={() => submit.mutate()}
        onSend={() => send.mutate()}
        onConfirm={() => confirm.mutate()}
        onNegotiate={() => setTab('Negotiate')}
        onBilling={() => nav('/billing')}
        onApprove={() => {
          const el = document.getElementById('approval-decision-card')
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' })
            const textarea = el.querySelector('textarea')
            if (textarea) textarea.focus()
          }
        }}
      />

      {canApprove ? (
        <Card id="approval-decision-card" className="card-pad stack approval-decision">
          <div className="spread">
            <div>
              <span className="badge teal" style={{ marginBottom: 6 }}>Approval</span>
              <h3 style={{ margin: '4px 0' }}>
                {q.workflow?.active_approver_role?.replaceAll('_', ' ') || user?.role?.replaceAll('_', ' ')}
              </h3>
              <p className="muted" style={{ margin: 0 }}>
                {q.current_approval?.reason || (q.workflow?.approval_reasons && q.workflow.approval_reasons[0]) || 'This deal requires management approval before it can be sent to the customer.'}
              </p>
            </div>
            <div className="row">
              <Btn kind="ghost" onClick={() => (q.current_approval?.id ? nav(`/approvals/${q.current_approval.id}`) : nav('/approvals'))}>
                Open in Approval Inbox
              </Btn>
            </div>
          </div>

          {q.current_approval?.steps && q.current_approval.steps.length > 1 ? (
            <div style={{ padding: 12, borderRadius: 8, background: 'var(--cream-100)' }}>
              <div className="kicker" style={{ marginBottom: 8 }}>Approval chain</div>
              <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
                {q.current_approval.steps.map((s) => (
                  <div key={s.id} className="row" style={{ gap: 8, alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>
                      Step {s.sequence}: {s.role.replace('_', ' ')}
                    </span>
                    <StatusBadge value={s.status} />
                    {s.comment ? <span className="muted" style={{ fontSize: 12 }}>({s.comment})</span> : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div style={{ marginTop: 8 }}>
            <label className="field" style={{ margin: 0 }}>
              Decision comment / instructions
              <textarea
                className="input"
                rows={2}
                value={approvalComment}
                onChange={(e) => setApprovalComment(e.target.value)}
                placeholder="Add notes or instructions for the sales rep (optional for approval, required for rejection/revision)"
              />
            </label>
            <div className="row" style={{ marginTop: 12, flexWrap: 'wrap', gap: 10 }}>
              <Btn
                kind="accent"
                disabled={busy}
                onClick={() => approveDeal.mutate(approvalComment || undefined)}
              >
                {approveDeal.isPending ? 'Approving…' : 'Approve'}
              </Btn>
              <Btn
                kind="danger"
                disabled={busy}
                onClick={() => {
                  if (!approvalComment.trim()) {
                    toast.error('Please enter a reason for rejecting this deal')
                    return
                  }
                  setPendingAction('reject')
                }}
              >
                Reject
              </Btn>
              <Btn
                kind="ghost"
                disabled={busy}
                onClick={() => {
                  if (!approvalComment.trim()) {
                    toast.error('Please enter revision instructions for the sales rep')
                    return
                  }
                  setPendingAction('revise')
                }}
              >
                Return for revision
              </Btn>
            </div>
          </div>
        </Card>
      ) : isWaitingOnManager ? (
        <Card
          className="card-pad stack"
          style={{
            border: '1px solid var(--border)',
            background: 'var(--warn-soft)',
          }}
        >
          <div className="spread">
            <div>
              <span className="badge warn" style={{ marginBottom: 6 }}>Pipeline: Step 1 In Progress</span>
              <h3 style={{ margin: '4px 0' }}>Queued for Sales Manager (Step 1 of 2)</h3>
              <p className="muted" style={{ margin: 0 }}>
                This high-risk deal requires two-stage governance: Sales Manager review first, followed by Finance approval. Once the Sales Manager approves, this deal will immediately unlock for your Finance review and approval.
              </p>
            </div>
            <Btn kind="ghost" onClick={() => (q.current_approval?.id ? nav(`/approvals/${q.current_approval.id}`) : nav('/approvals'))}>
              View in Approval Center
            </Btn>
          </div>
          {q.current_approval?.steps && (
            <div className="row" style={{ gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
              {q.current_approval.steps.map((s) => (
                <div key={s.id} className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    Step {s.sequence}: {s.role.replace('_', ' ')}
                  </span>
                  <StatusBadge value={s.status} />
                </div>
              ))}
            </div>
          )}
        </Card>
      ) : null}

      <div className="grid-4">
        <Metric label="Total" value={inr(q.total, true)} />
        <Metric label="Net revenue" value={inr((q.subtotal || 0) - (q.discount_total || 0), true)} />
        <Metric label="Gross profit" value={inr(q.gross_profit, true)} />
        <Metric label="Margin" value={<Percent value={q.gross_margin_percent} />} hint={`Discount ${inr(q.discount_total)}`} />
      </div>

      <div className="deal-grid">
        <div className="stack">
          <div className="tabs" role="tablist" aria-label="Deal sections">
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                className={`tab ${tab === t ? 'active' : ''}`}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === 'Lines' && (
            <div className="stack">
              <Card>
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Product</th><th>Qty</th><th>Price</th><th>Discount %</th><th>Net</th><th>Margin</th></tr></thead>
                    <tbody>
                      {q.lines.map((ln) => (
                        <tr key={ln.id}>
                          <td>{ln.product?.name}<div className="muted">{ln.product?.sku} · {ln.product?.category}</div></td>
                          <td>
                            <input
                              className="input"
                              style={{ maxWidth: 72 }}
                              type="number"
                              min={1}
                              defaultValue={ln.quantity}
                              key={`qty-${ln.id}-${ln.quantity}`}
                              onBlur={(e) => {
                                const qty = Math.max(1, Number(e.target.value) || 1)
                                if (qty !== ln.quantity) patchLine.mutate({ lineId: ln.id, quantity: qty })
                              }}
                            />
                          </td>
                          <td className="mono">{inr(ln.unit_price)}</td>
                          <td>
                            <input
                              className="input"
                              style={{ maxWidth: 88 }}
                              type="number"
                              defaultValue={ln.discount_percent}
                              key={`disc-${ln.id}-${ln.discount_percent}`}
                              onBlur={(e) => patchDisc.mutate({ lineId: ln.id, discount: Number(e.target.value) })}
                            />
                          </td>
                          <td className="mono">{inr(ln.net_amount)}</td>
                          <td><Percent value={ln.margin_percent} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="card-pad row" style={{ borderTop: '1px solid var(--line)', flexWrap: 'wrap' }}>
                  <label className="field" style={{ margin: 0, minWidth: 180 }}>
                    Order-level discount %
                    <input className="input" type="number" min={0} max={100} value={orderDisc} onChange={(e) => setOrderDisc(e.target.value)} />
                  </label>
                  <Btn disabled={applyOrderDisc.isPending} onClick={() => applyOrderDisc.mutate()}>Apply to all lines</Btn>
                </div>
              </Card>
              {((recs.data || []).filter((r) => !dismissed.includes(Number(r.id)))).length > 0 ? (
                <Card className="card-pad stack">
                  <h3>Upsell / cross-sell</h3>
                  {(recs.data || []).filter((r) => !dismissed.includes(Number(r.id))).map((r) => (
                    <div className="spread" key={String(r.id)}>
                      <div>
                        <div className="badge gold">{String(r.recommendation_type)}</div>
                        <strong style={{ display: 'block', marginTop: 6 }}>{String(r.product_name)}</strong>
                        <p className="muted">{String(r.reason)}</p>
                        <div className="muted">Revenue {inr(Number(r.additional_revenue))} · Profit {inr(Number(r.additional_profit))}</div>
                      </div>
                      <div className="row">
                        <Btn onClick={() => applyRec.mutate(Number(r.id))}>Add</Btn>
                        <Btn kind="ghost" onClick={() => setDismissed((d) => [...d, Number(r.id)])}>Dismiss</Btn>
                      </div>
                    </div>
                  ))}
                </Card>
              ) : null}
            </div>
          )}

          {tab === 'Insights' && (
            <div className="stack">
              <Card className="card-pad">
                <h3>Deal Copilot</h3>
                <p>{String(copilot.data?.headline || 'Analyzing deal…')}</p>
                <div className="grid-2" style={{ marginTop: 12 }}>
                  {['margin', 'discount', 'inventory', 'delivery', 'approval'].map((k) => (
                    <div key={k}><div className="muted">{k}</div><strong>{String(copilot.data?.[k] || '—')}</strong></div>
                  ))}
                </div>
              </Card>
              {((copilot.data?.actions as Record<string, unknown>[]) || []).map((a) => (
                <Card className="card-pad" key={String(a.id)}>
                  <div className="badge teal">{String(a.kind)} · {String(a.priority)}</div>
                  <h3 style={{ marginTop: 8 }}>{String(a.title)}</h3>
                  <p className="muted">{String(a.reason)}</p>
                </Card>
              ))}
              {(recs.data || []).filter((r) => !dismissed.includes(Number(r.id))).map((r) => (
                <Card className="card-pad" key={String(r.id)}>
                  <div className="spread">
                    <div>
                      <div className="badge gold">{String(r.recommendation_type)}</div>
                      <h3 style={{ marginTop: 6 }}>{String(r.product_name)}</h3>
                      <p>{String(r.reason)}</p>
                      <div className="muted">Revenue {inr(Number(r.additional_revenue))} · Profit {inr(Number(r.additional_profit))}</div>
                    </div>
                    <div className="row">
                      <Btn onClick={() => applyRec.mutate(Number(r.id))}>Add</Btn>
                      <Btn kind="ghost" onClick={() => setDismissed((d) => [...d, Number(r.id)])}>Dismiss</Btn>
                    </div>
                  </div>
                </Card>
              ))}
              <Card className="card-pad">
                <h3>Hybrid billing</h3>
                <div className="grid-3">
                  <Metric label="One-time" value={inr(Number((q.billing as { one_time?: number } | undefined)?.one_time), true)} />
                  <Metric label="MRR" value={inr(Number((q.billing as { mrr?: number } | undefined)?.mrr), true)} />
                  <Metric label="Due today" value={inr(q.total, true)} />
                </div>
              </Card>
            </div>
          )}

          {tab === 'Simulate' && <Simulator quoteId={Number(id)} lines={q.lines} onApplied={invalidate} />}

          {tab === 'Fulfill' && (
            <FulfillmentPanel
              quoteId={Number(id)}
              data={fulfillment.data}
              optimized={fulfillOpt.data}
              onOptimize={() => fulfillOpt.mutate()}
              onApply={() => fulfillApply.mutate()}
              onRefresh={() => { invalidate(); qc.invalidateQueries({ queryKey: ['fulfill', id] }) }}
            />
          )}

          {tab === 'Negotiate' && <NegotiationPanel quoteId={Number(id)} data={nego.data} onChange={() => { invalidate(); qc.invalidateQueries({ queryKey: ['nego', id] }) }} />}

          {tab === 'History' && (
            <Card className="card-pad">
              <div className="timeline">
                {(timeline.data || []).length === 0 ? <p className="muted">No events recorded yet.</p> : null}
                {(timeline.data || []).map((e) => (
                  <div className="t-item" key={e.id}>
                    <div>{e.description}</div>
                    <time>{new Date(e.created_at).toLocaleString()} · {e.type}</time>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        <aside className="intel-rail">
          <Card className="card-pad">
            <h3>Summary</h3>
            <div className="factor"><span>Subtotal</span><span className="mono">{inr(q.subtotal)}</span></div>
            <div className="factor"><span>Discount</span><span className="mono">{inr(q.discount_total)}</span></div>
            <div className="factor"><span>Tax</span><span className="mono">{inr(q.tax_total)}</span></div>
            <div className="factor"><strong>Total</strong><strong className="mono">{inr(q.total)}</strong></div>
            <div className="factor"><span>Margin</span><span><Percent value={q.gross_margin_percent} /></span></div>
          </Card>
          <Card className="card-pad">
            <h3>Health composition</h3>
            {(health.components || []).map((c) => (
              <div className="factor" key={c.label}><span>{c.label}</span><span className="mono">{c.points > 0 ? '+' : ''}{c.points}</span></div>
            ))}
            <h3 style={{ marginTop: 16 }}>Strengths</h3>
            <ul>{(health.strengths || ['None listed']).map((s) => <li key={s}>{s}</li>)}</ul>
            <h3>Watch-outs</h3>
            <ul>{(health.risks || ['None flagged']).map((s) => <li key={s}>{s}</li>)}</ul>
          </Card>
          <Card className="card-pad">
            <div className="spread">
              <h3>{risk.level ? `${risk.level.replaceAll('_', ' ')} risk` : 'Risk'}</h3>
              <RiskBadge score={q.risk_score} level={risk.level} />
            </div>
            {(risk.factors || q.risk_factors || []).slice(0, 6).map((f) => (
              <div className="factor" key={f.type + f.message}>
                <div>
                  <strong>{f.type.replaceAll('_', ' ')}</strong>
                  <div className="muted">{f.message}</div>
                </div>
                <span className="mono">+{Math.round(f.severity)}</span>
              </div>
            ))}
          </Card>
          <Card className="card-pad">
            <h3>Why approval</h3>
            {(approval.reasons || q.workflow?.approval_reasons || ['No approval required under current policy.']).map((r) => <p key={r}>• {r}</p>)}
            <div className="muted">Roles: {(approval.roles || q.workflow?.approval_roles || []).join(', ') || 'None'}</div>
            {guardian.recommendation ? (
              <div className="badge warn" style={{ marginTop: 10, display: 'block', borderRadius: 10, padding: 10 }}>
                Margin Guardian: {guardian.recommendation.recommended}
              </div>
            ) : null}
            <div style={{ marginTop: 12 }}><Btn kind="ghost" onClick={() => nav('/approvals')}>Open approval inbox</Btn></div>
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        open={pendingAction === 'reject'}
        title="Reject this deal?"
        body="The sales representative will be notified. A reason is required."
        confirmLabel="Reject"
        danger
        busy={rejectDeal.isPending}
        onClose={() => setPendingAction(null)}
        onConfirm={() => {
          rejectDeal.mutate(approvalComment)
          setPendingAction(null)
        }}
      />
      <ConfirmDialog
        open={pendingAction === 'revise'}
        title="Return for revision?"
        body="The quote goes back to the sales representative with your instructions."
        confirmLabel="Return for revision"
        busy={reviseDeal.isPending}
        onClose={() => setPendingAction(null)}
        onConfirm={() => {
          reviseDeal.mutate(approvalComment)
          setPendingAction(null)
        }}
      />
      <Modal open={Boolean(opt)} title="Optimize deal · Before → After" onClose={() => setOpt(null)}>
        {opt && (
          <div className="stack">
            {['revenue', 'margin', 'risk', 'shipments', 'shipping'].map((k) => {
              const cur = (opt.current as Record<string, number>)?.[k]
              const nxt = (opt.optimized as Record<string, number>)?.[k]
              return (
                <div className="factor" key={k}>
                  <span>{k}</span>
                  <span className="mono">{k === 'margin' || k === 'risk' || k === 'shipments' ? cur : inr(cur, true)} → {k === 'margin' || k === 'risk' || k === 'shipments' ? nxt : inr(nxt, true)}</span>
                </div>
              )
            })}
            <ul>{((opt.changes as { description: string }[]) || []).map((c) => <li key={c.description}>{c.description}</li>)}</ul>
            <Btn onClick={() => applyOpt.mutate()}>Apply optimization</Btn>
          </div>
        )}
      </Modal>
    </div>
  )
}

function Simulator({ quoteId, lines, onApplied }: { quoteId: number; lines: Quote['lines']; onApplied: () => void }) {
  const [discounts, setDiscounts] = useState<Record<string, number>>({})
  const [support, setSupport] = useState(false)
  const [consol, setConsol] = useState(false)
  const run = useMutation({
    mutationFn: async () =>
      (await api.post<ApiOk<Record<string, unknown>>>(`/quotes/${quoteId}/simulate`, {
        line_discounts: discounts,
        add_premium_support: support,
        consolidate_warehouse: consol,
      })).data.data,
  })
  const apply = useMutation({
    mutationFn: async (sid: number) => api.post(`/quotes/${quoteId}/simulate/${sid}/apply`),
    onSuccess: () => { toast.success('Scenario applied'); onApplied() },
  })
  const d = run.data
  return (
    <Card className="card-pad stack">
      <h3>What-if simulator</h3>
      <p className="muted">Preview margin and risk before you change the live quote.</p>
      {lines.map((ln) => (
        <label className="field" key={ln.id}>
          {ln.product?.name} discount {discounts[String(ln.id)] ?? ln.discount_percent}%
          <input type="range" min={0} max={30} value={discounts[String(ln.id)] ?? ln.discount_percent}
            onChange={(e) => setDiscounts({ ...discounts, [ln.id]: Number(e.target.value) })} />
        </label>
      ))}
      <label className="row"><input type="checkbox" checked={support} onChange={(e) => setSupport(e.target.checked)} /> Add Premium Support</label>
      <label className="row"><input type="checkbox" checked={consol} onChange={(e) => setConsol(e.target.checked)} /> Consolidate warehouse</label>
      <Btn onClick={() => run.mutate()}>Run scenario</Btn>
      {d && (
        <div className="grid-2">
          <Metric label="Current margin" value={pct(Number((d.current as { margin: number }).margin))} />
          <Metric label="Projected margin" value={pct(Number((d.projected as { margin: number }).margin))} />
          <Metric label="Current risk" value={Number((d.current as { risk: number }).risk)} />
          <Metric label="Projected risk" value={Number((d.projected as { risk: number }).risk)} />
          <Metric label="Profit impact" value={inr(Number((d.deltas as { profit: number }).profit))} />
          <Btn onClick={() => apply.mutate(Number(d.simulation_id))}>Apply scenario</Btn>
        </div>
      )}
    </Card>
  )
}

function FulfillmentPanel({
  quoteId,
  data,
  optimized,
  onOptimize,
  onApply,
  onRefresh,
}: {
  quoteId: number
  data?: Record<string, unknown>
  optimized?: Record<string, unknown>
  onOptimize: () => void
  onApply: () => void
  onRefresh: () => void
}) {
  const { user } = useAuth()
  const ops = user?.role === 'FINANCE' || user?.role === 'OPERATIONS' || user?.role === 'ADMIN' || user?.role === 'SALES_MANAGER'
  const current = (optimized?.current || data?.current || {}) as {
    warehouses?: { name: string; lines: { product: string; product_id?: number; quantity: number; is_backorder?: boolean }[] }[]
    shipments?: number
    shipping_cost?: number
    backorder_qty?: number
    backorders?: { product_id: number; backorder_qty: number; requested_qty: number; available_qty: number; expected_replenishment?: string }[]
  }
  const rec = (optimized?.recommended || data?.recommended || {}) as { warehouses?: { name: string; lines: { product: string; quantity: number }[] }[]; shipments?: number; shipping_cost?: number }
  const availability = (data?.availability || []) as { product_id: number; product: string; quantity: number; warehouses: { warehouse_id: number; name: string; free: number }[] }[]
  const [manual, setManual] = useState<Record<string, { warehouse_id: number; quantity: number }>>({})
  const saveAlloc = useMutation({
    mutationFn: async () => {
      const allocations = availability.map((p) => {
        const row = manual[p.product_id] || { warehouse_id: p.warehouses[0]?.warehouse_id, quantity: p.quantity }
        return { product_id: p.product_id, warehouse_id: Number(row.warehouse_id), quantity: Number(row.quantity || p.quantity) }
      }).filter((a) => a.warehouse_id && a.quantity > 0)
      return api.post(`/quotes/${quoteId}/fulfillment/allocate`, { allocations })
    },
    onSuccess: () => { toast.success('Warehouse split saved'); onRefresh() },
  })
  const consolidate = useMutation({
    mutationFn: async () => api.post(`/quotes/${quoteId}/fulfillment/consolidate`),
    onSuccess: () => { toast.success('Backorders rechecked against current stock'); onRefresh() },
  })
  return (
    <div className="stack">
      <div className="grid-2">
        <Card className="card-pad">
          <h3>Current plan</h3>
          {(current.warehouses || []).map((w) => (
            <div key={w.name} style={{ marginTop: 8 }}>
              <strong>{w.name}</strong>
              {w.lines.map((l) => (
                <div className="factor" key={l.product}>
                  <span>{l.product}{l.is_backorder ? <span className="badge warn" style={{ marginLeft: 8 }}>Backorder</span> : null}</span>
                  <span className="mono">{l.quantity}</span>
                </div>
              ))}
            </div>
          ))}
          <div className="factor"><span>Allocated shipments</span><span className="mono">{current.shipments ?? '—'}</span></div>
          <div className="factor"><span>Shipping</span><span className="mono">{inr(current.shipping_cost)}</span></div>
          <div className="factor"><span>Backordered</span><span className="mono">{current.backorder_qty ?? 0}</span></div>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <Btn onClick={onOptimize}>Optimize fulfillment</Btn>
            {ops && (current.backorder_qty || 0) > 0 ? (
              <Btn kind="ghost" disabled={consolidate.isPending} onClick={() => consolidate.mutate()}>Consolidate backorders</Btn>
            ) : null}
          </div>
        </Card>
        <Card className="card-pad">
          <h3>Recommended plan</h3>
          {(rec.warehouses || []).map((w) => (
            <div key={w.name} style={{ marginTop: 8 }}>
              <strong>{w.name}</strong>
              {w.lines.map((l) => <div key={l.product} className="muted">{l.quantity} × {l.product}</div>)}
            </div>
          ))}
          {rec.shipments != null ? <p>Shipments {rec.shipments} · Shipping {inr(rec.shipping_cost)}</p> : <p className="muted">Run optimize to compare shipment count and cost.</p>}
          {rec.shipments != null ? <Btn kind="accent" onClick={onApply}>Accept suggested split</Btn> : null}
        </Card>
      </div>
      {(current.backorders || []).length > 0 ? (
        <Card className="card-pad">
          <h3>Backorders</h3>
          {(current.backorders || []).map((b) => (
            <div key={b.product_id} style={{ marginTop: 8 }}>
              <strong>Product {b.product_id}</strong>
              <div className="factor"><span>Requested</span><span className="mono">{b.requested_qty}</span></div>
              <div className="factor"><span>Available</span><span className="mono">{b.available_qty}</span></div>
              <div className="factor"><span>Allocated</span><span className="mono">{Math.max(0, b.requested_qty - b.backorder_qty)}</span></div>
              <div className="factor"><span>Backordered</span><span className="mono">{b.backorder_qty}</span></div>
              <div className="muted">{b.expected_replenishment ? `ETA ${b.expected_replenishment}` : 'No ETA'}</div>
            </div>
          ))}
        </Card>
      ) : null}
      {ops && availability.length > 0 ? (
        <Card className="card-pad stack">
          <h3>Manual warehouse override</h3>
          {availability.map((p) => {
            const row = manual[p.product_id] || { warehouse_id: p.warehouses.find((w) => w.free > 0)?.warehouse_id || p.warehouses[0]?.warehouse_id, quantity: p.quantity }
            return (
              <div className="grid-2" key={p.product_id}>
                <div>
                  <strong>{p.product}</strong>
                  <div className="muted">Need {p.quantity} · {p.warehouses.map((w) => `${w.name} ${w.free}`).join(' · ')}</div>
                </div>
                <div className="grid-2">
                  <select
                    className="input"
                    value={row.warehouse_id || ''}
                    onChange={(e) => setManual({ ...manual, [p.product_id]: { ...row, warehouse_id: Number(e.target.value) } })}
                  >
                    {p.warehouses.map((w) => (
                      <option key={w.warehouse_id} value={w.warehouse_id}>{w.name} · free {w.free}</option>
                    ))}
                  </select>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    value={row.quantity}
                    onChange={(e) => setManual({ ...manual, [p.product_id]: { ...row, quantity: Number(e.target.value) } })}
                  />
                </div>
              </div>
            )
          })}
          <Btn disabled={saveAlloc.isPending} onClick={() => saveAlloc.mutate()}>Save allocation</Btn>
        </Card>
      ) : null}
    </div>
  )
}

function NegotiationPanel({ quoteId, data, onChange }: { quoteId: number; data: Record<string, unknown> | null | undefined; onChange: () => void }) {
  const { user } = useAuth()
  const [value, setValue] = useState('20')
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const manager = user?.role === 'SALES_MANAGER' || user?.role === 'FINANCE' || user?.role === 'ADMIN'
  const negoId = (data as { id?: number } | null)?.id
  const start = useMutation({
    mutationFn: async () =>
      (await api.post<ApiOk<Record<string, unknown>>>(`/quotes/${quoteId}/negotiation`, {
        request_type: 'DISCOUNT',
        requested_value: value,
        reason: reason || 'Internal counteroffer simulation',
      })).data.data,
    onSuccess: onChange,
  })
  const decide = useMutation({
    mutationFn: async (path: string) => api.post(`/negotiations/${negoId}/${path}`, { comment }),
    onSuccess: (_, path) => {
      toast.success(path === 'approve-changes' ? 'Requested terms accepted' : path === 'reject' ? 'Request rejected' : 'Returned to sales rep')
      onChange()
    },
  })
  const analysis = (start.data?.analysis || {}) as { counteroffer?: Record<string, unknown> }
  const requests = ((data as { requests?: { id: number; request_type?: string; type?: string; requested_value?: string; status: string; reason?: string; category?: string; current_discount?: string }[] } | null)?.requests) || []
  const pending = requests.filter((r) => r.status === 'PENDING')
  return (
    <Card className="card-pad stack">
      <h3>Customer negotiation</h3>
      <p className="muted">Category-wise discount requests and the customer’s comment. Open from Approval Center after a customer starts negotiation.</p>
      {requests.length > 0 ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Current discount</th>
                <th>Requested discount</th>
                <th>Customer comment</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td>{r.category || (r.request_type || r.type || 'DISCOUNT').replaceAll('_', ' ')}</td>
                  <td className="mono">{r.current_discount ? `${r.current_discount}%` : '—'}</td>
                  <td className="mono">{r.requested_value}%</td>
                  <td>{r.reason || '—'}</td>
                  <td><span className="badge">{r.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="muted">No customer requests yet.</p>}
      {negoId && pending.length > 0 ? (
        <>
          <label className="field">
            Reason / comment
            <textarea className="input" rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Stored with negotiation action" />
          </label>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <Btn kind="accent" disabled={decide.isPending} onClick={() => decide.mutate('approve-changes')}>Accept & apply requested terms</Btn>
            <Btn kind="danger" disabled={decide.isPending} onClick={() => decide.mutate('reject')}>Decline request</Btn>
            {manager ? <Btn kind="ghost" disabled={decide.isPending || !comment.trim()} onClick={() => decide.mutate('return-to-rep')}>Return to sales rep</Btn> : null}
          </div>
        </>
      ) : null}
      <label className="field">Requested service discount %
        <input className="input" value={value} onChange={(e) => setValue(e.target.value)} />
      </label>
      <label className="field">Note
        <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <Btn onClick={() => start.mutate()}>Generate counteroffer</Btn>
      {analysis.counteroffer && (
        <div className="card card-pad" style={{ background: 'var(--gold-soft)' }}>
          <h3>{String(analysis.counteroffer.headline)}</h3>
          <p>Instead of {String(analysis.counteroffer.instead_of)}</p>
          <p>Offer {String(analysis.counteroffer.offer)}</p>
          <p>Customer value {inr(Number(analysis.counteroffer.customer_value))} · Profit preserved {inr(Number(analysis.counteroffer.profit_preserved))}</p>
        </div>
      )}
    </Card>
  )
}
