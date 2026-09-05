import api from './api'

/**
 * System/platform endpoints.
 *
 * getHealth resolves for both 200 (ok) and 503 (degraded): a degraded backend
 * is information the status screen needs to render, not an error to swallow.
 */
export async function getHealth() {
  const response = await api.get('/health', {
    validateStatus: (status) => status === 200 || status === 503,
  })
  return response.data
}
