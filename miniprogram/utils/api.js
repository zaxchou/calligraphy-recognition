var BASE_URL = 'https://124.223.17.29'

function request(url, method, data) {
  method = method || 'GET'
  return new Promise(function (resolve, reject) {
    wx.request({
      url: BASE_URL + url,
      method: method,
      data: data,
      header: { 'Content-Type': 'application/json' },
      success: function (res) {
        if (res.statusCode === 200) {
          resolve(res.data)
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
    wx.uploadFile({
      url: BASE_URL + '/api/v1/composition/upload',
      filePath: filePath,
      name: 'file',
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
    wx.uploadFile({
      url: BASE_URL + '/api/v1/composition/qichengzhuanhe-analyze',
      filePath: filePath,
      name: 'file',
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
  // Bare filename: prepend BASE_URL with path separator
  if (s.indexOf('.') > 0) return BASE_URL + '/' + s
  // Unknown format: return empty to prevent 500 errors
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
  return request('/api/v1/knowledge/search', 'POST', {
    query: query,
    limit: limit || 20,
    book_ids: bookIds || null
  })
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

module.exports = {
  BASE_URL: BASE_URL,
  getImageUrl: getImageUrl,

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
  getCorrelation: getCorrelation
}
