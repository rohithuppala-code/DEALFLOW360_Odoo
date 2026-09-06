import axios from 'axios'

import { getAccessToken, supabase } from './supabase'

/**
 * The single Axios instance for every call to FastAPI.
 *
 * Two interceptors carry most of the weight:
 *
 * 1. **Request** - attaches the current Supabase access token. It is read fresh
 *    on every call rather than captured once, so a sign-in or sign-out that
 *    happens after this module loads is picked up immediately, and the SDK's
 *    background refresh is always reflected.
 *
 * 2. **Response** - flattens every failure into one predictable shape. The
 *    backend already answers `{detail, code}` for anything it raises on
 *    purpose (see backend/app/core/errors.py); this fills in the cases it
 *    cannot speak for, such as the server being down.
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

api.interceptors.request.use(async (config) => {
  const token = await getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status ?? 0
    const data = error.response?.data
    const detail = data?.detail

    let message
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail) && detail.length > 0) {
      message = detail.map((entry) => entry.msg ?? String(entry)).join(', ')
    } else if (status === 0) {
      message = 'Cannot reach the DealFlow360 API. Is the FastAPI server running?'
    } else if (status === 413) {
      message = 'That file is too large to upload.'
    } else if (status >= 500) {
      message = 'The server hit an unexpected error. Please try again.'
    } else {
      message = error.message || 'Something went wrong.'
    }

    // A 401 means the token is gone or expired. Clearing the Supabase session
    // makes AuthContext notice and route to sign-in, rather than leaving the
    // user on a screen whose every request now fails.
    if (status === 401) {
      const path = error.config?.url || ''
      if (!path.includes('/auth/login') && !path.includes('/auth/register')) {
        await supabase.auth.signOut().catch(() => {})
      }
    }

    return Promise.reject(
      Object.assign(error, {
        status,
        code: data?.code ?? 'error',
        friendlyMessage: message,
      }),
    )
  },
)

/** Drop keys that are null/undefined/'' so they never reach the query string. */
export function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => {
      if (value === null || value === undefined || value === '') return false
      if (Array.isArray(value) && value.length === 0) return false
      return true
    }),
  )
}

export default api
