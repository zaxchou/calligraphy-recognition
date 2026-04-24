import api from '../../../api'

export const compositionApi = {
  upload(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/composition/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000
    })
  },
  getTask(taskId) {
    return api.get(`/composition/task/${taskId}`)
  },
  getReport(taskId) {
    return api.get(`/composition/report/${taskId}`)
  },
  getHistory(limit = 30) {
    return api.get(`/composition/history?limit=${limit}`)
  },
  submitFeedback(payload) {
    return api.post('/composition/feedback', payload)
  },
  cancelTask(taskId) {
    return api.post(`/composition/task/${taskId}/cancel`)
  },
  deleteTask(taskId) {
    return api.delete(`/composition/task/${taskId}`)
  },
  getPdfUrl(taskId) {
    return `/api/v1/composition/report/${taskId}/pdf`
  }
}
