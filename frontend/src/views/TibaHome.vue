<template>
  <div class="home-dashboard">
    <!-- 顶部左右两栏模块 -->
    <div class="dashboard-row">
      <!-- 左侧：艺术家数据概览模块（70%） -->
      <ArtistStatsCard ref="artistStatsCardRef" @artist-change="onHomeArtistChange" style="flex: 6.5;" />

      <!-- 右侧：题跋比排行榜模块 -->
      <TibaRankingCard
        :history-list="filteredAnalyticsData"
        :get-display-age="getDisplayAge"
        :loading="analyticsLoading"
        style="flex: 3.5;"
        @item-click="$emit('item-click', $event)"
        @more="$emit('more')"
      />
    </div>

    <!-- 作品库列表 -->
    <TibaGallery
      :history-list="filteredHistoryList"
      :get-display-age="getDisplayAge"
      :get-item-all-tags="getItemAllTags"
      :filter-tag="filterTag"
      :loading="props.historyList.length === 0"
      :has-more="props.hasMore"
      :fetch-loading="props.historyLoading"
      @item-click="$emit('item-click', $event)"
      @edit="$emit('edit', $event)"
      @delete="$emit('delete', $event)"
      @search="$emit('search', $event)"
      @load-more="$emit('load-more')"
      @go-list="$emit('go-list')"
      @clear-tag-filter="$emit('clear-tag-filter')"
    />

    <!-- 名家对比区域（始终显示全部作者数据） -->
    <TibaComparison :history-list="analyticsData" />

    <!-- 趋势图卡片 -->
    <el-card shadow="hover" class="trend-card" v-if="filteredTrendChartData.length > 0">
      <template #header>
        <div class="card-header">
          <span class="card-title">题跋占比趋势</span>
          <div class="trend-stats">
            <el-select v-model="trendArtistFilter" size="small" style="width: 120px; margin-right: 10px;">
              <el-option label="全部作者" value="all" />
              <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
            </el-select>
            <el-tag type="info" size="small">共 {{ filteredTrendChartData.length }} 幅作品</el-tag>
            <el-tag type="success" size="small" v-if="trendStats.avgPercent">平均占比 {{ trendStats.avgPercent }}%</el-tag>
          </div>
        </div>
      </template>
      <div ref="trendChartRef" class="trend-chart"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import echarts from '../utils/echarts'
import { ElMessage } from 'element-plus'
import { getDisplayAge } from '../tiba/utils'
import ArtistStatsCard from '../tiba/ArtistStatsCard.vue'
import TibaRankingCard from '../components/tiba/TibaRankingCard.vue'
import TibaGallery from '../components/tiba/TibaGallery.vue'
import TibaComparison from '../components/tiba/TibaComparison.vue'

import api, { tibaApi } from '../api'
import { getSharedAnalyticsData, setSharedAnalyticsData, clearSharedAnalyticsData } from '../tiba/sharedCache'

const props = defineProps({
  historyList: { type: Array, default: () => [] },
  filterTag: { type: String, default: null },
  artistFilter: { type: String, default: null },
  hasMore: { type: Boolean, default: true },
  historyLoading: { type: Boolean, default: false },
  refreshKey: { type: Number, default: 0 }
})

// ── 分析图表数据（独立于 Gallery 翻页，一次拉全量） ──
// 共享缓存：同 session 内 TibaHome + TibaAnalysis 共用同一份
const analyticsData = ref([])
const analyticsLoading = ref(true)

async function fetchAnalyticsData(force = false) {
  const cached = getSharedAnalyticsData()
  if (cached && !force) {
    analyticsData.value = cached
    analyticsLoading.value = false
    return
  }
  analyticsLoading.value = true
  try {
    const res = await tibaApi.getAllResults(0, 2000)
    if (res.success) {
      const data = (res.data || []).map(item => ({
        ...item,
        inscriptionPercent: item.inscription_percent,
        paintingPercent: item.painting_percent,
        blankPercent: item.blank_percent,
        thumbnailUrl: item.thumbnail_url,
      }))
      setSharedAnalyticsData(data)
      analyticsData.value = data
    }
  } catch (e) {
    console.error('加载分析数据失败', e)
  } finally {
    analyticsLoading.value = false
  }
}

// 监听 refreshKey prop 变化 → 强制刷新分析数据
watch(() => props.refreshKey, (val) => {
  if (val > 0) {
    clearSharedAnalyticsData()
    fetchAnalyticsData(true)
  }
})

const emit = defineEmits([
  'item-click', 'edit', 'delete', 'search',
  'load-more', 'clear-tag-filter',
  'more', 'trend-click', 'artist-change', 'go-list'
])

// ── 解析 tags 字段 ──────────────────────────────
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

function getItemAllTags(item) {
  const auto = item.computed_tags || []
  const manual = parseTags(item.tags)
  const result = [...auto]
  for (const t of manual) {
    if (!result.includes(t)) result.push(t)
  }
  return result
}

// ── 艺术家统计 ─────────────────────────────────
const artistStatsCardRef = ref(null)

// ── 全局画家筛选（联动 ArtistStatsCard / 排行榜 / 作品库 / 趋势图）──
const homeArtistFilter = ref('李鱓')

// 监听 homeArtistFilter 变化，同步到 trendArtistFilter 和 ArtistStatsCard
watch(homeArtistFilter, (newVal) => {
  trendArtistFilter.value = newVal
  artistStatsCardRef.value?.setArtist?.(newVal)
})

function onHomeArtistChange(artist) {
  homeArtistFilter.value = artist
  // 同步趋势图筛选
  trendArtistFilter.value = artist
  // 通知父组件画家已切换（用于更新 URL）
  emit('artist-change', artist)
}

// 按画家过滤后的历史列表（传给排行榜、作品库）
const filteredHistoryList = computed(() => {
  if (!props.historyList || !Array.isArray(props.historyList)) return []
  if (homeArtistFilter.value === 'all') return props.historyList
  return props.historyList.filter(item => item.artist === homeArtistFilter.value)
})

// 分析数据也按当前作者过滤（排行榜用，名家对比保持全量）
const filteredAnalyticsData = computed(() => {
  if (!analyticsData.value || analyticsData.value.length === 0) return []
  if (homeArtistFilter.value === 'all') return analyticsData.value
  return analyticsData.value.filter(item => item.artist === homeArtistFilter.value)
})

// ── 趋势图 ─────────────────────────────────────
const trendChartRef = ref(null)
let trendChart = null

const trendChartData = ref([])
const trendArtistFilter = ref('李鱓')

// 监听父组件传入的 artistFilter，同步到内部状态（必须在 trendArtistFilter 声明之后）
watch(() => props.artistFilter, (newVal) => {
  if (newVal && newVal !== homeArtistFilter.value) {
    homeArtistFilter.value = newVal
    trendArtistFilter.value = newVal
    // 同步到 ArtistStatsCard（通过 ref 调用暴露的方法）
    nextTick(() => {
      artistStatsCardRef.value?.setArtist?.(newVal)
    })
  }
}, { immediate: true })

const artistList = ref([])
async function fetchArtistList() {
  try {
    const data = await api.get('/content-analysis/artists')
    artistList.value = data.artists || []
    // 默认选中李鱓，不存在时回退到第一个
    if (!artistList.value.includes(trendArtistFilter.value)) {
      if (artistList.value.includes('李鱓')) {
        trendArtistFilter.value = '李鱓'
      } else if (artistList.value.length > 0) {
        trendArtistFilter.value = artistList.value[0]
      }
    }
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}
const trendStats = reactive({
  avgPercent: 0,
  maxPercent: 0,
  minPercent: 0
})

const filteredTrendChartData = computed(() => {
  if (trendArtistFilter.value === 'all') {
    return trendChartData.value
  }
  return trendChartData.value.filter(item => item.artist === trendArtistFilter.value)
})

function updateTrendChart() {
  const list = analyticsData.value.length ? analyticsData.value : props.historyList
  // 筛选有年代信息的历史记录
  const validData = list.filter(item => {
    const hasYear = item.year && !isNaN(parseInt(item.year))
    const hasPercent = item.inscriptionPercent !== undefined && item.inscriptionPercent !== null
    return hasYear && hasPercent
  }).sort((a, b) => parseInt(a.year) - parseInt(b.year))

  trendChartData.value = validData

  const filteredData = filteredTrendChartData.value
  if (filteredData.length === 0) return

  // 按年份分组并计算平均值
  const yearGroups = {}
  filteredData.forEach(item => {
    const year = parseInt(item.year)
    if (!yearGroups[year]) {
      yearGroups[year] = []
    }
    yearGroups[year].push(item)
  })

  const trendData = Object.keys(yearGroups)
    .map(year => {
      const items = yearGroups[year]
      const avgPercent = items.reduce((sum, item) => sum + item.inscriptionPercent, 0) / items.length
      const latestItem = items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0]
      return {
        year,
        inscriptionPercent: Math.round(avgPercent * 10) / 10,
        count: items.length,
        id: latestItem.id,
        title: latestItem.title,
        artist: latestItem.artist,
        url: latestItem.url,
        thumbnailUrl: latestItem.thumbnailUrl,
        age: getDisplayAge(latestItem),
        created_at: latestItem.created_at,
        allItems: items
      }
    })
    .sort((a, b) => parseInt(a.year) - parseInt(b.year))

  const percents = filteredData.map(item => item.inscriptionPercent)
  trendStats.avgPercent = (percents.reduce((a, b) => a + b, 0) / percents.length).toFixed(1)
  trendStats.maxPercent = Math.max(...percents).toFixed(1)
  trendStats.minPercent = Math.min(...percents).toFixed(1)

  nextTick(() => {
    if (!trendChartRef.value) return

    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value)
      trendChart.on('click', function(params) {
        const dataIndex = params.dataIndex
        const item = trendData[dataIndex]
        if (item && item.id) {
          emit('trend-click', item.id)
          window.scrollTo({ top: 0, behavior: 'smooth' })
        }
      })
    }

    const xData = trendData.map(item => {
      if (trendArtistFilter.value !== 'all' && item.age !== null && item.age !== undefined) {
        return `${item.year}（${item.age}岁）`
      }
      return item.year.toString()
    })
    const yData = trendData.map(item => item.inscriptionPercent)

    const option = {
      animation: true,
      animationDuration: 800,
      animationDurationUpdate: 400,
      animationEasing: 'cubicOut',
      animationEasingUpdate: 'cubicOut',
      animationDelay: function (idx) {
        return idx * 60
      },
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
          const thumbUrl = item.thumbnailUrl || item.url
          const thumb = thumbUrl ? `<img src="${thumbUrl}" style="width:80px;height:80px;object-fit:cover;border-radius:8px;margin-bottom:8px;" />` : ''
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
        left: '3%', right: '4%', bottom: '15%', top: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: xData,
        boundaryGap: false,
        axisLine: { show: false },
        axisLabel: {
          color: '#8B7CB3', fontSize: 11,
          interval: 0,
          rotate: xData.length > 8 ? 45 : 0
        },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        name: '题跋占比 (%)',
        nameTextStyle: { color: '#8B7CB3', fontSize: 12 },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#8B7CB3', fontSize: 11, formatter: '{value}%' },
        splitLine: { lineStyle: { color: 'rgba(139, 124, 179, 0.15)', type: 'dashed' } }
      },
      series: [{
        name: '题跋占比', type: 'line', data: yData,
        smooth: 0.4, symbol: 'circle', symbolSize: 10,
        animationDuration: 800,
        animationEasing: 'cubicOut',
        animationDelay: function (idx) {
          return idx * 60
        },
        lineStyle: {
          width: 3, color: '#9B7ED8',
          shadowColor: 'rgba(155, 126, 216, 0.5)', shadowBlur: 10, shadowOffsetY: 5
        },
        itemStyle: {
          color: '#fff', borderColor: '#9B7ED8', borderWidth: 3,
          shadowBlur: 8, shadowColor: 'rgba(155, 126, 216, 0.6)'
        },
        emphasis: {
          scale: 1.5,
          itemStyle: {
            color: '#9B7ED8', borderColor: '#fff', borderWidth: 3,
            shadowBlur: 15, shadowColor: 'rgba(155, 126, 216, 0.8)'
          }
        },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
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

// 监听 historyList 和 trendArtistFilter 变化
watch([analyticsData, () => props.historyList, trendArtistFilter], () => {
  updateTrendChart()
}, { deep: true })

function handleResize() {
  trendChart?.resize()
}

onMounted(() => {
  fetchArtistList()
  fetchAnalyticsData()
  window.addEventListener('resize', handleResize)
  updateTrendChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  trendChart = null
})

defineExpose({
  refreshStats: () => artistStatsCardRef.value?.refresh(),
  updateTrendChart,
  setArtistFilter: (artist) => {
    artistStatsCardRef.value?.setArtist?.(artist)
  }
})
</script>

<style src="../tiba/TibaAnalysis.css" scoped></style>

<style scoped>
.trend-card .card-header {
  flex-wrap: nowrap;
  white-space: nowrap;
}

.trend-card .card-header .card-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}
</style>
