<template>
  <div class="tubi-analysis tubi-page">
    <!-- 页面标题 -->
    <div class="tubi-header" v-if="!currentImage">
      <h1>中国画题跋空间分析</h1>
      <p class="sub">上传国画图片，AI 自动识别画作中的题跋、绘画、留白区域</p>
      <div class="header-ornament">
        <span class="ornament-line"></span>
        <span class="ornament-dot">◇</span>
        <span class="ornament-line"></span>
      </div>
    </div>

    <!-- 初始加载状态：防止直接访问详情页时闪现首页框架 -->
    <div v-if="initialLoading" class="initial-loading-overlay">
      <div class="initial-loading-content">
        <el-icon class="loading-icon" :size="48"><Loading /></el-icon>
        <p class="loading-text">正在加载作品...</p>
      </div>
    </div>

    <!-- 首页概览视图 -->
    <TubiHome
      v-if="!currentImage &amp;&amp; !initialLoading"
      ref="tubiHomeRef"
      :history-list="historyList"
      :filter-tag="filterTag"
      :artist-filter="currentArtist"
      :has-more="historyHasMore"
      :history-loading="historyLoading"
      :refresh-key="refreshAnalyticsKey"
      @item-click="loadHistoryItem"
      @edit="editImageInfo"
      @delete="deleteImage"
      @search="handleSearch"
      @load-more="loadMoreGallery"
      @clear-tag-filter="clearTagFilter"
      @go-list="navigateToRanking"
      @more="navigateToRanking"
      @artist-change="onArtistChange"
      @trend-click="(id) =&gt; loadHistoryItem(historyList.find(h =&gt; h.id === id))"
    />

    <!-- 详情页视图 -->
    <TubiDetail
      v-if="currentImage"
      ref="tubiDetailRef"
      :current-image="currentImage"
      :analysis="analysisState"
      :analyze-status="analyzeStatus"
      :analyze-progress="analyzeProgress"
      :analyzing-step="analyzingStep"
      :area-stats="areaStats"
      :analysis-note="analysisNote"
      :position-analysis="positionAnalysis"
      :prev-image="prevImage"
      :next-image="nextImage"
      :album-navigation="albumNavigation"
      :history-list="historyList"
      :get-detail-all-tags="getDetailAllTags"
      @back="backToHome"
      @edit-current="editCurrentImage"
      @auto-analyze="autoAnalyze"
      @navigate="navigateToImage"
      @navigate-album="navigateToAlbumItem"
      @open-annotator="openAnnotator"
      @filter-by-tag="filterByTag"
      @history-item-click="loadHistoryItem"
    />


    <!-- 搜索结果弹窗 -->
    <TubiSearchDialog
      v-model="searchDialogVisible"
      :keyword="searchKeyword"
      :results="searchResults"
      :loading="searchLoading"
      @view="loadSearchResultItem"
      @edit="editHistoryItem"
      @delete="deleteHistoryItem"
      @preview="previewHistoryImage"
    />

    <!-- 图片预览对话框 -->
    <TubiImagePreviewDialog
      v-model="previewDialogVisible"
      :image-url="previewImageUrl"
    />

    <!-- 原图放大查看对话框 -->
    <TubiImageZoomDialog
      v-model="imagePreviewVisible"
      :image-url="currentPreviewImage"
    />

    <!-- 编辑历史记录对话框 -->
    <TubiEditDialog
      ref="editDialogRef"
      @saved="onEditSaved"
      @deleted="onEditDeleted"
      @replaced="onEditReplaced"
    />





  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import {
  Picture, Loading, Edit, HomeFilled, Clock, Search, ArrowLeft, ArrowRight, ArrowDown, Collection
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { tubiApi } from '../api'
import { getSharedAnalyticsData, setSharedAnalyticsData } from '../tubi/sharedCache'
import { ARTISTS } from '../tubi/constants'
import {
  calculateAge,
  calculateYear,
  getDisplayAge,
  formatDate
} from '../tubi/utils'
import ArtistStatsCard from '../tubi/ArtistStatsCard.vue'
import TubiRankingCard from '../components/tubi/TubiRankingCard.vue'
import TubiGallery from '../components/tubi/TubiGallery.vue'
import TubiEditDialog from '../components/tubi/TubiEditDialog.vue'
import TubiComparison from '../components/tubi/TubiComparison.vue'
import TubiSearchDialog from '../components/tubi/TubiSearchDialog.vue'
import TubiImagePreviewDialog from '../components/tubi/TubiImagePreviewDialog.vue'
import TubiImageZoomDialog from '../components/tubi/TubiImageZoomDialog.vue'
import TubiHome from './TubiHome.vue'
import TubiDetail from './TubiDetail.vue'

const router = useRouter()
const route = useRoute()
const uploadedImages = ref([])
const currentImage = ref(null)

// 初始加载状态：防止直接访问详情页时闪现首页框架
const initialLoading = ref(false)

const canvasRef = ref(null)
const editDialogRef = ref(null)
const tubiHomeRef = ref(null)
const tubiDetailRef = ref(null)
let canvas = null
let ctx = null

// 当前选中的画家（先给默认值，再通过 watch 响应 URL 参数变化）
const currentArtist = ref('李鱓')

// 用 watch 响应 route.query.artist 变化（初始加载由 onMounted 处理）
watch(
  () => route.query.artist,
  (newVal) => {
    if (newVal && newVal !== currentArtist.value) {
      currentArtist.value = newVal
      // 同步到 URL（如果切回默认画家，去掉 artist 参数保持 URL 整洁）
      const query = { ...route.query }
      if (newVal === '李鱓') {
        delete query.artist
      } else {
        query.artist = newVal
      }
      router.replace({
        name: route.name,
        params: route.params,
        query
      })
      // 重新加载历史列表（服务端过滤）
      historyPage.value = 1
      historyHasMore.value = true
      loadHistory(1)
    }
  }
)

// 历史记录相关
const refreshAnalyticsKey = ref(0) // 递增触发 TubiHome 刷新分析数据
const historyList = ref([])
const historyPageSize = ref(16)
const historyPage = ref(1)
const historyHasMore = ref(true)

// 全量作品列表（用于 prev/next 导航）
// 使用 sharedCache 与 TubiHome 共享数据，避免重复 API 请求
const fullItemList = ref([])
async function loadFullItemList(force = false) {
  console.log('loadFullItemList start, cached=', !!getSharedAnalyticsData())
  const cached = getSharedAnalyticsData()
  if (cached && !force) {
    fullItemList.value = cached
    console.log('loadFullItemList from cache, items:', cached.length)
    return
  }
  try {
    const res = await tubiApi.getAllResults(0, 2000)
    if (res.success) {
      const data = res.data || []
      setSharedAnalyticsData(data)
      fullItemList.value = data
      console.log('loadFullItemList done, items:', data.length)
    }
  } catch (e) {
    console.error('加载全量作品列表失败', e)
  }
}

// 搜索相关
const searchKeyword = ref('')
const searchDialogVisible = ref(false)
const searchResults = ref([])
const searchLoading = ref(false)
const historyLoading = ref(false)
const previewDialogVisible = ref(false)
const previewImageUrl = ref('')

// 解析 tags 字段（JSON数组或字符串数组）
function parseTags(tags) {
  if (!tags) return []
  if (Array.isArray(tags)) return tags
  try {
    const parsed = JSON.parse(tags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// 合并 computed_tags 和手动 tags，按顺序展示
function getItemAllTags(item) {
  const auto = item.computed_tags || []
  const manual = parseTags(item.tags)
  // computed_tags 在前，手动 tags 去重追加在后
  const result = [...auto]
  for (const t of manual) {
    if (!result.includes(t)) result.push(t)
  }
  return result
}

// 作品详情页的标签（computed_tags + 手动 tags）
function getDetailAllTags() {
  if (!currentImage.value) return []
  return getItemAllTags(currentImage.value)
}

// 标签筛选
const filterTag = ref(null)

function filterByTag(tag) {
  // 新窗口打开 list 页面，通过 URL 参数传递标签
  window.open(`${window.location.origin}/#/tubi/list?tag=${encodeURIComponent(tag)}`, '_blank')
}

function clearTagFilter() {
  filterTag.value = null
}

function loadMoreGallery() {
  if (!historyHasMore.value || historyLoading.value) return
  loadHistory(historyPage.value + 1)
}

// 在 historyList 或 fullItemList 中查找作品索引
function _findItemIndex(id) {
  let idx = historyList.value.findIndex(item => item.id === id)
  if (idx >= 0) { console.log('_findItemIndex found in historyList at', idx); return { list: historyList.value, idx, isFullList: false } }
  idx = fullItemList.value.findIndex(item => item.id === id)
  if (idx >= 0) { console.log('_findItemIndex found in fullItemList at', idx, 'total items:', fullItemList.value.length); return { list: fullItemList.value, idx, isFullList: true } }
  console.log('_findItemIndex NOT FOUND, historyList:', historyList.value.length, 'fullItemList:', fullItemList.value.length)
  return null
}

// 上一幅和下一幅作品
const prevImage = computed(() => {
  if (!currentImage.value) return null
  const found = _findItemIndex(currentImage.value.id)
  if (!found || found.idx <= 0) return null
  return found.list[found.idx - 1]
})

const nextImage = computed(() => {
  if (!currentImage.value) return null
  const found = _findItemIndex(currentImage.value.id)
  if (!found) return null
  // 如果当前不是所在列表的最后一条，直接返回下一条
  if (found.idx < found.list.length - 1) {
    return found.list[found.idx + 1]
  }
  // 如果是最后一条但还有更多页（仅限 historyList），返回翻页占位符
  if (!found.isFullList && historyHasMore.value) {
    return { _placeholder: true, id: '__next_page__' }
  }
  return null
})

// 导航到指定作品
async function navigateToImage(image) {
  if (!image) return
  // 如果是翻页占位符，先加载下一页再导航
  if (image._placeholder && historyHasMore.value) {
    await loadHistory(historyPage.value + 1)
    // 加载后取新追加的第一条（即原最后一条的下一条）
    if (currentImage.value) {
      const idx = historyList.value.findIndex(item => item.id === currentImage.value.id)
      const next = historyList.value[idx + 1]
      if (next) { loadHistoryItem(next); return }
    }
    return
  }
  loadHistoryItem(image)
}



// 打开手动标注工具
function openAnnotator() {
  if (!currentImage.value?.id) return
  router.push(`/annotate/${currentImage.value.id}`)
}

// 原图放大预览
const imagePreviewVisible = ref(false)
const currentPreviewImage = ref('')

// 打开原图预览
const openImagePreview = (imageUrl) => {
  currentPreviewImage.value = imageUrl
  imagePreviewVisible.value = true
}

// 编辑当前图片
const editCurrentImage = () => {
  if (currentImage.value) {
    editDialogRef.value.open(currentImage.value)
  } else {
    ElMessage.warning('请先选择一幅画作')
  }
}

// 编辑弹窗事件处理
function onEditSaved({ id, updates }) {
  loadHistory()
  if (currentImage.value?.id === id) {
    currentImage.value.title = updates.title
    currentImage.value.artist = updates.artist
    currentImage.value.year = updates.year
    currentImage.value.age = updates.age
    currentImage.value.analysisNote = updates.analysisNote
    currentImage.value.inscriptionContent = updates.inscriptionContent
    currentImage.value.sealContent = updates.sealContent
    currentImage.value.inscriptionPercent = updates.inscriptionPercent
    currentImage.value.paintingPercent = updates.paintingPercent
    currentImage.value.blankPercent = updates.blankPercent
    analysisNote.value = updates.analysisNote
    areaStats.inscriptionPercent = updates.inscriptionPercent
    areaStats.paintingPercent = updates.paintingPercent
    areaStats.blankPercent = updates.blankPercent
    tubiDetailRef.value?.updatePieChart?.()
  }
}

function onEditDeleted(id) {
  const idx = historyList.value.findIndex(item => item.id === id)
  if (idx > -1) {
    historyList.value.splice(idx, 1)
  }
  const sessionIdx = uploadedImages.value.findIndex(img => img.id === id)
  if (sessionIdx > -1) {
    uploadedImages.value.splice(sessionIdx, 1)
  }
  if (currentImage.value?.id === id) {
    currentImage.value = null
    analyzeStatus.value = 'pending'
    if (route.params.id) {
      const query = (currentArtist.value && currentArtist.value !== '李鱓') 
        ? { artist: currentArtist.value } 
        : {}
      router.replace({ name: 'TubiAnalysis', query })
    }
  }
}

function onEditReplaced({ id, url, thumbnail_url }) {
  if (currentImage.value?.id === id) {
    currentImage.value.url = url
    currentImage.value.thumbnailUrl = thumbnail_url
    currentImage.value.annotatedImageUrl = null
  }
  loadHistory()
}

// 分析状态
const analyzeStatus = ref('pending')
const analyzeProgress = ref(0)
const analyzingStep = ref('准备分析...')

// 区域统计
const areaStats = reactive({
  inscriptionPercent: 0,
  paintingPercent: 0,
  blankPercent: 0
})

// 区域数据
let regions = {
  inscription_regions: [],
  painting_regions: [],
  blank_regions: []
}

// 视图切换
// 分析说明
const analysisNote = ref('')

// 题跋位置分析
const positionAnalysis = ref(null)

// 图表引用
const trendChartRef = ref(null)
const friendCircleChartRef = ref(null)
const artistStatsCardRef = ref(null)

// 翻译折叠状态
const translationExpanded = ref(false)
let trendChart = null
let friendCircleChart = null

// 趋势图数据
// 趋势图数据
const trendChartData = ref([])
const trendArtistFilter = ref('李鱓')
const trendStats = reactive({
  avgPercent: 0,
  maxPercent: 0,
  minPercent: 0
})

// 根据作者筛选的趋势图数据
const filteredTrendChartData = computed(() => {
  if (trendArtistFilter.value === 'all') {
    return trendChartData.value
  }
  return trendChartData.value.filter(item => item.artist === trendArtistFilter.value)
})

// 聚合 analysis 相关 state（用于 TubiDetail）
const analysisState = computed(() => ({
  status: analyzeStatus.value,
  progress: analyzeProgress.value,
  step: analyzingStep.value,
  areaStats: {
    inscriptionPercent: areaStats.inscriptionPercent,
    paintingPercent: areaStats.paintingPercent,
    blankPercent: areaStats.blankPercent
  },
  note: analysisNote.value,
  positionAnalysis: positionAnalysis.value
}))

// 艺术家统计数据
const artistStats = computed(() => {
  const total = historyList.value.length || 0
  const liShanData = historyList.value.filter(item => item.artist === '李鱓')
  const zhengXieData = historyList.value.filter(item => item.artist === '郑燮')

  const avg = (list, key) => {
    const nums = list.map(item => Number(item[key])).filter(n => Number.isFinite(n))
    if (nums.length === 0) return 0
    return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10
  }

  // 获取 form_types 数组（兼容 positionAnalysis 和 position_analysis）
  const getFormTypes = (item) => {
    return item?.positionAnalysis?.form_types || item?.position_analysis?.form_types || []
  }

  // 获取 overlap_ratio（兼容 positionAnalysis 和 position_analysis）
  const getOverlapRatio = (item) => {
    const ratio = item?.positionAnalysis?.overlap_ratio ?? item?.position_analysis?.overlap_ratio
    return Number.isFinite(ratio) ? ratio : 0
  }

  // 计算形式丰富度：平均每幅画匹配的类型数量
  const calcFormRichness = (list) => {
    const counts = list.map(item => {
      const formTypes = getFormTypes(item)
      return formTypes.filter(ft => ft.matched).length
    }).filter(n => n > 0)
    if (counts.length === 0) return 0
    return Math.round((counts.reduce((a, b) => a + b, 0) / counts.length) * 10) / 10
  }

  // 计算主导形式占比：最常出现的类型 / 总数
  const calcDominantFormPercent = (list) => {
    if (list.length === 0) return { name: '-', percent: 0 }
    // 统计每种类型出现的次数
    const typeCounts = {}
    list.forEach(item => {
      const formTypes = getFormTypes(item)
      formTypes.filter(ft => ft.matched).forEach(ft => {
        typeCounts[ft.name] = (typeCounts[ft.name] || 0) + 1
      })
    })
    // 找到出现次数最多的类型
    let maxCount = 0
    let dominantName = '-'
    Object.entries(typeCounts).forEach(([name, count]) => {
      if (count > maxCount) {
        maxCount = count
        dominantName = name
      }
    })
    const percent = list.length > 0 ? Math.round((maxCount / list.length) * 1000) / 10 : 0
    return { name: dominantName, percent }
  }

  // 计算题跋侵入度：平均重叠率
  const calcInvasionPercent = (list) => {
    const ratios = list.map(item => getOverlapRatio(item)).filter(r => r > 0)
    if (ratios.length === 0) return 0
    return Math.round((ratios.reduce((a, b) => a + b, 0) / ratios.length) * 1000) / 10
  }

  const build = (list) => {
    const count = list.length
    const countPercent = total > 0 ? (count / total) * 100 : 0
    const fmt = (n) => `${Number(n).toFixed(1).replace(/\.0$/, '')}%`
    const formRichness = calcFormRichness(list)
    const dominantForm = calcDominantFormPercent(list)
    const invasionPercent = calcInvasionPercent(list)

    return {
      count,
      countPercent,
      countDisplay: `${count}`,
      avgInscription: avg(list, 'inscriptionPercent'),
      avgPainting: avg(list, 'paintingPercent'),
      avgBlank: avg(list, 'blankPercent'),
      formRichness,
      formRichnessDisplay: `${formRichness} 种/幅`,
      dominantFormName: dominantForm.name,
      dominantFormPercent: dominantForm.percent,
      dominantFormDisplay: `${dominantForm.name} ${dominantForm.percent}%`,
      invasionPercent,
      invasionDisplay: fmt(invasionPercent)
    }
  }

  return {
    total,
    liShan: build(liShanData),
    zhengXie: build(zhengXieData)
  }
})



// 跳转到排行榜页面
function navigateToRanking() {
  router.push('/tubi/list')
}

// 趋势图作者筛选变化
function onTrendArtistChange() {
  updateTrendChart()
}

// 画家筛选变化（来自 TubiHome）
function onArtistChange(artist) {
  currentArtist.value = artist
  historyPage.value = 1
  historyHasMore.value = true
  // 重新加载历史记录（服务端过滤）
  loadHistory(1)
  // fullItemList 已经有全量缓存，不需要重新拉取
  // 更新 URL 参数，刷新后保持
  const query = { ...route.query, artist }
  // 如果切回默认画家（李鱓），可以去掉 artist 参数保持 URL 整洁
  if (artist === '李鱓') {
    delete query.artist
  }
  router.replace({
    name: route.name,
    params: route.params,
    query
  })
}

// 返回首页
function backToHome() {
  currentImage.value = null
  analyzeStatus.value = 'idle'
  analysisNote.value = ''
  positionAnalysis.value = null
  areaStats.value = {
    inscriptionPercent: 0,
    paintingPercent: 0,
    blankPercent: 0
  }
  // 返回列表页URL，保留 artist 参数
  if (route.params.id) {
    const query = currentArtist.value && currentArtist.value !== '李鱓' 
      ? { artist: currentArtist.value } 
      : {}
    router.replace({ name: 'TubiAnalysis', query })
  }
  // 清空图表（pieChart 在 TubiDetail 中管理，不在本作用域）
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  
  // 返回首页后重新更新数据，并同步当前画家筛选
  nextTick(() => {
    tubiHomeRef.value?.setArtistFilter?.(currentArtist.value)
    updateTrendChart()
    artistStatsCardRef.value?.refresh() // 刷新统计数据
  })
  // 重新加载历史列表（保持当前画家筛选）
  historyPage.value = 1
  historyHasMore.value = true
  loadHistory(1)
}

// ============ 上传回调 ============


// ============ 后台轮询：检测历史列表中未完成的作品 ============
let _historyPollTimer = null

function startHistoryPollingForPending() {
  stopHistoryPolling()
  _historyPollTimer = setInterval(async () => {
    const pending = historyList.value.filter(
      i => i.status && !['analyzed', 'uploaded'].includes(i.status)
    )
    if (pending.length === 0) {
      stopHistoryPolling()
      return
    }
    const ids = pending.map(i => i.id)
    try {
      const result = await tubiApi.batchGetStatus(ids)
      if (!result.success) return
      let changed = false
      result.data.forEach(r => {
        const item = historyList.value.find(i => i.id === r.id)
        if (!item) return
        if (item.status !== r.status) {
          item.status = r.status
          changed = true
        }
        if (r.status === 'analyzed' || r.status === 'error') {
          // 刷新这条记录的数据
        }
      })
      // 有变化时重新加载历史列表以获取完整数据
      if (changed) {
        await loadHistory()
      }
    } catch (e) {
      console.error('history poll error:', e)
    }
  }, 8000)
}

function stopHistoryPolling() {
  if (_historyPollTimer) {
    clearInterval(_historyPollTimer)
    _historyPollTimer = null
  }
}

// 选择图片
async function selectImage(img) {
  // 确保全量作品列表已加载（prev/next 导航需要）
  if (!fullItemList.value || fullItemList.value.length === 0) {
    await loadFullItemList()
  }
  currentImage.value = img
    // 同步当前选中的艺术家：打开哪个艺术家的作品，返回就显示哪个艺术家的列表
    if (img.artist) {
      currentArtist.value = img.artist
    }
  
  // 设置页面标题：作品名 - 版块名 - 站点名
  const artworkTitle = img.title || img.name || '未命名作品'
  document.title = `${artworkTitle} - 题跋分析 - 中国画与书法AI综合分析系统`
  
  // 更新URL为详情页（仅真实ID，模拟数据ID为负数不更新URL）
  // 使用 image_id (UUID) 作为路由参数
  const routeId = img.image_id || img.id
  const isRealId = (typeof routeId === 'number' && routeId > 0) || (typeof routeId === 'string' && !routeId.startsWith('-'))
  if (isRealId && String(route.params.id) !== String(routeId)) {
    const query = (currentArtist.value && currentArtist.value !== '李鱓') 
      ? { artist: currentArtist.value } 
      : {}
    router.replace({ name: 'TubiDetail', params: { id: routeId }, query })
  }
  
  // 处理模拟数据（负数ID）
  if (img.id < 0) {
    analyzeStatus.value = 'analyzed'
    areaStats.inscriptionPercent = img.inscriptionPercent || 0
    areaStats.paintingPercent = img.paintingPercent || 0
    areaStats.blankPercent = img.blankPercent || 0
    regions = (typeof img.regions === 'string' ? JSON.parse(img.regions) : img.regions) || { inscription_regions: [], painting_regions: [], blank_regions: [] }
    
    analysisNote.value = img.analysisNote || ''
    
    // 设置位置分析
    positionAnalysis.value = img.positionAnalysis || {
      layout_type: '传统布局',
      position: '右上方',
      coverage_ratio: 0.2,
      overlap_ratio: 0.05,
      layout_description: '模拟数据的位置分析'
    }
  } else {
    // 处理真实数据
    analyzeStatus.value = img.regions ? 'analyzed' : 'pending'

    if (img.regions) {
      areaStats.inscriptionPercent = img.inscriptionPercent || 0
      areaStats.paintingPercent = img.paintingPercent || 0
      areaStats.blankPercent = img.blankPercent || 0
      regions = typeof img.regions === 'string' ? JSON.parse(img.regions) : img.regions
      
      analysisNote.value = img.analysisNote || ''
      
      // 设置位置分析（优先使用后端返回的数据，否则前端计算）
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

  // 等待DOM更新
  await nextTick()
  initCanvas()
  
  if (analyzeStatus.value === 'analyzed') {
    drawRegions()
    // 延迟执行图表更新，确保DOM已渲染
    setTimeout(() => {
      tubiDetailRef.value?.updatePieChart?.()
    }, 300)
  }
}

// 清空所有
async function clearAll() {
  try {
    await ElMessageBox.confirm('确定要清空所有图片吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    for (const img of uploadedImages.value) {
      try {
        await fetch(`/api/v1/tubi/image/${img.id}`, { method: 'DELETE' })
      } catch (e) {
        console.error('删除图片失败:', e)
      }
    }

    uploadedImages.value = []
    currentImage.value = null
    analyzeStatus.value = 'pending'
    if (route.params.id) {
      const query = (currentArtist.value && currentArtist.value !== '李鱓') 
        ? { artist: currentArtist.value } 
        : {}
      router.replace({ name: 'TubiAnalysis', query })
    }
    ElMessage.success('已清空')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// 初始化画布
function initCanvas() {
  if (!canvasRef.value || !currentImage.value) return
  
  // 检查图片 URL 是否有效
  const imageUrl = currentImage.value.url || currentImage.value.annotatedImageUrl
  if (!imageUrl) {
    console.warn('No valid image URL for canvas')
    return
  }

  canvas = canvasRef.value
  ctx = canvas.getContext('2d')

  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    const containerWidth = canvas.parentElement.clientWidth - 40
    const scale = containerWidth / img.width
    const displayWidth = containerWidth
    const displayHeight = img.height * scale

    canvas.width = displayWidth
    canvas.height = displayHeight
    canvas.style.width = displayWidth + 'px'
    canvas.style.height = displayHeight + 'px'

    ctx.drawImage(img, 0, 0, displayWidth, displayHeight)

    if (analyzeStatus.value === 'analyzed') {
      drawRegions()
    }
  }
  img.onerror = () => {
    console.error('Failed to load image:', imageUrl)
  }
  img.src = imageUrl
}

// 绘制区域标注
function drawRegions() {
  if (!ctx || !canvas || !currentImage.value) return

  // 检查图片 URL 是否有效
  const imageUrl = currentImage.value.url || currentImage.value.annotatedImageUrl
  if (!imageUrl) {
    console.warn('No valid image URL for drawRegions')
    return
  }

  const scaleX = canvas.width / currentImage.value.width
  const scaleY = canvas.height / currentImage.value.height

  // 清空画布并重新绘制图片
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    // 绘制区域
    const colors = {
      inscription: 'rgba(220, 92, 92, 0.3)',
      painting: 'rgba(74, 144, 217, 0.28)',
      blank: 'rgba(90, 184, 112, 0.25)'
    }

    const borderColors = {
      inscription: '#dc5c5c',
      painting: '#4a90d9',
      blank: '#5ab870'
    }

    // 绘制多边形区域的辅助函数
    function drawPolygonRegion(reg, color, borderColor) {
      // 检查是否是多边形（有points字段）
      if (reg.points && Array.isArray(reg.points) && reg.points.length >= 3) {
        // 绘制多边形
        ctx.beginPath()
        reg.points.forEach((point, index) => {
          const x = point.x * scaleX
          const y = point.y * scaleY
          if (index === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.closePath()
        
        // 填充
        ctx.fillStyle = color
        ctx.fill()
        
        // 描边
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.stroke()
      } else if (reg.x1 !== undefined && reg.y1 !== undefined && reg.x2 !== undefined && reg.y2 !== undefined) {
        // 绘制矩形（兼容旧数据）
        ctx.fillStyle = color
        ctx.fillRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.strokeRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
      }
    }

    // 绘制题跋区域
    regions.inscription_regions?.forEach(reg => {
      drawPolygonRegion(reg, colors.inscription, borderColors.inscription)
    })

    // 绘制绘画区域
    regions.painting_regions?.forEach(reg => {
      drawPolygonRegion(reg, colors.painting, borderColors.painting)
    })

    // 绘制留白区域
    regions.blank_regions?.forEach(reg => {
      drawPolygonRegion(reg, colors.blank, borderColors.blank)
    })
  }
  img.onerror = () => {
    console.error('Failed to load image in drawRegions:', imageUrl)
  }
  img.src = imageUrl
}

// AI自动分析
async function autoAnalyze() {
  if (!currentImage.value || analyzeStatus.value === 'analyzing') return

  analyzeStatus.value = 'analyzing'
  analyzeProgress.value = 0
  analyzingStep.value = '正在上传图片...'

  // 启动进度模拟
  const progressInterval = startAnalyzeProgress()

  try {
    const startResult = await tubiApi.autoAnalyze(currentImage.value.id)
    if (!startResult?.success) {
      throw new Error(startResult?.detail || startResult?.error || '分析任务启动失败')
    }
    
    // 检查是否成功入队（Redis 可能不可用）
    if (startResult.data?.enqueued === false) {
      ElMessage.warning('任务已创建但入队失败，请检查 Redis 和 tubi_worker 是否启动')
    }

    analyzingStep.value = '已加入队列，等待分析...'

    const startAt = Date.now()
    while (true) {
      const statusResult = await tubiApi.getAnalyzeStatus(currentImage.value.id)
      if (!statusResult?.success) {
        throw new Error(statusResult?.detail || statusResult?.error || '获取分析状态失败')
      }

      const status = statusResult.data?.status
      if (status === 'analyzed') break
      if (status === 'error') {
        throw new Error(statusResult.data?.analysis_note || '分析失败')
      }
      if (status === 'queued') {
        try {
          const qi = await tubiApi.getQueueInfo(currentImage.value.id)
          const pos = qi?.data?.position
          const est = qi?.data?.estimated_wait_seconds
          if (pos) {
            const mins = est ? Math.max(1, Math.ceil(est / 60)) : null
            analyzingStep.value = mins ? `排队中：前面还有${pos - 1}个，预计约${mins}分钟` : `排队中：前面还有${pos - 1}个`
          } else {
            analyzingStep.value = '排队中...'
          }
        } catch {
          analyzingStep.value = '排队中...'
        }
      } else if (status === 'analyzing') {
        analyzingStep.value = '分析中...'
      }
      const elapsed = Date.now() - startAt
      const waitMs = status === 'queued'
        ? (elapsed < 60_000 ? 5000 : 8000)
        : (elapsed < 60_000 ? 3000 : 6000)
      await new Promise(resolve => setTimeout(resolve, waitMs))
      if (Date.now() - startAt > 20 * 60 * 1000) {
        throw new Error('分析超时，请重试')
      }
    }

    const result = await tubiApi.getAnalysisResult(currentImage.value.id)
    clearInterval(progressInterval)

    if (!result?.success) {
      throw new Error(result?.detail || result?.error || '获取分析结果失败')
    }

    const data = result.data

    currentImage.value.inscriptionPercent = data.inscription_percent
    currentImage.value.paintingPercent = data.painting_percent
    currentImage.value.blankPercent = data.blank_percent
    currentImage.value.regions = parseRegions(data.regions)
    currentImage.value.annotatedImageUrl = data.annotated_image_url
    currentImage.value.sealContent = data.seal_content || ''
    currentImage.value.inscriptionContent = data.inscription_content || ''

    areaStats.inscriptionPercent = data.inscription_percent
    areaStats.paintingPercent = data.painting_percent
    areaStats.blankPercent = data.blank_percent

    regions = typeof data.regions === 'string' ? JSON.parse(data.regions) : data.regions
    analysisNote.value = data.analysis_note

    const calculatedPositionAnalysis = calculatePositionAnalysisByRules(
      regions,
      currentImage.value.width,
      currentImage.value.height
    )
    positionAnalysis.value = calculatedPositionAnalysis
    currentImage.value.positionAnalysis = calculatedPositionAnalysis

    drawRegions()

    const idx = uploadedImages.value.findIndex(img => img.id === currentImage.value.id)
    if (idx > -1) {
      uploadedImages.value[idx] = { ...currentImage.value }
    }

    analyzeProgress.value = 100
    analyzingStep.value = '分析完成！'
    analyzeStatus.value = 'analyzed'

    await nextTick()
    tubiDetailRef.value?.updatePieChart?.()

    await loadHistory()
    refreshAnalyticsKey.value++  // 通知 TubiHome 刷新分析图表缓存

    ElMessage.success('AI分析完成')
  } catch (error) {
    clearInterval(progressInterval)
    analyzeStatus.value = 'pending'
    ElMessage.error(`分析失败: ${error.message}`)
  }
}

// 模拟题跋分析进度
function startAnalyzeProgress() {
  analyzeProgress.value = 0
  analyzingStep.value = '正在上传图片...'

  const steps = [
    { percent: 10, text: '正在读取图像...' },
    { percent: 25, text: 'AI正在识别题跋区域...' },
    { percent: 40, text: 'AI正在识别绘画区域...' },
    { percent: 55, text: 'AI正在识别留白区域...' },
    { percent: 70, text: '正在计算面积占比...' },
    { percent: 85, text: '正在生成面积占比智能示意图...' }
  ]

  let stepIndex = 0
  const interval = setInterval(() => {
    if (analyzeStatus.value !== 'analyzing') {
      clearInterval(interval)
      return
    }

    if (stepIndex < steps.length) {
      const step = steps[stepIndex]
      analyzeProgress.value = step.percent
      analyzingStep.value = step.text
      stepIndex++
    }
  }, 8000)

  return interval
}

// 监听窗口大小变化
function handleResize() {
  trendChart?.resize()
  if (currentImage.value) {
    initCanvas()
    if (analyzeStatus.value === 'analyzed') {
      drawRegions()
    }
  }
}

// 更新趋势图
function updateTrendChart() {
  // 筛选有年代信息的历史记录
  const validData = historyList.value.filter(item => {
    const hasYear = item.year && !isNaN(parseInt(item.year))
    const hasPercent = item.inscriptionPercent !== undefined && item.inscriptionPercent !== null
    return hasYear && hasPercent
  }).sort((a, b) => parseInt(a.year) - parseInt(b.year))

  // 先设置数据，让 v-if 渲染卡片
  trendChartData.value = validData

  // 获取筛选后的数据
  const filteredData = filteredTrendChartData.value

  if (filteredData.length === 0) {
    return
  }

  // 按年份分组并计算平均值
  const yearGroups = {}
  filteredData.forEach(item => {
    const year = parseInt(item.year)
    if (!yearGroups[year]) {
      yearGroups[year] = []
    }
    yearGroups[year].push(item)
  })

  // 构建趋势图数据：同年取平均，保留最新画作信息
  const trendData = Object.keys(yearGroups)
    .map(year => {
      const items = yearGroups[year]
      const avgPercent = items.reduce((sum, item) => sum + item.inscriptionPercent, 0) / items.length
      // 按创建时间排序，取最新的画作
      const latestItem = items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0]
      
      return {
        year: year,
        inscriptionPercent: Math.round(avgPercent * 10) / 10, // 保留一位小数
        count: items.length,
        // 保留最新画作的详细信息
        id: latestItem.id,
        title: latestItem.title,
        artist: latestItem.artist,
        url: latestItem.url,
        thumbnailUrl: latestItem.thumbnailUrl,
        age: getDisplayAge(latestItem),
        created_at: latestItem.created_at,
        // 保存该年份所有画作
        allItems: items
      }
    })
    .sort((a, b) => parseInt(a.year) - parseInt(b.year))

  // 计算统计数据（基于原始数据）
  const percents = filteredData.map(item => item.inscriptionPercent)
  trendStats.avgPercent = (percents.reduce((a, b) => a + b, 0) / percents.length).toFixed(1)
  trendStats.maxPercent = Math.max(...percents).toFixed(1)
  trendStats.minPercent = Math.min(...percents).toFixed(1)

  // 等待 DOM 更新后再初始化图表
  nextTick(() => {
    if (!trendChartRef.value) return

    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value)
      
      // 添加点击事件 - 点击跳转到对应画作（最新的那幅）
      trendChart.on('click', function(params) {
        const dataIndex = params.dataIndex
        const item = trendData[dataIndex]
        if (item && item.id) {
          // 查找对应的图片数据
          const targetImage = uploadedImages.value.find(img => img.id === item.id)
          if (targetImage) {
            selectImage(targetImage)
            window.scrollTo({ top: 0, behavior: 'smooth' })
            ElMessage.success(`已切换到: ${item.title || '未命名'}`)
          } else {
            // 如果不在 uploadedImages 中，需要加载该图片
            loadAndSelectImage(item.id).then(() => {
              window.scrollTo({ top: 0, behavior: 'smooth' })
            })
          }
        }
      })
    }

  // 准备数据
  const xData = trendData.map(item => {
    if (trendArtistFilter.value !== 'all' && item.age !== null && item.age !== undefined) {
      return `${item.year}（${item.age}岁）`
    }
    return item.year.toString()
  })
  const yData = trendData.map(item => item.inscriptionPercent)

  const option = {
    tooltip: {
      trigger: 'axis',
      confine: true,
      enterable: false,
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#9B7ED8',
      borderWidth: 1,
      textStyle: { color: '#333' },
      extraCssText: 'pointer-events:none;',
      position: function (pos, params, dom, rect, size) {
        const padding = 12
        const contentSize = size.contentSize
        const viewSize = size.viewSize

        const x = Math.min(
          Math.max(pos[0] - contentSize[0] / 2, padding),
          viewSize[0] - contentSize[0] - padding
        )

        const preferredY = pos[1] - contentSize[1] - padding
        const y = preferredY < padding ? pos[1] + padding : preferredY

        return [x, y]
      },
      formatter: function(params) {
        const dataIndex = params[0].dataIndex
        const item = trendData[dataIndex]
        // 使用缩略图
        const thumbUrl = item.thumbnailUrl || item.url
        const thumb = thumbUrl ? `<img src="${thumbUrl}" style="width:80px;height:80px;object-fit:cover;border-radius:8px;margin-bottom:8px;" />` : ''
        
        // 如果有多个画作，显示数量提示
        const countTip = item.count > 1 
          ? `<div style="color:var(--cinnabar, #c96442);font-size:11px;margin-bottom:4px;">该年份共 ${item.count} 幅作品</div>` 
          : ''

        const ageTip = item.age !== null && item.age !== undefined
          ? ` · ${item.age}岁`
          : ''
        
        return `
          <div style="padding:8px;cursor:pointer;">
            ${thumb}
            ${countTip}
            <div style="font-weight:600;margin-bottom:4px;color:#6B5B95;">${item.title || '未命名'}</div>
            <div style="color:#8B7CB3;font-size:12px;margin-bottom:4px;">${item.artist || '未知作者'} · ${item.year}年${ageTip}</div>
            <div style="color:#9B7ED8;font-weight:600;margin-bottom:4px;">平均题跋占比: ${item.inscriptionPercent}%</div>
            <div style="color:#9B7ED8;font-size:11px;border-top:1px solid #E8E3F0;padding-top:4px;margin-top:4px;">点击查看详情</div>
          </div>
        `
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xData,
      boundaryGap: false,
      axisLine: { show: false },
      axisLabel: {
        color: '#8B7CB3',
        fontSize: 11,
        interval: 0,
        rotate: xData.length > 8 ? 45 : 0
      },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '题跋占比 (%)',
      nameTextStyle: {
        color: '#8B7CB3',
        fontSize: 12
      },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#8B7CB3',
        fontSize: 11,
        formatter: '{value}%'
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(139, 124, 179, 0.15)',
          type: 'dashed'
        }
      }
    },
    series: [{
      name: '题跋占比',
      type: 'line',
      data: yData,
      smooth: 0.4,
      symbol: 'circle',
      symbolSize: 10,
      lineStyle: {
        width: 3,
        color: '#9B7ED8',
        shadowColor: 'rgba(155, 126, 216, 0.5)',
        shadowBlur: 10,
        shadowOffsetY: 5
      },
      itemStyle: {
        color: '#fff',
        borderColor: '#9B7ED8',
        borderWidth: 3,
        shadowBlur: 8,
        shadowColor: 'rgba(155, 126, 216, 0.6)'
      },
      emphasis: {
        scale: 1.5,
        itemStyle: {
          color: '#9B7ED8',
          borderColor: '#fff',
          borderWidth: 3,
          shadowBlur: 15,
          shadowColor: 'rgba(155, 126, 216, 0.8)'
        }
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(155, 126, 216, 0.6)' },
            { offset: 0.3, color: 'rgba(155, 126, 216, 0.4)' },
            { offset: 0.6, color: 'rgba(155, 126, 216, 0.2)' },
            { offset: 1, color: 'rgba(155, 126, 216, 0.05)' }
          ]
        }
      }
    }]
  }

    trendChart.setOption(option, true)
  })
}

// 搜索画作
async function handleSearch(keyword) {
  const kw = (keyword || searchKeyword.value || '').trim()
  if (!kw) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  searchDialogVisible.value = true
  searchLoading.value = true
  try {
    const response = await tubiApi.searchImages(kw)
    if (response.success) {
      // 转换字段名（下划线转驼峰）
      searchResults.value = (response.data || []).map(item => ({
        ...item,
        inscriptionPercent: item.inscription_percent,
        paintingPercent: item.painting_percent,
        blankPercent: item.blank_percent,
        annotatedImageUrl: item.annotated_image_url,
        isManualAnnotated: item.is_manual_annotated,
        thumbnailUrl: item.thumbnail_url,
        analysisNote: item.analysis_note,
        inscriptionContent: item.inscription_content,
        inscriptionModern: item.inscription_modern,
        sealContent: item.seal_content
      }))
      if (searchResults.value.length === 0) {
        ElMessage.info('未找到匹配的画作')
      }
    } else {
      ElMessage.error(response.message || '搜索失败')
      searchResults.value = []
    }
  } catch (error) {
    console.error('搜索失败:', error)
    ElMessage.error('搜索失败: ' + (error.message || '网络错误'))
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

// 加载搜索结果项
async function loadSearchResultItem(row) {
  searchDialogVisible.value = false
  await loadHistoryItem(row)
}

// 加载历史记录
// 从AI分析说明中提取题跋内容
function extractInscriptionContent(analysisNote) {
  if (!analysisNote) return ''
  
  // 尝试提取题跋内容
  // 这里使用简单的正则表达式来提取可能的题跋内容
  // 实际应用中可能需要更复杂的逻辑
  const inscriptionPatterns = [
    /题跋内容[:：]([\s\S]*?)(?=\<br\>|$)/,
    /款识[:：]([\s\S]*?)(?=\<br\>|$)/,
    /题跋[:：]([\s\S]*?)(?=\<br\>|$)/,
    /跋文[:：]([\s\S]*?)(?=\<br\>|$)/
  ]
  
  for (const pattern of inscriptionPatterns) {
    const match = analysisNote.match(pattern)
    if (match && match[1]) {
      return match[1].trim()
    }
  }
  
  // 如果没有找到明确的题跋标记，尝试提取可能的题跋内容
  // 查找包含年月日、作者等信息的文本
  const datePattern = /[\d一二三四五六七八九十百千]+年[\d一二三四五六七八九十]+月|[\d一二三四五六七八九十百千]+年[春夏秋冬]/
  const authorPattern = /[\u4e00-\u9fa5]{2,4}\s*书|\s*写|\s*题/
  
  const lines = analysisNote.split('<br>')
  for (const line of lines) {
    if (datePattern.test(line) || authorPattern.test(line)) {
      return line.trim()
    }
  }
  
  return ''
}

async function loadHistory(page = 1) {
  historyLoading.value = true
  try {
    const skip = (page - 1) * historyPageSize.value
    const artistParam = currentArtist.value && currentArtist.value !== '李鱓' ? currentArtist.value : undefined
    const response = await tubiApi.getAllResults(skip, historyPageSize.value, artistParam)
    console.log('历史记录API响应:', response)
    if (response.success) {
      const items = (response.data || []).map(item => {
        const analysisNote = item.analysis_note || ''
        const inscriptionContent = item.inscription_content || extractInscriptionContent(analysisNote)
        
        return {
          ...item,
          image_id: item.image_id, // 确保保留 image_id
          album_name: item.album_name, // 保留册页名称
          tags: item.tags, // 保留标签
          inscriptionPercent: item.inscription_percent,
          paintingPercent: item.painting_percent,
          blankPercent: item.blank_percent,
          annotatedImageUrl: item.annotated_image_url,
          isManualAnnotated: item.is_manual_annotated,
          thumbnailUrl: item.thumbnail_url,
          analysisNote: analysisNote,
          inscriptionContent: inscriptionContent,
          sealContent: item.seal_content || ''
        }
      })
      if (page === 1) {
        historyList.value = items
      } else {
        historyList.value = historyList.value.concat(items)
      }
      historyPage.value = page
      historyHasMore.value = items.length >= historyPageSize.value
      console.log('历史记录加载成功:', historyList.value.length, '条，还有更多:', historyHasMore.value)
      // 加载完成后更新趋势图
      await nextTick()
      updateTrendChart()
    } else {
      console.error('历史记录API返回失败:', response)
      ElMessage.error(response.message || '加载历史记录失败')
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
    ElMessage.error('加载历史记录失败: ' + (error.message || '网络错误'))
  } finally {
    historyLoading.value = false
  }
}

// 预览历史图片
function previewHistoryImage(row) {
  previewImageUrl.value = row.url
  previewDialogVisible.value = true
}

// 加载历史记录项
async function loadHistoryItem(row) {
  try {
    // 处理模拟数据（负数ID）
    if (row.id < 0) {
      // 直接使用传入的row对象作为历史记录项
      const historyImage = {
        ...row,
        name: row.title || '模拟数据',
        url: row.thumbnailUrl || row.url,
        width: 800,
        height: 600,
        blankPercent: 100 - (row.inscriptionPercent || 0) - (row.paintingPercent || 0),
        annotatedImageUrl: row.thumbnailUrl || row.url,
        analysisNote: `这是一幅模拟画作：${row.title || '未命名'}`
      }

      // 添加到当前会话
      const exists = uploadedImages.value.find(img => img.id === historyImage.id)
      if (!exists) {
        uploadedImages.value.push(historyImage)
      }

      // 选中该图片
      selectImage(historyImage)
      
      // 滚动到页面顶部
      window.scrollTo({ top: 0, behavior: 'smooth' })
      
      ElMessage.success('已加载模拟数据')
    } else {
      // 正常加载真实数据 - 优先使用 image_id (UUID)
      const recordId = row.image_id || row.id
      const response = await tubiApi.getAnalysisResult(recordId)
      if (response.success) {
        const data = response.data

        // 创建图片对象
        const analysisNote = data.analysis_note || ''
        const inscriptionContent = data.inscription_content || extractInscriptionContent(analysisNote)
        
        const historyImage = {
          id: data.id,
          image_id: data.image_id, // 确保设置 image_id
          name: data.name || '历史记录',
          url: data.url,
          thumbnailUrl: data.thumbnail_url || data.url,
          width: data.width,
          height: data.height,
          title: data.title,
          artist: data.artist,
          year: data.year,
          period: data.period,
          inscriptionPercent: data.inscription_percent,
          paintingPercent: data.painting_percent,
          blankPercent: data.blank_percent,
          regions: parseRegions(data.regions),
          positionAnalysis: data.position_analysis,
          annotatedImageUrl: data.annotated_image_url,
          isManualAnnotated: data.is_manual_annotated,
          analysisNote: analysisNote,
          inscriptionContent: inscriptionContent,
          inscriptionModern: data.inscription_modern || '',
          sealContent: data.seal_content || '',
          contentAnalysis: data.content_analysis || null,
          artwork_width_cm: data.artwork_width_cm,
          artwork_height_cm: data.artwork_height_cm,
          tags: data.tags,
          album_name: data.album_name,
          album_index: data.album_index,
          period_phase: data.period_phase,
          material_tags: data.material_tags,
          computed_tags: data.computed_tags
        }

        // 添加到当前会话
        const exists = uploadedImages.value.find(img => img.id === historyImage.id)
        if (!exists) {
          uploadedImages.value.push(historyImage)
        }

        // 选中该图片（selectImage 内部会自动加载 fullItemList）
        selectImage(historyImage)

        // 滚动到页面顶部
        window.scrollTo({ top: 0, behavior: 'smooth' })
        
        ElMessage({ message: '已加载历史记录', type: 'success', customClass: 'toast-transparent', center: true })
      } else {
        ElMessage.error(response.message || '加载失败')
      }
    }
  } catch (error) {
    console.error('加载历史记录项失败:', error)
    // 检查是否是404错误
    if (error.response && error.response.status === 404) {
      ElMessage.error('该作品不存在或已被删除')
    } else {
      ElMessage.error('加载失败')
    }
  }
}



// 加载并选择指定ID的图片（用于趋势图点击）
async function loadAndSelectImage(imageId) {
  try {
    const response = await tubiApi.getAnalysisResult(imageId)
    if (response.success) {
      const data = response.data

      // 创建图片对象
      const analysisNote = data.analysis_note || ''
      const inscriptionContent = data.inscription_content || extractInscriptionContent(analysisNote)
      
      const image = {
        id: data.id,
        name: data.name || '画作',
        url: data.url,
        thumbnailUrl: data.thumbnail_url || data.url,
        width: data.width,
        height: data.height,
        title: data.title,
        artist: data.artist,
        year: data.year,
        period: data.period,
        inscriptionPercent: data.inscription_percent,
        paintingPercent: data.painting_percent,
        blankPercent: data.blank_percent,
        regions: parseRegions(data.regions),
        annotatedImageUrl: data.annotated_image_url,
        isManualAnnotated: data.is_manual_annotated,
        analysisNote: analysisNote,
        inscriptionContent: inscriptionContent,
        inscriptionModern: data.inscription_modern || '',
        sealContent: data.seal_content || '',
        contentAnalysis: data.content_analysis || null,
        artwork_width_cm: data.artwork_width_cm,
        artwork_height_cm: data.artwork_height_cm,
        tags: data.tags,
        album_name: data.album_name,
        album_index: data.album_index,
        period_phase: data.period_phase,
        material_tags: data.material_tags,
        computed_tags: data.computed_tags
      }

      // 添加到当前会话
      const exists = uploadedImages.value.find(img => img.id === image.id)
      if (!exists) {
        uploadedImages.value.push(image)
      }

      // 选中该图片
      selectImage(image)
      window.scrollTo({ top: 0, behavior: 'smooth' })
      ElMessage.success(`已切换到: ${image.title || '未命名'}`)
    } else {
      ElMessage.error(response.message || '加载画作失败')
    }
  } catch (error) {
    console.error('加载画作失败:', error)
    ElMessage.error('加载画作失败')
  }
}

// 删除历史记录项
async function deleteHistoryItem(row) {
  try {
    await ElMessageBox.confirm('确定要删除这条历史记录吗？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await tubiApi.deleteImage(row.id)
    if (response.success) {
      ElMessage.success('删除成功')
      // 从列表中移除
      const idx = historyList.value.findIndex(item => item.id === row.id)
      if (idx > -1) {
        historyList.value.splice(idx, 1)
      }
      // 从当前会话中移除
      const sessionIdx = uploadedImages.value.findIndex(img => img.id === row.id)
      if (sessionIdx > -1) {
        uploadedImages.value.splice(sessionIdx, 1)
        if (currentImage.value?.id === row.id) {
          currentImage.value = uploadedImages.value[0] || null
          if (currentImage.value) {
            selectImage(currentImage.value)
          } else {
            analyzeStatus.value = 'pending'
          }
        }
      }
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 编辑历史记录
function editHistoryItem(row) {
  editDialogRef.value.open(row)
}

// 编辑图片信息（作品库用）
function editImageInfo(item) {
  editDialogRef.value.open(item)
}

// 删除图片（作品库用）
async function deleteImage(item) {
  try {
    await ElMessageBox.confirm(`确定要删除「${item.title || '未命名'}」吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await tubiApi.deleteImage(item.id)
    if (response.success) {
      ElMessage.success('删除成功')
      // 从列表中移除
      const idx = historyList.value.findIndex(h => h.id === item.id)
      if (idx > -1) {
        historyList.value.splice(idx, 1)
      }
      // 从当前会话中移除
      const sessionIdx = uploadedImages.value.findIndex(img => img.id === item.id)
      if (sessionIdx > -1) {
        uploadedImages.value.splice(sessionIdx, 1)
      }
      // 如果删除的是当前选中的图片，清空当前选择
      if (currentImage.value?.id === item.id) {
        currentImage.value = null
        analyzeStatus.value = 'pending'
        if (route.params.id) {
          const query = (currentArtist.value && currentArtist.value !== '李鱓') 
            ? { artist: currentArtist.value } 
            : {}
          router.replace({ name: 'TubiAnalysis', query })
        }
      }
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 基于规则计算题跋位置分析（无需AI）
function calculatePositionAnalysisByRules(regions, imageWidth, imageHeight) {
  if (!regions || !regions.inscription_regions || regions.inscription_regions.length === 0) {
    return null
  }

  const inscriptionRegs = regions.inscription_regions
  const paintingRegs = regions.painting_regions || []

  // 计算题跋区域的边界框
  let minX = imageWidth, minY = imageHeight, maxX = 0, maxY = 0
  let totalInscriptionArea = 0

  inscriptionRegs.forEach(reg => {
    let x1, y1, x2, y2
    if (reg.points && reg.points.length >= 3) {
      // 多边形，计算边界框
      const xs = reg.points.map(p => p.x)
      const ys = reg.points.map(p => p.y)
      x1 = Math.min(...xs)
      y1 = Math.min(...ys)
      x2 = Math.max(...xs)
      y2 = Math.max(...ys)
    } else if (reg.x1 !== undefined) {
      // 矩形
      x1 = reg.x1
      y1 = reg.y1
      x2 = reg.x2
      y2 = reg.y2
    } else {
      return
    }

    minX = Math.min(minX, x1)
    minY = Math.min(minY, y1)
    maxX = Math.max(maxX, x2)
    maxY = Math.max(maxY, y2)
    totalInscriptionArea += (x2 - x1) * (y2 - y1)
  })

  const inscriptionWidth = maxX - minX
  const inscriptionHeight = maxY - minY
  const inscriptionCenterX = (minX + maxX) / 2
  const inscriptionCenterY = (minY + maxY) / 2

  // 计算与画面边缘的距离
  const marginLeft = minX
  const marginRight = imageWidth - maxX
  const marginTop = minY
  const marginBottom = imageHeight - maxY

  // 计算与绘画区域的重叠
  let overlapWithPainting = 0
  paintingRegs.forEach(paintReg => {
    let px1, py1, px2, py2
    if (paintReg.points && paintReg.points.length >= 3) {
      const xs = paintReg.points.map(p => p.x)
      const ys = paintReg.points.map(p => p.y)
      px1 = Math.min(...xs)
      py1 = Math.min(...ys)
      px2 = Math.max(...xs)
      py2 = Math.max(...ys)
    } else if (paintReg.x1 !== undefined) {
      px1 = paintReg.x1
      py1 = paintReg.y1
      px2 = paintReg.x2
      py2 = paintReg.y2
    } else {
      return
    }

    // 计算重叠面积
    const ox1 = Math.max(minX, px1)
    const oy1 = Math.max(minY, py1)
    const ox2 = Math.min(maxX, px2)
    const oy2 = Math.min(maxY, py2)

    if (ox2 > ox1 && oy2 > oy1) {
      overlapWithPainting += (ox2 - ox1) * (oy2 - oy1)
    }
  })

  const overlapRatio = totalInscriptionArea > 0 ? overlapWithPainting / totalInscriptionArea : 0

  // 判断位置类型
  let layoutType = ''
  let layoutDescription = ''
  let position = ''

  // 计算覆盖率
  const coverageRatio = totalInscriptionArea / (imageWidth * imageHeight)

  // 判断位置（基于中心点）
  const isLeft = inscriptionCenterX < imageWidth * 0.33
  const isRight = inscriptionCenterX > imageWidth * 0.67
  const isTop = inscriptionCenterY < imageHeight * 0.33
  const isBottom = inscriptionCenterY > imageHeight * 0.67
  const isCenterX = !isLeft && !isRight
  const isCenterY = !isTop && !isBottom

  if (isLeft && isTop) position = '左上'
  else if (isRight && isTop) position = '右上'
  else if (isLeft && isBottom) position = '左下'
  else if (isRight && isBottom) position = '右下'
  else if (isLeft && isCenterY) position = '左侧'
  else if (isRight && isCenterY) position = '右侧'
  else if (isCenterX && isTop) position = '顶部'
  else if (isCenterX && isBottom) position = '底部'
  else position = '中部'

  // 判断布局类型
  if (coverageRatio > 0.3) {
    layoutType = '满布式'
    layoutDescription = '题跋遍布画面大部分区域，与绘画内容紧密融合，形成图文交织的视觉效果。'
  } else if (overlapRatio > 0.5) {
    layoutType = '穿插式'
    layoutDescription = '题跋与绘画区域相互穿插，文字与图像形成有机的整体，增强了画面的层次感。'
  } else if (marginLeft < 20 || marginRight < 20 || marginTop < 20 || marginBottom < 20) {
    if ((marginLeft < 20 && marginTop < 20) ||
        (marginLeft < 20 && marginBottom < 20) ||
        (marginRight < 20 && marginTop < 20) ||
        (marginRight < 20 && marginBottom < 20)) {
      layoutType = '拦边封角式'
      layoutDescription = '题跋沿画面边缘布置，并在角落处汇聚，形成框景效果，突出中心绘画内容。'
    } else {
      layoutType = '边角式'
      layoutDescription = '题跋位于画面边角位置，既不影响主体绘画的展示，又能提供必要的文字说明。'
    }
  } else {
    layoutType = '独立式'
    layoutDescription = '题跋独立于绘画区域之外，与图像形成清晰的分离，便于分别欣赏文字和图像。'
  }

  // 构造form_types数组（兼容旧结构）
  const matchedCodes = new Set()
  if (layoutType === '边角式') matchedCodes.add(1)
  else if (layoutType === '拦边封角式') matchedCodes.add(2)
  else if (layoutType === '穿插式') matchedCodes.add(5)
  else if (layoutType === '满布式') matchedCodes.add(6)

  const FORM_TYPES_FALLBACK = [
    {code: 1, name: '边角规整式', description: '题款位于画面边角，形状规整，不侵入主体画面。'},
    {code: 2, name: '拦边封角式', description: '题款沿画面边缘或角落布置，形成对画面边角的封锁。'},
    {code: 3, name: '化虚为实/填充式', description: '题款填补画面大面积留白，将虚无的空间转化为实在的书法存在。'},
    {code: 4, name: '重力平衡式', description: '画面重心偏向某一侧，题款压阵于另一侧，形成稳定的视觉构图。'},
    {code: 5, name: '因势随形/穿插式', description: '题款穿插于物象之间，顺应走势，与绘画内容相互穿插。'},
    {code: 6, name: '侵入画位/喧宾夺主式', description: '题款极度扩张，占据画面核心位置，成为视觉焦点。'},
    {code: 7, name: '长篇排布/画材填空式', description: '题跋长篇密布，专门填补在画材空隙处。'},
    {code: 8, name: '从左起笔式', description: '打破传统从右向左，题款从画面左旁起笔向右延伸。'},
  ]
  const formTypes = FORM_TYPES_FALLBACK.map(ft => ({
    ...ft,
    matched: matchedCodes.has(ft.code),
    method: matchedCodes.has(ft.code) ? 'rule' : null,
    vl_status: null,
  }))

  return {
    layout_type: layoutType,
    position: position,
    layout_description: layoutDescription,
    coverage_ratio: coverageRatio,
    margin_left: marginLeft,
    margin_right: marginRight,
    margin_top: marginTop,
    margin_bottom: marginBottom,
    overlap_ratio: overlapRatio,
    vl_overall_status: 'ok',
    form_types: formTypes,
  }
}

// 获取位置标签样式类
function getPositionLabelClass() {
  if (!positionAnalysis.value) return ''
  const layoutType = positionAnalysis.value.layout_type
  if (layoutType === '边角式') return 'label-corner'
  if (layoutType === '拦边封角式') return 'label-frame'
  if (layoutType === '穿插式') return 'label-interleaved'
  if (layoutType === '满布式') return 'label-full'
  if (layoutType === '独立式') return 'label-independent'
  return ''
}

// 获取题跋区域示意图样式类（优先用form_types[0].code，兼容旧layout_type）
function getInscriptionAreaClass() {
  if (!positionAnalysis.value) return ''
  // 新结构：form_types 非排他，取第一个matched的类型
  if (positionAnalysis.value.form_types?.length) {
    const matched = positionAnalysis.value.form_types.filter(f => f.matched)
    if (matched.length) {
      return `area-code-${matched[0].code}`
    }
  }
  // 旧结构兼容
  const layoutType = positionAnalysis.value.layout_type
  if (layoutType === '边角式') return 'area-corner'
  if (layoutType === '拦边封角式') return 'area-frame'
  if (layoutType === '穿插式') return 'area-interleaved'
  if (layoutType === '满布式') return 'area-full'
  if (layoutType === '独立式') return 'area-independent'
  return ''
}

// 安全解析 regions（可能为 JSON 字符串或已解析对象）
type RegionsData = {
  inscription_regions: any[]
  painting_regions: any[]
  blank_regions: any[]
}
function parseRegions(regionsData: any): RegionsData {
  if (!regionsData) return { inscription_regions: [], painting_regions: [], blank_regions: [] }
  let parsed = regionsData
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed) } catch { return { inscription_regions: [], painting_regions: [], blank_regions: [] } }
  }
  return {
    inscription_regions: parsed.inscription_regions || [],
    painting_regions: parsed.painting_regions || [],
    blank_regions: parsed.blank_regions || []
  }
}

// 将 regions 多边形转为示意图 SVG 坐标（百分比 0-100）
const diagramRegions = computed(() => {
  const currentRegions = parseRegions(currentImage.value?.regions || regions)
  if (!currentRegions.inscription_regions?.length) {
    return { inscription_regions: [], painting_regions: [], blank_regions: [] }
  }
  return currentRegions
})

function toDiagramPoints(reg: any): string {
  if (!reg?.points || reg.points.length < 2) return ''
  const w = currentImage.value?.width || 1000
  const h = currentImage.value?.height || 1000
  const viewBoxH = 100 * h / w
  const pts = reg.points
  // 两点矩形 → 四点多边形
  if (pts.length === 2) {
    const [p1, p2] = pts
    const rect = [
      { x: Math.min(p1.x, p2.x), y: Math.min(p1.y, p2.y) },
      { x: Math.max(p1.x, p2.x), y: Math.min(p1.y, p2.y) },
      { x: Math.max(p1.x, p2.x), y: Math.max(p1.y, p2.y) },
      { x: Math.min(p1.x, p2.x), y: Math.max(p1.y, p2.y) },
    ]
    return rect.map((p: any) => `${(p.x / w * 100).toFixed(1)},${(p.y / h * viewBoxH).toFixed(1)}`).join(' ')
  }
  return pts.map((p: any) => `${(p.x / w * 100).toFixed(1)},${(p.y / h * viewBoxH).toFixed(1)}`).join(' ')
}

// 获取题跋区域示意图样式（fallback 用）
function getInscriptionAreaStyle() {
  if (!positionAnalysis.value) return {}
  const pos = positionAnalysis.value.position
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  const width = currentImage.value?.width || 1000
  const height = currentImage.value?.height || 1000

  // 优先用实际 margin 数据计算（V9 批处理后数据更准确）
  const leftPct = (ml / width) * 100
  const rightPct = (mr / width) * 100
  const topPct = (mt / height) * 100
  const bottomPct = (mb / height) * 100

  // 如果 margin 数据有效（总和 < 100%，即题跋区域有实际面积）
  const areaWidth = 100 - leftPct - rightPct
  const areaHeight = 100 - topPct - bottomPct
  if (areaWidth > 3 && areaHeight > 3 && areaWidth < 95 && areaHeight < 95) {
    return {
      left: leftPct.toFixed(1) + '%',
      top: topPct.toFixed(1) + '%',
      width: areaWidth.toFixed(1) + '%',
      height: areaHeight.toFixed(1) + '%'
    }
  }

  // fallback：根据位置名称硬编码
  if (pos === '左上') {
    return { left: '5%', top: '5%', width: '30%', height: '25%' }
  } else if (pos === '右上') {
    return { right: '5%', top: '5%', width: '30%', height: '25%' }
  } else if (pos === '左下') {
    return { left: '5%', bottom: '5%', width: '30%', height: '25%' }
  } else if (pos === '右下') {
    return { right: '5%', bottom: '5%', width: '30%', height: '25%' }
  } else if (pos === '左侧') {
    return { left: '5%', top: '20%', width: '25%', height: '60%' }
  } else if (pos === '右侧') {
    return { right: '5%', top: '20%', width: '25%', height: '60%' }
  } else if (pos === '上方') {
    return { left: '20%', top: '5%', width: '60%', height: '20%' }
  } else if (pos === '底部') {
    return { left: '20%', bottom: '5%', width: '60%', height: '20%' }
  } else {
    // 中部或其他 - 缩小为更合理的大小
    return { left: '35%', top: '35%', width: '30%', height: '30%' }
  }
}

// 获取边缘距离文本（完整版）
function getEdgeDistanceText() {
  if (!positionAnalysis.value) return ''
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  return `左${Math.round(ml)} 右${Math.round(mr)} 上${Math.round(mt)} 下${Math.round(mb)}`
}

// 获取边缘距离文本（简化版）
function getEdgeDistanceShortText() {
  if (!positionAnalysis.value) return ''
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  // 找出最小的边距
  const margins = [
    { name: '左', val: ml },
    { name: '右', val: mr },
    { name: '上', val: mt },
    { name: '下', val: mb }
  ]
  const minMargin = margins.reduce((min, cur) => cur.val < min.val ? cur : min)
  return `${minMargin.name}${Math.round(minMargin.val)}`
}

// 初始化朋友圈关系图
function initFriendCircleChart() {
  if (!friendCircleChartRef.value) return
  
  friendCircleChart = echarts.init(friendCircleChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}'
    },
    animationDurationUpdate: 1500,
    animationEasingUpdate: 'quinticInOut',
    series: [
      {
        type: 'graph',
        layout: 'force',
        force: {
          repulsion: 1000,
          gravity: 0.1,
          edgeLength: [80, 120]
        },
        roam: true,
        label: {
          show: false
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 8],
        edgeLabel: {
          fontSize: 12
        },
        data: [
          { name: '李鱓', value: 60, symbolSize: 60 },
          { name: '郑燮', value: 45, symbolSize: 45 },
          { name: '金农', value: 45, symbolSize: 45 },
          { name: '黄慎', value: 38, symbolSize: 38 },
          { name: '高翔', value: 38, symbolSize: 38 },
          { name: '汪士慎', value: 38, symbolSize: 38 },
          { name: '李方膺', value: 38, symbolSize: 38 },
          { name: '罗聘', value: 38, symbolSize: 38 },
          { name: '蒋廷锡', value: 38, symbolSize: 38 },
          { name: '王原祁', value: 38, symbolSize: 38 }
        ],
        links: [
          { source: '李鱓', target: '郑燮', lineStyle: { color: '#ff4444', width: 2 } }, // 挚友
          { source: '李鱓', target: '金农', lineStyle: { color: '#ff4444', width: 2 } }, // 挚友
          { source: '李鱓', target: '黄慎', lineStyle: { color: '#ff8800', width: 2 } }, // 道友
          { source: '李鱓', target: '高翔', lineStyle: { color: '#ff8800', width: 2 } }, // 道友
          { source: '李鱓', target: '汪士慎', lineStyle: { color: '#4488ff', width: 2 } }, // 画友
          { source: '李鱓', target: '李方膺', lineStyle: { color: '#4488ff', width: 2 } }, // 画友
          { source: '李鱓', target: '罗聘', lineStyle: { color: '#4488ff', width: 2 } }, // 画友
          { source: '蒋廷锡', target: '李鱓', lineStyle: { color: '#888888', width: 2, type: 'dashed' } }, // 师承
          { source: '王原祁', target: '李鱓', lineStyle: { color: '#888888', width: 2, type: 'dashed' } } // 师承
        ],
        lineStyle: {
          opacity: 0.9,
          width: 2,
          curveness: 0.1
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 4
          },
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold'
          }
        }
      }
    ]
  }
  
  friendCircleChart.setOption(option)
  
  // 响应式调整
  window.addEventListener('resize', () => {
    friendCircleChart.resize()
  })
}

onMounted(async () => {
  window.addEventListener('resize', handleResize)

  // 自动检测未完成的作品并启动后台轮询
  startHistoryPollingForPending()

  // 【关键】先检查路由参数，如果是详情页直接加载，避免先闪一下首页
  const imageId = route.params.id
  if (imageId) {
    // 详情页模式：显示 loading，等数据加载完成后再渲染
    initialLoading.value = true
    try {
      const response = await tubiApi.getAnalysisResult(imageId)
      if (response.success) {
        const data = response.data
        const analysisNoteText = data.analysis_note || ''
        const inscriptionContent = data.inscription_content || extractInscriptionContent(analysisNoteText)

        const historyImage = {
          id: data.id,
          image_id: data.image_id,
          name: data.name || '历史记录',
          url: data.url,
          thumbnailUrl: data.thumbnail_url || data.url,
          width: data.width,
          height: data.height,
          title: data.title,
          artist: data.artist,
          year: data.year,
          period: data.period,
          inscriptionPercent: data.inscription_percent,
          paintingPercent: data.painting_percent,
          blankPercent: data.blank_percent,
          regions: parseRegions(data.regions),
          positionAnalysis: data.position_analysis,
          annotatedImageUrl: data.annotated_image_url,
          isManualAnnotated: data.is_manual_annotated,
          analysisNote: analysisNoteText,
          inscriptionContent: inscriptionContent,
          inscriptionModern: data.inscription_modern || '',
          sealContent: data.seal_content || '',
          contentAnalysis: data.content_analysis || null,
          artwork_width_cm: data.artwork_width_cm,
          artwork_height_cm: data.artwork_height_cm,
          tags: data.tags,
          album_name: data.album_name,
          album_index: data.album_index,
          period_phase: data.period_phase,
          material_tags: data.material_tags,
          computed_tags: data.computed_tags
        }
        // 先保存数据到 uploadedImages（供后续使用）
        const exists = uploadedImages.value.find(img => img.id === historyImage.id)
        if (!exists) {
          uploadedImages.value.push(historyImage)
        }

        // 先加载全量作品列表（确保 prev/next 数据就绪），历史列表不阻塞 UI
        await loadFullItemList()
        loadHistory()

        // 所有数据就绪后才设置 currentImage，确保 TubiDetail 首次渲染时 prev/next 有数据
        selectImage(historyImage)
        ElMessage({ message: '已加载指定作品', type: 'success', customClass: 'toast-transparent', center: true })
      }
    } catch (error) {
      console.error('加载指定作品失败:', error)
      ElMessage.error('加载指定作品失败，可能已被删除')
      // 加载失败时回到列表页，保留 artist 参数
      const query = (currentArtist.value && currentArtist.value !== '李鱓') 
        ? { artist: currentArtist.value } 
        : {}
      router.replace({ name: 'TubiAnalysis', query })
      // 失败时也加载历史列表
      loadHistory()
    } finally {
      // 无论成功失败，都关闭 loading
      initialLoading.value = false
    }
  } else {
    // 首页模式：处理 URL 中的 artist 参数
    const artistFromUrl = route.query.artist
    if (artistFromUrl && typeof artistFromUrl === 'string') {
      currentArtist.value = artistFromUrl
    }
    // 正常加载历史列表（包 try-catch 防止白屏）
    try {
      await loadHistory()
    } catch (err) {
      console.error('loadHistory 失败（已捕获，页面不会白屏）:', err)
      ElMessage.error('加载历史记录失败，请刷新页面')
    }
    // 检查 sessionStorage（标签筛选）并滚动到作品库
    try {
      const storedTag = sessionStorage.getItem('filterTag')
      if (storedTag) {
        sessionStorage.removeItem('filterTag')
        filterTag.value = storedTag
        setTimeout(() => {
          document.getElementById('gallery-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }, 300)
      }
    } catch (e) {
      // ignore
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  friendCircleChart?.dispose()
  stopHistoryPolling()
})

// ── 册页导航逻辑 ───────────────────────────────────────────────────────────
const albumNavigation = reactive({
  is_in_album: false,
  album_name: '',
  current_index: -1,
  total_count: 0,
  items: []
})

async function loadAlbumNavigation() {
  if (!currentImage.value) return
  albumNavigation.is_in_album = false
  albumNavigation.items = []

  // 优先使用 image_id (UUID)，如果没有再用 id
  const recordId = currentImage.value.image_id || currentImage.value.id
  if (!recordId) return

  console.log('[册页导航] 加载导航，recordId:', recordId, 'currentImage:', currentImage.value)

  try {
    const res = await tubiApi.getAlbumNavigation(recordId)
    console.log('[册页导航] API响应:', res)
    if (res.success) {
      const data = res.data
      Object.assign(albumNavigation, data)
      console.log('[册页导航] 已设置:', albumNavigation)
    }
  } catch (e) {
    console.error('[册页导航] 加载失败:', e)
  }
}

async function navigateToAlbumItem(item) {
  if (item.is_current) return
  console.log('[册页导航] 点击item:', item)
  
  // 先在当前会话中找
  let targetImage = uploadedImages.value.find(img => 
    (item.image_id && img.image_id === item.image_id) || 
    (item.db_id && img.id === item.db_id) || 
    img.id === item.id
  )
  
  if (targetImage) {
    // 找到，直接切换
    selectImage(targetImage)
    return
  }
  
  // 没找到，通过 API 加载
  console.log('[册页导航] 未找到，通过API加载:', item.id)
  try {
    const response = await tubiApi.getAnalysisResult(item.id)
    if (response.success) {
      const data = response.data
      const analysisNoteText = data.analysis_note || ''
      const inscriptionContent = data.inscription_content || extractInscriptionContent(analysisNoteText)
      
      const historyImage = {
        id: data.id,
        image_id: data.image_id,
        name: data.name || '历史记录',
        url: data.url,
        thumbnailUrl: data.thumbnail_url || data.url,
        width: data.width,
        height: data.height,
        title: data.title,
        artist: data.artist,
        year: data.year,
        period: data.period,
        inscriptionPercent: data.inscription_percent,
        paintingPercent: data.painting_percent,
        blankPercent: data.blank_percent,
        regions: parseRegions(data.regions),
        positionAnalysis: data.position_analysis,
        annotatedImageUrl: data.annotated_image_url,
        isManualAnnotated: data.is_manual_annotated,
        analysisNote: analysisNoteText,
        inscriptionContent: inscriptionContent,
        inscriptionModern: data.inscription_modern || '',
        sealContent: data.seal_content || '',
        contentAnalysis: data.content_analysis || null,
        artwork_width_cm: data.artwork_width_cm,
        artwork_height_cm: data.artwork_height_cm
      }
      
      // 添加到当前会话
      uploadedImages.value.push(historyImage)
      selectImage(historyImage)
    }
  } catch (error) {
    console.error('[册页导航] 加载失败:', error)
    ElMessage.error('加载作品失败')
  }
}

// 监听 currentImage 变化，自动加载册页导航
watch(currentImage, (newVal) => {
  if (newVal) {
    loadAlbumNavigation()
  }
}, { immediate: true })
</script>

<style src="../tubi/TubiAnalysis.css" scoped></style>

<style scoped>
/* 初始加载遮罩：防止直接访问详情页时闪现首页框架 */
.initial-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-paper, #f5f4ed);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.initial-loading-content {
  text-align: center;
  color: var(--text-primary, #3d3d3d);
}

.loading-icon {
  animation: rotate 1.5s linear infinite;
  color: var(--cinnabar, #c96442);
  margin-bottom: 16px;
}

.loading-text {
  font-size: 16px;
  color: var(--text-secondary, #666);
  margin: 0;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Claude风格模式选择弹窗样式 */
.mode-selection-container {
  padding: 16px 0;
}

.mode-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.mode-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 20px;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  background: white;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.mode-card:hover {
  border-color: #d1d5db;
  background: #f9fafb;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.mode-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
}

.mode-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  margin-bottom: 16px;
  border-radius: 16px;
  background: #f3f4f6;
  color: #6b7280;
}

.mode-icon.highlight {
  background: #dbeafe;
  color: #3b82f6;
}

.mode-card.selected .mode-icon {
  background: #dbeafe;
  color: #3b82f6;
}

.mode-card.selected .mode-icon.highlight {
  background: #bfdbfe;
}

.mode-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
}

.mode-desc {
  font-size: 14px;
  color: #6b7280;
  text-align: center;
  line-height: 1.5;
}

/* Claude风格文件预览网格 */
.batch-file-preview {
  margin-top: 24px;
}

.batch-file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.batch-file-count {
  font-size: 16px;
  font-weight: 500;
  color: #111827;
}

.btn-clear-all {
  font-size: 13px;
}

.batch-file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}

.batch-file-card {
  position: relative;
  display: flex;
  flex-direction: column;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.batch-file-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.batch-file-thumb-wrapper {
  position: relative;
  width: 100%;
  padding-top: 75%;
  background: #f9fafb;
  overflow: hidden;
}

.batch-file-thumb {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.batch-file-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #9ca3af;
}

.batch-file-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(239, 68, 68, 0.9);
  color: white;
  border-radius: 50%;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s ease;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}

.batch-file-card:hover .batch-file-delete {
  opacity: 1;
}

.batch-file-delete:hover {
  background: #dc2626;
  transform: scale(1.1);
}

.batch-file-info {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.batch-file-name {
  font-size: 13px;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.batch-file-size {
  font-size: 12px;
  color: #6b7280;
}

/* 面积占比智能示意图标题与按钮同行 */
.annotated-image-section .section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: left;
}

.btn-annotate {
  font-size: 12px;
  padding: 4px 12px;
}

/* 现代文翻译样式 */
.inscription-translation {
  margin-top: 16px;
  padding-top: 16px;
}

.translation-divider {
  height: 1px;
  background: linear-gradient(to right, transparent, #e8e6dc 20%, #e8e6dc 80%, transparent);
  margin-bottom: 12px;
}

.translation-label {
  margin-bottom: 8px;
}

.clickable-tag-wrapper {
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.clickable-tag-wrapper:hover {
  transform: translateY(-1px);
}

.clickable-tag-wrapper:hover .clickable-tag {
  box-shadow: 0 2px 8px rgba(90, 138, 74, 0.25);
}

.clickable-tag {
  white-space: nowrap;
}

.expand-icon {
  transition: transform 0.2s ease;
  font-size: 14px;
  color: #5a8a4a;
  flex-shrink: 0;
}

.expand-icon.rotated {
  transform: rotate(180deg);
}

.card-title-artwork {
  font-size: 18px;
  color: #333;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-weight: 500;
}

/* Claude风格作品信息表格 */
.image-info-header {
  justify-content: flex-start !important;
  display: flex !important;
}

.artwork-info-table {
  width: 100%;
}

.info-row-horizontal {
  display: flex;
  gap: 8px;
  width: 100%;
}

.info-item {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.info-item:hover {
  background: #f1f3f5;
  transform: translateY(-1px);
}

.info-label {
  font-size: 11px;
  color: #6b7280;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.info-value {
  font-size: 12px;
  color: #111827;
  font-weight: 500;
  line-height: 1.3;
}

.translation-content {
  font-size: 14px;
  line-height: 1.9;
  color: #3d3d3a;
  background: #fffef8;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #ede9de;
  white-space: pre-wrap;
}

/* 册页导航样式 */
.album-navigation {
  margin-top: 12px;
  padding: 12px;
  background: #faf8f3;
  border-radius: 8px;
  border: 1px solid #ede9de;
}

.album-nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.album-nav-title {
  font-size: 14px;
  font-weight: 600;
  color: #c96442;
}

.album-nav-count {
  font-size: 12px;
  color: #8a8a7a;
}

.album-nav-thumbnails {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 4px 0;
  scroll-behavior: smooth;
}

.album-nav-thumbnails::-webkit-scrollbar {
  height: 4px;
}

.album-nav-thumbnails::-webkit-scrollbar-thumb {
  background: #d4cfc5;
  border-radius: 2px;
}

.album-nav-thumbnail {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 6px;
  border: 2px solid transparent;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0ece3;
}

.album-nav-thumbnail:hover {
  border-color: #4A90D9;
  transform: translateY(-1px);
}

.album-nav-thumbnail.active {
  border-color: #4A90D9;
  box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.25);
}

.album-nav-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.album-nav-thumbnail .thumb-placeholder {
  font-size: 12px;
  color: #8a8a7a;
  font-weight: 500;
}
</style>

<style>
/* ElMessage 透明+靠右样式（非 scoped，因为 ElMessage DOM 在组件外） */
.toast-transparent {
  opacity: 0.5 !important;
  backdrop-filter: blur(4px);
  top: 50% !important;
  left: 50% !important;
  transform: translate(-50%, -50%) !important;
  min-width: 140px !important;
  max-width: 80vw !important;
  padding: 8px 16px !important;
  font-size: 13px !important;
}
</style>
