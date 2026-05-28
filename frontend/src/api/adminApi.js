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
  // ── 情绪引擎 v3 分析日志 ──
  getEmotionLogs(params) {
    return api.get('/admin/emotion-logs', { params })
  },
  getEmotionLogDetail(recordId) {
    return api.get(`/admin/emotion-logs/${recordId}`)
  },
  reanalyzeEmotion(recordId) {
    return api.post(`/admin/emotion-logs/${recordId}/reanalyze`)
  },
  getEmotionStats() {
    return api.get('/admin/emotion-stats')
  },
  reanalyzeAllEmotion() {
    return api.post('/admin/emotion-logs/reanalyze-all')
  },
  reanalyzeAllStatus() {
    return api.get('/admin/emotion-logs/reanalyze-all/status')
  },
}
