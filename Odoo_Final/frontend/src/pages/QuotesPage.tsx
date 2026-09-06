import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type ApiOk, type Page } from '../api/client'
import type { Quote } from '../types'
import { Btn, Empty, ErrorState, HealthChip, PageHeader, RiskBadge, SkeletonGrid, StatusBadge } from '../components/ui'
import { inr, pct } from '../utils/format'

const COLS = [
  { key: 'DRAFT', label: 'Draft' },
  { key: 'PENDING_APPROVAL', label: 'Pending Approval' },
  { key: 'APPROVED', label: 'Approved' },
  { key: 'NEGOTIATING', label: 'Under Negotiation' },
  { key: 'CONFIRMED', label: 'Confirmed' },
]

export default function QuotesPage() {
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState('')
  const [qDebounced, setQDebounced] = useState('')
  const [view, setView] = useState<'board' | 'table'>('board')
  const [page, setPage] = useState(1)
  const [pageKey, setPageKey] = useState('')
  const [sort, setSort] = useState('updated_at')
  const status = sp.get('status') || ''
  const board = view === 'board' && !status
  const filterKey = `${status}|${qDebounced}|${view}`
  if (pageKey !== filterKey) {
    setPageKey(filterKey)
    setPage(1)
  }

  useEffect(() => {
    const t = window.setTimeout(() => setQDebounced(q.trim()), 280)
    return () => window.clearTimeout(t)
  }, [q])

  const list = useQuery({
    queryKey: ['quotes', status, qDebounced, page, sort, board],
    queryFn: async () =>
      (
        await api.get<ApiOk<Page<Quote>>>('/quotes', {
          params: {
            status: status || undefined,
            q: qDebounced || undefined,
            page: board ? 1 : page,
            page_size: board ? 50 : 20,
            sort: board ? undefined : sort,
          },
        })
      ).data.data,
    placeholderData: (prev) => prev,
  })
  const items = list.data?.items || []
  const grouped = useMemo(() => {
    const map: Record<string, Quote[]> = { DRAFT: [], PENDING_APPROVAL: [], APPROVED: [], NEGOTIATING: [], CONFIRMED: [] }
    for (const qt of list.data?.items || []) {
      if (map[qt.status]) map[qt.status].push(qt)
    }
    return map
  }, [list.data])

  function setStatus(value: string) {
    const next = new URLSearchParams(sp)
    if (value) next.set('status', value)
    else next.delete('status')
    setSp(next)
  }

  if (list.isError) return <ErrorState title="We couldn't load your quotations." onRetry={() => list.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Pipeline"
        title="Quotes"
        subtitle="Follow every deal through quote, approval, customer, and close."
        actions={<Btn kind="accent" onClick={() => nav('/quotes/new')}>New quote</Btn>}
      />
      <div className="spread" style={{ flexWrap: 'wrap' }}>
        <div className="row" style={{ flex: 1, flexWrap: 'wrap' }}>
          <label className="field" style={{ maxWidth: 280, margin: 0 }}>
            Search
            <input className="input" placeholder="Quote # or title" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <label className="field" style={{ maxWidth: 200, margin: 0 }}>
            Stage
            <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All stages</option>
              {COLS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
              <option value="REJECTED">Rejected</option>
            </select>
          </label>
          {view === 'table' ? (
            <label className="field" style={{ maxWidth: 180, margin: 0 }}>
              Sort
              <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="updated_at">Recent</option>
                <option value="total">Value</option>
                <option value="risk">Risk</option>
              </select>
            </label>
          ) : null}
        </div>
        <div className="seg" role="tablist" aria-label="Quotes view">
          <button
            type="button"
            className={board ? 'on' : ''}
            onClick={() => {
              setView('board')
              if (status) setStatus('')
            }}
          >
            Board
          </button>
          <button type="button" className={!board ? 'on' : ''} onClick={() => setView('table')}>Table</button>
        </div>
      </div>

      {list.isLoading ? <SkeletonGrid n={4} /> : null}

      {!list.isLoading && items.length === 0 ? (
        <div className="card">
          <Empty title="No quotations yet" body="Create your first quotation to start building the pipeline." action={<Btn onClick={() => nav('/quotes/new')}>New quote</Btn>} />
        </div>
      ) : null}

      {!list.isLoading && items.length > 0 && board ? (
        <div className="kanban">
          {COLS.map((col) => (
            <div className="kanban-col" key={col.key}>
              <h3>{col.label} <span className="muted">{grouped[col.key]?.length || 0}</span></h3>
              {(grouped[col.key] || []).map((qt) => (
                <button key={qt.id} type="button" className="quote-card" onClick={() => nav(`/quotes/${qt.id}`)}>
                  <div className="mono" style={{ fontSize: 12 }}>{qt.quote_number}</div>
                  <strong style={{ display: 'block', margin: '4px 0' }}>{qt.customer?.name}</strong>
                  <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{qt.title}</div>
                  <div className="spread">
                    <span className="mono">{inr(qt.total, true)}</span>
                    <RiskBadge score={qt.risk_score} />
                  </div>
                </button>
              ))}
            </div>
          ))}
        </div>
      ) : null}

      {!list.isLoading && items.length > 0 && !board ? (
        <div className="card">
          <div className="table-wrap tall stack-sm">
            <table className="table">
              <thead>
                <tr>
                  <th>Quote</th><th>Customer</th><th className="num">Value</th><th className="num">Margin</th><th>Risk</th><th>Health</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((qt) => (
                  <tr
                    key={qt.id}
                    tabIndex={0}
                    style={{ cursor: 'pointer' }}
                    onClick={() => nav(`/quotes/${qt.id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter') nav(`/quotes/${qt.id}`) }}
                  >
                    <td data-label="Quote">
                      <div className="mono">{qt.quote_number}</div>
                      <div className="muted">{qt.title}</div>
                    </td>
                    <td data-label="Customer">
                      {qt.customer?.name}
                      <div className="muted">{qt.customer?.tier?.name}</div>
                    </td>
                    <td className="num mono" data-label="Value">{inr(qt.total, true)}</td>
                    <td className="num mono" data-label="Margin">{pct(qt.gross_margin_percent)}</td>
                    <td data-label="Risk"><RiskBadge score={qt.risk_score} /></td>
                    <td data-label="Health"><HealthChip score={qt.deal_health_score} /></td>
                    <td data-label="Status"><StatusBadge value={qt.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(list.data?.pages || 0) > 1 ? (
            <div className="pager">
              <span className="muted">{list.data?.total} quotes</span>
              <div className="row">
                <button type="button" className="btn ghost sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
                <span className="muted">Page {list.data?.page} of {list.data?.pages}</span>
                <button type="button" className="btn ghost sm" disabled={page >= (list.data?.pages || 1)} onClick={() => setPage((p) => p + 1)}>Next</button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
