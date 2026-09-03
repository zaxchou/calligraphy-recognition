var api = require('../../utils/api')

Page({
  data: {
    libraries: [],
    loading: false,
    loggedIn: false
  },

  onLoad: function () {
    this.checkLogin()
  },

  onShow: function () {
    if (this.data.loggedIn) {
      this.loadLibraries()
    } else {
      this.checkLogin()
    }
  },

  onPullDownRefresh: function () {
    this.loadLibraries()
    wx.stopPullDownRefresh()
  },

  checkLogin: function () {
    var token = api.getToken()
    if (token) {
      this.setData({ loggedIn: true })
      this.loadLibraries()
    } else {
      // 尝试自动登录
      var that = this
      wx.login({
        success: function (res) {
          if (res.code) {
            api.wechatLogin(res.code).then(function (data) {
              api.setToken(data.token)
              that.setData({ loggedIn: true })
              that.loadLibraries()
            }).catch(function () {
              // Fallback: mock login
              api.wechatLogin('mock_miniprogram_user').then(function (data) {
                api.setToken(data.token)
                that.setData({ loggedIn: true })
                that.loadLibraries()
              }).catch(function () {
                wx.showToast({ title: '登录失败', icon: 'none' })
              })
            })
          }
        }
      })
    }
  },

  loadLibraries: function () {
    var that = this
    this.setData({ loading: true })
    api.getMyLibraries().then(function (data) {
      var libs = Array.isArray(data) ? data : (data.items || [])
      that.setData({ libraries: libs, loading: false })
    }).catch(function (err) {
      console.error('加载作品库失败:', err)
      that.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    })
  },

  goToLibrary: function (e) {
    var id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/libraries/detail?id=' + id })
  }
})
