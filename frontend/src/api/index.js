import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 120000, // 增加到120秒，因为AI识别可能需要较长时间
  headers: {
    'Content-Type': 'application/json'
  }
})

// ── 网络错误自动重试（最多1次，5秒后重试）──────────────────────────
const MAX_RETRY = 1
const RETRY_DELAY = 5000

api.interceptors.request.use(
  config => {
    // 初始化重试计数
    if (!config._retryCount) config._retryCount = 0
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
  async error => {
    const config = error.config
    // 仅对网络错误（无 response）或 502/503/504 自动重试
    const isNetworkError = !error.response
    const isServerDown = error.response && [502, 503, 504].includes(error.response.status)
    const shouldRetry = (isNetworkError || isServerDown)
      && config
      && config._retryCount < MAX_RETRY
      // 不重试上传请求（文件可能已被消费）
      && !config.url?.includes('/tubi/upload')

    if (shouldRetry) {
      config._retryCount++
      console.warn(`[API] 请求失败，${RETRY_DELAY / 1000}秒后重试 (${config._retryCount}/${MAX_RETRY}):`, config.url)
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
      return api(config)
    }

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
  uploadImage(file, fields = {}, onProgress) {
    if (typeof fields === 'function') {
      onProgress = fields
      fields = {}
    }
    const formData = new FormData()
    formData.append('file', file)
    Object.entries(fields || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      formData.append(k, String(v))
    })
    return api.post('/tubi/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 300000,
      onUploadProgress: evt => {
        if (!onProgress) return
        const total = evt.total || 0
        const loaded = evt.loaded || 0
        const percent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : null
        onProgress({ loaded, total, percent })
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
      timeout: 60000
    })
  },
  batchAutoAnalyze(imageIds, mode = 'analyze') {
    return api.post('/tubi/batch-auto-analyze', { image_ids: imageIds, mode }, {
      timeout: 60000
    })
  },
  getAnalyzeStatus(imageId) {
    return api.get(`/tubi/analyze-status/${imageId}`)
  },
  batchGetStatus(imageIds) {
    return api.post('/tubi/batch-status', { image_ids: imageIds }, {
      timeout: 30000
    })
  },
  getQueueInfo(imageId) {
    return api.get(`/tubi/queue-info/${imageId}`)
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
  getAllResults(skip = 0, limit = 500, artist = null) {
    const params = { skip, limit }
    if (artist && artist !== 'all') params.artist = artist
    return api.get('/tubi/results', { params })
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
  },
  replaceImage(imageId, file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/tubi/image/${imageId}/replace-image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
  getWordCloud(params = {}) {
    return api.get('/tubi/wordcloud', { params })
  },
  getWordCloudArtists() {
    return api.get('/tubi/wordcloud/artists')
  },

  // ── 册页管理 API ───────────────────────────────────────────────────────────
  getAlbums(artist = null) {
    const params = {}
    if (artist && artist !== 'all') params.artist = artist
    return api.get('/tubi/albums', { params })
  },
  getAlbum(albumName) {
    return api.get(`/tubi/albums/${encodeURIComponent(albumName)}`)
  },
  createAlbum(data) {
    return api.post('/tubi/albums', data)
  },
  renameAlbum(albumName, newName) {
    return api.put(`/tubi/albums/${encodeURIComponent(albumName)}`, { new_name: newName })
  },
  deleteAlbum(albumName) {
    return api.delete(`/tubi/albums/${encodeURIComponent(albumName)}`)
  },
  addItemsToAlbum(albumName, recordIds) {
    return api.post(`/tubi/albums/${encodeURIComponent(albumName)}/items`, { record_ids: recordIds })
  },
  removeItemFromAlbum(albumName, recordId) {
    return api.delete(`/tubi/albums/${encodeURIComponent(albumName)}/items/${recordId}`)
  },
  reorderAlbumItems(albumName, itemOrder) {
    return api.put(`/tubi/albums/${encodeURIComponent(albumName)}/reorder`, { item_order: itemOrder })
  },
  getAlbumNavigation(recordId) {
    return api.get(`/tubi/albums/navigation/${recordId}`)
  },

  // ── 标签管理 API ───────────────────────────────────────────────────────────
  getTags(artist = null) {
    const params = {}
    if (artist && artist !== 'all') params.artist = artist
    return api.get('/tubi/tags', { params })
  },
  getTagItems(tagName) {
    return api.get(`/tubi/tags/${encodeURIComponent(tagName)}`)
  },
  createTag(name) {
    return api.post('/tubi/tags', { name })
  },
  renameTag(oldName, newName) {
    return api.put('/tubi/tags', { old_name: oldName, new_name: newName })
  },
  deleteTag(tagName) {
    return api.delete(`/tubi/tags/${encodeURIComponent(tagName)}`)
  },
  addItemsToTag(tagName, recordIds) {
    return api.post('/tubi/tags/items', { tag_name: tagName, record_ids: recordIds })
  },
  removeItemFromTag(tagName, recordId) {
    return api.delete(`/tubi/tags/${encodeURIComponent(tagName)}/items/${recordId}`)
  },
  resetAllTags() {
    return api.delete('/tubi/tags/all')
  },

  // ── 统计扩展 API ───────────────────────────────────────────────────────────
  getExtendedStats() {
    return api.get('/tubi/stats/extended')
  }
}

export default api
