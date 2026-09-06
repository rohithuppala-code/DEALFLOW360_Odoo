import api, { cleanParams } from '../lib/api'

/** Dashboard, deal-health alerts and reporting. */

export const dashboardService = {
  overview: (days = 30) =>
    api.get('/dashboard', { params: { days } }).then((response) => response.data),
}

export const alertService = {
  list: (params = {}) =>
    api
      .get('/alerts', { params: cleanParams(params), paramsSerializer: { indexes: null } })
      .then((response) => response.data),

  /** Re-run the detectors. Safe to repeat: alerts refresh, they do not stack. */
  scan: () => api.post('/alerts/scan').then((response) => response.data),

  /** action is ACKNOWLEDGE, ESCALATE or RESOLVE. */
  act: (alertId, action, note) =>
    api.post(`/alerts/${alertId}/action`, { action, note }).then((response) => response.data),

  /** Escalate and write a chase onto the deal's activity trail. */
  nudge: (alertId) => api.post(`/alerts/${alertId}/nudge`).then((response) => response.data),
}

export const reportService = {
  sales: (filters = {}) =>
    api
      .get('/reports/sales', {
        params: cleanParams(filters),
        // Repeat `status` per value so FastAPI parses it as a list.
        paramsSerializer: { indexes: null },
      })
      .then((response) => response.data),

  /**
   * Render to PDF or XLSX.
   *
   * The file is generated server-side and returned as a short-lived signed URL
   * rather than a blob, so the figures in the file are exactly the ones the API
   * computed, and a report of the whole pipeline never has to pass through a
   * customer-reachable path.
   */
  export: (format, filters = {}) =>
    api
      .post('/reports/sales/export', null, {
        params: cleanParams({ ...filters, format }),
        paramsSerializer: { indexes: null },
      })
      .then((response) => response.data),
}

export const systemService = {
  health: () =>
    api
      .get('/health', { validateStatus: (status) => status === 200 || status === 503 })
      .then((response) => response.data),
}
