import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Run an async call and track its loading / error / data state.
 *
 * Every screen here reads live data over a network, so all three states are the
 * norm rather than an edge case. Two details matter:
 *
 * - A response from a superseded request is discarded. Typing in a search box
 *   fires several overlapping requests, and without this the slowest one wins.
 * - `refetch` does not clear `data`, so a background refresh after an action
 *   does not blank the screen the user is looking at.
 */
export function useApi(fetcher, deps = [], { immediate = true } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(immediate)
  const [error, setError] = useState(null)

  const requestId = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(
    async ({ silent = false } = {}) => {
      const id = ++requestId.current
      if (!silent) setLoading(true)
      setError(null)
      try {
        const result = await fetcher()
        if (mounted.current && id === requestId.current) setData(result)
        return result
      } catch (caught) {
        if (mounted.current && id === requestId.current) {
          setError(caught.friendlyMessage || caught.message || 'Request failed')
        }
        return null
      } finally {
        if (mounted.current && id === requestId.current) setLoading(false)
      }
    },
    // The caller declares what the fetcher depends on; a new closure each
    // render would otherwise loop forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps,
  )

  useEffect(() => {
    if (immediate) run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, immediate])

  return {
    data,
    loading,
    error,
    setData,
    refetch: run,
    /** Refresh without flipping back to the loading skeleton. */
    reload: () => run({ silent: true }),
  }
}

/**
 * Debounce a fast-changing value, so a search box does not fire a request per
 * keystroke.
 */
export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}

/**
 * Track an async action's in-flight state, so a button can disable itself and
 * a double-click cannot submit twice.
 */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const perform = useCallback(async (action) => {
    setBusy(true)
    try {
      return await action()
    } finally {
      if (mounted.current) setBusy(false)
    }
  }, [])

  return { busy, perform }
}
