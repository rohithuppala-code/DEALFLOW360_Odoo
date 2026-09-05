import { getHealth } from '../services/systemService'
import { useApi } from '../hooks/useApi'
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/StateViews'

/**
 * System status screen.
 *
 * This is the end-to-end proof for Phase 1: React calls FastAPI over Axios,
 * FastAPI queries PostgreSQL through SQLAlchemy, and the real result of that
 * query is what renders here. Nothing on this page is a placeholder value.
 */
export default function SystemStatus() {
  const { data, loading, error, refetch } = useApi(getHealth, [])

  if (loading) return <LoadingState label="Checking API and database..." />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="No health data returned" />

  const db = data.database
  const healthy = data.status === 'ok'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">System Status</h1>
          <p className="mt-1 text-sm text-slate-500">
            Live response from <code className="text-slate-700">GET /api/health</code>
          </p>
        </div>
        <button
          type="button"
          onClick={refetch}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Reload data
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Overall" value={healthy ? 'Healthy' : 'Degraded'}>
          <StatusBadge tone={healthy ? 'green' : 'red'}>{data.status}</StatusBadge>
        </StatCard>

        <StatCard label="FastAPI" value="Running">
          <StatusBadge tone="green">{data.api}</StatusBadge>
        </StatCard>

        <StatCard label="PostgreSQL" value={db.connected ? 'Connected' : 'Not reachable'}>
          <StatusBadge tone={db.connected ? 'green' : 'red'}>
            {db.connected ? 'connected' : (db.error ?? 'unavailable')}
          </StatusBadge>
        </StatCard>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <tbody className="divide-y divide-slate-100">
            <Row label="Application" value={data.app} />
            <Row label="Environment" value={data.environment} />
            <Row label="Database dialect" value={db.dialect} />
            <Row label="Server version" value={db.server_version ?? '-'} />
            <Row label="Database name" value={db.database ?? '-'} />
            <Row
              label="Tables in public schema"
              value={`${db.tables_present} present / ${db.tables_expected} declared by the ORM`}
            />
          </tbody>
        </table>
      </div>

      {!db.connected && (
        <ErrorState
          message="FastAPI is up but PostgreSQL is not reachable. Check DATABASE_URL in backend/.env and that the PostgreSQL server is accepting connections, then run: alembic upgrade head"
          onRetry={refetch}
        />
      )}
    </div>
  )
}

function StatCard({ label, value, children }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <tr>
      <th scope="row" className="w-64 px-4 py-3 text-left font-medium text-slate-600">
        {label}
      </th>
      <td className="px-4 py-3 text-slate-900">{value}</td>
    </tr>
  )
}
