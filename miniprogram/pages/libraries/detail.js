var api = require('../../utils/api')

Page({
  data: {
    libraryId: null,
    library: null,
    artworks: [],
    loading: false,
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: false
  },

  onLoad: function (options) {
    var id = parseInt(options.id)
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.setData({ libraryId: id })
    this.loadLibrary()
    this.loadArtworks()
  },

  onPullDownRefresh: function () {
    this.setData({ page: 1, artworks: [] })
    this.loadArtworks()
    wx.stopPullDownRefresh()
  },

  onReachBottom: function () {
    if (this.data.hasMore && !this.data.loading) {
      this.loadArtworks()
    }
  },

  loadLibrary: function () {
    var that = this
    api.getLibraryDetail(this.data.libraryId).then(function (data) {
      that.setData({ library: data })
    }).catch(function (err) {
      console.error('加载库详情失败:', err)
    })
  },

  loadArtworks: function () {
    var that = this
    if (this.data.loading) return
    this.setData({ loading: true })

    api.getLibraryArtworks(this.data.libraryId, this.data.page, this.data.pageSize).then(function (data) {
      var items = data.items || []
      var newArtworks = that.data.page === 1 ? items : that.data.artworks.concat(items)
      that.setData({
        artworks: newArtworks,
        total: data.total || 0,
        hasMore: newArtworks.length < (data.total || 0),
        loading: false,
        page: that.data.page + 1
      })
    }).catch(function (err) {
      console.error('加载作品失败:', err)
      that.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    })
  },

  goToArtwork: function (e) {
    var imageId = e.currentTarget.dataset.imageId
    if (imageId) {
      wx.navigateTo({ url: '/pages/tubi/tubi?id=' + imageId })
    }
  },

  formatImageUrl: function (path) {
    return api.getImageUrl(path)
  }
})
