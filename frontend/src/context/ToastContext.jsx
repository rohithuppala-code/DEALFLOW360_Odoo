import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

const ToastContext = createContext(null)

const TONES = {
  success: {
    ring: 'ring-emerald-200 dark:ring-emerald-900',
    bar: 'bg-emerald-500',
    icon: 'text-emerald-600 dark:text-emerald-400',
    path: 'M4 12l5 5L20 6',
  },
  error: {
    ring: 'ring-red-200 dark:ring-red-900',
    bar: 'bg-red-500',
    icon: 'text-red-600 dark:text-red-400',
    path: 'M6 6l12 12M18 6L6 18',
  },
  warning: {
    ring: 'ring-amber-200 dark:ring-amber-900',
    bar: 'bg-amber-500',
    icon: 'text-amber-600 dark:text-amber-400',
    path: 'M12 8v5M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  },
  info: {
    ring: 'ring-blue-200 dark:ring-blue-900',
    bar: 'bg-blue-500',
    icon: 'text-blue-600 dark:text-blue-400',
    path: 'M12 16v-5M12 8h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
}

/**
 * Toast notifications.
 *
 * Errors stay on screen twice as long as successes, and can be dismissed by
 * hand: a failure usually carries something the user has to read and act on,
 * whereas "Saved" only has to be noticed.
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const push = useCallback(
    (message, tone = 'info', options = {}) => {
      if (!message) return null
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const duration = options.duration ?? (tone === 'error' ? 8000 : 4000)

      setToasts((current) => [...current.slice(-4), { id, message, tone, title: options.title }])
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), duration),
      )
      return id
    },
    [dismiss],
  )

  // Clear every pending timer on unmount so nothing fires into a dead tree.
  useEffect(() => {
    const pending = timers.current
    return () => {
      pending.forEach((timer) => clearTimeout(timer))
      pending.clear()
    }
  }, [])

  const value = useMemo(
    () => ({
      toast: push,
      success: (message, options) => push(message, 'success', options),
      error: (message, options) => push(message, 'error', options),
      warning: (message, options) => push(message, 'warning', options),
      info: (message, options) => push(message, 'info', options),
      dismiss,
    }),
    [push, dismiss],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 top-4 z-[100] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:items-end"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((toast) => {
          const tone = TONES[toast.tone] ?? TONES.info
          return (
            <div
              key={toast.id}
              role="status"
              aria-live="polite"
              className={`pointer-events-auto flex w-full max-w-md animate-toast-in overflow-hidden rounded-xl bg-white shadow-lg ring-1 dark:bg-slate-800 ${tone.ring}`}
            >
              <span className={`w-1 shrink-0 ${tone.bar}`} aria-hidden="true" />
              <div className="flex flex-1 items-start gap-3 p-3.5">
                <svg
                  className={`mt-0.5 h-5 w-5 shrink-0 ${tone.icon}`}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d={tone.path} />
                </svg>
                <div className="min-w-0 flex-1">
                  {toast.title && (
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {toast.title}
                    </p>
                  )}
                  <p className="break-words text-sm text-slate-600 dark:text-slate-300">
                    {toast.message}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(toast.id)}
                  className="rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
                  aria-label="Dismiss notification"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used inside a ToastProvider')
  }
  return context
}
