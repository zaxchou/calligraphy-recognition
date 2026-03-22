import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 增加到120秒，因为AI识别可能需要较长时间
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export const recognitionApi = {
  recognize(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/recognize', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000 // AI识别可能需要较长时间
    })
  },
  search(file, topK = 5) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('top_k', topK)
    return api.post('/search', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  getHistory(page = 1, pageSize = 10) {
    return api.get('/recognition/history', {
      params: { page, page_size: pageSize }
    })
  },
  deleteHistory(logId) {
    return api.delete(`/recognition/history/${logId}`)
  }
}

export const steleApi = {
  getSteles(params = {}) {
    return api.get('/steles', { params })
  },
  getStele(id) {
    return api.get(`/steles/${id}`)
  },
  getSteleCharacters(id, params = {}) {
    return api.get(`/steles/${id}/characters`, { params })
  },
  getCharacter(id) {
    return api.get(`/characters/${id}`)
  }
}

export const tubiApi = {
  uploadImage(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/tubi/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  uploadImages(files) {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    return api.post('/tubi/upload-multiple', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  autoAnalyze(imageId) {
    return api.post(`/tubi/auto-analyze/${imageId}`, {}, {
      timeout: 300000 // 题跋分析可能需要5分钟
    })
  },
  analyzeRegions(imageId, regions) {
    return api.post('/tubi/analyze', {
      image_id: imageId,
      regions: regions
    })
  },
  getAnalysisResult(imageId) {
    return api.get(`/tubi/result/${imageId}`)
  },
  saveYearData(imageId, yearData) {
    return api.post('/tubi/year', {
      image_id: imageId,
      year: yearData.year,
      period: yearData.period,
      notes: yearData.notes
    })
  },
  getAllResults() {
    return api.get('/tubi/results')
  },
  searchImages(keyword) {
    return api.get('/tubi/search', {
      params: { keyword }
    })
  },
  deleteImage(imageId) {
    return api.delete(`/tubi/image/${imageId}`)
  },
  updateImageInfo(imageId, data) {
    return api.put(`/tubi/image-info/${imageId}`, data)
  }
}

export default api
