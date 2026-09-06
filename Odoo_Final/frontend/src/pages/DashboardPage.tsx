import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type ApiOk } from '../api/client'
import { useAuth } from '../auth'
import { Btn, ErrorState, Metric, PageHeader, SkeletonGrid, StatusBadge } from '../components/ui'
import { CHART_ACCENT, CHART_GRID } from '../theme'
import { inr } from '../utils/format'

type Summary = {
  pipeline: number
  confirmed_revenue: number
  expected_revenue: number
  active_deals: number
  at_risk: number
  pending_approvals: number
  gross_margin: number
  negotiations: number
  backorders: number
  mrr: number
}

type Action = { id: string; kind: string; title: string; detail: string; href: string; tone: string }

type HealthAlert = {
  id?: number
  quote_id?: number
  quote_number?: string
  customer?: string
  reason?: string
  message?: string
  href?: string
  status?: string
}

export default function DashboardPage() {
  const nav = useNavigate()
  const { user } = useAuth()
  const summary = useQuery({ queryKey: ['dash', 'summary'], queryFn: async () => (await api.get<ApiOk<Summary>>('/dashboard/summary')).data.data })
  const pipeline = useQuery({ queryKey: ['dash', 'pipeline'], queryFn: async () => (await api.get<ApiOk<{ stages: { key: string; label: string; value: number; count: number }[] }>>('/dashboard/pipeline')).data.data })
  const risks = useQuery({
    queryKey: ['dash', 'risks'],
    queryFn: async () =>
      (
        await api.get<
          ApiOk<{
            deals: { id: number; quote_number: string; customer: string; total: number; risk: number; margin: number; status: string }[]
            stalled?: HealthAlert[]
            discount_anomalies?: HealthAlert[]
            delivery_slippage?: HealthAlert[]
          }>
        >('/dashboard/risks')
      ).data.data,
  })
  const activity = useQuery({ queryKey: ['dash', 'activity'], queryFn: async () => (await api.get<ApiOk<{ id: number; description: string; created_at: string; quote_id?: number }[]>>('/dashboard/activity')).data.data })
  const actions = useQuery({ queryKey: ['dash', 'actions'], queryFn: async () => (await api.get<ApiOk<Action[]>>('/dashboard/actions')).data.data })
  const s = summary.data
  const hour = new Date().getHours()
  const hello = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const canApprove = user?.role === 'SALES_MANAGER' || user?.role === 'FINANCE' || user?.role === 'ADMIN'
  const inbox = (actions.data || []).filter((a) => a.kind === 'approval')
  const other = (actions.data || []).filter((a) => a.kind !== 'approval')

  if (summary.isLoading) return <SkeletonGrid n={8} />
  if (summary.isError) return <ErrorState title="We couldn't load the control tower." onRetry={() => summary.refetch()} />

  return (
    <div className="stack" style={{ gap: 22 }}>
      <PageHeader
        kicker={user?.role === 'SALES_MANAGER' ? 'Sales manager workspace' : user?.role === 'FINANCE' ? 'Finance workspace' : user?.role === 'OPERATIONS' ? 'Operations workspace' : user?.role === 'ADMIN' ? 'Admin workspace' : 'Sales control tower'}
        title={`${hello}, ${user?.name?.split(' ')[0] || 'team'}`}
        subtitle="Watch the path from quote to cash. Start with the next action, then drill into any deal that looks unhealthy."
        actions={
          user?.role === 'ADMIN' ? (
            <Btn kind="accent" onClick={() => nav('/admin')}>Open admin</Btn>
          ) : user?.role === 'SALES_MANAGER' || user?.role === 'FINANCE' ? (
            <Btn kind="accent" onClick={() => nav('/approvals')}>Approval inbox</Btn>
          ) : user?.role === 'OPERATIONS' ? (
            <Btn kind="accent" onClick={() => nav('/fulfillment')}>Fulfillment</Btn>
          ) : (
            <Btn kind="accent" onClick={() => nav('/quotes/new')}>New quote</Btn>
          )
        }
      />

      {canApprove || inbox.length > 0 || other.length > 0 ? (
        <section className="stack">
          <div className="kicker">Needs attention</div>
          {canApprove && inbox.length === 0 && !actions.isLoading ? (
            <p className="muted" style={{ margin: 0 }}>No pending approvals.</p>
          ) : null}
          {inbox.length > 0 ? (
            <div className="approval-grid">
              {inbox.map((a) => (
                <button key={a.id} type="button" className="approval-card" onClick={() => nav(a.href)}>
                  <div>
                    <div className="kicker">Pending Approval</div>
                    <h3>{a.title}</h3>
                    <p className="muted">{a.detail}</p>
                  </div>
                  <ArrowRight size={18} aria-hidden />
                </button>
              ))}
            </div>
          ) : null}
          {other.length > 0 ? (
            <div className="grid-2">
              {other.slice(0, 4).map((a) => (
                <button key={a.id} type="button" className={`next-action ${a.tone}`} onClick={() => nav(a.href)}>
                  <div>
                    <div className="kicker">{a.kind}</div>
                    <h3 style={{ marginTop: 4 }}>{a.title}</h3>
                    <p className="muted" style={{ margin: '4px 0 0' }}>{a.detail}</p>
                  </div>
                  <ArrowRight size={18} aria-hidden />
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid-4">
        <Metric label="Pipeline" value={inr(s?.pipeline, true)} hint={`${s?.active_deals || 0} live deals`} />
        <Metric label="Expected revenue" value={inr(s?.expected_revenue, true)} />
        <Metric label="At risk" value={s?.at_risk ?? '—'} hint="Risk ≥ 60 or health < 55" />
        <Metric label="Pending approvals" value={s?.pending_approvals ?? '—'} />
      </div>

      <section className="stack">
        <div className="kicker">Pipeline</div>
        <div className="funnel">
          {(pipeline.data?.stages || []).map((st) => (
            <button key={st.key} type="button" className="funnel-step" onClick={() => nav(`/quotes?status=${st.key}`)}>
              <div className="n">{st.count}</div>
              <div className="l">{st.label}</div>
              <div className="muted mono" style={{ marginTop: 6, fontSize: 12 }}>{inr(st.value, true)}</div>
            </button>
          ))}
        </div>
        <div className="card card-pad">
          <h3>Revenue by stage</h3>
          <div style={{ height: 240, marginTop: 8 }}>
            <ResponsiveContainer>
              <BarChart data={pipeline.data?.stages || []}>
                <CartesianGrid stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => inr(v, true)} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => inr(Number(v), true)} />
                <Bar dataKey="value" fill={CHART_ACCENT} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <div className="card">
        <div className="card-pad spread"><h3>Deals that need attention</h3></div>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Quote</th><th>Customer</th><th>Value</th><th>Risk</th><th>Status</th></tr></thead>
            <tbody>
              {(risks.data?.deals || []).length === 0 ? (
                <tr><td colSpan={5} className="muted">No deals currently flagged.</td></tr>
              ) : (
                (risks.data?.deals || []).slice(0, 8).map((d) => (
                  <tr
                    key={d.id}
                    tabIndex={0}
                    style={{ cursor: 'pointer' }}
                    onClick={() => nav(`/quotes/${d.id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter') nav(`/quotes/${d.id}`) }}
                  >
                    <td className="mono">{d.quote_number}</td>
                    <td>{d.customer}</td>
                    <td className="mono">{inr(d.total, true)}</td>
                    <td className="mono">{Math.round(d.risk)}</td>
                    <td><StatusBadge value={d.status} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-4">
        <Metric quiet label="Gross margin" value={`${s?.gross_margin ?? 0}%`} />
        <Metric quiet label="Negotiations" value={s?.negotiations ?? '—'} />
        <Metric quiet label="Backorders" value={s?.backorders ?? '—'} />
        <Metric quiet label="MRR" value={inr(s?.mrr, true)} hint={`Confirmed ${inr(s?.confirmed_revenue, true)}`} />
      </div>

      <div className="card card-pad">
        <h3>Deal Health</h3>
        <p className="muted">Stalled deals, discount anomalies, and delivery slippage. Open an alert to inspect the quote.</p>
        <div className="grid-3" style={{ marginTop: 12 }}>
          <HealthList title="Stalled deals" items={risks.data?.stalled} nav={nav} />
          <HealthList title="Discount anomalies" items={risks.data?.discount_anomalies} nav={nav} />
          <HealthList title="Delivery slippage" items={risks.data?.delivery_slippage} nav={nav} />
        </div>
      </div>

      <div className="card card-pad">
        <h3>Recent activity</h3>
        <div className="timeline" style={{ marginTop: 12 }}>
          {(activity.data || []).length === 0 ? <p className="muted">No recent activity.</p> : null}
          {(activity.data || []).slice(0, 8).map((e) => (
            <div
              className="t-item"
              key={e.id}
              role={e.quote_id ? 'link' : undefined}
              tabIndex={e.quote_id ? 0 : undefined}
              style={{ cursor: e.quote_id ? 'pointer' : 'default' }}
              onClick={() => e.quote_id && nav(`/quotes/${e.quote_id}`)}
              onKeyDown={(eKey) => { if (e.quote_id && eKey.key === 'Enter') nav(`/quotes/${e.quote_id}`) }}
            >
              <div>{e.description}</div>
              <time>{new Date(e.created_at).toLocaleString()}</time>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function HealthList({ title, items, nav }: { title: string; items?: HealthAlert[]; nav: (to: string) => void }) {
  const rows = items || []
  return (
    <div>
      <h3>{title} <span className="muted">{rows.length}</span></h3>
      {rows.length === 0 ? <p className="muted" style={{ marginTop: 8 }}>None right now.</p> : (
        <div className="stack" style={{ marginTop: 8 }}>
          {rows.slice(0, 5).map((a, i) => {
            const href = a.href || (a.quote_id ? `/quotes/${a.quote_id}` : a.id ? `/quotes/${a.id}` : '')
            return (
              <button
                key={`${a.quote_number || a.id || i}`}
                type="button"
                className="card card-pad"
                style={{ textAlign: 'left', cursor: href ? 'pointer' : 'default', padding: 12 }}
                onClick={() => href && nav(href)}
              >
                <div className="mono">{a.quote_number || '—'}</div>
                <strong>{a.customer || 'Deal'}</strong>
                <div className="muted">{a.reason || a.message}</div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
