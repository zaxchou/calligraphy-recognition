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
  },
  ingestRules(payload) {
    return api.post('/composition/knowledge/ingest/rules', payload, { timeout: 120000 })
  },
  getIngestTask(taskId) {
    return api.get(`/composition/knowledge/task/${taskId}`, { timeout: 120000 })
  },
  uploadBook(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/composition/knowledge/upload/book', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000
    })
  },
  ingestImages({ files, mapping, ruleset_version }) {
    const formData = new FormData()
    ;(files || []).forEach((f) => {
      formData.append('files', f)
    })
    if (mapping) {
      formData.append('mapping', mapping)
    }
    if (ruleset_version) {
      formData.append('ruleset_version', ruleset_version)
    }
    return api.post('/composition/knowledge/ingest/images', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000
    })
  },
  ingestBookPdf({ pdf_path, mapping, ruleset_version }) {
    const formData = new FormData()
    formData.append('pdf_path', pdf_path || '')
    if (mapping) {
      formData.append('mapping', mapping)
    }
    if (ruleset_version) {
      formData.append('ruleset_version', ruleset_version)
    }
    return api.post('/composition/knowledge/ingest/book/pdf', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000
    })
  }
}
