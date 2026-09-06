import api, { cleanParams } from '../lib/api'

/**
 * Backend configuration: the catalogue, the governance rules, customers,
 * warehouses and users.
 *
 * Reads are open to any member of staff; the writes below all require an
 * administrator, and the API enforces that regardless of what the UI shows.
 */

export const catalogService = {
  // --- products -----------------------------------------------------------
  listProducts: (params = {}) =>
    api.get('/products', { params: cleanParams(params) }).then((response) => response.data),

  getProduct: (id) => api.get(`/products/${id}`).then((response) => response.data),

  createProduct: (payload) => api.post('/products', payload).then((response) => response.data),

  updateProduct: (id, payload) =>
    api.patch(`/products/${id}`, payload).then((response) => response.data),

  deleteProduct: (id) => api.delete(`/products/${id}`).then((response) => response.data),

  categories: () => api.get('/products/categories').then((response) => response.data.items),

  uploadProductImage: (id, file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    return api
      .post(`/products/${id}/image`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (event) => {
          if (onProgress && event.total) onProgress(Math.round((event.loaded * 100) / event.total))
        },
      })
      .then((response) => response.data)
  },

  // --- variants -----------------------------------------------------------
  createVariant: (productId, payload) =>
    api.post(`/products/${productId}/variants`, payload).then((response) => response.data),

  updateVariant: (variantId, payload) =>
    api.patch(`/variants/${variantId}`, payload).then((response) => response.data),

  deleteVariant: (variantId) => api.delete(`/variants/${variantId}`).then((response) => response.data),

  // --- subscription plans -------------------------------------------------
  listPlans: (params = {}) =>
    api.get('/subscription-plans', { params: cleanParams(params) }).then((response) => response.data),

  createPlan: (payload) => api.post('/subscription-plans', payload).then((response) => response.data),

  updatePlan: (id, payload) =>
    api.patch(`/subscription-plans/${id}`, payload).then((response) => response.data),

  deletePlan: (id) => api.delete(`/subscription-plans/${id}`).then((response) => response.data),

  // --- price lists --------------------------------------------------------
  listPriceLists: (params = {}) =>
    api.get('/price-lists', { params: cleanParams(params) }).then((response) => response.data),

  getPriceList: (id) => api.get(`/price-lists/${id}`).then((response) => response.data),

  createPriceList: (payload) => api.post('/price-lists', payload).then((response) => response.data),

  updatePriceList: (id, payload) =>
    api.patch(`/price-lists/${id}`, payload).then((response) => response.data),

  deletePriceList: (id) => api.delete(`/price-lists/${id}`).then((response) => response.data),

  addPriceListItem: (id, payload) =>
    api.post(`/price-lists/${id}/items`, payload).then((response) => response.data),

  updatePriceListItem: (itemId, payload) =>
    api.patch(`/price-list-items/${itemId}`, payload).then((response) => response.data),

  deletePriceListItem: (itemId) =>
    api.delete(`/price-list-items/${itemId}`).then((response) => response.data),
}

export const configService = {
  // --- discount governance -------------------------------------------------
  listDiscountRules: (params = {}) =>
    api.get('/config/discount-rules', { params: cleanParams(params) }).then((response) => response.data),

  /** The ceilings as the risk engine sees them, for the builder's hints. */
  ceilings: () => api.get('/config/discount-ceilings').then((response) => response.data),

  createDiscountRule: (payload) =>
    api.post('/config/discount-rules', payload).then((response) => response.data),

  updateDiscountRule: (id, payload) =>
    api.patch(`/config/discount-rules/${id}`, payload).then((response) => response.data),

  deleteDiscountRule: (id) =>
    api.delete(`/config/discount-rules/${id}`).then((response) => response.data),

  // --- approval chain ------------------------------------------------------
  listApprovalRules: (params = {}) =>
    api.get('/config/approval-rules', { params: cleanParams(params) }).then((response) => response.data),

  /** Try a hypothetical risk score against the configured chain. */
  previewChain: (riskScore) =>
    api
      .get('/config/approval-chain/preview', { params: { risk_score: riskScore } })
      .then((response) => response.data),

  createApprovalRule: (payload) =>
    api.post('/config/approval-rules', payload).then((response) => response.data),

  updateApprovalRule: (id, payload) =>
    api.patch(`/config/approval-rules/${id}`, payload).then((response) => response.data),

  deleteApprovalRule: (id) =>
    api.delete(`/config/approval-rules/${id}`).then((response) => response.data),

  // --- upsell pairings -----------------------------------------------------
  listRecommendationRules: (params = {}) =>
    api
      .get('/config/recommendation-rules', { params: cleanParams(params) })
      .then((response) => response.data),

  createRecommendationRule: (payload) =>
    api.post('/config/recommendation-rules', payload).then((response) => response.data),

  updateRecommendationRule: (id, payload) =>
    api.patch(`/config/recommendation-rules/${id}`, payload).then((response) => response.data),

  deleteRecommendationRule: (id) =>
    api.delete(`/config/recommendation-rules/${id}`).then((response) => response.data),

  // --- tunable constants ---------------------------------------------------
  settings: () => api.get('/config/settings').then((response) => response.data.items),

  updateSetting: (key, payload) =>
    api.put(`/config/settings/${key}`, payload).then((response) => response.data),
}

export const customerService = {
  list: (params = {}) =>
    api.get('/customers', { params: cleanParams(params) }).then((response) => response.data),

  get: (id) => api.get(`/customers/${id}`).then((response) => response.data),

  create: (payload) => api.post('/customers', payload).then((response) => response.data),

  update: (id, payload) => api.patch(`/customers/${id}`, payload).then((response) => response.data),

  remove: (id) => api.delete(`/customers/${id}`).then((response) => response.data),
}

export const warehouseService = {
  list: (params = {}) =>
    api.get('/warehouses', { params: cleanParams(params) }).then((response) => response.data),

  get: (id) => api.get(`/warehouses/${id}`).then((response) => response.data),

  create: (payload) => api.post('/warehouses', payload).then((response) => response.data),

  update: (id, payload) => api.patch(`/warehouses/${id}`, payload).then((response) => response.data),

  remove: (id) => api.delete(`/warehouses/${id}`).then((response) => response.data),

  inventory: (params = {}) =>
    api.get('/inventory', { params: cleanParams(params) }).then((response) => response.data.items),

  setStock: (payload) => api.put('/inventory', payload).then((response) => response.data),
}

export const userService = {
  list: (params = {}) =>
    api.get('/users', { params: cleanParams(params) }).then((response) => response.data),

  /** Active reps and managers, for quotation assignment. Any staff may read. */
  salesReps: () => api.get('/users/sales-reps').then((response) => response.data.items),

  get: (id) => api.get(`/users/${id}`).then((response) => response.data),

  create: (payload) => api.post('/users', payload).then((response) => response.data),

  update: (id, payload) => api.patch(`/users/${id}`, payload).then((response) => response.data),

  setActive: (id, active) =>
    api.post(`/users/${id}/${active ? 'activate' : 'deactivate'}`).then((response) => response.data),

  remove: (id) => api.delete(`/users/${id}`).then((response) => response.data),

  roles: () => api.get('/auth/roles').then((response) => response.data.roles),
}
