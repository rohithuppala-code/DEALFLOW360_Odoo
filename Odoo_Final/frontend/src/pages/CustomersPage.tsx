import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { api, type ApiOk, type Page } from '../api/client'
import type { Customer } from '../types'
import { Btn, Empty, ErrorState, Modal, PageHeader, Pagination, SkeletonGrid, StatusBadge } from '../components/ui'
import { inr } from '../utils/format'

const INITIAL_CUST_FORM = {
  name: '',
  code: '',
  email: '',
  phone: '',
  industry: '',
  city: '',
  customer_tier_id: '',
  credit_limit: '1000000',
  payment_terms: '30',
}

export default function CustomersPage() {
  const [sp, setSp] = useSearchParams()
  const q = sp.get('q') || ''
  const [debounced, setDebounced] = useState(q)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [pageKey, setPageKey] = useState(q)
  const [showCreate, setShowCreate] = useState(false)
  const [custForm, setCustForm] = useState(INITIAL_CUST_FORM)
  const [isSaving, setIsSaving] = useState(false)

  if (pageKey !== debounced) {
    setPageKey(debounced)
    setPage(1)
  }

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(q.trim()), 280)
    return () => window.clearTimeout(t)
  }, [q])

  const list = useQuery({
    queryKey: ['customers', debounced, page, pageSize],
    queryFn: async () =>
      (await api.get<ApiOk<Page<Customer>>>('/customers', { params: { page_size: pageSize, page, q: debounced || undefined } })).data.data,
    placeholderData: (prev) => prev,
  })
  const items = list.data?.items || []

  const tiers = useQuery({
    queryKey: ['customers', 'tiers'],
    queryFn: async () => (await api.get<ApiOk<{ id: number; name: string }[]>>('/customers/tiers')).data.data,
  })

  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!custForm.name.trim() || !custForm.code.trim() || !custForm.email.trim()) {
      toast.error('Please fill in Name, Code, and Email.')
      return
    }
    setIsSaving(true)
    try {
      await api.post('/customers', {
        name: custForm.name.trim(),
        code: custForm.code.trim().toUpperCase(),
        email: custForm.email.trim().toLowerCase(),
        phone: custForm.phone.trim() || undefined,
        industry: custForm.industry.trim() || undefined,
        city: custForm.city.trim() || undefined,
        customer_tier_id: custForm.customer_tier_id ? Number(custForm.customer_tier_id) : undefined,
        credit_limit: Number(custForm.credit_limit) || 1000000,
        payment_terms: Number(custForm.payment_terms) || 30,
      })
      toast.success('Customer created successfully')
      // Reset form ONLY on success
      setCustForm(INITIAL_CUST_FORM)
      setShowCreate(false)
      list.refetch()
    } catch (err: any) {
      // Retain form data and current input on failure so user does not lose progress
      toast.error(err?.response?.data?.detail || 'Failed to create customer')
    } finally {
      setIsSaving(false)
    }
  }

  if (list.isError) return <ErrorState title="We couldn't load customers." onRetry={() => list.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Accounts"
        title="Customers"
        subtitle="Tier, credit, and payment terms drive discount policy and risk."
        actions={
          <Btn onClick={() => setShowCreate(true)}>+ New customer</Btn>
        }
      />
      <label className="field" style={{ maxWidth: 320 }}>
        Search
        <input
          className="input"
          placeholder="Name, code, or email"
          value={q}
          onChange={(e) => {
            const next = new URLSearchParams(sp)
            if (e.target.value) next.set('q', e.target.value)
            else next.delete('q')
            setSp(next, { replace: true })
          }}
        />
      </label>
      {list.isLoading ? <SkeletonGrid n={4} /> : null}
      <div className="card">
        {!list.isLoading && items.length === 0 ? (
          <Empty title="No customers" body="Customers created here or via customer signup appear in the quote builder." action={<Btn onClick={() => setShowCreate(true)}>Create Customer</Btn>} />
        ) : (
          <div className="table-wrap tall stack-sm">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Code</th>
                  <th>Contact</th>
                  <th>Tier</th>
                  <th className="num">Credit</th>
                  <th>Terms</th>
                  <th>Portal</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id}>
                    <td data-label="Customer">
                      <strong>{c.name}</strong>
                      <div className="muted">{c.industry || c.city || '—'}</div>
                    </td>
                    <td className="mono" data-label="Code">{c.code}</td>
                    <td data-label="Contact">
                      {c.email}
                      {c.city ? <div className="muted">{c.city}</div> : null}
                    </td>
                    <td data-label="Tier">{c.tier?.name || '—'}</td>
                    <td className="num mono" data-label="Credit">{inr(c.credit_limit)}</td>
                    <td data-label="Terms">{c.payment_terms}d</td>
                    <td data-label="Portal">{c.has_portal ? <StatusBadge value="ACTIVE" /> : <span className="muted">No login</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={list.data?.page || 1}
          pages={list.data?.pages || 1}
          total={list.data?.total || 0}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={(ps) => {
            setPageSize(ps)
            setPage(1)
          }}
        />
      </div>

      {showCreate ? (
        <Modal open={showCreate} title="Create New Customer" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreateCustomer} className="stack" style={{ gap: 14 }}>
            <div className="grid-2">
              <label className="field">
                Customer / Company name *
                <input
                  className="input"
                  required
                  placeholder="Acme Corp"
                  value={custForm.name}
                  onChange={(e) => setCustForm({ ...custForm, name: e.target.value })}
                />
              </label>
              <label className="field">
                Customer Code *
                <input
                  className="input"
                  required
                  placeholder="ACME01"
                  value={custForm.code}
                  onChange={(e) => setCustForm({ ...custForm, code: e.target.value.toUpperCase() })}
                />
              </label>
            </div>
            <div className="grid-2">
              <label className="field">
                Email *
                <input
                  type="email"
                  className="input"
                  required
                  placeholder="buyer@acme.com"
                  value={custForm.email}
                  onChange={(e) => setCustForm({ ...custForm, email: e.target.value })}
                />
              </label>
              <label className="field">
                Phone
                <input
                  className="input"
                  placeholder="+91 9876543210"
                  value={custForm.phone}
                  onChange={(e) => setCustForm({ ...custForm, phone: e.target.value })}
                />
              </label>
            </div>
            <div className="grid-2">
              <label className="field">
                Customer Tier
                <select
                  className="input"
                  value={custForm.customer_tier_id}
                  onChange={(e) => setCustForm({ ...custForm, customer_tier_id: e.target.value })}
                >
                  <option value="">Select Tier (Optional)</option>
                  {(tiers.data || []).map((t) => (
                    <option key={t.id} value={String(t.id)}>{t.name}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                Industry
                <input
                  className="input"
                  placeholder="Technology, Manufacturing..."
                  value={custForm.industry}
                  onChange={(e) => setCustForm({ ...custForm, industry: e.target.value })}
                />
              </label>
            </div>
            <div className="grid-3">
              <label className="field">
                City
                <input
                  className="input"
                  placeholder="Mumbai"
                  value={custForm.city}
                  onChange={(e) => setCustForm({ ...custForm, city: e.target.value })}
                />
              </label>
              <label className="field">
                Credit limit (₹)
                <input
                  type="number"
                  className="input"
                  min="0"
                  value={custForm.credit_limit}
                  onChange={(e) => setCustForm({ ...custForm, credit_limit: e.target.value })}
                />
              </label>
              <label className="field">
                Payment terms (days)
                <input
                  type="number"
                  className="input"
                  min="0"
                  value={custForm.payment_terms}
                  onChange={(e) => setCustForm({ ...custForm, payment_terms: e.target.value })}
                />
              </label>
            </div>
            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 10, gap: 10 }}>
              <Btn type="button" kind="ghost" onClick={() => setShowCreate(false)}>Cancel</Btn>
              <Btn type="submit" disabled={isSaving}>{isSaving ? 'Creating...' : 'Create Customer'}</Btn>
            </div>
          </form>
        </Modal>
      ) : null}
    </div>
  )
}

