import { Check } from 'lucide-react'
import type { Workflow } from '../types'
import { Btn } from './ui'

export function DealStepper({ workflow }: { workflow?: Workflow | null }) {
  const stages = workflow?.stages || []
  if (!stages.length) return null
  return (
    <div className="card card-pad">
      <div className="kicker" style={{ marginBottom: 12 }}>Deal path</div>
      <div className="stepper" role="list">
        {stages.map((s, i) => (
          <div key={s.key} className={`stepper-step ${s.state}`} role="listitem">
            <div className="step-dot" aria-hidden>
              {s.state === 'done' ? <Check size={14} /> : i + 1}
            </div>
            <div className="step-copy">
              <div className="l">{s.label}</div>
              <div className="h">{s.hint}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function NextAction({
  workflow,
  busy,
  onSubmit,
  onSend,
  onConfirm,
  onNegotiate,
  onBilling,
  onApprove,
}: {
  workflow?: Workflow | null
  busy?: boolean
  onSubmit?: () => void
  onSend?: () => void
  onConfirm?: () => void
  onNegotiate?: () => void
  onBilling?: () => void
  onApprove?: () => void
}) {
  const action = workflow?.next_action
  if (!action) return null
  const tone = action.tone === 'accent' ? 'good' : action.tone
  const run = () => {
    if (action.id === 'submit') {
      onSubmit?.()
      return
    }
    if (action.id === 'approve') {
      onApprove?.()
      return
    }
    if (action.id === 'send' || action.id === 'revise') {
      if (onSend) onSend()
      else onSubmit?.()
      return
    }
    if (action.id === 'confirm') onConfirm?.()
    if (action.id === 'negotiate') onNegotiate?.()
    if (action.id === 'billing') onBilling?.()
  }
  const clickable = !['wait', 'none'].includes(action.id)
  return (
    <div className={`next-action ${tone || ''}`}>
      <div>
        <div className="kicker">What to do next</div>
        <h3 style={{ marginTop: 4 }}>{action.label}</h3>
        <p className="muted" style={{ margin: '6px 0 0', maxWidth: 640 }}>{action.reason}</p>
      </div>
      {clickable ? (
        <Btn kind="accent" disabled={busy} onClick={run}>
          {busy ? 'Working…' : action.label}
        </Btn>
      ) : null}
    </div>
  )
}
