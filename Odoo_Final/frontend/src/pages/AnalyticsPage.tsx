import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { toast } from 'sonner'
import { api, type ApiOk } from '../api/client'
import { Btn, ErrorState, Metric, PageHeader } from '../components/ui'
import { CHART_ACCENT, CHART_GRID } from '../theme'
import { inr } from '../utils/format'

export default function AnalyticsPage() {
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [repId, setRepId] = useState('')
  const [status, setStatus] = useState('')
  const [approval, setApproval] = useState('')
  const params = {
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    sales_rep_id: repId || undefined,
    status: status || undefined,
    approval_status: approval || undefined,
  }
  const sales = useQuery({ queryKey: ['rep', 'sales', params], queryFn: async () => (await api.get<ApiOk<Record<string, number>>>('/reports/sales', { params })).data.data })
  const margin = useQuery({ queryKey: ['rep', 'margin', params], queryFn: async () => (await api.get<ApiOk<{ gross_margin?: number; distribution?: { bucket: string; count: number }[]; by_rep?: { name?: string; rep?: string; margin: number; deals?: number }[] }>>('/reports/margin', { params })).data.data })
  const approvals = useQuery({ queryKey: ['rep', 'appr', params], queryFn: async () => (await api.get<ApiOk<Record<string, number>>>('/reports/approvals', { params: { approval_status: approval || undefined } })).data.data })
  const fulfill = useQuery({ queryKey: ['rep', 'ff'], queryFn: async () => (await api.get<ApiOk<Record<string, number>>>('/reports/fulfillment')).data.data })
  const subs = useQuery({ queryKey: ['rep', 'sub'], queryFn: async () => (await api.get<ApiOk<Record<string, number>>>('/reports/subscriptions')).data.data })
  const reps = useQuery({
    queryKey: ['users', 'analytics'],
    queryFn: async () => {
      try {
        return (await api.get<ApiOk<{ id: number; name: string; role: string }[]>>('/users')).data.data
      } catch {
        return []
      }
    },
  })

  async function download(fmt: string) {
    const res = await api.get('/reports/export', { params: { format: fmt, ...params }, responseType: 'blob' })
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dealflow-report.${fmt === 'xlsx' || fmt === 'xls' ? 'xls' : fmt}`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(`Exported ${fmt.toUpperCase()}`)
  }

  if (sales.isError) return <ErrorState title="We couldn't load analytics." onRetry={() => sales.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Reporting"
        title="Analytics"
        subtitle="Won revenue, margin quality, approval throughput, and recurring run-rate. Filters apply to live MySQL data."
        actions={
          <div className="row">
            <Btn kind="ghost" onClick={() => download('csv')}>CSV</Btn>
            <Btn kind="ghost" onClick={() => download('xls')}>XLS</Btn>
            <Btn kind="ghost" onClick={() => download('pdf')}>PDF</Btn>
          </div>
        }
      />
      <div className="card card-pad grid-2">
        <label className="field">From
          <input className="input" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </label>
        <label className="field">To
          <input className="input" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </label>
        <label className="field">Sales rep
          <select className="input" value={repId} onChange={(e) => setRepId(e.target.value)}>
            <option value="">All sales reps</option>
            {(reps.data || []).filter((u) => u.role === 'SALES_REP' || u.role === 'ADMIN').map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </label>
        <label className="field">Quote status
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All quote status</option>
            {['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'NEGOTIATING', 'CONFIRMED', 'REJECTED'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="field">Approval status
          <select className="input" value={approval} onChange={(e) => setApproval(e.target.value)}>
            <option value="">All approval status</option>
            {['NOT_REQUIRED', 'PENDING', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
      </div>
      <div className="grid-4">
        <Metric label="Won revenue" value={inr(sales.data?.revenue, true)} />
        <Metric label="Win rate" value={`${sales.data?.win_rate ?? 0}%`} />
        <Metric label="Avg deal" value={inr(sales.data?.average_deal_size, true)} />
        <Metric label="Gross margin" value={`${margin.data?.gross_margin ?? 0}%`} />
      </div>
      <div className="grid-4">
        <Metric quiet label="Avg discount" value={`${Number(sales.data?.discount_average || 0).toFixed(1)}%`} />
        <Metric quiet label="Approval rate" value={`${approvals.data?.approval_rate ?? 0}%`} />
        <Metric quiet label="Shipping cost" value={inr(fulfill.data?.shipping_cost, true)} />
        <Metric quiet label="MRR" value={inr(subs.data?.mrr, true)} />
      </div>
      <div className="grid-2">
        <div className="card card-pad">
          <h3>Margin distribution</h3>
          <div style={{ height: 240 }}>
            <ResponsiveContainer>
              <BarChart data={margin.data?.distribution || []}>
                <CartesianGrid stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill={CHART_ACCENT} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card">
          <div className="card-pad"><h3>By sales rep</h3></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Rep</th><th className="num">Deals</th><th className="num">Margin</th></tr></thead>
              <tbody>
                {(margin.data?.by_rep || []).length === 0 ? (
                  <tr><td colSpan={3} className="muted">No rep breakdown for these filters.</td></tr>
                ) : (
                  (margin.data?.by_rep || []).map((r) => (
                    <tr key={r.rep || r.name}>
                      <td>{r.rep || r.name}</td>
                      <td className="num mono">{r.deals ?? '—'}</td>
                      <td className="num mono">{r.margin}%</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
