/**
 * 题跋详情页共享逻辑 composable
 * 被 TibaAnalysis.vue（首页）和 TibaDetailPage.vue（独立详情页）共用
 */

import { ref, reactive, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tibaApi } from '../api'
import { getSharedAnalyticsData, setSharedAnalyticsData } from '../tiba/sharedCache'
import { siteConfig } from '../config'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

const MAX_UPLOADED = 50

// ── 本地缓存配置 ──
const CACHE_KEY = 'tiba_detail_cache'
const CACHE_EXPIRY = 30 * 60 * 1000  // 30分钟过期
const MAX_CACHE_ITEMS = 10  // 最多缓存10个作品

// 本地缓存工具函数
const detailCache = {
  get(id: string) {
    try {
      const cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}')
      const item = cache[id]
      if (item && Date.now() - item.timestamp < CACHE_EXPIRY) {
        return item.data
      }
      // 清理过期项
      if (item) delete cache[id]
      localStorage.setItem(CACHE_KEY, JSON.stringify(cache))
    } catch {}
    return null
  },
  set(id: string, data: any) {
    try {
      const cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}')
      // 保持缓存数量在限制内
      const keys = Object.keys(cache)
      if (keys.length >= MAX_CACHE_ITEMS) {
        // 删除最早过期的项
        const sorted = keys.sort((a, b) => (cache[a].timestamp || 0) - (cache[b].timestamp || 0))
        sorted.slice(0, keys.length - MAX_CACHE_ITEMS + 1).forEach(k => delete cache[k])
      }
      cache[id] = { data, timestamp: Date.now() }
      localStorage.setItem(CACHE_KEY, JSON.stringify(cache))
    } catch {}
  },
  clear() {
    try {
      localStorage.removeItem(CACHE_KEY)
    } catch {}
  }
}

export function useTibaDetail(router: Router, route: RouteLocationNormalizedLoaded) {
  // ── 状态 ──
  const uploadedImages = ref([])
  const currentImage = ref(null)
  const canvasRef = ref(null)
  let canvas = null
  let ctx = null

  const currentArtist = ref('李鱓')
  const fullItemList = ref([])

  // 分析状态
  const analyzeStatus = ref('pending')
  const analyzeProgress = ref(0)
  const analyzingStep = ref('准备分析...')
  const areaStats = reactive({
    inscriptionPercent: 0,
    paintingPercent: 0,
    blankPercent: 0,
  })
  const analysisNote = ref('')
  const positionAnalysis = ref(null)
  let regions = { inscription_regions: [], painting_regions: [], blank_regions: [] }

  // 预览
  const imagePreviewVisible = ref(false)
  const currentPreviewImage = ref('')

  // ── 计算属性 ──
  const prevImage = computed(() => {
    if (!currentImage.value) return null
    const found = _findItemIndex(currentImage.value.id)
    if (found && found.idx > 0) return found.list[found.idx - 1]
    const pid = currentImage.value.prev_image_id
    return pid ? { id: pid, image_id: pid } : null
  })

  const nextImage = computed(() => {
    if (!currentImage.value) return null
    const found = _findItemIndex(currentImage.value.id)
    if (found && found.idx < found.list.length - 1) return found.list[found.idx + 1]
    const nid = currentImage.value.next_image_id
    return nid ? { id: nid, image_id: nid } : null
  })

  // ── 函数 ──
  function pushUploaded(img) {
    uploadedImages.value.push(img)
    if (uploadedImages.value.length > MAX_UPLOADED) {
      uploadedImages.value.splice(0, uploadedImages.value.length - MAX_UPLOADED)
    }
  }

  async function loadFullItemList(force = false) {
    const cached = getSharedAnalyticsData()
    if (cached && !force) {
      fullItemList.value = cached
      return
    }
    try {
      const res = await tibaApi.getAllResults(0, 2000, currentArtist.value || undefined)
      if (res.success) {
        const data = (res.data || []).map(item => ({
          ...item,
          inscriptionPercent: item.inscription_percent,
          paintingPercent: item.painting_percent,
          blankPercent: item.blank_percent,
          thumbnailUrl: item.thumbnail_url,
        }))
        setSharedAnalyticsData(data)
        fullItemList.value = data
      }
    } catch (e) {
      console.error('loadFullItemList failed', e)
    }
  }

  function _findItemIndex(id) {
    // 在 fullItemList 中查找（独立详情页用）
    let idx = fullItemList.value.findIndex(item => item.id === id)
    if (idx >= 0) return { list: fullItemList.value, idx, isFullList: true }
    return null
  }

  async function selectImage(img) {
    if (!fullItemList.value || fullItemList.value.length === 0) {
      await loadFullItemList()
    }
    currentImage.value = img
    if (img.artist) {
      currentArtist.value = img.artist
    }

    const artworkTitle = img.title || img.name || '未命名作品'
    document.title = `${artworkTitle} - 题跋分析 - ${document.title.split(' - ').pop() || siteConfig?.title || '墨林百科'}`

    if (img.id < 0) {
      analyzeStatus.value = 'analyzed'
      areaStats.inscriptionPercent = img.inscriptionPercent || 0
      areaStats.paintingPercent = img.paintingPercent || 0
      areaStats.blankPercent = img.blankPercent || 0
      regions = (typeof img.regions === 'string' ? JSON.parse(img.regions) : img.regions) ||
        { inscription_regions: [], painting_regions: [], blank_regions: [] }
      analysisNote.value = img.analysisNote || ''
      positionAnalysis.value = img.positionAnalysis || {
        layout_type: '传统布局', position: '右上方', coverage_ratio: 0.2, overlap_ratio: 0.05, layout_description: '模拟数据'
      }
    } else {
      analyzeStatus.value = img.regions ? 'analyzed' : 'pending'
      if (img.regions) {
        areaStats.inscriptionPercent = img.inscriptionPercent || 0
        areaStats.paintingPercent = img.paintingPercent || 0
        areaStats.blankPercent = img.blankPercent || 0
        regions = typeof img.regions === 'string' ? JSON.parse(img.regions) : img.regions
        analysisNote.value = img.analysisNote || ''
        if (img.positionAnalysis) {
          positionAnalysis.value = img.positionAnalysis
        } else if (img.regions && img.width && img.height) {
          positionAnalysis.value = calculatePositionAnalysisByRules(img.regions, img.width, img.height)
        }
      } else {
        areaStats.inscriptionPercent = 0
        areaStats.paintingPercent = 0
        areaStats.blankPercent = 0
        regions = { inscription_regions: [], painting_regions: [], blank_regions: [] }
        analysisNote.value = ''
        positionAnalysis.value = null
      }
    }
  }

  async function loadHistoryItem(row) {
    try {
      if (row.id < 0) {
        const historyImage = {
          ...row,
          name: row.title || '模拟数据',
          url: row.thumbnailUrl || row.url,
          width: 800, height: 600,
          blankPercent: 100 - (row.inscriptionPercent || 0) - (row.paintingPercent || 0),
          annotatedImageUrl: row.thumbnailUrl || row.url,
          analysisNote: `这是一幅模拟画作：${row.title || '未命名'}`,
        }
        const exists = uploadedImages.value.find(img => img.id === historyImage.id)
        if (!exists) pushUploaded(historyImage)
        await selectImage(historyImage)
        window.scrollTo({ top: 0, behavior: 'smooth' })
        ElMessage.success('已加载模拟数据')
      } else {
        const recordId = row.image_id || row.id
        const response = await tibaApi.getAnalysisResult(recordId)
        if (response.success) {
          const data = response.data
          const analysisNoteText = data.analysis_note || ''
          const inscriptionContent = data.inscription_content || extractInscriptionContent(analysisNoteText)
          const historyImage = {
            id: data.id, image_id: data.image_id, owner_id: data.owner_id, library_id: data.library_id,
            name: data.name || '历史记录', url: data.url,
            thumbnailUrl: data.thumbnail_url || data.url, width: data.width, height: data.height,
            title: data.title, artist: data.artist, year: data.year, period: data.period,
            inscriptionPercent: data.inscription_percent, paintingPercent: data.painting_percent,
            blankPercent: data.blank_percent, regions: parseRegions(data.regions),
            positionAnalysis: data.position_analysis,
            annotatedImageUrl: data.annotated_image_url, isManualAnnotated: data.is_manual_annotated,
            analysisNote: analysisNoteText, inscriptionContent, sealContent: data.seal_content || '',
            inscriptionModern: data.inscription_modern || '', inscriptionEn: data.inscription_en || '',
            contentAnalysis: data.content_analysis || null, dzi_url: data.dzi_url,
            artwork_width_cm: data.artwork_width_cm, artwork_height_cm: data.artwork_height_cm,
            tags: data.tags, album_name: data.album_name, album_index: data.album_index,
            page_role: data.page_role, period_phase: data.period_phase,
            material_tags: data.material_tags, computed_tags: data.computed_tags,
            prev_image_id: data.prev_image_id, next_image_id: data.next_image_id,
          }
          const exists = uploadedImages.value.find(img => img.id === historyImage.id)
          if (!exists) pushUploaded(historyImage)
          await selectImage(historyImage)
          window.scrollTo({ top: 0, behavior: 'smooth' })
        }
      }
    } catch (error) {
      console.error('loadHistoryItem failed', error)
      ElMessage.error('加载作品失败')
    }
  }

  async function navigateToImage(image) {
    if (!image) return
    if (image._placeholder) {
      return
    }
    await loadHistoryItem(image)
  }

  function openImagePreview(imageUrl, dziUrl) {
    currentPreviewImage.value = dziUrl || imageUrl
    imagePreviewVisible.value = true
  }

  async function autoAnalyze() {
    if (!currentImage.value || analyzeStatus.value === 'analyzing') return
    analyzeStatus.value = 'analyzing'
    analyzeProgress.value = 0
    analyzingStep.value = '正在上传图片...'
    const progressInterval = startAnalyzeProgress()
    try {
      const startResult = await tibaApi.autoAnalyze(currentImage.value.id)
      if (!startResult?.success) throw new Error(startResult?.detail || startResult?.error || '分析失败')
      analyzingStep.value = '已加入队列，等待分析...'
      const startAt = Date.now()
      let pollInterval = 3000
      while (true) {
        const statusResult = await tibaApi.getAnalyzeStatus(currentImage.value.id)
        if (!statusResult?.success) throw new Error(statusResult?.detail || '获取状态失败')
        const status = statusResult.data?.status
        if (status === 'analyzed') break
        if (status === 'error') throw new Error(statusResult.data?.analysis_note || '分析失败')
        if (status === 'queued') {
          try {
            const qi = await tibaApi.getQueueInfo(currentImage.value.id)
            const pos = qi?.data?.position
            const est = qi?.data?.estimated_wait_seconds
            analyzingStep.value = pos
              ? `排队中：前面还有${pos - 1}个${est ? `，预计约${Math.max(1, Math.ceil(est / 60))}分钟` : ''}`
              : '排队中...'
          } catch { analyzingStep.value = '排队中...' }
        } else {
          analyzingStep.value = '分析中...'
        }
        await new Promise(r => setTimeout(r, pollInterval))
        pollInterval = Math.min(pollInterval * 1.5, 15000)
      }
      clearInterval(progressInterval)
      const result = await tibaApi.getAnalysisResult(currentImage.value.id)
      if (result.success) {
        const data = result.data
        currentImage.value.inscriptionPercent = data.inscription_percent
        currentImage.value.paintingPercent = data.painting_percent
        currentImage.value.blankPercent = data.blank_percent
        currentImage.value.regions = parseRegions(data.regions)
        currentImage.value.annotatedImageUrl = data.annotated_image_url
        currentImage.value.positionAnalysis = data.position_analysis
        currentImage.value.analysisNote = data.analysis_note || ''
        currentImage.value.inscriptionContent = data.inscription_content || extractInscriptionContent(data.analysis_note || '')
        areaStats.inscriptionPercent = data.inscription_percent || 0
        areaStats.paintingPercent = data.painting_percent || 0
        areaStats.blankPercent = data.blank_percent || 0
        analysisNote.value = data.analysis_note || ''
        positionAnalysis.value = data.position_analysis || null
        regions = parseRegions(data.regions)
        analyzeStatus.value = 'analyzed'
        ElMessage.success('分析完成！')
      }
    } catch (error) {
      console.error('autoAnalyze failed', error)
      analyzeStatus.value = 'error'
      ElMessage.error(error.message || '分析失败')
    } finally {
      clearInterval(progressInterval)
    }
  }

  function startAnalyzeProgress() {
    analyzeProgress.value = 0
    return setInterval(() => {
      if (analyzeProgress.value < 90) analyzeProgress.value += Math.random() * 5
    }, 2000)
  }

  async function loadAndSelectImage(imageId) {
    try {
      const response = await tibaApi.getAnalysisResult(imageId)
      if (response.success) {
        const data = response.data
        const analysisNoteText = data.analysis_note || ''
        const historyImage = {
          id: data.id, image_id: data.image_id, name: data.name || '', url: data.url,
          thumbnailUrl: data.thumbnail_url || data.url,
          width: data.width, height: data.height, title: data.title, artist: data.artist,
          year: data.year, tags: data.tags,
          regions: parseRegions(data.regions),
          positionAnalysis: data.position_analysis,
          analysisNote: analysisNoteText,
          album_name: data.album_name, period_phase: data.period_phase,
          computed_tags: data.computed_tags,
          prev_image_id: data.prev_image_id, next_image_id: data.next_image_id,
        }
        await selectImage(historyImage)
      }
    } catch (e) {
      console.error('loadAndSelectImage failed', e)
    }
  }

  function parseTags(tags) {
    if (!tags) return []
    if (Array.isArray(tags)) return tags
    try { return JSON.parse(tags) } catch { return [] }
  }

  function getItemAllTags(item) {
    const auto = item.computed_tags || []
    const manual = parseTags(item.tags)
    const result = [...auto]
    for (const t of manual) {
      if (!result.includes(t)) result.push(t)
    }
    return result
  }

  function getDetailAllTags() {
    if (!currentImage.value) return []
    return getItemAllTags(currentImage.value)
  }

  function filterByTag(tag) {
    window.open(`${window.location.origin}/#/tiba/list?tag=${encodeURIComponent(tag)}`, '_blank')
  }

  function handleResize() { }

  return {
    // 状态
    uploadedImages, currentImage, canvasRef, canvas, ctx,
    currentArtist, fullItemList,
    analyzeStatus, analyzeProgress, analyzingStep, areaStats, analysisNote, positionAnalysis,
    imagePreviewVisible, currentPreviewImage,
    prevImage, nextImage,

    // 函数
    pushUploaded, loadFullItemList, selectImage, loadHistoryItem,
    navigateToImage, autoAnalyze, openImagePreview,
    parseTags, getItemAllTags, getDetailAllTags, filterByTag,
    handleResize, loadAndSelectImage,
  }
}

// ── 工具函数 ──

function extractInscriptionContent(text) {
  if (!text) return ''
  const lines = text.split('\n')
  let inInscription = false
  const result = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.includes('题跋内容') || trimmed.includes('题跋原文')) { inInscription = true; continue }
    if (inInscription) {
      if (trimmed === '' && result.length > 0) break
      if (trimmed) result.push(trimmed.trim())
    }
  }
  return result.join('\n') || text.slice(0, 500)
}

function parseRegions(data) {
  if (!data) return { inscription_regions: [], painting_regions: [], blank_regions: [] }
  if (typeof data === 'string') {
    try { return JSON.parse(data) } catch { return { inscription_regions: [], painting_regions: [], blank_regions: [] } }
  }
  return data
}

function calculatePositionAnalysisByRules(regions, width, height) {
  if (!regions || !width || !height) return null
  let hasInscription = false
  const inscriptionRegions = regions.inscription_regions || []
  for (const r of inscriptionRegions) {
    if (r.points && r.points.length > 0) { hasInscription = true; break }
    if (r.x1 !== undefined) { hasInscription = true; break }
  }
  if (!hasInscription) return null

  let centerY = 0, count = 0
  for (const r of inscriptionRegions) {
    if (r.points && r.points.length > 0) {
      for (const p of r.points) { centerY += p.y; count++ }
    } else if (r.y1 !== undefined) { centerY += (r.y1 + r.y2) / 2; count++ }
  }
  centerY = count > 0 ? centerY / count : 0
  const ratio = centerY / height
  const layoutType = ratio < 0.33 ? '上方式布局' : ratio < 0.66 ? '中央布局' : '下方式布局'

  let coverage = 0, coverageCount = 0
  for (const r of inscriptionRegions) {
    if (r.points && r.points.length > 0) {
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const p of r.points) {
        minX = Math.min(minX, p.x); minY = Math.min(minY, p.y)
        maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y)
      }
      coverage += ((maxX - minX) * (maxY - minY)) / (width * height)
      coverageCount++
    } else if (r.x1 !== undefined) {
      coverage += ((r.x2 - r.x1) * (r.y2 - r.y1)) / (width * height)
      coverageCount++
    }
  }

  return {
    layout_type: layoutType,
    coverage_ratio: Math.round((coverage / Math.max(1, coverageCount)) * 100) / 100,
    layout_description: `题跋在画面${ratio < 0.33 ? '上方' : ratio < 0.66 ? '中央' : '下方'}，覆盖约 ${Math.round(coverage * 100)}% 画面`,
  }
}
