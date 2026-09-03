var api = require('../../utils/api')

Page({
  data: {
    // State: list | detail
    state: 'list',
    // List
    artworks: [],
    total: 0,
    skip: 0,
    pageSize: 20,
    hasMore: true,
    loading: false,
    // Filters
    selectedArtist: '',
    artistList: ['全部画家'],
    artistIndex: 0,
    // Overview
    overview: null,
    // Detail
    currentArtwork: null,
    detailLoading: false
  },

  onLoad: function () {
    this._loadArtists()
    this._loadArtworks(true)
    this._loadOverview()
  },

  onPullDownRefresh: function () {
    if (this.data.state === 'list') {
      this._loadArtworks(true)
      this._loadOverview()
    }
    wx.stopPullDownRefresh()
  },

  // ===== Overview =====
  _loadOverview: function () {
    var that = this
    api.getContentStats().then(function (stats) {
      var totalWorks = stats.total_count || 0

      // Aggregate sentiment by count (not percentage, since percentages are per-period)
      var negCount = 0, posCount = 0, neuCount = 0, sentTotal = 0
      var sentList = stats.sentiment_distribution || []
      sentList.forEach(function (s) {
        var label = (s.polarity || '').toLowerCase()
        var cnt = s.count || 0
        sentTotal += cnt
        if (label === 'negative') negCount += cnt
        else if (label === 'positive') posCount += cnt
        else if (label === 'neutral') neuCount += cnt
      })
      var negPct = sentTotal > 0 ? (negCount / sentTotal * 100) : 0
      var posPct = sentTotal > 0 ? (posCount / sentTotal * 100) : 0
      var neuPct = sentTotal > 0 ? (neuCount / sentTotal * 100) : 0

      // Aggregate themes across periods (field: theme_name, need to merge same-named entries)
      var themeMap = {}
      var themeDist = stats.theme_distribution || []
      themeDist.forEach(function (t) {
        var name = t.theme_name || ''
        if (!name) return
        if (!themeMap[name]) themeMap[name] = { name: name, count: 0, pct: 0 }
        themeMap[name].count += (t.count || 0)
        themeMap[name].pct += (t.percentage || 0)
      })
      var topThemes = Object.values(themeMap)
        .sort(function (a, b) { return b.pct - a.pct })
        .slice(0, 5)
        .map(function (t) {
          return { name: t.name, pct: t.pct.toFixed(1), count: t.count }
        })

      // Period list
      var periods = (stats.period_stats || [])
        .filter(function (p) { return p.period && p.period !== '未分期' })
        .map(function (p) { return p.period })
        .filter(Boolean)

      // Period stats for chart
      var periodStats = (stats.period_stats || [])
        .filter(function (p) { return p.period && p.period !== '未分期' })
        .map(function (p) { return { label: p.period, value: Math.round(p.avg_char_count || 0), count: p.count } })

      // Chart heights
      var periodChartH = periodStats.length > 0 ? periodStats.length * 48 + 30 : 0
      var themeChartH = topThemes.length > 0 ? topThemes.length * 48 + 30 : 0

      that.setData({
        overview: {
          totalWorks: totalWorks,
          negPct: negPct.toFixed(1),
          posPct: posPct.toFixed(1),
          neuPct: neuPct.toFixed(1),
          topThemes: topThemes,
          periods: periods.slice(0, 5),
          periodStats: periodStats,
          periodChartH: periodChartH,
          themeChartH: themeChartH
        }
      })

      // Draw charts after DOM update
      if (periodStats.length > 0) {
        setTimeout(function () { _drawBarChart('periodChart', periodStats, '字', '#c9a96e') }, 700)
      }
      if (topThemes.length > 0) {
        var themeChartData = topThemes.map(function (t) { return { label: t.name, value: t.count, count: t.count } })
        setTimeout(function () { _drawBarChart('themeChart2', themeChartData, '件', '#5b7a8c') }, 700)
      }
    }).catch(function () {})
  },

  // ===== Artists =====
  _loadArtists: function () {
    var that = this
    // Get unique artists from actual artwork data (not artists table which may have fake entries)
    api.getResults(0, 500).then(function (res) {
      var items = res.data || (Array.isArray(res) ? res : [])
      var seen = {}
      items.forEach(function (item) {
        var name = (item.artist || '').trim()
        if (name) seen[name] = true
      })
      var names = Object.keys(seen).sort()
      that.setData({ artistList: ['全部画家'].concat(names) })
    }).catch(function () {
      // Fallback to artists table
      api.getArtists().then(function (data) {
        var artists = data.artists || (Array.isArray(data) ? data : [])
        var names = artists.map(function (a) { return a.name || '' }).filter(Boolean)
        that.setData({ artistList: ['全部画家'].concat(names) })
      }).catch(function () {})
    })
  },

  onArtistChange: function (e) {
    var idx = parseInt(e.detail.value)
    var name = this.data.artistList[idx]
    this.setData({
      artistIndex: idx,
      selectedArtist: idx === 0 ? '' : name,
      skip: 0,
      artworks: [],
      hasMore: true
    })
    this._loadArtworks(true)
  },

  // ===== Artworks =====
  _loadArtworks: function (reset) {
    var that = this
    if (this.data.loading) return

    var skip = reset ? 0 : this.data.skip
    this.setData({ loading: true })

    api.getResults(skip, this.data.pageSize, this.data.selectedArtist).then(function (res) {
      // Response: {success, data: [...], total}
      var items = res.data || (Array.isArray(res) ? res : [])
      var total = res.total || items.length

      // Pre-process artwork items
      items = items.map(function (item) {
        return {
          id: item.id || item.image_id || '',
          title: item.title || '未命名',
          artist: item.artist || item.artist_name || '未知',
          year: item.year || '未知',
          inscriptionPct: item.inscription_percent,
          paintingPct: item.painting_percent,
          thumbUrl: api.getImageUrl(item.thumbnail_url || item.url || ''),
          tags: _parseTags(item.tags || item.computed_tags)
        }
      })

      var newList = reset ? items : that.data.artworks.concat(items)

      that.setData({
        artworks: newList,
        total: total,
        skip: skip + items.length,
        hasMore: newList.length < total,
        loading: false
      })
    }).catch(function () {
      that.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    })
  },

  onLoadMore: function () {
    if (this.data.hasMore && !this.data.loading) {
      this._loadArtworks(false)
    }
  },

  // ===== Detail =====
  onArtworkTap: function (e) {
    var id = e.currentTarget.dataset.id
    if (!id) return
    var that = this
    this.setData({ state: 'detail', detailLoading: true, currentArtwork: null })

    api.getArtworkDetail(id).then(function (data) {
      // Response: {success, data: {...}}

      var raw = data.data || data
      var tags = _parseTags(raw.tags || raw.computed_tags)
      var materialTags = _parseTags(raw.material_tags)

      // Parse content_analysis
      var ca = raw.content_analysis
      if (typeof ca === 'string') {
        try { ca = JSON.parse(ca) } catch (e) { ca = null }
      }
      var contentTags = []
      var aiAnalysisHtml = ''
      if (ca) {
        // Themes: ca.themes is array of {code, name, confidence, score}
        var themeList = ca.themes || ca.theme || []
        if (!Array.isArray(themeList)) themeList = [themeList]
        contentTags = themeList.map(function (t) {
          return (typeof t === 'object' ? (t.name || t.code || '') : String(t))
        }).filter(Boolean)

        var parts = []
        // Summary
        if (ca.summary) parts.push('<p style="margin:12rpx 0;line-height:1.8">' + _esc(String(ca.summary)) + '</p>')

        // Sentiment: ca.sentiment is {polarity, emotion_score, reasoning, reasoning_steps}
        var sent = ca.sentiment
        if (sent && typeof sent === 'object') {
          var polarity = sent.polarity || ''
          var pLower = String(polarity).toLowerCase()
          var color = '#c04030'
          if (pLower.indexOf('pos') >= 0 || String(polarity).indexOf('积极') >= 0) color = '#67c23a'
          else if (pLower.indexOf('neu') >= 0 || String(polarity).indexOf('中性') >= 0) color = '#8b7d6b'
          var scoreStr = sent.emotion_score != null ? ' (' + sent.emotion_score + ')' : ''
          parts.push('<p style="margin:8rpx 0"><span style="font-weight:600">情感：</span><span style="color:' + color + ';font-weight:600">' + _esc(String(polarity)) + scoreStr + '</span></p>')

          // Reasoning chain
          if (sent.reasoning) {
            parts.push('<p style="margin:6rpx 0;line-height:1.8;color:#555;font-size:26rpx">' + _esc(String(sent.reasoning)) + '</p>')
          }
          var steps = sent.reasoning_steps || []
          if (Array.isArray(steps) && steps.length > 0) {
            parts.push('<p style="margin:10rpx 0 4rpx;font-weight:600;font-size:24rpx;color:#c9a96e">推理步骤</p>')
            steps.forEach(function (step) {
              if (typeof step === 'object') {
                var label = step.label || step.step || ''
                var text = step.detail || step.text || step.content || step.analysis || ''
                parts.push('<p style="margin:6rpx 0;padding-left:16rpx;border-left:3rpx solid #c9a96e;color:#666;font-size:24rpx;line-height:1.7"><b>' + _esc(String(label)) + '</b><br/>' + _esc(String(text)) + '</p>')
              } else {
                parts.push('<p style="margin:6rpx 0;padding-left:16rpx;border-left:3rpx solid #c9a96e;color:#666;font-size:24rpx">' + _esc(String(step)) + '</p>')
              }
            })
          }
        } else if (sent && typeof sent === 'string') {
          var sColor = '#c04030'
          if (String(sent).indexOf('积极') >= 0) sColor = '#67c23a'
          parts.push('<p style="margin:8rpx 0"><span style="font-weight:600">情感：</span><span style="color:' + sColor + ';font-weight:600">' + _esc(String(sent)) + '</span></p>')
        }

        // Theme list
        if (contentTags.length > 0) {
          parts.push('<p style="margin:8rpx 0"><span style="font-weight:600">主题：</span>' + _esc(contentTags.join('、')) + '</p>')
        }

        // Feature words
        if (ca.feature_words && typeof ca.feature_words === 'object') {
          var fw = ca.feature_words
          var fwList = fw.emotion || fw.core_arts || fw.social || fw.v4_signals || []
          if (!Array.isArray(fwList)) fwList = [fwList]
          fwList = fwList.filter(Boolean)
          if (fwList.length > 0) {
            parts.push('<p style="margin:8rpx 0"><span style="font-weight:600;font-size:24rpx;color:#8b7d6b">特征词：</span>' + _esc(fwList.slice(0, 10).join('、')) + '</p>')
          }
        }

        aiAnalysisHtml = parts.join('')
      }

      // Parse regions for overlay
      var regionsData = _parseRegions(raw.regions)
      var hasRegions = regionsData && (regionsData.inscription_regions.length > 0 || regionsData.painting_regions.length > 0)
      var imgW = raw.width || raw.image_width || 782
      var imgH = raw.height || raw.image_height || 616
      var canvasH = hasRegions ? Math.round(300 * imgH / imgW) : 0

      var artwork = {
        id: raw.id || raw.image_id || '',
        title: raw.title || '未命名',
        artist: raw.artist || raw.artist_name || '未知',
        year: raw.year || null,
        period: raw.period || raw.period_phase || '',
        inscriptionPct: raw.inscription_percent,
        paintingPct: raw.painting_percent,
        blankPct: raw.blank_percent,
        imageUrl: api.getImageUrl(raw.url || raw.annotated_image_url || raw.thumbnail_url || ''),
        widthCm: raw.artwork_width_cm || raw.width_cm || null,
        heightCm: raw.artwork_height_cm || raw.height_cm || null,
        albumName: raw.album_name || '',
        albumIndex: raw.album_index != null ? raw.album_index : null,
        sealContent: raw.seal_content || '',
        materialTags: materialTags,
        tags: tags,
        contentTags: contentTags,
        inscriptionText: raw.inscription_content || '',
        translatedText: raw.inscription_modern || '',
        aiAnalysisHtml: aiAnalysisHtml,
        hasRegions: hasRegions,
        regionsCanvasH: canvasH
      }

      that.setData({ currentArtwork: artwork, detailLoading: false })

      // Draw regions overlay after DOM update
      if (hasRegions) {
        setTimeout(function () {
          _drawRegionsOverlay(artwork.imageUrl, regionsData, imgW, imgH)
        }, 600)
      }
    }).catch(function () {
      that.setData({ detailLoading: false })
      wx.showToast({ title: '加载详情失败', icon: 'none' })
    })
  },

  onBackFromDetail: function () {
    this.setData({ state: 'list', currentArtwork: null })
  },

  onPreviewHero: function (e) {
    var url = e.currentTarget.dataset.url
    if (url) wx.previewImage({ urls: [url], current: url })
  },

  onShareAppMessage: function () {
    var title = '题跋分析 — 中国画题跋数据库'
    if (this.data.state === 'detail' && this.data.currentArtwork) {
      title = this.data.currentArtwork.title || title
    }
    return { title: title, path: '/pages/tubi/tubi' }
  }
})

// Parse tags: could be JSON string or already an array
function _parseTags(tags) {
  if (!tags) return []
  if (Array.isArray(tags)) return tags
  if (typeof tags === 'string') {
    try { return JSON.parse(tags) } catch (e) { return [tags] }
  }
  return []
}

// Basic HTML escape
function _esc(s) {
  if (!s) return ''
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// Parse regions (could be JSON string or object)
function _parseRegions(regions) {
  if (!regions) return null
  if (typeof regions === 'string') {
    try { return JSON.parse(regions) } catch (e) { return null }
  }
  return regions
}

// Draw horizontal bar chart on canvas
function _drawBarChart(canvasId, data, unit, color) {
  if (!data || !data.length) return
  var query = wx.createSelectorQuery()
  query.select('#' + canvasId).fields({ node: true, size: true }).exec(function (res) {
    if (!res || !res[0] || !res[0].node) return
    var canvas = res[0].node
    var ctx = canvas.getContext('2d')
    var dpr = wx.getWindowInfo().pixelRatio
    var W = res[0].width
    var barH = 48
    var H = data.length * barH + 30
    canvas.width = W * dpr
    canvas.height = H * dpr
    ctx.scale(dpr, dpr)

    ctx.clearRect(0, 0, W, H)

    var barMaxW = W - 180
    var maxVal = Math.max.apply(null, data.map(function (d) { return d.value }))
    if (maxVal === 0) maxVal = 1

    data.forEach(function (d, i) {
      var y = 10 + i * barH
      var barW = Math.max(4, (d.value / maxVal) * barMaxW)

      // Label
      ctx.fillStyle = '#2c2416'
      ctx.font = '12px sans-serif'
      ctx.textAlign = 'right'
      ctx.fillText(d.label, 105, y + 17)

      // Bar bg
      ctx.fillStyle = '#f0ebe0'
      ctx.fillRect(112, y, barMaxW, 22)

      // Bar fill
      ctx.fillStyle = color
      ctx.fillRect(112, y, barW, 22)

      // Value text
      ctx.fillStyle = '#2c2416'
      ctx.font = '11px sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText(d.value + ' ' + unit, 112 + barW + 6, y + 16)
    })
  })
}

// Draw regions overlay on canvas
function _drawRegionsOverlay(imageUrl, regionsData, imgW, imgH) {
  var query = wx.createSelectorQuery()
  query.select('#regionsCanvas').fields({ node: true, size: true }).exec(function (res) {
    if (!res || !res[0] || !res[0].node) return
    var canvas = res[0].node
    var ctx = canvas.getContext('2d')
    var dpr = wx.getWindowInfo().pixelRatio
    var cw = 300  // fixed display width
    var ratio = cw / imgW
    var ch = Math.round(imgH * ratio)

    canvas.width = cw * dpr
    canvas.height = ch * dpr
    ctx.scale(dpr, dpr)

    // Load and draw the image
    var img = canvas.createImage()
    img.onload = function () {
      ctx.drawImage(img, 0, 0, cw, ch)

      // Draw painting regions (teal, semi-transparent fill)
      var pRegions = regionsData.painting_regions || []
      pRegions.forEach(function (r) {
        if (r.type === 'polygon' && r.points && r.points.length > 2) {
          ctx.beginPath()
          r.points.forEach(function (p, i) {
            var x = (p.x || 0) * ratio
            var y = (p.y || 0) * ratio
            if (i === 0) ctx.moveTo(x, y)
            else ctx.lineTo(x, y)
          })
          ctx.closePath()
          ctx.fillStyle = 'rgba(91, 122, 140, 0.25)'
          ctx.fill()
          ctx.strokeStyle = 'rgba(91, 122, 140, 0.6)'
          ctx.lineWidth = 1.5
          ctx.stroke()
        }
      })

      // Draw inscription regions (gold, semi-transparent fill)
      var iRegions = regionsData.inscription_regions || []
      iRegions.forEach(function (r) {
        if (r.type === 'polygon' && r.points && r.points.length > 2) {
          ctx.beginPath()
          r.points.forEach(function (p, i) {
            var x = (p.x || 0) * ratio
            var y = (p.y || 0) * ratio
            if (i === 0) ctx.moveTo(x, y)
            else ctx.lineTo(x, y)
          })
          ctx.closePath()
          ctx.fillStyle = 'rgba(201, 169, 110, 0.3)'
          ctx.fill()
          ctx.strokeStyle = 'rgba(201, 169, 110, 0.7)'
          ctx.lineWidth = 2
          ctx.stroke()
        }
      })
    }
    img.onerror = function () {
      ctx.fillStyle = '#f0ebe0'
      ctx.fillRect(0, 0, cw, ch)
    }
    img.src = imageUrl
  })
}
