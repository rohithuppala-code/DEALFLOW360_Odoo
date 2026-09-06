import { createClient } from '@supabase/supabase-js'

/**
 * Supabase browser client.
 *
 * This is the one place the frontend talks to Supabase directly, and it does
 * exactly one job: authentication. Sign-in, sign-up, session persistence and
 * token refresh are things the Supabase SDK does properly - refreshing a token
 * before it expires, and restoring a session after a page reload - and
 * reimplementing them over our own API would be strictly worse.
 *
 * Everything else - quotations, approvals, fulfilment, billing - goes through
 * FastAPI. This client is never used to read or write application tables. If it
 * ever were, Row Level Security would still stand in the way (see
 * backend/supabase/02_rls.sql), but the architecture is that business logic
 * lives in one place, on the server.
 *
 * The key here is the *anon* key, which is public by design and constrained by
 * RLS. The service-role key must never appear in this bundle.
 */
const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

/** True once real credentials are present, so the UI can explain what is missing. */
export const isSupabaseConfigured = Boolean(url && anonKey)

if (!isSupabaseConfigured) {
  console.warn(
    'Supabase is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY ' +
      'in frontend/.env, then restart the dev server.',
  )
}

/**
 * Created even without credentials so imports never explode; calls simply fail
 * and the sign-in screen shows the setup notice instead of a blank page.
 */
export const supabase = createClient(url || 'http://localhost', anonKey || 'public-anon-key', {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storageKey: 'dealflow360.auth',
  },
})

/** The current access token, or null. Used by the API layer per request. */
export async function getAccessToken() {
  if (!isSupabaseConfigured) return null
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    console.warn('Could not read the Supabase session:', error.message)
    return null
  }
  return data.session?.access_token ?? null
}
