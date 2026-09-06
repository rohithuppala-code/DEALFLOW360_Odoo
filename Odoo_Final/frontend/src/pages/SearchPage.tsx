import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type ApiOk } from '../api/client'
import { Empty, ErrorState, PageHeader } from '../components/ui'
import { inr } from '../utils/format'
import { searchHits, type SearchPayload } from '../utils/search'

export default function SearchPage() {
  const [sp, setSp] = useSearchParams()
  const q = sp.get('q') || ''
  const [debounced, setDebounced] = useState(q)
  const nav = useNavigate()
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(q.trim()), 280)
    return () => window.clearTimeout(t)
  }, [q])
  const res = useQuery({
    queryKey: ['search', debounced],
    enabled: debounced.length >= 2,
    queryFn: async ({ signal }) => (await api.get<ApiOk<SearchPayload>>('/search', { params: { q: debounced }, signal })).data.data,
  })
  const groups = useMemo(() => {
    const hits = searchHits(res.data)
    const map = new Map<string, typeof hits>()
    for (const hit of hits) {
      const rows = map.get(hit.groupLabel) || []
      rows.push(hit)
      map.set(hit.groupLabel, rows)
    }
    return [...map.entries()]
  }, [res.data])

  if (res.isError) return <ErrorState title="We couldn't search." onRetry={() => res.refetch()} />

  return (
    <div className="stack">
      <PageHeader kicker="Search" title={q ? `“${q}”` : 'Search'} subtitle="Quotes, customers, products, orders, and invoices." />
      <label className="field" style={{ maxWidth: 420 }}>
        Query
        <input
          className="input"
          value={q}
          onChange={(e) => {
            const next = new URLSearchParams(sp)
            if (e.target.value) next.set('q', e.target.value)
            else next.delete('q')
            setSp(next, { replace: true })
          }}
        />
      </label>
      {debounced.length < 2 ? <Empty title="Type at least two characters" /> : null}
      {res.isFetching ? <p className="muted">Searching…</p> : null}
      {!res.isFetching && debounced.length >= 2 && groups.length === 0 ? (
        <Empty title="No matches" body="Try a quote number, customer name, or SKU." />
      ) : null}
      {groups.map(([label, rows]) => (
        <div className="card card-pad" key={label}>
          <h3>{label}</h3>
          {rows.map((hit) => (
            <button
              key={hit.key}
              type="button"
              className="search-hit"
              style={{ width: '100%' }}
              onClick={() => { if (hit.href) nav(hit.href) }}
            >
              <span>
                <strong>{hit.title}</strong>
                {hit.meta ? <span className="muted"> · {hit.meta}</span> : null}
              </span>
              {hit.amount != null ? <span className="mono">{inr(hit.amount, true)}</span> : null}
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}
