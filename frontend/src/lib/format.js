/**
 * Display helpers.
 *
 * These format values for the screen only. Every amount, discount, margin and
 * risk score shown in the UI is computed by FastAPI and arrives as a string;
 * nothing here derives a figure, because a number the browser worked out could
 * disagree with the invoice.
 */

export function formatCurrency(value, currency = 'INR', options = {}) {
  const amount = Number(value ?? 0)
  if (Number.isNaN(amount)) return '-'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: currency || 'INR',
    maximumFractionDigits: options.decimals ?? 2,
    minimumFractionDigits: options.decimals ?? 2,
  }).format(amount)
}

/** Short form for dashboard tiles, where 1,25,00,000 does not fit. */
export function formatCompactCurrency(value, currency = 'INR') {
  const amount = Number(value ?? 0)
  if (Number.isNaN(amount)) return '-'
  const symbol = currency === 'INR' ? '₹' : ''
  const abs = Math.abs(amount)
  if (abs >= 1_00_00_000) return `${symbol}${(amount / 1_00_00_000).toFixed(2)} Cr`
  if (abs >= 1_00_000) return `${symbol}${(amount / 1_00_000).toFixed(2)} L`
  if (abs >= 1_000) return `${symbol}${(amount / 1_000).toFixed(1)}K`
  return formatCurrency(amount, currency, { decimals: 0 })
}

export function formatPercent(value, digits = 2) {
  const number = Number(value ?? 0)
  if (Number.isNaN(number)) return '-'
  return `${number.toFixed(digits)}%`
}

export function formatNumber(value) {
  const number = Number(value ?? 0)
  if (Number.isNaN(number)) return '-'
  return new Intl.NumberFormat('en-IN').format(number)
}

export function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

/** "3 days ago" / "in 2 days", for activity trails and stalled-deal warnings. */
export function formatRelative(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'

  const seconds = Math.round((date.getTime() - Date.now()) / 1000)
  const units = [
    ['year', 60 * 60 * 24 * 365],
    ['month', 60 * 60 * 24 * 30],
    ['day', 60 * 60 * 24],
    ['hour', 60 * 60],
    ['minute', 60],
  ]
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  for (const [unit, secondsPerUnit] of units) {
    if (Math.abs(seconds) >= secondsPerUnit) {
      return formatter.format(Math.round(seconds / secondsPerUnit), unit)
    }
  }
  return 'just now'
}

export function daysSince(value) {
  if (!value) return 0
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 0
  return Math.max(0, Math.floor((Date.now() - date.getTime()) / 86_400_000))
}

/** Turn an enum such as PENDING_APPROVAL into "Pending Approval". */
export function humanize(value) {
  if (!value) return '-'
  return String(value)
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function initials(name) {
  if (!name) return '?'
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

export function formatFileSize(bytes) {
  const size = Number(bytes ?? 0)
  if (!size) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(units.length - 1, Math.floor(Math.log(size) / Math.log(1024)))
  return `${(size / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export function isoDaysAgo(days) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}
