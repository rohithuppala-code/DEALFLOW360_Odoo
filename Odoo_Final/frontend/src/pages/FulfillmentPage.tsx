import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { api, type ApiOk } from '../api/client'
import { Bar, Empty, ErrorState, PageHeader, SkeletonGrid, StatusBadge } from '../components/ui'
import { inr } from '../utils/format'

type QueueRow = {
  id: number
  quote_number: string
  customer?: string
  sales_rep?: string
  status: string
  shipments: number
  shipping_total: number
  backorder_qty: number
  href: string
}

export default function FulfillmentPage() {
  const nav = useNavigate()
  const queue = useQuery({
    queryKey: ['fulfill-queue'],
    queryFn: async () => (await api.get<ApiOk<QueueRow[]>>('/fulfillment/queue')).data.data,
  })
  const inv = useQuery({
    queryKey: ['inventory'],
    queryFn: async () => (await api.get<ApiOk<Record<string, unknown>[]>>('/inventory')).data.data,
  })
  const rows = inv.data || []
  const max = Math.max(1, ...rows.map((r) => Number(r.available_qty || 0) + Number(r.reserved_qty || 0)))
  const deals = queue.data || []
  const exceptions = deals.filter((d) => d.backorder_qty > 0)
  const rest = deals.filter((d) => d.backorder_qty <= 0)

  if (queue.isError) return <ErrorState title="We couldn't load fulfillment." onRetry={() => queue.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Operations"
        title="Fulfillment"
        subtitle="Warehouse recommendations, splits, backorders, and stock. Open a deal to accept the suggested split or override it."
      />
      {queue.isLoading ? <SkeletonGrid n={4} /> : null}

      {exceptions.length > 0 ? (
        <section className="stack">
          <div className="kicker">Backorders</div>
          <div className="approval-grid">
            {exceptions.map((d) => (
              <button
                key={d.id}
                type="button"
                className="approval-card warn-accent"
                onClick={() => nav(d.href || `/quotes/${d.id}?tab=Fulfill`)}
              >
                <div>
                  <div className="kicker">Shortage</div>
                  <h3>{d.quote_number}</h3>
                  <p className="muted">{d.customer || 'Customer'}</p>
                  <div className="muted" style={{ marginTop: 8 }}>
                    Backordered {d.backorder_qty} · Shipments {d.shipments} · Shipping {inr(d.shipping_total)}
                  </div>
                  <div style={{ marginTop: 8 }}><StatusBadge value={d.status} /></div>
                </div>
                <ArrowRight size={18} aria-hidden />
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <div className="card">
        <div className="card-pad"><h3>Deals to allocate</h3></div>
        {rest.length === 0 && exceptions.length === 0 && !queue.isLoading ? (
          <Empty title="No open allocations" body="Approved quotes with warehouse splits or backorders appear here." />
        ) : rest.length === 0 && !queue.isLoading ? (
          <Empty title="No other open allocations" body="Exception deals are listed above." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Quote</th>
                  <th>Customer</th>
                  <th>Rep</th>
                  <th className="num">Shipments</th>
                  <th className="num">Backorder</th>
                  <th className="num">Shipping</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rest.map((d) => (
                  <tr
                    key={d.id}
                    tabIndex={0}
                    style={{ cursor: 'pointer' }}
                    onClick={() => nav(d.href || `/quotes/${d.id}?tab=Fulfill`)}
                    onKeyDown={(e) => { if (e.key === 'Enter') nav(d.href || `/quotes/${d.id}?tab=Fulfill`) }}
                  >
                    <td className="mono">{d.quote_number}</td>
                    <td>{d.customer}</td>
                    <td>{d.sales_rep || '—'}</td>
                    <td className="num mono">{d.shipments}</td>
                    <td className="num mono">{d.backorder_qty}</td>
                    <td className="num mono">{inr(d.shipping_total)}</td>
                    <td><StatusBadge value={d.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="card">
        <div className="card-pad"><h3>Inventory by warehouse</h3></div>
        {rows.length === 0 && !inv.isLoading ? (
          <Empty title="No inventory rows" />
        ) : (
          <div className="table-wrap tall">
            <table className="table">
              <thead>
                <tr>
                  <th>Warehouse</th>
                  <th>Product</th>
                  <th className="num">Available</th>
                  <th className="num">Reserved</th>
                  <th className="num">Free</th>
                  <th>Load</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={String(r.id)} className={Number(r.free) <= 0 ? 'row-warn' : undefined}>
                    <td>
                      {String(r.warehouse)}
                      <div className="muted">{String(r.city || '')}</div>
                    </td>
                    <td>
                      {String(r.product)}
                      {r.sku ? <div className="muted mono">{String(r.sku)}</div> : null}
                    </td>
                    <td className="num mono">{String(r.available_qty)}</td>
                    <td className="num mono">{String(r.reserved_qty)}</td>
                    <td className="num mono">{String(r.free)}</td>
                    <td style={{ minWidth: 120 }}>
                      <Bar value={Number(r.reserved_qty || 0)} max={max} tone={Number(r.free) <= 0 ? 'bad' : 'good'} />
                    </td>
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
