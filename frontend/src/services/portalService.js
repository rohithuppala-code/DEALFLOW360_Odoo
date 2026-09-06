import api from '../lib/api'

/**
 * The customer portal API.
 *
 * Every call here is scoped by the signed-in customer's own profile on the
 * server - notice that none of these functions takes a customer id. There is
 * nothing for the browser to tamper with.
 */
export const portalService = {
  quotations: (limit = 50) =>
    api.get('/portal/quotations', { params: { limit } }).then((response) => response.data.items),

  quotation: (id) => api.get(`/portal/quotations/${id}`).then((response) => response.data),

  /** Ask a question, request a change, or counter the discount. */
  raiseRequest: (quotationId, payload) =>
    api.post(`/portal/quotations/${quotationId}/requests`, payload).then((response) => response.data),

  comment: (negotiationId, message) =>
    api
      .post(`/portal/negotiations/${negotiationId}/comments`, { message })
      .then((response) => response.data),

  /**
   * Confirm the quotation.
   *
   * The response carries `requires_approval`: when negotiation has pushed the
   * terms past our ceilings, confirming sends the quote back for internal
   * approval instead, and the UI says so rather than claiming an order was
   * placed.
   */
  confirm: (quotationId) =>
    api.post(`/portal/quotations/${quotationId}/confirm`).then((response) => response.data),

  invoices: (limit = 50) =>
    api.get('/portal/invoices', { params: { limit } }).then((response) => response.data),

  invoice: (id) => api.get(`/portal/invoices/${id}`).then((response) => response.data),

  subscriptions: () => api.get('/portal/subscriptions').then((response) => response.data.items),

  downloadUrl: (documentId) =>
    api.get(`/portal/documents/${documentId}/download`).then((response) => response.data),
}

export const profileService = {
  me: () => api.get('/auth/me').then((response) => response.data),

  update: (payload) => api.patch('/auth/me', payload).then((response) => response.data),

  changePassword: (currentPassword, newPassword) =>
    api
      .post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      .then((response) => response.data),

  forgotPassword: (email) =>
    api.post('/auth/forgot-password', { email }).then((response) => response.data),

  uploadAvatar: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api
      .post('/auth/me/avatar', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((response) => response.data)
  },
}
