var api = require('../../utils/api')
var md = require('../../utils/md')

var DEMO_REPORT = {
  summary: { total_score: 83 },
  llm: {
    text: [
      '## 构图总评',
      '',
      '该作品整体呈现出**疏密有致、虚实相生**的构图格局。画面以对角线式展开，主体置于右下角**黄金分割点**附近，视觉重心稳定。',
      '',
      '### 开合之势（起承转合）',
      '',
      '- **起**（左下方）：以浓墨重笔起势，形成视觉锚点',
      '- **承**（中部偏右）：笔势顺势延伸，形成流畅的视觉动线',
      '- **转**（上部）：以淡墨虚笔转换气势，制造空间张力',
      '- **合**（左上方）：落款题字收束全局，一气呵成',
      '',
      '### 疏密节奏',
      '',
      '画面在疏密关系上处理得当。**密处**集中在右下角主体区域，用笔密度约占总面积 **42%**，**疏处**位于左上角留白区域，形成鲜明的节奏对比。疏密比约 **4:6**，符合传统构图中\'疏可走马，密不透风\'的审美原则。',
      '',
      '### 虚实留白',
      '',
      '留白处理是该作的一大亮点。画面左侧留有约 **35%** 的空白区域，不仅为画面提供呼吸感，更与右侧的密实形成阴阳对比。虚中有实、实中见虚，体现了**计白当黑**的构图智慧。',
      '',
      '### 气韵生动',
      '',
      '整体笔势走向自然流畅，墨色浓淡变化丰富，从起笔的**重墨**到收尾的**淡墨**，形成了完整的视觉韵律。画面虽静，却有**蓄势待发**的动感，体现了中国画\'气韵生动\'的至高境界。'
    ].join('\n')
  }
}

Page({
  data: {
    state: 'idle',
    imagePath: '',
    loading: false,
    progress: 0,
    stageText: '',
    etaSeconds: null,
    totalScore: null,
    llmHtml: '',
    radarDims: [],
    qczhImage: '',
    pathType: '',
    qczhLoading: false,
    errorMsg: '',
    showDemoBtn: true,
    hasRadar: false,
    hasOverlay: false,
    hasQczh: false,
    shareCanvasH: 800
  },

  _taskId: null,
  _pollTimer: null,
  _timeoutTimer: null,
  _qczhRes: null,
  _reportText: '',
  POLL_INTERVAL: 2000,
  TIMEOUT_MS: 300000,

  onShareAppMessage: function () { return { title: '潘天寿教你构图 — AI 中国画构图分析', path: '/pages/analyze/analyze' } },
  onShareTimeline: function () { return { title: '潘天寿教你构图', query: '' } },

  chooseImage: function () {
    var that = this
    wx.chooseImage({
      count: 1, sizeType: ['compressed'], sourceType: ['album', 'camera'],
      success: function (res) { that.setData({ imagePath: res.tempFilePaths[0], state: 'preview' }) }
    })
  },

  startAnalyze: function () {
    var that = this
    var filePath = this.data.imagePath
    if (!filePath) return

    this._qczhRes = null
    this._reportText = ''
    this.setData({ state: 'analyzing', progress: 0, stageText: '正在上传图片...', qczhLoading: false, hasQczh: false })

    // 请求1: 构图评分系统 (上传 + 轮询)
    this._startTimeout()
    api.upload(filePath).then(function (res) {
      that._taskId = res.task_id
      that._startPolling()
    }).catch(function () {
      that.setData({ state: 'error', errorMsg: '上传失败，请检查网络' })
    })

    // 请求2: 起承转合曲线 (独立，不阻塞评分)
    api.uploadQczh(filePath).then(function (res) {
      that._onQczhDone(res)
    }).catch(function () {
      that._onQczhDone(null)
    })
  },

  _startPolling: function () {
    var that = this
    this._pollTimer = setInterval(function () {
      api.getTask(that._taskId).then(function (data) {
        that.setData({
          progress: data.progress || 0,
          stageText: data.stage_text || data.stage || '',
          etaSeconds: data.eta_seconds || null
        })
        if (data.status === 'done') { that._stopPolling(); that._loadReport() }
        else if (data.status === 'failed') {
          that._stopPolling()
          that.setData({ state: 'error', errorMsg: data.error_message || '分析失败' })
        }
      }).catch(function () {})
    }, this.POLL_INTERVAL)
  },

  _loadReport: function () {
    var that = this
    api.getReport(this._taskId).then(function (report) {
      that._renderResult(report)
    }).catch(function () {
      that.setData({ state: 'error', errorMsg: '获取报告失败' })
    })
  },

  _renderResult: function (report) {
    var llmText = (report && report.llm && report.llm.text) ? String(report.llm.text) : ''
    this._reportText = llmText

    var totalScore = null
    if (report && report.summary && report.summary.total_score != null) {
      var ts = Number(report.summary.total_score)
      if (!isNaN(ts)) totalScore = ts
    }
    var hasOverlay = !!(report && report.assets && report.assets.arrow_overlay_url)
    var radarDims = _buildRadarDims(report)
    var qczhPending = this._qczhRes === null

    this.setData({
      state: 'done', progress: 100,
      totalScore: totalScore,
      llmHtml: md.blocksToHtml(llmText),
      radarDims: radarDims,
      qczhLoading: qczhPending,
      showDemoBtn: false,
      hasRadar: radarDims.length > 0,
      hasOverlay: hasOverlay,
      hasQczh: false
    })

    if (radarDims.length > 0) {
      var that = this
      setTimeout(function () { _drawRadar(that) }, 400)
    }

    // qczh 可能在报告之前就已经返回了
    if (this._qczhRes) {
      this._applyQczh(this._qczhRes)
    }
  },

  _onQczhDone: function (res) {
    this._qczhRes = res
    if (this.data.state === 'done') {
      this._applyQczh(res)
    }
  },

  _applyQczh: function (res) {
    this._qczhRes = null
    var img = ''
    var pathType = ''

    if (res) {
      img = res.preview_image || ''
      pathType = res.path_type || ''
    }

    this.setData({
      qczhImage: img,
      pathType: pathType,
      hasQczh: !!img,
      qczhLoading: false
    })

    if (!!img) {
      wx.showToast({ title: '起承转合分析完成', icon: 'success', duration: 2000 })
    }
  },

  loadDemo: function () {
    var that = this
    this.setData({ state: 'preview', imagePath: '' })
    setTimeout(function () {
      that.setData({
        state: 'done', progress: 100, totalScore: 83,
        llmHtml: md.blocksToHtml(DEMO_REPORT.llm.text),
        radarDims: [
          { label:'开合', score:17, max:20, pct:85, color:'#b0886a' },
          { label:'虚实', score:13, max:18, pct:72, color:'#8daa94' },
          { label:'疏密', score:16, max:18, pct:89, color:'#8b9bb4' },
          { label:'辅助', score:10, max:14, pct:71, color:'#9e8c7a' },
          { label:'均衡', score:10, max:12, pct:83, color:'#8c9aad' },
          { label:'穿插', score:7,  max:10, pct:70, color:'#b0a28a' },
          { label:'边角', score:6,  max:8,  pct:75, color:'#7d9b8a' }
        ],
        qczhLoading: false, hasQczh: false,
        showDemoBtn: false, hasRadar: true, hasOverlay: true
      })
      setTimeout(function () { _drawRadar(that) }, 500)
    }, 300)
  },

  loadHistoryItem: function () {
    var that = this
    wx.showLoading({ title: '加载中...' })
    api.getHistory(10).then(function (res) {
      var items = (res && res.items) || []
      var done = null
      for (var i = 0; i < items.length; i++) { if (items[i].status === 'done') { done = items[i]; break } }
      if (!done) { wx.hideLoading(); wx.showToast({ title: '没有已完成的历史记录', icon: 'none' }); return }
      that.setData({ imagePath: done.thumb_url ? (api.BASE_URL + done.thumb_url) : '' })
      api.getReport(done.task_id).then(function (report) {
        wx.hideLoading()
        that._renderResult(report)
      }).catch(function () { wx.hideLoading(); wx.showToast({ title: '获取报告失败', icon: 'none' }) })
    }).catch(function () { wx.hideLoading(); wx.showToast({ title: '获取历史记录失败', icon: 'none' }) })
  },

  generateShareImage: function () {
    var that = this
    var totalScore = this.data.totalScore || 0
    var rawText = this._reportText || ''
    var maxChars = 6000
    var hasRadar = this.data.hasRadar
    var hasQczh = this.data.hasQczh
    var qczhImg = this.data.qczhImage || ''

    wx.showLoading({ title: '生成中...' })

    function begin(radarPath) {
      var query = wx.createSelectorQuery()
      query.select('#shareCanvas').fields({ node: true, size: true }).exec(function (res) {
        if (!res || !res[0] || !res[0].node) { wx.hideLoading(); return }
        var canvas = res[0].node
        var ctx = canvas.getContext('2d')

        // 收集需要加载的图片
        var imgsToLoad = []
        if (radarPath) imgsToLoad.push({ key: 'radar', src: radarPath })
        if (hasQczh && qczhImg) imgsToLoad.push({ key: 'qczh', src: qczhImg })

        var loaded = { radar: null, qczh: null }
        var needCount = imgsToLoad.length
        var doneCount = 0

        function doDraw() {
          doneCount++
          if (doneCount < needCount) return

          var dpr = 2
          var W = 600
          var padding = 60
          var textW = W - padding * 2
          var titleFont = 'bold 28px sans-serif'
          var bodyFont = '16px sans-serif'
          var smallFont = '14px sans-serif'
          var lineH = 26
          var titleLineH = 36

          // 图片区域高度
          var imgAreaH = 0
          var radarDH = 0, qczhDH = 0
          if (loaded.radar && loaded.radar.width > 0) {
            var rs = Math.min(1, textW / loaded.radar.width)
            radarDH = loaded.radar.height * rs + 24
            imgAreaH += radarDH
          }
          if (loaded.qczh && loaded.qczh.width > 0) {
            var qs = Math.min(1, textW / loaded.qczh.width)
            qczhDH = loaded.qczh.height * qs + 24
            imgAreaH += qczhDH
          }
          if (imgAreaH > 0) imgAreaH += 16

          var textLines = that._buildShareLines(ctx, rawText, maxChars, textW, titleFont, bodyFont, smallFont, titleLineH, lineH)
          var textBlockH = 0
          for (var i = 0; i < textLines.length; i++) { textBlockH += textLines[i].h }

          var footerH = 80
          var headerH = 360
          var H = headerH + imgAreaH + textBlockH + footerH
          if (H > 8000) H = 8000

          that.setData({ shareCanvasH: H })
          canvas.width = W * dpr
          canvas.height = H * dpr
          ctx.scale(dpr, dpr)

          ctx.fillStyle = '#faf8f3'
          ctx.fillRect(0, 0, W, H)

          ctx.fillStyle = '#292524'
          ctx.fillRect(0, 0, W, 6)

          ctx.fillStyle = '#292524'
          ctx.font = 'bold 36px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText('潘天寿教你构图', W / 2, 70)

          ctx.fillStyle = '#a8a29e'
          ctx.font = '20px sans-serif'
          ctx.fillText('AI 中国画构图分析', W / 2, 104)

          ctx.strokeStyle = '#e7e5e4'; ctx.lineWidth = 1
          ctx.beginPath(); ctx.moveTo(80, 130); ctx.lineTo(W - 80, 130); ctx.stroke()

          var ringCx = W / 2, ringCy = 220, ringR = 70
          ctx.beginPath(); ctx.arc(ringCx, ringCy, ringR, 0, Math.PI * 2)
          ctx.strokeStyle = '#292524'; ctx.lineWidth = 6; ctx.stroke()

          ctx.fillStyle = '#292524'; ctx.font = 'bold 56px sans-serif'
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
          ctx.fillText(String(totalScore || '—'), ringCx, ringCy - 4)
          ctx.fillStyle = '#78716c'; ctx.font = '16px sans-serif'
          ctx.fillText('分', ringCx, ringCy + 32); ctx.textBaseline = 'alphabetic'
          ctx.fillStyle = '#78716c'; ctx.font = '15px sans-serif'
          ctx.fillText('综合构图评分', ringCx, ringCy + ringR + 30)

          var curY = ringCy + ringR + 70
          ctx.strokeStyle = '#e7e5e4'
          ctx.beginPath(); ctx.moveTo(80, curY); ctx.lineTo(W - 80, curY); ctx.stroke()
          curY += 24

          if (loaded.radar && radarDH > 0) {
            ctx.fillStyle = '#78716c'; ctx.font = '14px sans-serif'; ctx.textAlign = 'left'
            ctx.fillText('七维雷达图', padding, curY); curY += 22
            var rs = Math.min(1, textW / loaded.radar.width)
            ctx.drawImage(loaded.radar, (W - loaded.radar.width * rs) / 2, curY, loaded.radar.width * rs, loaded.radar.height * rs)
            curY += loaded.radar.height * rs + 16
          }

          if (loaded.qczh && qczhDH > 0) {
            ctx.fillStyle = '#78716c'; ctx.font = '14px sans-serif'; ctx.textAlign = 'left'
            ctx.fillText('起承转合 · 曲线分析', padding, curY); curY += 22
            var qs = Math.min(1, textW / loaded.qczh.width)
            ctx.drawImage(loaded.qczh, (W - loaded.qczh.width * qs) / 2, curY, loaded.qczh.width * qs, loaded.qczh.height * qs)
            curY += loaded.qczh.height * qs + 16
          }

          if (imgAreaH > 0) {
            curY += 4
            ctx.strokeStyle = '#e7e5e4'
            ctx.beginPath(); ctx.moveTo(80, curY); ctx.lineTo(W - 80, curY); ctx.stroke()
            curY += 20
          }

          for (var i = 0; i < textLines.length; i++) {
            var tl = textLines[i]
            if (curY + tl.h > H - footerH) break
            ctx.fillStyle = tl.color; ctx.font = tl.font
            ctx.textAlign = tl.center ? 'center' : 'left'
            ctx.fillText(tl.text, tl.center ? W / 2 : padding, curY + tl.h - 6)
            curY += tl.h
          }

          var footerY = H - 50
          ctx.strokeStyle = '#e7e5e4'
          ctx.beginPath(); ctx.moveTo(80, footerY - 16); ctx.lineTo(W - 80, footerY - 16); ctx.stroke()
          ctx.fillStyle = '#a8a29e'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center'
          ctx.fillText('分析由 AI 生成 · 仅供学习参考', W / 2, footerY + 10)

          wx.canvasToTempFilePath({
            canvas: canvas,
            success: function (res) {
              wx.hideLoading()
              wx.saveImageToPhotosAlbum({
                filePath: res.tempFilePath,
                success: function () { wx.showToast({ title: '已保存到相册', icon: 'success' }) },
                fail: function () { wx.previewImage({ urls: [res.tempFilePath] }) }
              })
            },
            fail: function () { wx.hideLoading(); wx.showToast({ title: '生成失败', icon: 'none' }) }
          })
        }

        if (needCount === 0) { doDraw(); return }

        for (var i = 0; i < imgsToLoad.length; i++) {
          ;(function (key, src) {
            var img = canvas.createImage()
            img.onload = function () { loaded[key] = img; doDraw() }
            img.onerror = function () { doDraw() }
            img.src = src
          })(imgsToLoad[i].key, imgsToLoad[i].src)
        }
      })
    }

    if (hasRadar) {
      var rQuery = wx.createSelectorQuery()
      rQuery.select('#radarCanvas').fields({ node: true }).exec(function (rres) {
        if (rres && rres[0] && rres[0].node) {
          wx.canvasToTempFilePath({ canvas: rres[0].node, success: function (tmp) { begin(tmp.tempFilePath) }, fail: function () { begin('') } })
        } else { begin('') }
      })
    } else { begin('') }
  },

  _buildShareLines: function (ctx, rawText, maxChars, textW, titleFont, bodyFont, smallFont, titleLineH, lineH) {
    var result = []
    var text = rawText.slice(0, maxChars)
    var lines = text.split('\n')
    var foundContent = false
    var tableMode = false

    for (var i = 0; i < lines.length; i++) {
      var t = lines[i].trim()
      if (!t) {
        if (foundContent) result.push({ text: ' ', h: 10, font: bodyFont, color: '#faf8f3' })
        result.push({ text: '', h: 8, font: bodyFont, color: '#444' })
        continue
      }

      if (t.indexOf('|') === 0) {
        var clean = t.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\|/g, '  ').trim()
        if (clean.length > 2) {
          result.push({ text: clean, h: lineH, font: smallFont, color: '#78716c' })
        }
        continue
      }

      if (t.indexOf('---') === 0) {
        result.push({ text: '— — — — —', h: titleLineH, font: smallFont, color: '#d6d3d1', center: true })
        continue
      }

      // Heading
      if (t.indexOf('## ') === 0) {
        foundContent = true
        var hd = t.slice(3).replace(/\*\*(.+?)\*\*/g, '$1')
        result.push({ text: hd, h: titleLineH, font: titleFont, color: '#1c1917' })
        continue
      }
      if (t.indexOf('### ') === 0) {
        foundContent = true
        var hd = t.slice(4).replace(/\*\*(.+?)\*\*/g, '$1')
        result.push({ text: hd, h: lineH + 4, font: 'bold 17px sans-serif', color: '#44403c' })
        continue
      }

      // List
      var isLi = t.indexOf('- ') === 0 || t.indexOf('* ') === 0
      var isOli = /^\d+\.\s/.test(t)
      var prefix = ''
      if (isLi) { prefix = '— '; t = t.slice(2) }
      if (isOli) { prefix = t.replace(/^(\d+)\.\s.*/, '$1. ') + ' '; t = t.replace(/^\d+\.\s/, '') }

      t = prefix + t.replace(/\*\*(.+?)\*\*/g, '$1')
      foundContent = true

      var wrapped = this._wrapLines(ctx, t, textW, bodyFont)
      for (var w = 0; w < wrapped.length; w++) {
        result.push({ text: wrapped[w], h: lineH, font: isLi || isOli ? smallFont : bodyFont, color: '#44403c' })
      }
    }

    // Ensure minimum text block
    if (result.filter(function(l) { return l.text && l.text.length > 2 }).length < 3) {
      result = [{ text: 'AI 已完成对该中国画作品的构图分析。', h: lineH, font: bodyFont, color: '#44403c' }]
    }

    return result
  },

  _wrapLines: function (ctx, text, maxWidth, font) {
    ctx.font = font
    var lines = []
    var chars = text.split('')
    var line = ''
    for (var i = 0; i < chars.length; i++) {
      var test = line + chars[i]
      if (ctx.measureText(test).width > maxWidth) {
        lines.push(line); line = chars[i]
      } else {
        line = test
      }
    }
    if (line) lines.push(line)
    return lines
  },

  _startTimeout: function () {
    var that = this
    this._timeoutTimer = setTimeout(function () {
      that._stopPolling()
      if (that.data.state === 'analyzing') { that.setData({ state: 'error', errorMsg: '分析超时（超过5分钟），请重试' }) }
    }, this.TIMEOUT_MS)
  },

  _stopPolling: function () {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null }
    if (this._timeoutTimer) { clearTimeout(this._timeoutTimer); this._timeoutTimer = null }
  },

  resetPage: function () {
    this._qczhRes = null
    this._reportText = ''
    this._stopPolling()
    this.setData({
      state: 'idle', imagePath: '', loading: false, progress: 0,
      stageText: '', etaSeconds: null, totalScore: null,
      llmHtml: '', radarDims: [],
      qczhImage: '', pathType: '', qczhLoading: false,
      errorMsg: '',
      showDemoBtn: true, hasRadar: false, hasOverlay: false, hasQczh: false
    })
  },

  onUnload: function () { this._stopPolling() }
})

function _buildRadarDims(report) {
  var dims = (report && report.dimensions) ? report.dimensions : []
  if (!dims.length) return []
  var colors = ['#b0886a', '#8daa94', '#8b9bb4', '#9e8c7a', '#8c9aad', '#b0a28a', '#7d9b8a']
  var shortNames = { '开合之势': '开合', '虚实相生': '虚实', '疏密有致': '疏密', '辅助元素': '辅助', '均衡节奏': '均衡', '穿插结构': '穿插', '边角空间': '边角' }
  return dims.map(function (d, i) {
    var maxVal = (typeof d.max === 'number' && !isNaN(d.max) && d.max > 0) ? d.max : 20
    var score = (typeof d.score === 'number' && !isNaN(d.score)) ? d.score : 0
    var pct = Math.round(score / maxVal * 100)
    if (isNaN(pct)) pct = 0
    return { label: shortNames[d.name] || d.name, score: score, max: maxVal, pct: pct, color: colors[i % colors.length] }
  })
}

function _drawRadar(page) {
  var dims = page.data.radarDims
  if (!dims.length) return
  var query = wx.createSelectorQuery()
  query.select('#radarCanvas').fields({ node: true, size: true }).exec(function (res) { _onRadarCanvasReady(dims, res) })
}

function _onRadarCanvasReady(dims, res) {
  if (!res || !res[0] || !res[0].node) return
  var canvas = res[0].node
  var ctx = canvas.getContext('2d')
  var dpr = wx.getWindowInfo().pixelRatio
  var W = res[0].width, H = res[0].height
  canvas.width = W * dpr; canvas.height = H * dpr; ctx.scale(dpr, dpr)

  var cx = W / 2, cy = H / 2, n = dims.length
  var step = Math.PI * 2 / n, start = -Math.PI / 2, maxR = Math.min(cx, cy) - 40
  ctx.clearRect(0, 0, W, H)

  for (var l = 1; l <= 4; l++) {
    var r = (maxR / 4) * l; ctx.beginPath()
    for (var i = 0; i < n; i++) { var a = start + step * i; var x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y) }
    ctx.closePath(); ctx.strokeStyle = '#e7e5e4'; ctx.lineWidth = 1; ctx.stroke()
  }
  for (var i = 0; i < n; i++) { var a = start + step * i; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a) * maxR, cy + Math.sin(a) * maxR); ctx.strokeStyle = '#f0ede8'; ctx.stroke() }

  ctx.beginPath()
  for (var i = 0; i < n; i++) { var pct = dims[i].pct / 100; var r = maxR * pct; var a = start + step * i; var x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y) }
  ctx.closePath(); ctx.fillStyle = 'rgba(41,37,36,0.12)'; ctx.fill(); ctx.strokeStyle = '#292524'; ctx.lineWidth = 2; ctx.stroke()

  for (var i = 0; i < n; i++) { var pct = dims[i].pct / 100; var r = maxR * pct; var a = start + step * i; var x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r; ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fillStyle = dims[i].color; ctx.fill() }

  ctx.font = '12px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; var lr = maxR + 28
  for (var i = 0; i < n; i++) { var a = start + step * i; var lx = cx + Math.cos(a) * lr, ly = cy + Math.sin(a) * lr; if (lx < 50) lx = 50; if (lx > W - 50) lx = W - 50; if (ly < 30) ly = 30; if (ly > H - 20) ly = H - 20; ctx.fillStyle = '#57534e'; ctx.fillText(dims[i].label, lx, ly); ctx.fillStyle = '#a8a29e'; ctx.font = '10px sans-serif'; ctx.fillText(dims[i].score + '/' + dims[i].max, lx, ly + 16) }
}
