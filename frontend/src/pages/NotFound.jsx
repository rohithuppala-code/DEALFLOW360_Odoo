import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-10 text-center">
      <p className="text-3xl font-semibold text-slate-900">404</p>
      <p className="mt-2 text-sm text-slate-500">This page does not exist.</p>
      <Link
        to="/"
        className="mt-6 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        Back to System Status
      </Link>
    </div>
  )
}
