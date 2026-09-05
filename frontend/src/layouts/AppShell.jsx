import { NavLink, Outlet } from 'react-router-dom'

/**
 * Shell for the internal application.
 *
 * Role-specific layouts (Admin, Sales, Manager, Finance) and the separate
 * customer portal layout are added in Phase 2; this shell holds the shared
 * chrome those layouts will build on.
 */
export default function AppShell() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-900 text-sm font-bold text-white">
              D
            </span>
            <div>
              <p className="text-sm font-semibold leading-tight">DealFlow360</p>
              <p className="text-xs text-slate-500">Sales Operations Platform</p>
            </div>
          </div>
          <nav className="flex items-center gap-1">
            <NavItem to="/">System Status</NavItem>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}

function NavItem({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-sm font-medium transition ${
          isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
        }`
      }
    >
      {children}
    </NavLink>
  )
}
