import { Fragment, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Bell,
  ClipboardCheck,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Receipt,
  Settings,
  Truck,
  Users,
  Wallet,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth'
import { api, type ApiOk } from '../api/client'
import GlobalSearch from '../components/GlobalSearch'
import type { Role } from '../types'

const NAV: { to: string; label: string; icon: typeof LayoutDashboard; roles: Role[]; group: string }[] = [
  { to: '/', label: 'Control Tower', icon: LayoutDashboard, roles: ['SALES_REP', 'SALES_MANAGER', 'FINANCE', 'OPERATIONS', 'ADMIN'], group: 'Workspace' },
  { to: '/quotes', label: 'Quotes', icon: ClipboardCheck, roles: ['SALES_REP', 'SALES_MANAGER', 'FINANCE', 'OPERATIONS', 'ADMIN'], group: 'Workspace' },
  { to: '/approvals', label: 'Approvals', icon: Gauge, roles: ['SALES_MANAGER', 'FINANCE', 'ADMIN', 'SALES_REP'], group: 'Workspace' },
  { to: '/customers', label: 'Customers', icon: Users, roles: ['SALES_REP', 'SALES_MANAGER', 'ADMIN'], group: 'Workspace' },
  { to: '/fulfillment', label: 'Fulfillment', icon: Truck, roles: ['OPERATIONS', 'FINANCE', 'ADMIN', 'SALES_MANAGER'], group: 'Workspace' },
  { to: '/billing', label: 'Billing', icon: Receipt, roles: ['FINANCE', 'ADMIN', 'SALES_MANAGER', 'OPERATIONS'], group: 'Workspace' },
  { to: '/analytics', label: 'Analytics', icon: Wallet, roles: ['SALES_MANAGER', 'FINANCE', 'ADMIN', 'OPERATIONS'], group: 'Workspace' },
  { to: '/admin', label: 'Admin', icon: Settings, roles: ['ADMIN'], group: 'Administration' },
]

function initials(name?: string) {
  return (name || '?')
    .split(' ')
    .slice(0, 2)
    .map((p) => p[0])
    .join('')
    .toUpperCase()
}

function prettyRole(role?: string) {
  return (role || '').replaceAll('_', ' ')
}

export default function AppLayout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const menuBtnRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)
  const profileRef = useRef<HTMLDivElement>(null)
  const notes = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => (await api.get<ApiOk<{ is_read: boolean }[]>>('/notifications')).data.data,
    refetchInterval: 15000,
  })
  const unread = (notes.data || []).filter((n) => !n.is_read).length
  const items = NAV.filter((n) => user && n.roles.includes(user.role))

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 860px)')
    const apply = () => {
      setIsMobile(mq.matches)
      if (mq.matches) setCollapsed(false)
      else setOpen(false)
    }
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    if (!open) return
    const menuBtn = menuBtnRef.current
    const first = sidebarRef.current?.querySelector<HTMLElement>('a, button')
    first?.focus()
    const nodes = () => [...(sidebarRef.current?.querySelectorAll<HTMLElement>('a, button') || [])]
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        return
      }
      if (e.key !== 'Tab') return
      const list = nodes()
      if (!list.length) return
      const firstEl = list[0]
      const lastEl = list[list.length - 1]
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault()
        lastEl.focus()
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault()
        firstEl.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.classList.add('nav-lock')
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('nav-lock')
      menuBtn?.focus()
    }
  }, [open])

  useEffect(() => {
    if (!profileOpen) return
    const onDoc = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) setProfileOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setProfileOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [profileOpen])

  function toggleNav() {
    if (isMobile) setOpen((v) => !v)
    else setCollapsed((v) => !v)
  }

  return (
    <div className={`shell ${collapsed && !isMobile ? 'collapsed' : ''}`}>
      <a className="skip-link" href="#main">Skip to content</a>
      {open ? <div className="nav-backdrop" onClick={() => setOpen(false)} /> : null}
      <aside
        id="app-sidebar"
        ref={sidebarRef}
        className={`sidebar ${open ? 'open' : ''}`}
        aria-label="Workspace"
        role={open ? 'dialog' : 'navigation'}
        aria-modal={open || undefined}
      >
        <div className="brand">
          <div className="brand-mark" aria-hidden>DF</div>
          <div className="brand-copy">
            <strong>DealFlow360</strong>
            <span>Quote → Close</span>
          </div>
        </div>
        {items.map((n, i) => (
          <Fragment key={n.to}>
            {collapsed && !isMobile && i > 0 && items[i - 1].group !== n.group ? <div className="nav-divider" /> : null}
            {(!collapsed || isMobile) && (i === 0 || items[i - 1].group !== n.group) ? (
              <div className="nav-label">{n.group}</div>
            ) : null}
            <NavLink
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              data-label={n.label}
              aria-label={n.label}
              onClick={() => setOpen(false)}
            >
              <n.icon aria-hidden />
              <span className="nav-text">{n.label}</span>
            </NavLink>
          </Fragment>
        ))}
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="row" style={{ flex: 1, minWidth: 0 }}>
            <button
              ref={menuBtnRef}
              className="icon-btn"
              type="button"
              onClick={toggleNav}
              aria-label={isMobile ? (open ? 'Close menu' : 'Open menu') : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-expanded={isMobile ? open : !collapsed}
              aria-controls="app-sidebar"
            >
              <Menu size={16} />
            </button>
            <GlobalSearch />
          </div>
          <div className="row">
            <button
              className="icon-btn"
              type="button"
              onClick={() => nav('/notifications')}
              aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
            >
              <Bell size={16} />
              {unread > 0 ? <span className="dot" /> : null}
            </button>
            <div className="profile" ref={profileRef}>
              <button
                className="profile-trigger"
                type="button"
                aria-haspopup="menu"
                aria-expanded={profileOpen}
                onClick={() => setProfileOpen((v) => !v)}
              >
                <div className="avatar">{initials(user?.name)}</div>
                <div className="meta">
                  <strong>{user?.name}</strong>
                  <span>{prettyRole(user?.role)}</span>
                </div>
              </button>
              {profileOpen ? (
                <div className="profile-menu" role="menu">
                  <div className="who">
                    <strong>{user?.name}</strong>
                    <span>{prettyRole(user?.role)}</span>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setProfileOpen(false)
                      logout()
                      nav('/login')
                    }}
                  >
                    <LogOut size={14} /> Sign out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>
        <main id="main" className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function CustomerLayout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div className="portal-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="topbar">
        <div className="portal-brand">
          <div className="brand-mark" aria-hidden>DF</div>
          <div>
            <strong>DealFlow360</strong>
            <span>Customer Portal</span>
          </div>
        </div>
        <div className="row">
          <NavLink to="/portal" end className={({ isActive }) => `portal-link ${isActive ? 'active' : ''}`}>
            Quotes
          </NavLink>
          <NavLink to="/portal/invoices" className={({ isActive }) => `portal-link ${isActive ? 'active' : ''}`}>
            Invoices
          </NavLink>
          <span className="muted">{user?.name}</span>
          <button className="btn ghost sm" type="button" onClick={() => { logout(); nav('/login') }}>
            Sign out
          </button>
        </div>
      </header>
      <main id="main" className="page">
        <Outlet />
      </main>
    </div>
  )
}
