import axios from 'axios'

/**
 * Single Axios instance for every call to the FastAPI backend.
 *
 * The base URL comes from VITE_API_BASE_URL so the same build can point at a
 * different backend host without a code change. In development it defaults to
 * "/api", which the Vite dev server proxies to FastAPI (see vite.config.js) -
 * that keeps the browser on one origin and sidesteps CORS during local work.
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
})

/**
 * Request interceptor: attach the JWT issued by /auth/login.
 *
 * The token is read on every request rather than captured once, so a login or
 * logout that happens after this module loads is picked up immediately.
 */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('dealflow_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * Response interceptor: normalise errors into a predictable shape.
 *
 * Components should never have to dig through error.response.data.detail, and
 * they should never surface a raw stack trace to the user.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status ?? 0
    const detail = error.response?.data?.detail

    let message
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI validation errors arrive as a list of {loc, msg, type}.
      message = detail.map((d) => d.msg).join(', ')
    } else if (status === 0) {
      message = 'Cannot reach the DealFlow360 API. Is the FastAPI server running?'
    } else {
      message = error.message || 'Unexpected error'
    }

    return Promise.reject(Object.assign(error, { status, friendlyMessage: message }))
  },
)

export default api
