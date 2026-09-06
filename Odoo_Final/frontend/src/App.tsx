import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import AppLayout, { CustomerLayout } from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'
import QuotesPage from './pages/QuotesPage'
import QuoteBuilderPage from './pages/QuoteBuilderPage'
import DealCenterPage from './pages/DealCenterPage'
import ApprovalsPage from './pages/ApprovalsPage'
import ApprovalDetailPage from './pages/ApprovalDetailPage'
import CustomersPage from './pages/CustomersPage'
import FulfillmentPage from './pages/FulfillmentPage'
import BillingPage from './pages/BillingPage'
import AnalyticsPage from './pages/AnalyticsPage'
import AdminPage from './pages/AdminPage'
import SearchPage from './pages/SearchPage'
import NotificationsPage from './pages/NotificationsPage'
import { CustomerHome, CustomerInvoices, CustomerQuote } from './pages/CustomerPortal'
import type { Role } from './types'

function Guard({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'CUSTOMER' && !window.location.pathname.startsWith('/portal')) {
    return <Navigate to="/portal" replace />
  }
  if (roles && !roles.includes(user.role) && user.role !== 'ADMIN') return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        element={
          <Guard>
            <AppLayout />
          </Guard>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/quotes" element={<QuotesPage />} />
        <Route path="/quotes/new" element={<QuoteBuilderPage />} />
        <Route path="/quotes/:id" element={<DealCenterPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/approvals/:id" element={<ApprovalDetailPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/fulfillment" element={<FulfillmentPage />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
      </Route>
      <Route
        element={
          <Guard>
            <CustomerLayout />
          </Guard>
        }
      >
        <Route path="/portal" element={<CustomerHome />} />
        <Route path="/portal/quotes/:id" element={<CustomerQuote />} />
        <Route path="/portal/invoices" element={<CustomerInvoices />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
