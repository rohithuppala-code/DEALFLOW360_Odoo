/**
 * Display helpers. These format values for the screen only - every amount,
 * discount and margin shown here is computed by FastAPI and never derived
 * in the browser.
 */

export function formatCurrency(value, currency = 'INR') {
  const amount = Number(value ?? 0)
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(amount)
}

export function formatPercent(value, fractionDigits = 2) {
  return `${Number(value ?? 0).toFixed(fractionDigits)}%`
}

export function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

/** Turn an enum such as PENDING_APPROVAL into "Pending Approval". */
export function humanizeEnum(value) {
  if (!value) return '-'
  return String(value)
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
