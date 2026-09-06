export function inr(value?: number | null, compact = false): string {
  const n = Number(value || 0)
  const sign = n < 0 ? '-' : ''
  const abs = Math.abs(n)
  if (compact) {
    if (abs >= 10_000_000) return `${sign}₹${(abs / 10_000_000).toFixed(2)} Cr`
    if (abs >= 100_000) return `${sign}₹${(abs / 100_000).toFixed(2)}L`
  }
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

export function pct(value?: number | null, digits = 1): string {
  return `${Number(value || 0).toFixed(digits)}%`
}

export function riskTone(score?: number | null): 'good' | 'warn' | 'bad' | 'gold' {
  const s = Number(score || 0)
  if (s <= 29) return 'good'
  if (s <= 59) return 'gold'
  if (s <= 79) return 'warn'
  return 'bad'
}

export function healthTone(score?: number | null): 'good' | 'warn' | 'bad' {
  const s = Number(score || 0)
  if (s >= 75) return 'good'
  if (s >= 55) return 'warn'
  return 'bad'
}

export function statusTone(status?: string): 'good' | 'warn' | 'bad' | 'info' | 'gold' | 'teal' {
  switch (status) {
    case 'APPROVED':
    case 'CONFIRMED':
    case 'PAID':
    case 'ACTIVE':
    case 'COMPLETED':
      return 'good'
    case 'PENDING':
    case 'PENDING_APPROVAL':
    case 'DRAFT':
    case 'ISSUED':
      return 'gold'
    case 'NEGOTIATING':
    case 'CHANGES_REQUESTED':
      return 'info'
    case 'PARTIALLY_PAID':
    case 'HIGH':
      return 'warn'
    case 'REJECTED':
    case 'CANCELLED':
    case 'CRITICAL':
    case 'OVERDUE':
    case 'VOID':
    case 'FAILED':
      return 'bad'
    default:
      return 'teal'
  }
}

export function prettyStatus(s?: string): string {
  if (!s) return ''
  if (s === 'PENDING_APPROVAL') return 'Pending Approval'
  if (s === 'NEGOTIATING') return 'Under Negotiation'
  if (s === 'CONFIRMED') return 'Confirmed'
  if (s === 'PARTIALLY_PAID') return 'Partially Paid'
  if (s === 'CHANGES_REQUESTED') return 'Changes Requested'
  if (s === 'NOT_REQUIRED') return 'Not Required'
  return s
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

export function when(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.round(hrs / 24)
  if (days < 7) return `${days}d ago`
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
