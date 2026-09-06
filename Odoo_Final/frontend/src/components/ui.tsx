import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import { clsx } from 'clsx'
import { healthTone, pct, prettyStatus, riskTone, statusTone } from '../utils/format'

function useDialogFocus(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    const root = ref.current
    const items = () =>
      [...(root?.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])') || [])].filter((el) => !el.hasAttribute('disabled'))
    items()[0]?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab') return
      const list = items()
      if (!list.length) return
      const first = list[0]
      const last = list[list.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.classList.add('nav-lock')
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('nav-lock')
      prev?.focus()
    }
  }, [])
  return ref
}

export function Card({ children, className, style, id }: { children: ReactNode; className?: string; style?: CSSProperties; id?: string }) {
  return <section id={id} style={style} className={clsx('card', className)}>{children}</section>
}

export function Metric({ label, value, hint, quiet }: { label: string; value: ReactNode; hint?: string; quiet?: boolean }) {
  return (
    <div className={clsx('card metric', quiet && 'quiet')}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  )
}

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  return <span className={clsx('badge', tone)}>{children}</span>
}

export function StatusBadge({ value }: { value?: string }) {
  return <Badge tone={statusTone(value)}>{prettyStatus(value)}</Badge>
}

export function RiskBadge({ score, level }: { score?: number; level?: string }) {
  return (
    <Badge tone={riskTone(score)}>
      Risk {Math.round(score || 0)} {level ? `· ${level}` : ''}
    </Badge>
  )
}

export function HealthScore({ score }: { score?: number }) {
  const p = Math.max(0, Math.min(100, Number(score || 0)))
  return (
    <div className="health-ring" style={{ '--p': p } as CSSProperties} aria-label={`Deal health ${p}`}>
      <div>
        <strong>{Math.round(p)}</strong>
        <div className="muted" style={{ fontSize: 9 }}>HEALTH</div>
      </div>
    </div>
  )
}

export function Percent({ value }: { value?: number }) {
  const tone = Number(value) >= 18 ? 'good' : Number(value) >= 12 ? 'warn' : 'bad'
  return (
    <span className={clsx('mono', tone === 'good' ? 'delta-up' : tone === 'bad' ? 'delta-down' : '')}>
      {pct(value)}
    </span>
  )
}

export function Btn({
  children,
  onClick,
  kind = 'primary',
  disabled,
  type = 'button',
}: {
  children: ReactNode
  onClick?: () => void
  kind?: 'primary' | 'ghost' | 'accent' | 'danger' | 'sm'
  disabled?: boolean
  type?: 'button' | 'submit'
}) {
  const cls = kind === 'sm' ? 'btn sm ghost' : kind === 'primary' || kind === 'accent' ? 'btn' : `btn ${kind}`
  return (
    <button className={cls} onClick={onClick} disabled={disabled} type={type}>
      {children}
    </button>
  )
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {body ? <p>{body}</p> : null}
      {action}
    </div>
  )
}

export function SkeletonGrid({ n = 4 }: { n?: number }) {
  return (
    <div className="grid-4">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="card" style={{ padding: 16 }}>
          <div className="skeleton" />
          <div className="skeleton" style={{ marginTop: 12, height: 24 }} />
        </div>
      ))}
    </div>
  )
}

export function Modal({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
}) {
  if (!open) return null
  return <DialogShell titleId="modal-title" title={title} onClose={onClose}>{children}</DialogShell>
}

function DialogShell({
  titleId,
  title,
  onClose,
  children,
  compact,
  hideClose,
}: {
  titleId: string
  title: string
  onClose: () => void
  children: ReactNode
  compact?: boolean
  hideClose?: boolean
}) {
  const ref = useDialogFocus(onClose)
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        ref={ref}
        className="modal card-pad"
        style={compact ? { width: 'min(440px, 100%)' } : undefined}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        {hideClose ? (
          <h2 id={titleId}>{title}</h2>
        ) : (
          <div className="spread" style={{ marginBottom: 12 }}>
            <h2 id={titleId}>{title}</h2>
            <Btn kind="ghost" onClick={onClose}>Close</Btn>
          </div>
        )}
        {children}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  body: string
  confirmLabel: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onClose: () => void
}) {
  if (!open) return null
  return (
    <DialogShell titleId="confirm-title" title={title} onClose={onClose} compact hideClose>
      <p className="muted">{body}</p>
      <div className="row" style={{ marginTop: 16, justifyContent: 'flex-end' }}>
        <Btn kind="ghost" onClick={onClose}>Cancel</Btn>
        <Btn kind={danger ? 'danger' : 'accent'} disabled={busy} onClick={onConfirm}>
          {busy ? 'Working…' : confirmLabel}
        </Btn>
      </div>
    </DialogShell>
  )
}

export function HealthChip({ score }: { score?: number }) {
  return <Badge tone={healthTone(score)}>Health {Math.round(score || 0)}</Badge>
}

export function PageHeader({
  kicker,
  title,
  subtitle,
  actions,
}: {
  kicker?: string
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="page-head">
      <div>
        {kicker ? <div className="kicker">{kicker}</div> : null}
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div className="row" style={{ flexWrap: 'wrap' }}>{actions}</div> : null}
    </div>
  )
}

export function ErrorState({
  title = 'Could not load this view',
  body,
  onRetry,
}: {
  title?: string
  body?: string
  onRetry?: () => void
}) {
  return (
    <Card className="card-pad">
      <Empty
        title={title}
        body={body || 'Please try again.'}
        action={onRetry ? <Btn onClick={onRetry}>Retry</Btn> : undefined}
      />
    </Card>
  )
}

export function Bar({ value, max = 100, tone }: { value: number; max?: number; tone?: string }) {
  const p = Math.max(0, Math.min(100, (value / (max || 1)) * 100))
  const color =
    tone === 'warn' ? 'var(--warn)' : tone === 'bad' ? 'var(--bad)' : tone === 'good' ? 'var(--good)' : 'var(--accent)'
  return (
    <div className="bar" role="meter" aria-label="Inventory load" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${p}%`, background: color }} />
    </div>
  )
}

export function Pagination({
  page,
  pageSize = 20,
  total = 0,
  pages = 1,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
}: {
  page: number
  pageSize?: number
  total?: number
  pages?: number
  onPageChange: (newPage: number) => void
  onPageSizeChange?: (newPageSize: number) => void
  pageSizeOptions?: number[]
}) {
  const calcPages = pages || Math.max(1, Math.ceil(total / (pageSize || 20)))
  if (calcPages <= 1 && total === 0) return null

  const startItem = total > 0 ? (page - 1) * pageSize + 1 : 0
  const endItem = total > 0 ? Math.min(page * pageSize, total) : 0

  const getPageNumbers = () => {
    const items: (number | string)[] = []
    if (calcPages <= 7) {
      for (let i = 1; i <= calcPages; i++) items.push(i)
    } else {
      items.push(1)
      if (page > 3) items.push('...')
      const start = Math.max(2, page - 1)
      const end = Math.min(calcPages - 1, page + 1)
      for (let i = start; i <= end; i++) items.push(i)
      if (page < calcPages - 2) items.push('...')
      items.push(calcPages)
    }
    return items
  }

  return (
    <div className="pagination">
      <div className="row muted" style={{ fontSize: 13 }}>
        {total > 0 ? (
          <span>Showing <strong>{startItem}–{endItem}</strong> of <strong>{total}</strong></span>
        ) : (
          <span>Page {page} of {calcPages}</span>
        )}
        {onPageSizeChange ? (
          <label className="pagination-size" style={{ marginLeft: 12 }}>
            <span>Per page:</span>
            <select
              className="input"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <div className="pagination-pages">
        <button
          type="button"
          className="pagination-page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Previous page"
        >
          ‹
        </button>
        {getPageNumbers().map((p, idx) =>
          typeof p === 'number' ? (
            <button
              key={`p-${p}`}
              type="button"
              className={clsx('pagination-page', p === page && 'active')}
              onClick={() => onPageChange(p)}
            >
              {p}
            </button>
          ) : (
            <span key={`e-${idx}`} className="pagination-ellipsis">…</span>
          )
        )}
        <button
          type="button"
          className="pagination-page"
          disabled={page >= calcPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
        >
          ›
        </button>
      </div>
    </div>
  )
}

