import { useCallback, useEffect, useState } from 'react'

/**
 * Run an async API call and track its loading / error / data state.
 *
 * Every screen in DealFlow360 reads live PostgreSQL data through FastAPI, so
 * loading and error states are the norm rather than an afterthought - this
 * hook keeps that handling in one place instead of in each component.
 *
 * @param {Function} apiCall - async function returning the response payload
 * @param {Array} deps - re-run when these change
 */
export function useApi(apiCall, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const run = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await apiCall())
    } catch (err) {
      setError(err.friendlyMessage || 'Request failed')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    let cancelled = false
    // Guard against a state update after the component unmounts.
    const execute = async () => {
      if (!cancelled) await run()
    }
    execute()
    return () => {
      cancelled = true
    }
  }, [run])

  return { data, loading, error, refetch: run }
}
