import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '../auth'
import { Btn } from '../components/ui'

export default function LoginPage() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(email, password)
      toast.success(`Welcome back, ${user.name}`)
      nav(user.role === 'CUSTOMER' ? '/portal' : '/')
    } catch {
      setError('Invalid email or password')
      toast.error('Invalid email or password')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-art">
        <div>
          <div className="badge teal">DEAL OPERATING SYSTEM</div>
          <h1 style={{ margin: '18px 0 12px' }}>
            One path from quotation to cash.
          </h1>
          <p style={{ maxWidth: 480, fontSize: 16 }}>
            Quote, approve, share, negotiate, fulfill, and bill — with every commercial decision explained.
          </p>
        </div>
      </section>
      <section className="login-form">
        <form className="card card-pad" style={{ width: 'min(440px, 100%)' }} onSubmit={submit} aria-busy={busy}>
          <div className="kicker">Workspace</div>
          <h2 style={{ fontFamily: 'var(--display)', fontSize: 28, marginTop: 4 }}>Sign in</h2>
          <p className="muted">Use the account you created on the signup page.</p>
          <div className="stack" style={{ marginTop: 16 }}>
            <label className="field">
              Email
              <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
            </label>
            <label className="field">
              Password
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </label>
            {error ? <p className="auth-error" role="alert">{error}</p> : null}
            <Btn type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Enter workspace'}</Btn>
          </div>
          <p className="muted" style={{ marginTop: 16 }}>
            New here? <Link to="/signup" style={{ color: 'var(--wine-800)', fontWeight: 650 }}>Create an account</Link>
          </p>
        </form>
      </section>
    </div>
  )
}
