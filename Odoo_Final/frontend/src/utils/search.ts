export type SearchPayload = {
  quotes?: { id: number; quote_number?: string; title?: string; total?: number }[]
  customers?: { id: number; name?: string; code?: string }[]
  products?: { id: number; sku?: string; name?: string; price?: number }[]
  orders?: { id: number; order_number?: string; total?: number }[]
  invoices?: { id: number; invoice_number?: string; total?: number }[]
}

export type SearchHit = {
  key: string
  group: string
  groupLabel: string
  title: string
  meta?: string
  amount?: number
  href: string | null
}

const GROUPS: { key: keyof SearchPayload; label: string }[] = [
  { key: 'quotes', label: 'Quotes' },
  { key: 'customers', label: 'Customers' },
  { key: 'products', label: 'Products' },
  { key: 'orders', label: 'Orders' },
  { key: 'invoices', label: 'Invoices' },
]

export function searchHits(data?: SearchPayload | null): SearchHit[] {
  if (!data) return []
  const out: SearchHit[] = []
  for (const g of GROUPS) {
    for (const item of data[g.key] || []) {
      const id = item.id
      if (g.key === 'quotes') {
        const row = item as NonNullable<SearchPayload['quotes']>[number]
        out.push({
          key: `quotes-${id}`,
          group: g.key,
          groupLabel: g.label,
          title: row.quote_number || 'Quote',
          meta: row.title,
          amount: row.total,
          href: `/quotes/${id}`,
        })
      } else if (g.key === 'customers') {
        const row = item as NonNullable<SearchPayload['customers']>[number]
        const name = row.name || 'Customer'
        out.push({
          key: `customers-${id}`,
          group: g.key,
          groupLabel: g.label,
          title: name,
          meta: row.code,
          href: `/customers?q=${encodeURIComponent(name)}`,
        })
      } else if (g.key === 'products') {
        const row = item as NonNullable<SearchPayload['products']>[number]
        out.push({
          key: `products-${id}`,
          group: g.key,
          groupLabel: g.label,
          title: row.name || row.sku || 'Product',
          meta: row.sku,
          amount: row.price,
          href: null,
        })
      } else if (g.key === 'orders') {
        const row = item as NonNullable<SearchPayload['orders']>[number]
        out.push({
          key: `orders-${id}`,
          group: g.key,
          groupLabel: g.label,
          title: row.order_number || 'Order',
          amount: row.total,
          href: null,
        })
      } else {
        const row = item as NonNullable<SearchPayload['invoices']>[number]
        out.push({
          key: `invoices-${id}`,
          group: g.key,
          groupLabel: g.label,
          title: row.invoice_number || 'Invoice',
          amount: row.total,
          href: '/billing',
        })
      }
    }
  }
  return out
}
