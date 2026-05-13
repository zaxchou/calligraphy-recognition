var api = require('../../utils/api')

Page({
  data: {
    // Phase 4c: Tab
    activeTab: 'public',
    hasToken: false,
    myStats: null,
    myLoading: false,
    myError: false,
    myPublicTotal: 0,

    loading: true,

    // Sentiment
    negPct: 0, posPct: 0, neuPct: 0,
    negPctStr: '', posPctStr: '', neuPctStr: '',

    // Period distribution
    periodItems: [],

    // Size stats
    sizeItems: [],
    periodSizeItems: [],

    // Invasive rate
    invasiveItems: [],

    // Area distribution
    areaDistItems: [],

    // Totals
    totalWorks: 0
  },

  onLoad: function () {
    this.setData({ hasToken: !!api.getToken() })
    this._loadAll()
  },
  onPullDownRefresh: function () { this._loadAll(); wx.stopPullDownRefresh() },

  // Phase 4c: Tab switching
  onSwitchTab: function (e) {
    var tab = e.currentTarget.dataset.tab
    this.setData({ activeTab: tab })
    if (tab === 'my' && this.data.hasToken && !this.data.myStats) {
      this._loadMyStats()
    }
  },

  // Phase 4c: Load my stats
  _loadMyStats: function () {
    var that = this
    if (!this.data.hasToken) return
    this.setData({ myLoading: true, myError: false })
    api.getMyStats().then(function (data) {
      if (data.success) {
        that.setData({
          myStats: data.my_stats,
          myPublicTotal: data.public_total,
          myLoading: false
        })
      } else {
        that.setData({ myError: true, myLoading: false })
      }
    }).catch(function () {
      that.setData({ myError: true, myLoading: false })
    })
  },

  _loadAll: function () {
    var that = this
    this.setData({ loading: true })

    Promise.all([
      api.getContentStats().catch(function () { return null }),
      api.getCorrelation().catch(function () { return null }),
      api.getSizeStats().catch(function () { return null }),
      api.getResults(0, 500).catch(function () { return null })
    ]).then(function (res) {
      var stats = res[0] || {};
      var corr = res[1] || {};
      var sizeStats = res[2] || {};
      var results = res[3] || {};

      // === 1. Sentiment (aggregated by count) ===
      var negCount = 0, posCount = 0, neuCount = 0, sentTotal = 0;
      (stats.sentiment_distribution || []).forEach(function (s) {
        var p = (s.polarity || '').toLowerCase()
        var c = s.count || 0
        sentTotal += c
        if (p === 'negative') negCount += c
        else if (p === 'positive') posCount += c
        else if (p === 'neutral') neuCount += c
      })
      var negPct = sentTotal > 0 ? (negCount / sentTotal * 100) : 0
      var posPct = sentTotal > 0 ? (posCount / sentTotal * 100) : 0
      var neuPct = sentTotal > 0 ? (neuCount / sentTotal * 100) : 0

      // === 2. Period distribution ===
      var periodItems = (stats.period_stats || [])
        .filter(function (p) { return p.period && p.period !== '未分期' })
        .map(function (p) { return { label: p.period, count: p.count, pct: (p.count / (stats.total_count || 1) * 100).toFixed(1) } })

      // === 3. Size stats ===
      var sizeItems = (sizeStats.size_distribution || []).map(function (s) {
        return { category: s.category, count: s.count, pct: (s.percentage || 0).toFixed(1) }
      })
      var periodSizeItems = (sizeStats.period_size_distribution || [])
        .filter(function (p) { return p.period && p.period !== '未分期' })
        .map(function (p) {
          return { period: p.period, avgH: Math.round(p.avg_height || 0), avgW: Math.round(p.avg_width || 0), count: p.count }
        })

      // === 4. Invasive rate ===
      var invasiveItems = (corr.invasive_analysis && corr.invasive_analysis.invasive_items || [])
        .sort(function (a, b) { return b.invasive_rate - a.invasive_rate })
        .map(function (item) {
          return {
            theme: item.theme,
            rate: (item.invasive_rate * 100).toFixed(1),
            invasive: item.invasive_count,
            nonInvasive: item.non_invasive_count
          }
        })

      // === 5. Inscription area distribution ===
      var areaBuckets = { '0-10%': 0, '10-20%': 0, '20-30%': 0, '30-40%': 0, '40-50%': 0, '>50%': 0 }
      var resultItems = results.data || (Array.isArray(results) ? results : [])
      resultItems.forEach(function (item) {
        var pct = parseFloat(item.inscription_percent) || 0
        if (pct <= 10) areaBuckets['0-10%']++
        else if (pct <= 20) areaBuckets['10-20%']++
        else if (pct <= 30) areaBuckets['20-30%']++
        else if (pct <= 40) areaBuckets['30-40%']++
        else if (pct <= 50) areaBuckets['40-50%']++
        else areaBuckets['>50%']++
      })
      var totalForArea = resultItems.length || 1
      var areaDistItems = Object.keys(areaBuckets).map(function (k) {
        return { range: k, count: areaBuckets[k], pct: (areaBuckets[k] / totalForArea * 100).toFixed(1) }
      })

      that.setData({
        loading: false,
        totalWorks: stats.total_count || 0,
        negPct: negPct, posPct: posPct, neuPct: neuPct,
        negPctStr: negPct.toFixed(1) + '%',
        posPctStr: posPct.toFixed(1) + '%',
        neuPctStr: neuPct.toFixed(1) + '%',
        periodItems: periodItems,
        sizeItems: sizeItems,
        periodSizeItems: periodSizeItems,
        invasiveItems: invasiveItems,
        areaDistItems: areaDistItems
      });
    }).catch(function (err) {
      that.setData({ loading: false })
      console.error('Data load error:', err)
      wx.showToast({ title: '加载失败: ' + (err && err.msg || '未知'), icon: 'none' })
    })
  },

  onShareAppMessage: function () {
    return { title: '题跋大数据分析 — 量化洞察', path: '/pages/data/data' }
  }
})
