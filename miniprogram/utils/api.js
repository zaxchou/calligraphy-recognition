var BASE_URL = 'https://124.223.17.29'

// Phase 1: Token 管理
var AUTH_TOKEN_KEY = 'auth_token'

function getToken() {
  try {
    return wx.getStorageSync(AUTH_TOKEN_KEY) || null
  } catch (e) {
    return null
  }
}

function setToken(token) {
  try {
    wx.setStorageSync(AUTH_TOKEN_KEY, token)
  } catch (e) {
    console.error('存储 token 失败', e)
  }
}

function clearToken() {
  try {
    wx.removeStorageSync(AUTH_TOKEN_KEY)
  } catch (e) {
    console.error('清除 token 失败', e)
  }
}

function request(url, method, data) {
  method = method || 'GET'
  var header = { 'Content-Type': 'application/json' }
  var token = getToken()
  if (token) {
    header['Authorization'] = 'Bearer ' + token
  }
  return new Promise(function (resolve, reject) {
    wx.request({
      url: BASE_URL + url,
      method: method,
      data: data,
      header: header,
      success: function (res) {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          // Token 过期，清除
          clearToken()
          reject({ code: 401, msg: '登录已过期，请重新进入小程序' })
        } else {
          reject({ code: res.statusCode, msg: res.data })
        }
      },
      fail: function (err) {
        reject({ code: -1, msg: '网络请求失败', detail: err })
      }
    })
  })
}

function uploadFile(filePath) {
  return new Promise(function (resolve, reject) {
    var header = {}
    var token = getToken()
    if (token) {
      header['Authorization'] = 'Bearer ' + token
    }
    wx.uploadFile({
      url: BASE_URL + '/api/v1/composition/upload',
      filePath: filePath,
      name: 'file',
      header: header,
      timeout: 120000,
      success: function (res) {
        if (res.statusCode === 200) {
          try { resolve(JSON.parse(res.data)) } catch (e) { reject({ code: -1, msg: '响应解析失败' }) }
        } else {
          reject({ code: res.statusCode, msg: '上传失败' })
        }
      },
      fail: function (err) { reject({ code: -1, msg: '上传网络错误', detail: err }) }
    })
  })
}

function uploadQczh(filePath) {
  return new Promise(function (resolve, reject) {
    var header = {}
    var token = getToken()
    if (token) {
      header['Authorization'] = 'Bearer ' + token
    }
    wx.uploadFile({
      url: BASE_URL + '/api/v1/composition/qichengzhuanhe-analyze',
      filePath: filePath,
      name: 'file',
      header: header,
      timeout: 120000,
      success: function (res) {
        if (res.statusCode === 200) {
          try { resolve(JSON.parse(res.data)) } catch (e) { reject({ code: -1, msg: '响应解析失败' }) }
        } else {
          reject({ code: res.statusCode, msg: '分析失败: ' + res.statusCode })
        }
      },
      fail: function (err) { reject({ code: -1, msg: '分析超时，请重试', detail: err }) }
    })
  })
}

// ===== 通用工具 =====
function getImageUrl(path) {
  if (!path) return ''
  var s = String(path).trim()
  if (!s) return ''
  if (s.indexOf('http') === 0) return s
  if (s.indexOf('/') === 0) return BASE_URL + s
  if (s.indexOf('.') > 0) return BASE_URL + '/' + s
  return ''
}

// ===== 知识库 API =====
function getBooks() {
  return request('/api/v1/knowledge/books')
}

function getBook(bookId) {
  return request('/api/v1/knowledge/books/' + bookId)
}

function getBookOutline(bookId) {
  return request('/api/v1/knowledge/books/' + bookId + '/outline')
}

function getBookMarkdown(bookId) {
  return request('/api/v1/knowledge/books/' + bookId + '/markdown')
}

function getBookImages(bookId) {
  return request('/api/v1/knowledge/books/' + bookId + '/images')
}

function getKnowledgeStats() {
  return request('/api/v1/knowledge/stats')
}

function searchKnowledge(query, limit, bookIds) {
  var data = {
    query: query,
    limit: limit || 20,
    book_ids: bookIds || null
  }
  // Phase 3d: 登录用户自动搜索私人文档
  if (getToken()) {
    data.include_private = true
  }
  return request('/api/v1/knowledge/search', 'POST', data)
}

// ===== 题跋分析 API =====
function getResults(skip, limit, artist) {
  var params = 'skip=' + (skip || 0) + '&limit=' + (limit || 20)
  if (artist) params += '&artist=' + encodeURIComponent(artist)
  return request('/api/v1/tubi/results?' + params)
}

function getArtworkDetail(id) {
  return request('/api/v1/tubi/result/' + id)
}

function searchArtworks(keyword) {
  return request('/api/v1/tubi/search?keyword=' + encodeURIComponent(keyword))
}

function getArtists() {
  return request('/api/v1/artists')
}

// ===== 大数据 API =====
function getContentReport() {
  return request('/api/v1/content-analysis/report')
}

function getContentStats() {
  return request('/api/v1/content-analysis/stats')
}

function getCorrelation() {
  return request('/api/v1/content-analysis/correlation')
}

function getSizeStats() {
  return request('/api/v1/content-analysis/size-stats')
}

// Phase 1: 微信登录
function wechatLogin(code) {
  return request('/api/v1/auth/wechat-login', 'POST', { code: code })
}

module.exports = {
  BASE_URL: BASE_URL,
  getImageUrl: getImageUrl,

  // Auth
  getToken: getToken,
  setToken: setToken,
  clearToken: clearToken,
  wechatLogin: wechatLogin,

  // Composition (existing)
  getTask: function (taskId) { return request('/api/v1/composition/task/' + taskId) },
  getReport: function (taskId) { return request('/api/v1/composition/report/' + taskId) },
  getHistory: function (limit) { return request('/api/v1/composition/history?limit=' + (limit || 10)) },
  upload: uploadFile,
  uploadQczh: uploadQczh,

  // Knowledge Base
  getBooks: getBooks,
  getBook: getBook,
  getBookOutline: getBookOutline,
  getBookMarkdown: getBookMarkdown,
  getBookImages: getBookImages,
  getKnowledgeStats: getKnowledgeStats,
  searchKnowledge: searchKnowledge,

  // Tubi
  getResults: getResults,
  getArtworkDetail: getArtworkDetail,
  searchArtworks: searchArtworks,
  getArtists: getArtists,

  // Big Data
  getContentReport: getContentReport,
  getContentStats: getContentStats,
  getCorrelation: getCorrelation,
  getSizeStats: getSizeStats,

  // Phase 2: 作品库
  getMyLibraries: function () {
    return request('/api/v1/libraries')
  },
  getPublicLibraries: function (page, pageSize) {
    var params = 'page=' + (page || 1) + '&page_size=' + (pageSize || 20)
    return request('/api/v1/libraries/public?' + params)
  },
  getLibraryDetail: function (libraryId) {
    return request('/api/v1/libraries/' + libraryId)
  },
  getLibraryArtworks: function (libraryId, page, pageSize) {
    var params = 'page=' + (page || 1) + '&page_size=' + (pageSize || 20)
    return request('/api/v1/libraries/' + libraryId + '/artworks?' + params)
  },
  getArtworkDetailV2: function (artworkId) {
    return request('/api/v1/artworks/' + artworkId)
  },

  // Phase 4a: 我的知识库文档
  getMyDocuments: function () {
    return request('/api/v1/knowledge/documents')
  },
  deleteMyDocument: function (docId) {
    return request('/api/v1/knowledge/documents/' + docId, 'DELETE')
  },

  // Phase 4c: 我的统计数据
  getMyStats: function () {
    return request('/api/v1/tubi/stats/my')
  }
}
