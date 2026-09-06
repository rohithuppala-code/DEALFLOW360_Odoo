/**
 * The UI kit.
 *
 * One module so every screen imports from the same place and the app stays
 * visually consistent - the same button, the same table, the same empty state,
 * everywhere. Each component is deliberately small and unopinionated about
 * data; the pages own the behaviour.
 *
 * Loading, empty and error states are first-class here rather than an
 * afterthought, because every screen in this app is reading live data over a
 * network and will hit all three.
 */
import { useEffect, useId, useRef, useState } from 'react'

import { humanize } from '../../lib/format'

/* ------------------------------------------------------------------ utils */
export function cx(...classes) {
  return classes.filter(Boolean).join(' ')
}

/* ----------------------------------------------------------------- Button */
const BUTTON_VARIANTS = {
  primary:
    'bg-indigo-600 text-white shadow-sm hover:bg-indigo-700 focus-visible:ring-indigo-500 disabled:bg-indigo-300 dark:disabled:bg-indigo-900',
  secondary:
    'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700',
  subtle:
    'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700',
  danger: 'bg-red-600 text-white shadow-sm hover:bg-red-700 disabled:bg-red-300',
  success: 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 disabled:bg-emerald-300',
  ghost:
    'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800',
}

const BUTTON_SIZES = {
  xs: 'px-2 py-1 text-xs gap-1',
  sm: 'px-2.5 py-1.5 text-sm gap-1.5',
  md: 'px-3.5 py-2 text-sm gap-2',
  lg: 'px-5 py-2.5 text-base gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon = null,
  className = '',
  children,
  ...props
}) {
  return (
    <button
      // Defaulting to "button" matters: an unspecified button inside a form
      // submits it, which has caused more accidental saves than any other
      // default in HTML.
      type={props.type ?? 'button'}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        'inline-flex items-center justify-center rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-70',
        BUTTON_VARIANTS[variant] ?? BUTTON_VARIANTS.primary,
        BUTTON_SIZES[size] ?? BUTTON_SIZES.md,
        className,
      )}
      {...props}
    >
      {loading ? <Spinner className="h-4 w-4" /> : icon}
      {children}
    </button>
  )
}

export function Spinner({ className = 'h-5 w-5' }) {
  return (
    <span
      className={cx(
        'inline-block animate-spin rounded-full border-2 border-current border-t-transparent opacity-70',
        className,
      )}
      role="presentation"
    />
  )
}

/* ------------------------------------------------------------------- Card */
export function Card({ className = '', children, ...props }) {
  return (
    <div className={cx('card', className)} {...props}>
      {children}
    </div>
  )
}

export function CardHeader({ title, description, actions, className = '' }) {
  return (
    <div
      className={cx(
        'flex flex-col gap-3 border-b border-slate-200 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5 dark:border-slate-800',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
        {description && (
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function CardBody({ className = '', children }) {
  return <div className={cx('p-4 sm:p-5', className)}>{children}</div>
}

/* ------------------------------------------------------------------ Badge */
const BADGE_TONES = {
  slate: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700',
  emerald:
    'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-900',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-900',
  orange:
    'bg-orange-50 text-orange-800 ring-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:ring-orange-900',
  red: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-300 dark:ring-red-900',
  blue: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:ring-blue-900',
  cyan: 'bg-cyan-50 text-cyan-700 ring-cyan-200 dark:bg-cyan-950 dark:text-cyan-300 dark:ring-cyan-900',
  violet:
    'bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-950 dark:text-violet-300 dark:ring-violet-900',
  indigo:
    'bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-900',
}

export function Badge({ tone = 'slate', size = 'sm', className = '', children }) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full font-medium ring-1 ring-inset whitespace-nowrap',
        size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-xs',
        BADGE_TONES[tone] ?? BADGE_TONES.slate,
        className,
      )}
    >
      {children}
    </span>
  )
}

/** A badge that labels itself from an enum value, e.g. PENDING_APPROVAL. */
export function StatusBadge({ status, tone, size = 'sm' }) {
  if (!status) return <span className="text-slate-400">-</span>
  return (
    <Badge tone={tone} size={size}>
      {humanize(status)}
    </Badge>
  )
}

/* ------------------------------------------------------------- form fields */
export function Field({ label, hint, error, required, children, className = '' }) {
  return (
    <div className={cx('space-y-1.5', className)}>
      {label && (
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
          {required && <span className="ml-0.5 text-red-500">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      ) : (
        hint && <p className="text-xs text-slate-500 dark:text-slate-400">{hint}</p>
      )}
    </div>
  )
}

const CONTROL_CLASSES =
  'block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 transition placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 dark:bg-slate-900 dark:text-slate-100 dark:ring-slate-700 dark:disabled:bg-slate-800'

export function Input({ className = '', invalid = false, ...props }) {
  return (
    <input
      className={cx(CONTROL_CLASSES, invalid && 'ring-red-400 focus:ring-red-500', className)}
      aria-invalid={invalid || undefined}
      {...props}
    />
  )
}

export function Textarea({ className = '', rows = 3, ...props }) {
  return <textarea rows={rows} className={cx(CONTROL_CLASSES, className)} {...props} />
}

export function Select({ className = '', children, placeholder, ...props }) {
  return (
    <select className={cx(CONTROL_CLASSES, 'pr-8', className)} {...props}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {children}
    </select>
  )
}

/** A select whose options come from an enum list, humanised for display. */
export function EnumSelect({ options = [], labels, placeholder = 'All', ...props }) {
  return (
    <Select placeholder={placeholder} {...props}>
      {options.map((option) => (
        <option key={option} value={option}>
          {labels?.[option] ?? humanize(option)}
        </option>
      ))}
    </Select>
  )
}

export function Checkbox({ label, description, className = '', ...props }) {
  const id = useId()
  return (
    <div className={cx('flex items-start gap-2.5', className)}>
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800"
        {...props}
      />
      <div className="min-w-0">
        {label && (
          <label htmlFor={id} className="block text-sm text-slate-700 dark:text-slate-300">
            {label}
          </label>
        )}
        {description && (
          <p className="text-xs text-slate-500 dark:text-slate-400">{description}</p>
        )}
      </div>
    </div>
  )
}

/** Search box with a magnifier and a clear button. */
export function SearchInput({ value, onChange, placeholder = 'Search...', className = '' }) {
  return (
    <div className={cx('relative', className)}>
      <svg
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className={cx(CONTROL_CLASSES, 'pl-9')}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ Modal */
export function Modal({ open, onClose, title, description, size = 'md', footer, children }) {
  const panel = useRef(null)

  // Escape closes, and the page behind must not scroll while a dialog is open.
  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.focus()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-6xl',
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-slate-900/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === 'string' ? title : 'Dialog'}
      onMouseDown={(event) => {
        // Only a click that starts on the backdrop closes. Starting inside and
        // releasing outside (a drag off a text selection) must not close.
        if (event.target === event.currentTarget) onClose?.()
      }}
    >
      <div
        ref={panel}
        tabIndex={-1}
        className={cx(
          'animate-scale-in max-h-[92vh] w-full overflow-hidden rounded-t-2xl bg-white shadow-xl sm:rounded-2xl dark:bg-slate-900',
          sizes[size] ?? sizes.md,
        )}
      >
        {(title || description) && (
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
              {description && (
                <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
              aria-label="Close dialog"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        )}
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3.5 dark:border-slate-800 dark:bg-slate-950/50">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

/** Confirmation dialog for anything destructive or hard to reverse. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Confirm',
  variant = 'danger',
  loading = false,
  children,
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant={variant} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {message && <p className="text-sm text-slate-600 dark:text-slate-300">{message}</p>}
      {children}
    </Modal>
  )
}

/* ------------------------------------------------------------------ Table */
export function Table({ columns = [], rows = [], rowKey, onRowClick, empty, className = '' }) {
  if (!rows.length) return empty ?? null

  return (
    <div className={cx('scroll-x', className)}>
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-800">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cx(
                  'whitespace-nowrap px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400',
                  column.align === 'right' && 'text-right',
                  column.align === 'center' && 'text-center',
                  column.className,
                )}
              >
                {column.sortable ? (
                  <button
                    type="button"
                    onClick={() => column.onSort?.(column.key)}
                    className="inline-flex items-center gap-1 transition hover:text-slate-700 dark:hover:text-slate-200"
                  >
                    {column.header}
                    <SortGlyph direction={column.sortDirection} />
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row, index) => (
            <tr
              key={rowKey ? rowKey(row, index) : (row.id ?? index)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cx(
                'transition',
                onRowClick && 'cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60',
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cx(
                    'px-4 py-3 align-middle text-slate-700 dark:text-slate-300',
                    column.align === 'right' && 'text-right',
                    column.align === 'center' && 'text-center',
                    column.cellClassName,
                  )}
                >
                  {column.render ? column.render(row, index) : (row[column.key] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SortGlyph({ direction }) {
  return (
    <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M6 2v8M6 2L3 5M6 2l3 3" className={direction === 'asc' ? 'opacity-100' : 'opacity-30'} />
      {direction === 'desc' && <path d="M6 10L3 7M6 10l3-3" />}
    </svg>
  )
}

/* -------------------------------------------------------------- Pagination */
export function Pagination({ page, totalPages, total, pageSize, onChange, className = '' }) {
  if (!totalPages || totalPages <= 1) {
    return total ? (
      <p className={cx('px-4 py-3 text-xs text-slate-500 dark:text-slate-400', className)}>
        {total} {total === 1 ? 'result' : 'results'}
      </p>
    ) : null
  }

  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  return (
    <div
      className={cx(
        'flex flex-col gap-3 border-t border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800',
        className,
      )}
    >
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Showing <span className="font-medium text-slate-700 dark:text-slate-300">{from}</span>-
        <span className="font-medium text-slate-700 dark:text-slate-300">{to}</span> of{' '}
        <span className="font-medium text-slate-700 dark:text-slate-300">{total}</span>
      </p>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="secondary" onClick={() => onChange(page - 1)} disabled={page <= 1}>
          Previous
        </Button>
        {pageNumbers(page, totalPages).map((entry, index) =>
          entry === '...' ? (
            <span key={`gap-${index}`} className="px-2 text-sm text-slate-400">
              ...
            </span>
          ) : (
            <button
              key={entry}
              type="button"
              onClick={() => onChange(entry)}
              aria-current={entry === page ? 'page' : undefined}
              className={cx(
                'min-w-[2rem] rounded-lg px-2 py-1.5 text-sm font-medium transition',
                entry === page
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
              )}
            >
              {entry}
            </button>
          ),
        )}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>
    </div>
  )
}

/** First, last, and a window around the current page - with gaps elided. */
function pageNumbers(page, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1)

  const pages = new Set([1, totalPages, page, page - 1, page + 1])
  const sorted = [...pages].filter((entry) => entry >= 1 && entry <= totalPages).sort((a, b) => a - b)

  const result = []
  let previous = 0
  for (const entry of sorted) {
    if (previous && entry - previous > 1) result.push('...')
    result.push(entry)
    previous = entry
  }
  return result
}

/* ------------------------------------------------------------ page states */
export function Skeleton({ className = 'h-4 w-full' }) {
  return <div className={cx('skeleton', className)} />
}

export function TableSkeleton({ rows = 5, columns = 5 }) {
  return (
    <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <Skeleton
              key={columnIndex}
              className={cx('h-5', columnIndex === 0 ? 'w-1/4' : 'flex-1')}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton({ count = 4 }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="card p-5">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-7 w-32" />
          <Skeleton className="mt-2 h-3 w-20" />
        </div>
      ))}
    </div>
  )
}

export function LoadingState({ label = 'Loading...' }) {
  return (
    <div className="flex items-center justify-center gap-3 p-10 text-slate-500 dark:text-slate-400">
      <Spinner />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950/40">
      <div className="flex items-start gap-3">
        <svg
          className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v5M12 16h.01" strokeLinecap="round" />
        </svg>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-red-800 dark:text-red-300">{title}</p>
          {message && <p className="mt-1 text-sm text-red-700 dark:text-red-400">{message}</p>}
          {onRetry && (
            <Button variant="danger" size="sm" className="mt-4" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', description, action, icon }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800">
        {icon ?? (
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M4 7h16M4 12h16M4 17h10" strokeLinecap="round" />
          </svg>
        )}
      </div>
      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/* ------------------------------------------------------------------- Tabs */
export function Tabs({ tabs = [], active, onChange, className = '' }) {
  return (
    <div className={cx('scroll-x border-b border-slate-200 dark:border-slate-800', className)}>
      <nav className="flex min-w-max gap-1" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active === tab.key}
            onClick={() => onChange(tab.key)}
            className={cx(
              '-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm font-medium transition',
              active === tab.key
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200',
            )}
          >
            {tab.label}
            {tab.count !== undefined && tab.count !== null && (
              <Badge size="xs" tone={active === tab.key ? 'indigo' : 'slate'}>
                {tab.count}
              </Badge>
            )}
          </button>
        ))}
      </nav>
    </div>
  )
}

/* --------------------------------------------------------------- Stat tile */
export function StatCard({ label, value, sub, tone = 'slate', icon, onClick }) {
  const tones = {
    slate: 'text-slate-900 dark:text-slate-100',
    emerald: 'text-emerald-600 dark:text-emerald-400',
    amber: 'text-amber-600 dark:text-amber-400',
    red: 'text-red-600 dark:text-red-400',
    indigo: 'text-indigo-600 dark:text-indigo-400',
    blue: 'text-blue-600 dark:text-blue-400',
  }
  const Wrapper = onClick ? 'button' : 'div'

  return (
    <Wrapper
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={cx(
        'card p-4 text-left transition sm:p-5',
        onClick && 'hover:border-indigo-300 hover:shadow-md dark:hover:border-indigo-700',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {label}
        </p>
        {icon && <span className="text-slate-300 dark:text-slate-600">{icon}</span>}
      </div>
      <p className={cx('mt-2 text-2xl font-semibold tracking-tight', tones[tone] ?? tones.slate)}>
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{sub}</p>}
    </Wrapper>
  )
}

/* ------------------------------------------------------------ misc pieces */
export function Divider({ label, className = '' }) {
  if (!label) return <hr className={cx('border-slate-200 dark:border-slate-800', className)} />
  return (
    <div className={cx('flex items-center gap-3', className)}>
      <hr className="flex-1 border-slate-200 dark:border-slate-800" />
      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</span>
      <hr className="flex-1 border-slate-200 dark:border-slate-800" />
    </div>
  )
}

/** A label/value row, used all over detail panels. */
export function DetailRow({ label, children, className = '' }) {
  return (
    <div className={cx('flex items-baseline justify-between gap-4 py-1.5', className)}>
      <dt className="shrink-0 text-sm text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="min-w-0 text-right text-sm font-medium text-slate-900 dark:text-slate-100">
        {children}
      </dd>
    </div>
  )
}

/** Toolbar above a list: search on the left, filters and actions on the right. */
export function Toolbar({ children, className = '' }) {
  return (
    <div
      className={cx(
        'flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between dark:border-slate-800',
        className,
      )}
    >
      {children}
    </div>
  )
}

/** Progress meter, used for margin, collection and fulfilment completeness. */
export function ProgressBar({ value = 0, tone = 'indigo', className = '', label }) {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0))
  const tones = {
    indigo: 'bg-indigo-500',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  }
  return (
    <div className={className}>
      {label && (
        <div className="mb-1 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span>{label}</span>
          <span className="font-medium text-slate-700 dark:text-slate-300">{clamped.toFixed(1)}%</span>
        </div>
      )}
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cx('h-full rounded-full transition-all duration-300', tones[tone] ?? tones.indigo)}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}

/** Number input with +/- steppers, for line quantities. */
export function QuantityStepper({ value, onChange, min = 1, max = 100000, disabled }) {
  const [draft, setDraft] = useState(String(value ?? min))

  // Re-sync when the server echoes a different value back (a manager override,
  // or another tab changing the line).
  useEffect(() => {
    setDraft(String(value ?? min))
  }, [value, min])

  const commit = (next) => {
    const parsed = Number.parseInt(next, 10)
    const clamped = Number.isNaN(parsed) ? min : Math.max(min, Math.min(max, parsed))
    setDraft(String(clamped))
    if (clamped !== value) onChange(clamped)
  }

  return (
    <div className="inline-flex items-stretch overflow-hidden rounded-lg ring-1 ring-inset ring-slate-300 dark:ring-slate-700">
      <button
        type="button"
        disabled={disabled || value <= min}
        onClick={() => commit(String(Number(value) - 1))}
        className="px-2.5 text-slate-600 transition hover:bg-slate-100 disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-800"
        aria-label="Decrease quantity"
      >
        -
      </button>
      <input
        type="number"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={(event) => commit(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur()
        }}
        aria-label="Quantity"
        className="w-14 border-0 bg-transparent py-1.5 text-center text-sm text-slate-900 focus:ring-0 dark:text-slate-100"
      />
      <button
        type="button"
        disabled={disabled || value >= max}
        onClick={() => commit(String(Number(value) + 1))}
        className="px-2.5 text-slate-600 transition hover:bg-slate-100 disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-800"
        aria-label="Increase quantity"
      >
        +
      </button>
    </div>
  )
}

/** Avatar with initials fallback, used in headers and activity trails. */
export function Avatar({ name, src, size = 'md' }) {
  const sizes = { sm: 'h-7 w-7 text-xs', md: 'h-9 w-9 text-sm', lg: 'h-12 w-12 text-base' }
  const [broken, setBroken] = useState(false)

  if (src && !broken) {
    return (
      <img
        src={src}
        alt={name || 'User'}
        onError={() => setBroken(true)}
        className={cx('shrink-0 rounded-full object-cover', sizes[size] ?? sizes.md)}
      />
    )
  }

  return (
    <span
      className={cx(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-indigo-100 font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
        sizes[size] ?? sizes.md,
      )}
      aria-hidden="true"
    >
      {(name || '?')
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part.charAt(0).toUpperCase())
        .join('')}
    </span>
  )
}
