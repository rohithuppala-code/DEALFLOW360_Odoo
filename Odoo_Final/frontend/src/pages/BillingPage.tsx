import { Fragment, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, type ApiOk, type Page } from '../api/client'
import { useAuth } from '../auth'
import { Btn, ConfirmDialog, Empty, ErrorState, Modal, PageHeader, Pagination, SkeletonGrid, StatusBadge } from '../components/ui'
import { inr } from '../utils/format'

type Invoice = {
  id: number
  invoice_number: string
  customer?: { name?: string }
  total: number
  balance_due: number
  status: string
  one_time?: number
  recurring?: number
  proration?: number
  quote_id?: number
  lines?: { id: number; description: string; quantity: number; amount: number; billing_type: string }[]
  payments?: { id: number; amount: number; method: string; status: string }[]
}

type Sub = {
  id: number
  customer?: string
  plan?: string
  plan_id?: number
  mrr: number
  status: string
  next_billing_date?: string
  quantity: number
  unit_price: number
  interval?: string
  schedule?: string[]
}

type PaymentRecord = {
  id: number
  invoice_id: number
  invoice_number?: string
  customer?: string
  amount: number
  method: string
  status: string
  paid_at?: string
  reference?: string
}

function lineGroup(lines: Invoice['lines'], type: string) {
  return (lines || []).filter((ln) => ln.billing_type === type)
}

export default function BillingPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const canPay = user?.role === 'FINANCE' || user?.role === 'ADMIN'
  const [open, setOpen] = useState<number | null>(null)
  const [cancelId, setCancelId] = useState<number | null>(null)

  // Pagination states
  const [invPage, setInvPage] = useState(1)
  const [invPageSize, setInvPageSize] = useState(20)
  const [subPage, setSubPage] = useState(1)
  const [subPageSize, setSubPageSize] = useState(20)
  const [payPage, setPayPage] = useState(1)
  const [payPageSize, setPayPageSize] = useState(20)

  // Payment modal state
  const [payInvoice, setPayInvoice] = useState<Invoice | null>(null)
  const [payType, setPayType] = useState<'FULL' | 'PARTIAL'>('FULL')
  const [payAmount, setPayAmount] = useState('')
  const [payMethod, setPayMethod] = useState('BANK_TRANSFER')
  const [payError, setPayError] = useState<string | null>(null)

  const invoices = useQuery({
    queryKey: ['invoices', invPage, invPageSize],
    queryFn: async () =>
      (await api.get<ApiOk<Page<Invoice>>>('/invoices', { params: { page: invPage, page_size: invPageSize } })).data.data,
  })
  const subs = useQuery({
    queryKey: ['subs', subPage, subPageSize],
    queryFn: async () =>
      (await api.get<ApiOk<Page<Sub> | Sub[]>>('/subscriptions', { params: { page: subPage, page_size: subPageSize } })).data.data,
  })
  const paymentsQuery = useQuery({
    queryKey: ['payments', payPage, payPageSize],
    queryFn: async () =>
      (await api.get<ApiOk<Page<PaymentRecord> | PaymentRecord[]>>('/payments', { params: { page: payPage, page_size: payPageSize } })).data.data,
    enabled: canPay,
  })
  const plans = useQuery({
    queryKey: ['sub-plans'],
    queryFn: async () => (await api.get<ApiOk<{ id: number; name: string; price: number }[]>>('/subscriptions/plans')).data.data,
    enabled: canPay,
  })
  const schedule = useQuery({
    queryKey: ['bill-sched'],
    queryFn: async () => (await api.get<ApiOk<{ id: number; customer?: string; plan?: string; next_billing_date?: string; mrr: number; interval?: string }[]>>('/billing/schedules')).data.data,
  })

  const pay = useMutation({
    mutationFn: async ({ id, amount, method }: { id: number; amount: number; method: string }) =>
      api.post(`/invoices/${id}/pay`, { amount, payment_method: method }),
    onSuccess: () => {
      toast.success('Payment recorded successfully')
      qc.invalidateQueries({ queryKey: ['invoices'] })
      qc.invalidateQueries({ queryKey: ['payments'] })
      qc.invalidateQueries({ queryKey: ['subs'] })
      setPayInvoice(null)
      setPayType('FULL')
      setPayAmount('')
      setPayError(null)
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || 'Failed to record payment'
      setPayError(msg)
      toast.error(msg)
    },
  })

  const cancel = useMutation({
    mutationFn: async (id: number) => api.post(`/subscriptions/${id}/cancel`, { reason: 'Cancelled by finance' }),
    onSuccess: () => {
      toast.success('Subscription cancelled · credit note issued if unused days remain')
      qc.invalidateQueries({ queryKey: ['subs'] })
      qc.invalidateQueries({ queryKey: ['invoices'] })
      setCancelId(null)
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to cancel subscription')
    },
  })

  const change = useMutation({
    mutationFn: async ({ id, plan_id }: { id: number; plan_id: number }) =>
      api.post(`/subscriptions/${id}/change`, { plan_id, reason: 'Plan change by finance' }),
    onSuccess: () => {
      toast.success('Plan updated with proration')
      qc.invalidateQueries({ queryKey: ['subs'] })
      qc.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to change plan')
    },
  })

  const invoiceItems = invoices.data?.items || []
  const subItems: Sub[] = Array.isArray(subs.data) ? subs.data : subs.data?.items || []
  const subTotal = Array.isArray(subs.data) ? subs.data.length : subs.data?.total || 0
  const subPages = Array.isArray(subs.data) ? 1 : subs.data?.pages || 1

  const paymentItems: PaymentRecord[] = Array.isArray(paymentsQuery.data)
    ? paymentsQuery.data
    : paymentsQuery.data?.items || []
  const paymentTotal = Array.isArray(paymentsQuery.data) ? paymentsQuery.data.length : paymentsQuery.data?.total || 0
  const paymentPages = Array.isArray(paymentsQuery.data) ? 1 : paymentsQuery.data?.pages || 1

  if (invoices.isError) return <ErrorState title="We couldn't load billing." onRetry={() => invoices.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Finance"
        title="Billing"
        subtitle="One-time invoices, recurring schedules, proration, credits, and payment status."
      />
      {invoices.isLoading ? <SkeletonGrid n={4} /> : null}

      <div className="card">
        <div className="card-pad"><h3>Invoices</h3></div>
        {invoiceItems.length === 0 && !invoices.isLoading ? (
          <Empty title="No invoices yet" body="Confirm an approved quote to raise the first invoice." />
        ) : (
          <div className="table-wrap tall">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Customer</th>
                  <th className="num">One-time</th>
                  <th className="num">Recurring</th>
                  <th className="num">Total</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {invoiceItems.map((inv) => {
                  const oneTime = lineGroup(inv.lines, 'ONE_TIME')
                  const recurring = lineGroup(inv.lines, 'RECURRING')
                  const proration = lineGroup(inv.lines, 'PRORATION')
                  const paid = Number(inv.total) - Number(inv.balance_due)
                  return (
                    <Fragment key={inv.id}>
                      <tr
                        tabIndex={0}
                        style={{ cursor: 'pointer' }}
                        onClick={() => setOpen(open === inv.id ? null : inv.id)}
                        onKeyDown={(e) => { if (e.key === 'Enter') setOpen(open === inv.id ? null : inv.id) }}
                      >
                        <td className="mono">{inv.invoice_number}</td>
                        <td>{inv.customer?.name || ''}</td>
                        <td className="num mono">{inr(Number(inv.one_time))}</td>
                        <td className="num mono">{inr(Number(inv.recurring))}</td>
                        <td className="num mono">{inr(Number(inv.total))}</td>
                        <td className="num mono">{inr(Number(inv.balance_due))}</td>
                        <td><StatusBadge value={inv.status} /></td>
                        <td onClick={(e) => e.stopPropagation()}>
                          {canPay && Number(inv.balance_due) > 0 ? (
                            <Btn
                              kind="sm"
                              onClick={() => {
                                setPayInvoice(inv)
                                setPayType('FULL')
                                setPayAmount(String(inv.balance_due))
                                setPayMethod('BANK_TRANSFER')
                                setPayError(null)
                              }}
                            >
                              Record payment
                            </Btn>
                          ) : null}
                        </td>
                      </tr>
                      {open === inv.id ? (
                        <tr className="invoice-detail">
                          <td colSpan={8}>
                            <div className="card-pad stack">
                              {oneTime.length > 0 ? (
                                <div>
                                  <div className="kicker">One-time</div>
                                  {oneTime.map((ln) => (
                                    <div className="factor" key={ln.id}>
                                      <span>{ln.description} <span className="muted">× {ln.quantity}</span></span>
                                      <span className="mono">{inr(ln.amount)}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {recurring.length > 0 ? (
                                <div>
                                  <div className="kicker">Recurring</div>
                                  {recurring.map((ln) => (
                                    <div className="factor" key={ln.id}>
                                      <span>{ln.description} <span className="muted">× {ln.quantity}</span></span>
                                      <span className="mono">{inr(ln.amount)}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {proration.length > 0 ? (
                                <div>
                                  <div className="kicker">Proration / credits</div>
                                  {proration.map((ln) => (
                                    <div className="factor" key={ln.id}>
                                      <span>{ln.description}</span>
                                      <span className="mono">{inr(ln.amount)}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {(inv.lines || []).length === 0 ? <p className="muted">No line items on this invoice.</p> : null}
                              <div className="factor"><span>Paid</span><span className="mono">{inr(paid)}</span></div>
                              <div className="factor"><strong>Balance</strong><strong className="mono">{inr(Number(inv.balance_due))}</strong></div>
                              {(inv.payments || []).length > 0 ? (
                                <div>
                                  <div className="kicker">Payment history</div>
                                  {(inv.payments || []).map((p) => (
                                    <div className="factor" key={p.id}>
                                      <span>{p.method} · {p.status}</span>
                                      <span className="mono">{inr(p.amount)}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={invPage}
          pageSize={invPageSize}
          total={invoices.data?.total || 0}
          pages={invoices.data?.pages || 1}
          onPageChange={setInvPage}
          onPageSizeChange={setInvPageSize}
        />
      </div>

      {canPay ? (
        <div className="card">
          <div className="card-pad"><h3>Recent Payments</h3></div>
          {paymentItems.length === 0 && !paymentsQuery.isLoading ? (
            <Empty title="No payments recorded" body="Recorded payments across all invoices will show here." />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Customer</th>
                    <th className="num">Amount</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Paid At</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentItems.map((p) => (
                    <tr key={p.id}>
                      <td className="mono">{p.invoice_number || `Invoice #${p.invoice_id}`}</td>
                      <td>{p.customer || '—'}</td>
                      <td className="num mono">{inr(p.amount)}</td>
                      <td>{p.method.replace('_', ' ')}</td>
                      <td><StatusBadge value={p.status} /></td>
                      <td className="muted">{p.paid_at ? new Date(p.paid_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pagination
            page={payPage}
            pageSize={payPageSize}
            total={paymentTotal}
            pages={paymentPages}
            onPageChange={setPayPage}
            onPageSizeChange={setPayPageSize}
          />
        </div>
      ) : null}

      <div className="card">
        <div className="card-pad"><h3>Recurring schedules</h3></div>
        {(schedule.data || []).length === 0 && !schedule.isLoading ? (
          <Empty title="No recurring schedules" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Plan</th>
                  <th>Next bill</th>
                  <th className="num">MRR</th>
                  <th>Interval</th>
                </tr>
              </thead>
              <tbody>
                {(schedule.data || []).map((s) => (
                  <tr key={s.id}>
                    <td>{s.customer}</td>
                    <td>{s.plan}</td>
                    <td>{s.next_billing_date || '—'}</td>
                    <td className="num mono">{inr(Number(s.mrr))}</td>
                    <td>{s.interval}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-pad"><h3>Subscriptions</h3></div>
        {subItems.length === 0 && !subs.isLoading ? (
          <Empty title="No subscriptions" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Plan</th>
                  <th className="num">Qty</th>
                  <th className="num">MRR</th>
                  <th>Status</th>
                  <th>Next bill</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {subItems.map((s) => (
                  <tr key={s.id}>
                    <td>{s.customer}</td>
                    <td>{s.plan}</td>
                    <td className="num mono">{s.quantity}</td>
                    <td className="num mono">{inr(Number(s.mrr))}</td>
                    <td><StatusBadge value={s.status} /></td>
                    <td>{s.next_billing_date || '—'}</td>
                    <td>
                      {canPay && s.status !== 'CANCELLED' ? (
                        <div className="row">
                          <select
                            className="input"
                            style={{ maxWidth: 160 }}
                            defaultValue=""
                            onChange={(e) => {
                              const planId = Number(e.target.value)
                              if (planId) change.mutate({ id: s.id, plan_id: planId })
                            }}
                          >
                            <option value="">Change plan</option>
                            {(plans.data || []).map((p) => (
                              <option key={p.id} value={p.id}>{p.name} · {inr(p.price, true)}</option>
                            ))}
                          </select>
                          <Btn kind="ghost" onClick={() => setCancelId(s.id)}>Cancel + credit</Btn>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={subPage}
          pageSize={subPageSize}
          total={subTotal}
          pages={subPages}
          onPageChange={setSubPage}
          onPageSizeChange={setSubPageSize}
        />
      </div>

      {/* Record Payment Modal */}
      <Modal
        open={payInvoice != null}
        title={`Record Payment — ${payInvoice?.invoice_number || ''}`}
        onClose={() => {
          setPayInvoice(null)
          setPayError(null)
        }}
      >
        {payInvoice ? (() => {
          const total = Number(payInvoice.total) || 0
          const balance = Number(payInvoice.balance_due) || 0
          const paidSoFar = Math.max(0, total - balance)
          const effectiveAmount = payType === 'FULL' ? balance : Number(payAmount) || 0
          const remainingAfter = Math.max(0, balance - effectiveAmount)
          const resultingStatus = effectiveAmount >= balance - 0.001 ? 'PAID' : 'PARTIALLY_PAID'
          const isAmountInvalid =
            payType === 'PARTIAL' && (isNaN(Number(payAmount)) || Number(payAmount) <= 0 || Number(payAmount) > balance + 0.05)

          return (
            <div className="stack" style={{ gap: 16 }}>
              <p className="muted" style={{ margin: 0 }}>
                Customer: <strong>{payInvoice.customer?.name || 'Customer'}</strong>
              </p>

              <div className="grid-3" style={{ gap: 10 }}>
                <div className="card card-pad" style={{ padding: 12, background: 'var(--cream-50)' }}>
                  <div className="muted" style={{ fontSize: 11, fontWeight: 650, textTransform: 'uppercase' }}>Invoice Total</div>
                  <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>{inr(total)}</div>
                </div>
                <div className="card card-pad" style={{ padding: 12, background: 'var(--cream-50)' }}>
                  <div className="muted" style={{ fontSize: 11, fontWeight: 650, textTransform: 'uppercase' }}>Already Paid</div>
                  <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4, color: 'var(--good)' }}>{inr(paidSoFar)}</div>
                </div>
                <div className="card card-pad" style={{ padding: 12, background: 'var(--cream-50)' }}>
                  <div className="muted" style={{ fontSize: 11, fontWeight: 650, textTransform: 'uppercase' }}>Remaining Balance</div>
                  <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4, color: 'var(--wine-700)' }}>{inr(balance)}</div>
                </div>
              </div>

              <div>
                <label style={{ fontWeight: 650, fontSize: 13, marginBottom: 6, display: 'block' }}>Payment Option</label>
                <div className="row" style={{ gap: 12 }}>
                  <label className="row" style={{ cursor: 'pointer', padding: '8px 14px', border: '1px solid var(--border)', borderRadius: 8, background: payType === 'FULL' ? 'var(--cream-100)' : '#fff' }}>
                    <input
                      type="radio"
                      name="payType"
                      checked={payType === 'FULL'}
                      onChange={() => {
                        setPayType('FULL')
                        setPayAmount(String(balance))
                        setPayError(null)
                      }}
                    />
                    <span style={{ fontWeight: 600 }}>Full Payment ({inr(balance)})</span>
                  </label>
                  <label className="row" style={{ cursor: 'pointer', padding: '8px 14px', border: '1px solid var(--border)', borderRadius: 8, background: payType === 'PARTIAL' ? 'var(--cream-100)' : '#fff' }}>
                    <input
                      type="radio"
                      name="payType"
                      checked={payType === 'PARTIAL'}
                      onChange={() => {
                        setPayType('PARTIAL')
                        setPayAmount('')
                        setPayError(null)
                      }}
                    />
                    <span style={{ fontWeight: 600 }}>Partial Payment</span>
                  </label>
                </div>
              </div>

              {payType === 'PARTIAL' ? (
                <label className="field">
                  <span>Payment Amount (₹) <span className="muted">(Max {inr(balance)})</span></span>
                  <input
                    type="number"
                    className="input"
                    step="any"
                    min="1"
                    max={balance}
                    placeholder={`Enter amount up to ${balance}`}
                    value={payAmount}
                    onChange={(e) => {
                      setPayAmount(e.target.value)
                      const val = Number(e.target.value)
                      if (val <= 0) {
                        setPayError('Payment amount must be greater than 0.')
                      } else if (val > balance + 0.05) {
                        setPayError(`Payment amount cannot exceed remaining balance of ${inr(balance)}.`)
                      } else {
                        setPayError(null)
                      }
                    }}
                  />
                </label>
              ) : null}

              <label className="field">
                <span>Payment Method</span>
                <select
                  className="input"
                  value={payMethod}
                  onChange={(e) => setPayMethod(e.target.value)}
                >
                  <option value="BANK_TRANSFER">Bank Transfer</option>
                  <option value="UPI">UPI</option>
                  <option value="CHEQUE">Cheque</option>
                  <option value="CREDIT_CARD">Credit / Debit Card</option>
                  <option value="CASH">Cash</option>
                </select>
              </label>

              {payError ? (
                <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bad-soft)', color: 'var(--bad)', fontSize: 13, fontWeight: 600 }}>
                  {payError}
                </div>
              ) : null}

              <div className="card card-pad" style={{ background: 'var(--cream-100)', padding: 12 }}>
                <div className="spread" style={{ fontSize: 13, marginBottom: 4 }}>
                  <span>Amount to Record:</span>
                  <strong className="mono">{inr(effectiveAmount)}</strong>
                </div>
                <div className="spread" style={{ fontSize: 13, marginBottom: 4 }}>
                  <span>Remaining Balance After Payment:</span>
                  <strong className="mono">{inr(remainingAfter)}</strong>
                </div>
                <div className="spread" style={{ fontSize: 13 }}>
                  <span>New Invoice Status:</span>
                  <StatusBadge value={resultingStatus} />
                </div>
              </div>

              <div className="row" style={{ justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
                <Btn
                  kind="ghost"
                  type="button"
                  onClick={() => {
                    setPayInvoice(null)
                    setPayError(null)
                  }}
                >
                  Cancel
                </Btn>
                <Btn
                  kind="accent"
                  type="button"
                  disabled={effectiveAmount <= 0 || isAmountInvalid || pay.isPending}
                  onClick={() => {
                    if (effectiveAmount <= 0 || isAmountInvalid) return
                    pay.mutate({
                      id: payInvoice.id,
                      amount: effectiveAmount,
                      method: payMethod,
                    })
                  }}
                >
                  {pay.isPending ? 'Recording…' : `Record Payment (${inr(effectiveAmount)})`}
                </Btn>
              </div>
            </div>
          )
        })() : null}
      </Modal>

      <ConfirmDialog
        open={cancelId != null}
        title="Cancel this subscription?"
        body="Unused days may be credited according to billing settings. This cannot be undone from this screen."
        confirmLabel="Cancel + credit"
        danger
        busy={cancel.isPending}
        onClose={() => setCancelId(null)}
        onConfirm={() => { if (cancelId != null) cancel.mutate(cancelId) }}
      />
    </div>
  )
}
