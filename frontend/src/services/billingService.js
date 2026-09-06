import api, { cleanParams } from '../lib/api'

/** Invoices, payments and subscriptions - the hybrid billing half of a deal. */
export const billingService = {
  /** One-time and recurring, side by side, for one quotation. */
  overview: (quotationId) =>
    api.get(`/quotations/${quotationId}/billing`).then((response) => response.data),

  listInvoices: (params = {}) =>
    api.get('/invoices', { params: cleanParams(params) }).then((response) => response.data),

  getInvoice: (id) => api.get(`/invoices/${id}`).then((response) => response.data),

  /** The invoice status is re-derived from payments; it is never set by hand. */
  recordPayment: (invoiceId, payload) =>
    api.post(`/invoices/${invoiceId}/payments`, payload).then((response) => response.data),

  refundPayment: (paymentId, reason) =>
    api.post(`/payments/${paymentId}/refund`, { reason }).then((response) => response.data),

  cancelInvoice: (invoiceId, reason) =>
    api.post(`/invoices/${invoiceId}/cancel`, { reason }).then((response) => response.data),

  /** Invoice every recurring period that has fallen due. */
  runBilling: (payload = {}) => api.post('/billing/run', payload).then((response) => response.data),
}

export const subscriptionService = {
  list: (params = {}) =>
    api.get('/subscriptions', { params: cleanParams(params) }).then((response) => response.data),

  upcoming: (limit = 50) =>
    api.get('/subscriptions/upcoming', { params: { limit } }).then((response) => response.data.items),

  get: (id) => api.get(`/subscriptions/${id}`).then((response) => response.data),

  /** Prorates the current period and reprices future ones. */
  changeQuantity: (id, quantity) =>
    api.patch(`/subscriptions/${id}/quantity`, { quantity }).then((response) => response.data),

  setStatus: (id, status) =>
    api.post(`/subscriptions/${id}/status`, { status }).then((response) => response.data),

  /** Applies the plan's cancellation and refund rules, raising a credit note. */
  cancel: (id, reason) =>
    api.post(`/subscriptions/${id}/cancel`, { reason }).then((response) => response.data),
}
