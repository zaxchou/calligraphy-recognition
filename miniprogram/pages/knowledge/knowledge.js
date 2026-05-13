var api = require('../../utils/api')
var md = require('../../utils/md')

Page({
  data: {
    // Phase 4a: Tab
    activeTab: 'public',
    hasToken: false,
    // My documents
    myDocs: [],
    myDocsLoading: false,
    // State: browse | searching | results | detail
    state: 'browse',
    // Search
    searchQuery: '',
    searchFocused: false,
    // Browse
    books: [],
    stats: { total_books: 0, total_chunks: 0, total_images: 0 },
    // Results
    aiSummary: null,
    searchResults: [],
    searchTotal: 0,
    relatedImages: [],
    // Detail
    currentBook: null,
    detailTab: 'outline', // outline | content | images
    outline: null,
    markdownHtml: '',
    bookImages: [],
    // Search result → detail context
    matchedResult: null,
    // Loading
    loading: false,
    searching: false
  },

  onLoad: function () {
    this.setData({ hasToken: !!api.getToken() })
    this._loadBrowse()
  },

  onPullDownRefresh: function () {
    if (this.data.state === 'browse') {
      this._loadBrowse()
    }
    wx.stopPullDownRefresh()
  },

  onShow: function () {
    if (this.data.state === 'browse' && this.data.books.length === 0) {
      this._loadBrowse()
    }
    // Refresh token state
    this.setData({ hasToken: !!api.getToken() })
  },

  // Phase 4a: Tab switching
  onSwitchTab: function (e) {
    var tab = e.currentTarget.dataset.tab
    this.setData({ activeTab: tab })
    if (tab === 'my' && this.data.hasToken && this.data.myDocs.length === 0) {
      this._loadMyDocs()
    }
  },

  // Phase 4a: Load my documents
  _loadMyDocs: function () {
    var that = this
    if (!this.data.hasToken) return
    this.setData({ myDocsLoading: true })
    api.getMyDocuments().then(function (data) {
      var docs = Array.isArray(data) ? data : (data.documents || [])
      that.setData({ myDocs: docs, myDocsLoading: false })
    }).catch(function () {
      that.setData({ myDocsLoading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    })
  },

  // Phase 4a: Delete my document
  onDeleteMyDoc: function (e) {
    var id = e.currentTarget.dataset.id
    if (!id) return
    var that = this
    wx.showModal({
      title: '确认删除',
      content: '确定删除此文档及其数据？',
      success: function (res) {
        if (res.confirm) {
          api.deleteMyDocument(id).then(function () {
            wx.showToast({ title: '已删除', icon: 'success' })
            that._loadMyDocs()
          }).catch(function () {
            wx.showToast({ title: '删除失败', icon: 'none' })
          })
        }
      }
    })
  },

  // ===== Browse =====
  _loadBrowse: function () {
    var that = this
    this.setData({ loading: true })
    Promise.all([
      api.getBooks().catch(function () { return [] }),
      api.getKnowledgeStats().catch(function () { return {} })
    ]).then(function (res) {
      var raw = Array.isArray(res[0]) ? res[0] : (res[0].books || [])
      var stats = res[1] || {}
      // Pre-process books with computed fields
      var books = raw.map(function (b) {
        return {
          id: b.id || b.book_id || '',
          title: b.title || b.book_title || '未命名',
          author: b.author || '',
          chapterCount: b.chapter_count || b.total_chunks || 0,
          coverChar: (b.title || '书').charAt(0),
          coverColor: ((b.id || 'a').charCodeAt(0) % 2 === 0) ? '#c9a96e' : '#5b7a8c'
        }
      })
      // Stats: {books: {total: N, by_status: ...}, tasks: {...}, contents: {chunks: N, images: N}}
      var b = stats.books || {}
      var c = stats.contents || {}
      that.setData({
        books: books,
        stats: {
          total_books: b.total || books.length,
          total_chunks: c.chunks || 0,
          total_images: c.images || 0
        },
        loading: false
      })
    }).catch(function () {
      that.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    })
  },

  // ===== Search =====
  onSearchInput: function (e) {
    this.setData({ searchQuery: e.detail.value })
  },

  onSearchFocus: function () {
    this.setData({ searchFocused: true })
  },

  onSearchBlur: function () {
    if (!this.data.searchQuery) {
      this.setData({ searchFocused: false })
    }
  },

  onSearchConfirm: function () {
    var q = (this.data.searchQuery || '').trim()
    if (!q) return
    this._doSearch(q)
  },

  onClearSearch: function () {
    this.setData({
      searchQuery: '',
      searchFocused: false,
      state: 'browse',
      aiSummary: null,
      searchResults: [],
      searchTotal: 0,
      relatedImages: []
    })
  },

  _doSearch: function (query) {
    var that = this
    this.setData({ searching: true, state: 'searching' })

    api.searchKnowledge(query, 20).then(function (res) {
      var results = (res.results || []).map(function (r) {
        return {
          chunk_id: r.chunk_id || r.vector_id || '',
          content: md.cleanText(r.content || ''),
          book_id: r.book_id || '',
          book_title: r.book_title || '未知书籍',
          chapter_title: r.chapter_title || '',
          page_start: r.page_start || null,
          page_end: r.page_end || null,
          score: r.score || 0,
          scorePct: ((r.score || 0) * 100).toFixed(0),
          locText: (r.chapter_title || '') + (r.page_start ? ' · p.' + r.page_start : ''),
          source: r.source || 'public',
          sourceLabel: r.source === 'private' ? '[我的]' : ''
        }
      })

      var aiSummary = res.ai_summary || null
      // Convert AI summary markdown to HTML and pre-compute display fields
      if (aiSummary) {
        if (aiSummary.answer) {
          aiSummary.answerHtml = md.blocksToHtml(aiSummary.answer)
        }
        aiSummary.confidencePct = aiSummary.confidence ? Math.round(aiSummary.confidence * 100) + '%' : ''
      }

      var relatedImages = (res.related_images || [])
        .filter(function (img) { return img.stored_url || img.url || img.image_url })
        .map(function (img) {
          var u = img.stored_url || img.url || img.image_url || ''
          return {
            url: api.getImageUrl(u),
            caption: img.display_label || img.caption || img.title || ''
          }
        })

      that.setData({
        state: 'results',
        searching: false,
        searchResults: results,
        searchTotal: res.total || results.length,
        aiSummary: aiSummary,
        relatedImages: relatedImages
      })
    }).catch(function () {
      that.setData({ searching: false, state: 'browse' })
      wx.showToast({ title: '搜索失败', icon: 'none' })
    })
  },

  // ===== Book Detail =====
  onBookTap: function (e) {
    var bookId = e.currentTarget.dataset.id
    if (!bookId) return

    // Find book in loaded books array
    var book = null
    var books = this.data.books
    for (var i = 0; i < books.length; i++) {
      if (books[i].id === bookId) { book = books[i]; break }
    }

    var that = this
    this.setData({
      state: 'detail',
      currentBook: book || { id: bookId, title: '', author: '' },
      detailTab: 'outline',
      outline: null,
      markdownHtml: '',
      bookImages: []
    })

    // Load outline
    api.getBookOutline(bookId).then(function (data) {
      // Normalize outline data
      var outline = Array.isArray(data) ? data : (data.outline || data.chapters || [])
      outline = outline.map(function (item) {
        if (typeof item === 'string') return { title: item, sections: [], expanded: false }
        return {
          title: item.title || item.chapter || item.name || '',
          sections: item.sections || item.subsections || [],
          expanded: false
        }
      })
      that.setData({ outline: outline })
    }).catch(function () {})

    // Load markdown
    api.getBookMarkdown(bookId).then(function (data) {
      var raw = ''
      if (typeof data === 'string') raw = data
      else if (data && data.content) raw = data.content
      else if (data && data.markdown) raw = data.markdown
      that.setData({ markdownHtml: md.blocksToHtml(raw) })
    }).catch(function () {})

    // Load images
    api.getBookImages(bookId).then(function (data) {
      var images = Array.isArray(data) ? data : (data && data.images || [])
      images = images.map(function (img) {
        return {
          id: img.id || img.image_id || '',
          url: api.getImageUrl(img.stored_url || img.url || img.image_url || img.path || ''),
          caption: img.caption || img.title || ''
        }
      })
      that.setData({ bookImages: images })
    }).catch(function () {})
  },

  onSwitchDetailTab: function (e) {
    var tab = e.currentTarget.dataset.tab
    this.setData({ detailTab: tab })
  },

  onBackFromDetail: function () {
    this.setData({
      state: 'browse',
      currentBook: null,
      outline: null,
      markdownHtml: '',
      bookImages: [],
      matchedResult: null
    })
  },

  // ===== Image Preview =====
  onImageTap: function (e) {
    var url = e.currentTarget.dataset.url
    if (url) {
      wx.previewImage({ current: url, urls: [url] })
    }
  },

  // ===== Result Tap → Book Detail =====
  onResultTap: function (e) {
    var bookId = e.currentTarget.dataset.bookId
    var idx = e.currentTarget.dataset.index
    if (!bookId) return
    // Save matched result for display in book detail
    var result = this.data.searchResults[idx]
    this.setData({ matchedResult: result || null })
    // Open book detail with content tab (search result implies user wants content)
    this.onBookTap({ currentTarget: { dataset: { id: bookId } } })
    var that = this
    setTimeout(function () { that.setData({ detailTab: 'content' }) }, 100)
  },

  onShareAppMessage: function () {
    return {
      title: '写意知识库 — 中国画知识检索',
      path: '/pages/knowledge/knowledge'
    }
  }
})
