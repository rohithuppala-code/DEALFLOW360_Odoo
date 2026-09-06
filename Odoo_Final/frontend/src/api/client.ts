import axios from 'axios'
import { toast } from 'sonner'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export const api = axios.create({ baseURL, timeout: 20000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('df_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === 'ERR_CANCELED' || err.name === 'CanceledError') return Promise.reject(err)
    const status = err.response?.status
    const message = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Request failed'
    if (status === 401) {
      localStorage.removeItem('df_token')
      localStorage.removeItem('df_user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    } else if (status !== 422) {
      toast.error(message)
    }
    return Promise.reject(err)
  },
)

export type ApiOk<T> = { success: true; data: T; message: string | null }
export type Page<T> = { items: T[]; total: number; page: number; page_size: number; pages: number }
