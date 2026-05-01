var BASE_URL = 'http://localhost:8001'

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
          try {
            resolve(JSON.parse(res.data))
          } catch (e) {
            reject({ code: -1, msg: '响应解析失败' })
          }
        } else {
          reject({ code: res.statusCode, msg: '上传失败' })
        }
      },
      fail: function (err) {
        reject({ code: -1, msg: '上传网络错误', detail: err })
      }
    })
  })
}

module.exports = {
  BASE_URL: BASE_URL,

  getTask: function (taskId) {
    return request('/api/v1/composition/task/' + taskId)
  },

  getReport: function (taskId) {
    return request('/api/v1/composition/report/' + taskId)
  },

  getHistory: function (limit) {
    return request('/api/v1/composition/history?limit=' + (limit || 10))
  },

  upload: uploadFile
}
