import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

import api from '../lib/api'
import { INTERNAL_ROLES, ROLES } from '../lib/constants'
import { isSupabaseConfigured, supabase } from '../lib/supabase'

const AuthContext = createContext(null)

/**
 * Authentication state for the whole app.
 *
 * Two halves that have to agree:
 *
 * - **The session** is Supabase's. The SDK persists it, refreshes it in the
 *   background and tells us via onAuthStateChange when it changes.
 * - **The profile** is ours, fetched from `GET /auth/me`. It carries the role,
 *   and it is deliberately read from the server rather than from the token, so
 *   a role change or a deactivation takes effect on the next load instead of
 *   whenever the token happens to expire.
 *
 * `initialising` is what stops protected content flashing before we know who
 * the user is. Until it clears, the app renders a splash rather than guessing.
 */
export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [initialising, setInitialising] = useState(true)
  const [profileError, setProfileError] = useState(null)

  // Guards against setting state after unmount, and against a slow profile
  // fetch from a previous session overwriting a newer one.
  const mounted = useRef(true)
  const loadId = useRef(0)

  const loadProfile = useCallback(async () => {
    const requestId = ++loadId.current
    try {
      const { data } = await api.get('/auth/me')
      if (mounted.current && requestId === loadId.current) {
        setProfile(data)
        setProfileError(null)
      }
      return data
    } catch (error) {
      if (mounted.current && requestId === loadId.current) {
        setProfile(null)
        setProfileError(error.friendlyMessage || 'Could not load your profile.')
      }
      return null
    }
  }, [])

  useEffect(() => {
    mounted.current = true

    if (!isSupabaseConfigured) {
      setInitialising(false)
      return () => {
        mounted.current = false
      }
    }

    // Restore whatever session is already in storage, then keep in step with it.
    supabase.auth
      .getSession()
      .then(async ({ data }) => {
        if (!mounted.current) return
        setSession(data.session ?? null)
        if (data.session) await loadProfile()
      })
      .finally(() => {
        if (mounted.current) setInitialising(false)
      })

    const { data: subscription } = supabase.auth.onAuthStateChange(async (event, nextSession) => {
      if (!mounted.current) return
      setSession(nextSession ?? null)

      if (!nextSession) {
        setProfile(null)
        setProfileError(null)
        return
      }
      // TOKEN_REFRESHED fires often and changes nothing about who the user is,
      // so it must not trigger a profile refetch on a timer.
      if (event === 'SIGNED_IN' || event === 'USER_UPDATED') {
        await loadProfile()
      }
    })

    return () => {
      mounted.current = false
      subscription?.subscription?.unsubscribe()
    }
  }, [loadProfile])

  const signIn = useCallback(
    async (email, password) => {
      // Sign in through our API so the backend can reject a deactivated account
      // and stamp last_login_at, then hand the tokens to the SDK so it owns
      // refresh and persistence from there.
      const { data } = await api.post('/auth/login', { email, password })
      const { error } = await supabase.auth.setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      })
      if (error) throw new Error(error.message)

      setProfile(data.user)
      setProfileError(null)
      return data.user
    },
    [],
  )

  const signUp = useCallback(async (email, password, fullName) => {
    const { data } = await api.post('/auth/register', {
      email,
      password,
      full_name: fullName,
    })

    // The project may require email confirmation, in which case there is no
    // session yet and the caller shows a "check your inbox" message.
    if (data.requires_email_confirmation || !data.access_token) {
      return { requiresConfirmation: true, message: data.message }
    }

    const { error } = await supabase.auth.setSession({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    })
    if (error) throw new Error(error.message)

    setProfile(data.user)
    return { requiresConfirmation: false, user: data.user }
  }, [])

  const signOut = useCallback(async () => {
    // Tell the backend first so it can revoke the refresh token; then clear
    // locally regardless, so a failed revoke never traps the user signed in.
    await api.post('/auth/logout').catch(() => {})
    await supabase.auth.signOut().catch(() => {})
    setProfile(null)
    setSession(null)
  }, [])

  const value = useMemo(() => {
    const role = profile?.role ?? null
    return {
      session,
      profile,
      role,
      initialising,
      profileError,
      isAuthenticated: Boolean(session && profile),
      isInternal: Boolean(role && INTERNAL_ROLES.includes(role)),
      isCustomer: role === ROLES.CUSTOMER,
      isAdmin: role === ROLES.ADMIN,
      hasRole: (...roles) => Boolean(role && roles.flat().includes(role)),
      signIn,
      signUp,
      signOut,
      refreshProfile: loadProfile,
      setProfile,
    }
  }, [session, profile, initialising, profileError, signIn, signUp, signOut, loadProfile])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return context
}
