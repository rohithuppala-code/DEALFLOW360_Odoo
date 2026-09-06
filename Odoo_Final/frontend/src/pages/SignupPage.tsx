import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '../auth'
import { Btn } from '../components/ui'

const ROLES = [
  { value: 'SALES_REP', label: 'Sales Rep' },
  { value: 'SALES_MANAGER', label: 'Sales Manager' },
  { value: 'FINANCE', label: 'Finance' },
  { value: 'ADMIN', label: 'Admin' },
  { value: 'CUSTOMER', label: 'Customer' },
]

export default function SignupPage() {
  const { signup } = useAuth()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('SALES_REP')
  const [company, setCompany] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const user = await signup({
        name,
        email,
        password,
        role,
        company: role === 'CUSTOMER' ? company : undefined,
      })
      toast.success(`Welcome, ${user.name}`)
      nav(user.role === 'CUSTOMER' ? '/portal' : '/')
    } catch {
      toast.error('Could not create the account. Try a different email.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-art">
        <div>
          <div className="badge teal">DEAL OPERATING SYSTEM</div>
          <h1 style={{ margin: '18px 0 12px' }}>Create your workspace identity.</h1>
          <p style={{ maxWidth: 480, fontSize: 16 }}>
            Sign up as sales, finance, admin, or a customer to negotiate live quotations.
          </p>
        </div>
      </section>
      <section className="login-form">
        <form className="card card-pad" style={{ width: 'min(440px, 100%)' }} onSubmit={submit} aria-busy={busy}>
          <div className="kicker">Workspace</div>
          <h2 style={{ fontFamily: 'var(--display)', fontSize: 28, marginTop: 4 }}>Sign up</h2>
          <p className="muted">Choose exactly one role. Customers can negotiate quotes sent to them.</p>
          <div className="stack" style={{ marginTop: 16 }}>
            <label className="field">
              Full name
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label className="field">
              Email
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
            </label>
            <label className="field">
              Password
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={6} required />
            </label>
            <label className="field">
              Role
              <select className="input" value={role} onChange={(e) => setRole(e.target.value)} required>
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </label>
            {role === 'CUSTOMER' ? (
              <label className="field">
                Company
                <input className="input" value={company} onChange={(e) => setCompany(e.target.value)} required />
              </label>
            ) : null}
            <Btn type="submit" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</Btn>
          </div>
          <p className="muted" style={{ marginTop: 16 }}>
            Already have an account? <Link to="/login" style={{ color: 'var(--wine-800)', fontWeight: 650 }}>Sign in</Link>
          </p>
        </form>
      </section>
    </div>
  )
}
