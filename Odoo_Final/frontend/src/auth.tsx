import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, type ApiOk } from './api/client'
import type { User } from './types'

type SignupPayload = {
  name: string
  email: string
  password: string
  role: string
  company?: string
}

type AuthState = {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<User>
  signup: (payload: SignupPayload) => Promise<User>
  logout: () => void
}

const Ctx = createContext<AuthState | null>(null)

function readUser(): User | null {
  try {
    const raw = localStorage.getItem('df_user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readUser)
  const [token, setToken] = useState<string | null>(localStorage.getItem('df_token'))
  const qc = useQueryClient()

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      async login(email, password) {
        const { data } = await api.post<ApiOk<{ access_token: string; user: User }>>('/auth/login', { email, password })
        localStorage.setItem('df_token', data.data.access_token)
        localStorage.setItem('df_user', JSON.stringify(data.data.user))
        setToken(data.data.access_token)
        setUser(data.data.user)
        qc.clear()
        return data.data.user
      },
      async signup(payload) {
        const { data } = await api.post<ApiOk<{ access_token: string; user: User }>>('/auth/signup', payload)
        localStorage.setItem('df_token', data.data.access_token)
        localStorage.setItem('df_user', JSON.stringify(data.data.user))
        setToken(data.data.access_token)
        setUser(data.data.user)
        qc.clear()
        return data.data.user
      },
      logout() {
        localStorage.removeItem('df_token')
        localStorage.removeItem('df_user')
        setToken(null)
        setUser(null)
        qc.clear()
      },
    }),
    [user, token, qc],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('AuthProvider missing')
  return ctx
}
