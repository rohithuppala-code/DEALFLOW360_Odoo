import api, { cleanParams } from '../lib/api'

/**
 * The quotation workspace: building a quote, scoring it, routing it for
 * approval, splitting it across warehouses and negotiating it.
 *
 * Note what these functions return. Any call that changes a line comes back
 * with the quotation as the server recomputed it, so the caller replaces its
 * state from the response rather than patching a local copy. That is what keeps
 * the margin indicator and the risk score honest after every edit.
 */

export const quotationService = {
  list: (params = {}) =>
    api.get('/quotations', { params: cleanParams(params) }).then((response) => response.data),

  pipeline: (mineOnly = false) =>
    api
      .get('/quotations/pipeline', { params: { mine_only: mineOnly } })
      .then((response) => response.data),

  statuses: () => api.get('/quotations/statuses').then((response) => response.data),

  get: (id) => api.get(`/quotations/${id}`).then((response) => response.data),

  create: (payload) => api.post('/quotations', payload).then((response) => response.data),

  update: (id, payload) => api.patch(`/quotations/${id}`, payload).then((response) => response.data),

  duplicate: (id) => api.post(`/quotations/${id}/duplicate`).then((response) => response.data),

  /** Re-resolve prices and re-apply the current ceilings ("Reload Data"). */
  recalculate: (id) => api.post(`/quotations/${id}/recalculate`).then((response) => response.data),

  /** Routing is automatic - this does not choose an approver. */
  submit: (id) => api.post(`/quotations/${id}/submit`).then((response) => response.data),

  send: (id) => api.post(`/quotations/${id}/send`).then((response) => response.data),

  confirm: (id) => api.post(`/quotations/${id}/confirm`).then((response) => response.data),

  cancel: (id, reason) =>
    api.post(`/quotations/${id}/cancel`, { reason }).then((response) => response.data),

  // --- line items ---------------------------------------------------------
  items: (id) => api.get(`/quotations/${id}/items`).then((response) => response.data.items),

  addItem: (id, payload) =>
    api.post(`/quotations/${id}/items`, payload).then((response) => response.data),

  updateItem: (id, itemId, payload) =>
    api.patch(`/quotations/${id}/items/${itemId}`, payload).then((response) => response.data),

  removeItem: (id, itemId) =>
    api.delete(`/quotations/${id}/items/${itemId}`).then((response) => response.data),

  // --- upsell panel -------------------------------------------------------
  recommendations: (id, { limit = 6, dismissed = [] } = {}) =>
    api
      .get(`/quotations/${id}/recommendations`, {
        params: cleanParams({ limit, dismissed }),
        // Repeat the key per value so FastAPI reads a list, not "a,b,c".
        paramsSerializer: { indexes: null },
      })
      .then((response) => response.data),

  // --- approvals ----------------------------------------------------------
  approvals: (id) => api.get(`/quotations/${id}/approvals`).then((response) => response.data),

  // --- documents ----------------------------------------------------------
  documents: (id) => api.get(`/quotations/${id}/documents`).then((response) => response.data.items),

  uploadDocument: (id, file, { description, isCustomerVisible = false, onProgress } = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (description) form.append('description', description)
    form.append('is_customer_visible', String(isCustomerVisible))

    return api
      .post(`/quotations/${id}/documents`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (event) => {
          if (onProgress && event.total) {
            onProgress(Math.round((event.loaded * 100) / event.total))
          }
        },
      })
      .then((response) => response.data)
  },

  activity: (id, limit = 100) =>
    api.get(`/quotations/${id}/activity`, { params: { limit } }).then((response) => response.data.items),
}

export const approvalService = {
  pending: (limit = 50) =>
    api.get('/approvals/pending', { params: { limit } }).then((response) => response.data.items),

  list: (params = {}) =>
    api.get('/approvals', { params: cleanParams(params) }).then((response) => response.data),

  forQuotation: (quotationId) =>
    api.get(`/approvals/quotation/${quotationId}`).then((response) => response.data),

  /** action is APPROVE, REJECT or RETURN. The latter two need a comment. */
  act: (approvalId, action, comment) =>
    api.post(`/approvals/${approvalId}/action`, { action, comment }).then((response) => response.data),
}

export const fulfillmentService = {
  /** Reads stock and proposes a split. Reserves nothing. */
  plan: (quotationId) => api.get(`/fulfillment/${quotationId}/plan`).then((response) => response.data),

  overview: (quotationId) => api.get(`/fulfillment/${quotationId}`).then((response) => response.data),

  /** Commits the split and reserves stock. Pass overrides for a manual split. */
  accept: (quotationId, { overrides, promisedDeliveryDate } = {}) =>
    api
      .post(`/fulfillment/${quotationId}/accept`, {
        overrides,
        promised_delivery_date: promisedDeliveryDate || null,
      })
      .then((response) => response.data),

  advance: (splitId, status) =>
    api.post(`/fulfillment/splits/${splitId}/status`, { status }).then((response) => response.data),

  consolidateBackorders: (quotationId) =>
    api.post(`/fulfillment/${quotationId}/consolidate-backorders`).then((response) => response.data),
}

export const negotiationService = {
  open: (limit = 50) =>
    api.get('/negotiations/open', { params: { limit } }).then((response) => response.data.items),

  thread: (quotationId) =>
    api.get(`/negotiations/quotation/${quotationId}`).then((response) => response.data.items),

  raise: (quotationId, payload) =>
    api.post(`/negotiations/quotation/${quotationId}`, payload).then((response) => response.data),

  /** decision is ACCEPT, REJECT or UNDER_REVIEW. */
  respond: (negotiationId, payload) =>
    api.post(`/negotiations/${negotiationId}/respond`, payload).then((response) => response.data),

  comment: (negotiationId, message, isInternal = false) =>
    api
      .post(`/negotiations/${negotiationId}/comments`, { message, is_internal: isInternal })
      .then((response) => response.data),
}

export const documentService = {
  get: (id) => api.get(`/documents/${id}`).then((response) => response.data),
  downloadUrl: (id) => api.get(`/documents/${id}/download`).then((response) => response.data),
  remove: (id) => api.delete(`/documents/${id}`).then((response) => response.data),
}
