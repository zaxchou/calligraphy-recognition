import api from './index'

export const adminApi = {
  getUsers(params) {
    return api.get('/admin/users', { params })
  },
  updateUser(id, data) {
    return api.put(`/admin/users/${id}`, data)
  },
  deleteUser(id) {
    return api.delete(`/admin/users/${id}`)
  },
  getStats() {
    return api.get('/admin/stats')
  },
  getSubscriptions(params) {
    return api.get('/admin/subscriptions', { params })
  },
  createSubscription(data) {
    return api.post('/admin/subscriptions', data)
  },
  getConfig() {
    return api.get('/admin/config')
  },
  getPermissions() {
    return api.get('/admin/permissions')
  },
  savePermissions(data) {
    return api.put('/admin/permissions', data)
  },
  getMyPermissions() {
    return api.get('/admin/my-permissions')
  },
}
