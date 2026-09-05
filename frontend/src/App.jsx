import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AppShell from './layouts/AppShell'
import NotFound from './pages/NotFound'
import SystemStatus from './pages/SystemStatus'

/**
 * Application router.
 *
 * Phase 1 exposes the system status screen only. Authentication routes
 * (/login, /signup, /customer-login), the role-guarded internal layouts and
 * the separate /portal customer experience are added in Phase 2.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<SystemStatus />} />
          <Route path="/status" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
