import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 120000, // 增加到120秒，因为AI识别可能需要较长时间
  // 不设默认 Content-Type，让 axios 自动判断（JSON body → application/json, FormData → multipart/form-data）
})

// ── 网络错误自动重试（最多1次，5秒后重试）──────────────────────────
const MAX_RETRY = 1
const RETRY_DELAY = 5000

api.interceptors.request.use(
  config => {
    // 初始化重试计数
    if (!config._retryCount) config._retryCount = 0
    // 自动附加 JWT Token
    const authToken = localStorage.getItem('auth_token')
    if (authToken) {
      config.headers['Authorization'] = `Bearer ${authToken}`
    }
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

    // Phase 1: 401 自动清除 token（由页面组件决定是否跳转登录页）
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
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
      timeout: 120000
    })
  },
  search(file, topK = 5) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('top_k', topK)
    return api.post('/search', formData)
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
    return api.post('/tubi/upload-multiple', formData)
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
  batchCancel(imageIds) {
    return api.post('/tubi/batch-cancel', { image_ids: imageIds })
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
  getAllResults(skip = 0, limit = 500, artist = null, libraryId = null, sortBy = null, sortDir = 'desc') {
    const params = { skip, limit }
    if (artist && artist !== 'all') params.artist = artist
    if (libraryId) params.library_id = libraryId
    if (sortBy) {
      params.sort_by = sortBy
      params.sort_dir = sortDir
    }
    return api.get('/tubi/results', { params })
  },
  searchImages(keyword, skip = 0, limit = 500, artist = null) {
    return api.get('/tubi/search', {
      params: { keyword, skip, limit, ...(artist && artist !== 'all' ? { artist } : {}) }
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
    return api.post(`/tubi/image/${imageId}/replace-image`, formData)
  },
  getWordCloud(params = {}) {
    return api.get('/tubi/wordcloud', { params })
  },
  getWordCloudArtists() {
    return api.get('/tubi/wordcloud/artists')
  },

  // ── 册页管理 API ───────────────────────────────────────────────────────────
  getAlbums(artist = null, libraryId = null) {
    const params = {}
    if (artist && artist !== 'all') params.artist = artist
    if (libraryId) params.library_id = libraryId
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
  getTags(artist = null, libraryId = null) {
    const params = {}
    if (artist && artist !== 'all') params.artist = artist
    if (libraryId) params.library_id = libraryId
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

// ── 印章管理 API ───────────────────────────────────────────────────────────
export const sealsApi = {
  list(params = {}) {
    return api.get('/seals', { params })
  },
  get(sealId) {
    return api.get(`/seals/${sealId}`)
  },
  getByName(name, params = {}) {
    return api.get(`/seals/by-name/${encodeURIComponent(name)}`, { params })
  },
  create(data) {
    return api.post('/seals', data)
  },
  update(sealId, data) {
    return api.put(`/seals/${sealId}`, data)
  },
  delete(sealId) {
    return api.delete(`/seals/${sealId}`)
  },
  artworks(sealId) {
    return api.get(`/seals/${sealId}/artworks`)
  },
  uploadImage(sealId, file, description = '') {
    const formData = new FormData()
    formData.append('file', file)
    if (description) formData.append('description', description)
    return api.post(`/seals/${sealId}/images`, formData)
  },
  updateImage(sealId, imageId, data) {
    return api.put(`/seals/${sealId}/images/${imageId}`, data)
  },
  deleteImage(sealId, imageId) {
    return api.delete(`/seals/${sealId}/images/${imageId}`)
  },
  extract() {
    return api.post('/seals/extract')
  },
  batchDelete(ids) {
    return api.post('/seals/batch-delete', { ids })
  }
}

// ── 画家规则 API ───────────────────────────────────────────────────────────
export const artistRulesApi = {
  list() {
    return api.get('/artist-rules')
  },
  get(ruleId) {
    return api.get(`/artist-rules/${ruleId}`)
  },
  getByName(artistName) {
    return api.get(`/artist-rules/by-name/${encodeURIComponent(artistName)}`)
  },
  create(data) {
    return api.post('/artist-rules', data)
  },
  update(ruleId, data) {
    return api.put(`/artist-rules/${ruleId}`, data)
  },
  delete(ruleId) {
    return api.delete(`/artist-rules/${ruleId}`)
  },
  aiDiscover(artistName) {
    return api.post(`/artist-rules/ai-discover/${encodeURIComponent(artistName)}`)
  },
  generateLifeStages(artistName) {
    return api.get(`/artist-rules/generate-life-stages/${encodeURIComponent(artistName)}`)
  }
}

// ════════════════════════════════════════════════════════════════
// Phase 2: 作品库产品线 API
// ════════════════════════════════════════════════════════════════

export const libraryApi = {
  create(data) {
    return api.post('/libraries', data)
  },
  getMine() {
    return api.get('/libraries')
  },
  getPublic(page = 1, pageSize = 20) {
    return api.get('/libraries/public', { params: { page, page_size: pageSize } })
  },
  getDetail(libraryId) {
    return api.get(`/libraries/${libraryId}`)
  },
  update(libraryId, data) {
    return api.put(`/libraries/${libraryId}`, data)
  },
  delete(libraryId, cascade = false) {
    return api.delete(`/libraries/${libraryId}`, { params: { cascade } })
  },
  // 协作者管理
  getCollaborators(libraryId) {
    return api.get(`/libraries/${libraryId}/collaborators`)
  },
  addCollaborator(libraryId, data) {
    return api.post(`/libraries/${libraryId}/collaborators`, data)
  },
  removeCollaborator(libraryId, userId) {
    return api.delete(`/libraries/${libraryId}/collaborators/${userId}`)
  },
  // 变更请求
  getAllChangeRequests(status = 'pending') {
    return api.get('/libraries/requests/all', { params: { status } })
  },
  getMyChangeRequests(status) {
    const params = {}
    if (status) params.status = status
    return api.get('/libraries/requests/my', { params })
  },
  getChangeRequests(libraryId, status = 'pending') {
    return api.get(`/libraries/${libraryId}/requests`, { params: { status } })
  },
  submitChangeRequest(libraryId, data) {
    return api.post(`/libraries/${libraryId}/requests`, data)
  },
  reviewChangeRequest(requestId, data) {
    return api.post(`/libraries/requests/${requestId}/review`, data)
  },
}

export const artworkApi = {
  upload(libraryId, file, fields = {}, onProgress) {
    const formData = new FormData()
    formData.append('file', file)
    Object.entries(fields || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      formData.append(k, String(v))
    })
    return api.post(`/libraries/${libraryId}/artworks`, formData, {
      timeout: 300000,
      onUploadProgress: evt => {
        if (!onProgress) return
        const total = evt.total || 0
        const loaded = evt.loaded || 0
        const percent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : null
        onProgress({ loaded, total, percent })
      },
    })
  },
  list(libraryId, params = {}) {
    return api.get(`/libraries/${libraryId}/artworks`, { params })
  },
  getDetail(artworkId) {
    return api.get(`/artworks/${artworkId}`)
  },
  update(artworkId, data) {
    return api.put(`/artworks/${artworkId}`, data)
  },
  delete(artworkId) {
    return api.delete(`/artworks/${artworkId}`)
  },
  // AI 分析
  triggerAnalysis(artworkId) {
    return api.post(`/artworks/${artworkId}/analyze`, {}, { timeout: 60000 })
  },
  getAnalysis(artworkId) {
    return api.get(`/artworks/${artworkId}/analysis`)
  },
  // 著录引用
  addLiterature(artworkId, data) {
    return api.post(`/artworks/${artworkId}/literature`, data)
  },
  deleteLiterature(artworkId, refId) {
    return api.delete(`/artworks/${artworkId}/literature/${refId}`)
  },
  // 拍卖记录
  addAuction(artworkId, data) {
    return api.post(`/artworks/${artworkId}/auctions`, data)
  },
  deleteAuction(artworkId, recId) {
    return api.delete(`/artworks/${artworkId}/auctions/${recId}`)
  },
}

export const notesApi = {
  create(artworkId, data) {
    return api.post(`/artworks/${artworkId}/notes`, data)
  },
  list(artworkId) {
    return api.get(`/artworks/${artworkId}/notes`)
  },
  get(noteId) {
    return api.get(`/notes/${noteId}`)
  },
  update(noteId, data) {
    return api.put(`/notes/${noteId}`, data)
  },
  delete(noteId) {
    return api.delete(`/notes/${noteId}`)
  },
}

export const notificationApi = {
  list() { return api.get('/notifications') },
  unreadCount() { return api.get('/notifications/unread-count') },
  markRead(id) { return api.put(`/notifications/${id}/read`) },
  markAllRead() { return api.put('/notifications/read-all') },
  myContributions() { return api.get('/notifications/my/contributions') },
}

export default api
