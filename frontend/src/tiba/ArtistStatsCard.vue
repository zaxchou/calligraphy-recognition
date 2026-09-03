<template>
  <div class="stats-module">
    <div class="stats-header">
      <h3 class="stats-title">{{ displayArtistName }}题跋数据概览</h3>
      <el-select v-model="currentArtist" size="default" @change="onArtistChange" style="width: 120px;">
        <el-option value="all" label="全部作者" />
        <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
      </el-select>
    </div>

    <div class="stats-content" v-loading="loading">
      <div v-if="!loading && totalCount === 0" class="stats-empty">
        <el-icon size="48" color="#dcdfe6"><DataAnalysis /></el-icon>
        <p>暂无分析数据</p>
        <p class="empty-tip">上传画作后将自动生成统计数据</p>
      </div>

      <template v-else>
        <!-- 紧凑统计行 -->
        <div class="stat-bar">
          <div class="stat-bar-left">
            <div class="stat-total-group">
              <span class="stat-total-num">{{ displayTotalCount }}</span>
              <span class="stat-total-unit">幅</span>
            </div>
            <div class="stat-period-group">
              <span class="period-chip" v-if="periodStats.early">早 {{ periodStats.early }}</span>
              <span class="period-chip" v-if="periodStats.mid">中 {{ periodStats.mid }}</span>
              <span class="period-chip" v-if="periodStats.late">晚 {{ periodStats.late }}</span>
              <span class="period-chip chip-unknown" v-if="periodStats.unknown">未分 {{ periodStats.unknown }}</span>
            </div>
          </div>
          <div class="stat-bar-center">
            <div class="stat-words">
              <span class="stat-words-label">字数</span>
              <span class="stat-words-value">最低 {{ charStatsOverall.min }}</span>
              <span class="stat-words-sep">·</span>
              <span class="stat-words-value">平均 {{ charStatsOverall.avg }}</span>
              <span class="stat-words-sep">·</span>
              <span class="stat-words-value">最高 {{ charStatsOverall.max }}</span>
            </div>
          </div>
          <div class="stat-bar-right">
            <div class="stat-sentiment" v-if="sentimentBars.length">
              <span
                v-for="(bar, i) in sentimentBars"
                :key="i"
                class="sentiment-chip"
                :style="{ '--chip-color': bar.color }"
              >
                <span class="sentiment-chip-dot" :style="{ background: bar.color }"></span>
                {{ bar.label }} {{ bar.percent }}%
              </span>
            </div>
          </div>
        </div>

        <!-- 图表行 -->
        <div class="chart-row">
          <div class="chart-col">
            <div class="chart-col-label">主题 × 题跋面积</div>
            <div ref="themeBarChartRef" class="chart-col-canvas"></div>
          </div>
          <div class="chart-col">
            <div class="chart-col-label">分期 × 题跋面积</div>
            <div ref="periodTrendChartRef" class="chart-col-canvas"></div>
          </div>
        </div>

        <!-- 主题占比 + 洞察 行 -->
        <div class="bottom-row">
          <div class="theme-bar-compact">
            <div class="theme-bar-compact-label">主题占比</div>
            <div class="theme-bar-compact-body">
              <div v-for="(item, i) in topThemes" :key="i" class="theme-bar-compact-row">
                <span class="tbc-label theme-link" @click="navigateToTheme(item.name)">{{ item.name }}</span>
                <div class="tbc-track">
                  <div
                    class="tbc-fill"
                    :style="{ width: item.percent + '%', background: themeColors[i % themeColors.length] }"
                  ></div>
                </div>
                <span class="tbc-value">{{ item.count }}<span class="tbc-pct">({{ item.percent }}%)</span></span>
              </div>
            </div>
          </div>
          <div class="insight-compact" v-if="areaThemeData.insights.length">
            <div class="insight-headline" v-for="(insight, idx) in areaThemeData.insights" :key="idx">
              <span class="headline-marker">{{ ['壹', '贰'][idx] }}</span>
              <span v-html="boldNumbers(insight)"></span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'
import echarts from '../utils/echarts'

const emit = defineEmits(['artist-change'])

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

// ── 作者列表 ──
const artistList = ref([])
const currentArtist = ref('李鱓')

const displayArtistName = computed(() => {
  return currentArtist.value === 'all' ? '全部' : currentArtist.value
})

async function fetchArtistList() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

// ── 统计数据 ──
const loading = ref(false)
const totalCount = ref(0)
const displayTotalCount = ref(0)
const themeDistribution = ref([])
const sentimentDistribution = ref([])
const periodDistribution = ref([])
let totalCountRafId = null

const themeColors = ['#c96442', '#a65d3f', '#547a8c', '#8b6f8e', '#4a4a5a', '#b8a47e']
const sentimentColors = { positive: '#c96442', neutral: '#9090A0', negative: '#3A3A3A', '积极': '#c96442', '中性': '#9090A0', '消极': '#3A3A3A' }
const sentimentLabels = { positive: '积极', neutral: '中性', negative: '消极', '积极': '积极', '中性': '中性', '消极': '消极' }

const periodStats = computed(() => {
  const map = { early: 0, mid: 0, late: 0, unknown: 0 }
  for (const item of periodDistribution.value) {
    if (item.period === '早期') map.early = item.count
    else if (item.period === '中期') map.mid = item.count
    else if (item.period === '晚期') map.late = item.count
    else if (item.period === '年代不详') map.unknown = item.count
  }
  return map
})

const ALL_THEMES = ['咏物寄兴', '身世自况', '交游赠答', '吉语祥瑞', '画理自叙', '时事讽喻']

const topThemes = computed(() => {
  // 用6个固定主题构建，API返回的数据填充count，未命中=0
  const themeMap = {}
  for (const item of themeDistribution.value) {
    themeMap[item.theme_name || item.name] = item.count || 0
  }
  return ALL_THEMES.map(name => ({
    name,
    count: themeMap[name] || 0,
    percent: totalCount.value > 0 ? Math.round(((themeMap[name] || 0) / totalCount.value) * 100) : 0
  })).sort((a, b) => b.count - a.count)
})

const charStatsOverall = computed(() => {
  const ps = periodDistribution.value
  if (!ps || ps.length === 0) return { min: 0, avg: 0, max: 0, totalChars: 0, totalInscriptions: 0 }
  let totalChars = 0
  let totalCount = 0
  let globalMin = Infinity
  let globalMax = 0
  for (const p of ps) {
    const cnt = p.count || 0
    totalCount += cnt
    totalChars += Math.round((p.avg_char_count || 0) * cnt)
    if (p.min_char_count > 0 && p.min_char_count < globalMin) globalMin = p.min_char_count
    if (p.max_char_count > globalMax) globalMax = p.max_char_count
  }
  return {
    min: globalMin === Infinity ? 0 : globalMin,
    avg: totalCount > 0 ? Math.round(totalChars / totalCount) : 0,
    max: globalMax,
    totalChars,
    totalInscriptions: totalCount
  }
})

const sentimentItems = computed(() => {
  const total = sentimentDistribution.value.reduce((sum, item) => sum + item.count, 0)
  return sentimentDistribution.value.map(item => ({
    key: item.key,
    count: item.count,
    percent: total > 0 ? Math.round((item.count / total) * 100) : 0
  }))
})

const sentimentBars = computed(() => {
  return sentimentItems.value.map(item => ({
    label: sentimentLabels[item.key],
    percent: item.percent,
    color: sentimentColors[item.key]
  }))
})

function animateTotalCount(target, duration = 900) {
  if (totalCountRafId) cancelAnimationFrame(totalCountRafId)
  const start = displayTotalCount.value
  const startTime = performance.now()
  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    displayTotalCount.value = Math.round(start + (target - start) * eased)
    if (progress < 1) totalCountRafId = requestAnimationFrame(step)
  }
  totalCountRafId = requestAnimationFrame(step)
}

async function fetchStats() {
  loading.value = true
  try {
    const resp = await fetch(`${API_BASE}/content-analysis/stats?artist=${encodeURIComponent(currentArtist.value)}`)
    const data = await resp.json()
    if (data.total_count !== undefined) {
      totalCount.value = data.total_count
      const themeMap = {}
      for (const item of (data.theme_distribution || [])) {
        if (!themeMap[item.theme_name]) themeMap[item.theme_name] = 0
        themeMap[item.theme_name] += item.count
      }
      themeDistribution.value = Object.entries(themeMap).map(([name, count]) => ({ name, count }))
      const sentimentMap = {}
      for (const item of (data.sentiment_distribution || [])) {
        if (!sentimentMap[item.polarity]) sentimentMap[item.polarity] = 0
        sentimentMap[item.polarity] += item.count
      }
      sentimentDistribution.value = Object.entries(sentimentMap).map(([key, count]) => ({ key, count }))
      periodDistribution.value = data.period_stats || []
      animateTotalCount(totalCount.value)
    } else {
      totalCount.value = 0
      themeDistribution.value = []
      sentimentDistribution.value = []
      periodDistribution.value = []
    }
  } catch (e) {
    console.error('加载统计数据失败:', e)
    totalCount.value = 0
    themeDistribution.value = []
    sentimentDistribution.value = []
    periodDistribution.value = []
  } finally {
    loading.value = false
  }
}

function onArtistChange() {
  fetchStats()
  fetchAreaThemeStats()
  emit('artist-change', currentArtist.value)
}

function navigateToTheme(themeName) {
  window.location.href = `/#/content-analysis?theme=${encodeURIComponent(themeName)}`
}

function boldNumbers(text) {
  return text.replace(/(\d+[\.\d]*%?)/g, '<strong>$1</strong>')
}

// ── 内容×空间 图表 ──
const themeBarChartRef = ref(null)
const periodTrendChartRef = ref(null)
let themeBarChart = null
let periodTrendChart = null

const areaThemeData = ref({ sample_total: 0, theme_area: [], period_trend: [], insights: [] })

async function fetchAreaThemeStats() {
  try {
    const artist = currentArtist.value === 'all' ? 'all' : currentArtist.value
    const res = await fetch(`${API_BASE}/content-analysis/area-theme-stats?artist=${encodeURIComponent(artist)}`)
    const data = await res.json()
    areaThemeData.value = {
      sample_total: data.sample_total || 0,
      theme_area: data.theme_area || [],
      period_trend: (data.period_trend || []).filter(p => p.period !== '未分期' && p.period !== '年代不详'),
      insights: data.insights || [],
    }
    nextTick(() => {
      renderThemeBarChart()
      renderPeriodTrendChart()
    })
  } catch (e) {
    console.error('获取内容×空间数据失败', e)
  }
}

function renderThemeBarChart() {
  if (!themeBarChartRef.value || !areaThemeData.value.theme_area.length) return
  if (!themeBarChart) themeBarChart = echarts.init(themeBarChartRef.value)
  const items = areaThemeData.value.theme_area
  const chartColors = ['#c96442', '#b8a47e', '#6B5B95', '#4ecdc4', '#667eea', '#ff6b6b']
  themeBarChart.setOption({
    animation: true, animationDuration: 600,
    grid: { left: '3%', right: '12%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category', data: items.map(i => i.theme),
      axisLabel: { color: '#8a8070', fontSize: 10, interval: 0, rotate: items.length > 4 ? 20 : 0 },
      axisLine: { show: false }, axisTick: { show: false },
    },
    yAxis: {
      type: 'value', name: '面积(%)', nameTextStyle: { color: '#8a8070', fontSize: 10 },
      axisLabel: { color: '#8a8070', fontSize: 10, formatter: '{value}%' },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: 'rgba(139,124,179,0.12)', type: 'dashed' } },
    },
    series: [{
      type: 'bar',
      data: items.map((i, idx) => ({
        value: i.avg_area,
        itemStyle: { color: chartColors[idx % chartColors.length], borderRadius: [4, 4, 0, 0] },
      })),
      barWidth: '50%',
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 10, color: '#666' },
    }],
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const d = params[0]; const item = items[d.dataIndex]
        return `<b>${item.theme}</b><br/>平均面积: ${item.avg_area}%<br/>样本: ${item.n}幅<br/>平均词数: ${item.avg_words}`
      },
    },
  }, true)
}

function renderPeriodTrendChart() {
  if (!periodTrendChartRef.value || !areaThemeData.value.period_trend.length) return
  if (!periodTrendChart) periodTrendChart = echarts.init(periodTrendChartRef.value)
  const items = areaThemeData.value.period_trend
  periodTrendChart.setOption({
    animation: true, animationDuration: 600,
    grid: { left: '3%', right: '8%', bottom: '3%', top: '12%', containLabel: true },
    xAxis: {
      type: 'category', data: items.map(i => i.period),
      axisLabel: { color: '#8a8070', fontSize: 11 },
      axisLine: { lineStyle: { color: '#d1cfc5' } }, axisTick: { show: false },
    },
    yAxis: {
      type: 'value', name: '面积(%)', nameTextStyle: { color: '#8a8070', fontSize: 10 },
      axisLabel: { color: '#8a8070', fontSize: 10, formatter: '{value}%' },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: 'rgba(139,124,179,0.12)', type: 'dashed' } },
    },
    series: [{
      type: 'line', data: items.map(i => i.avg_area),
      smooth: 0.3, symbol: 'circle', symbolSize: 10,
      lineStyle: { width: 2.5, color: '#c96442' },
      itemStyle: { color: '#c96442', borderColor: '#fff', borderWidth: 2 },
      label: { show: true, position: 'top', formatter: (p) => `${p.value}%`, fontSize: 10, color: '#c96442', fontWeight: 600 },
      areaStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(201,100,66,0.3)' }, { offset: 1, color: 'rgba(201,100,66,0.02)' }] },
      },
    }],
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const d = params[0]; const item = items[d.dataIndex]
        return `<b>${item.period}</b><br/>平均面积: ${item.avg_area}%<br/>样本: ${item.n}幅`
      },
    },
  }, true)
}

// ── 生命周期 ──
function handleResize() {
  themeBarChart?.resize()
  periodTrendChart?.resize()
}

onMounted(() => {
  fetchArtistList()
  fetchStats()
  fetchAreaThemeStats()
  window.addEventListener('resize', handleResize)
})

watch(currentArtist, () => {
  fetchAreaThemeStats()
})

defineExpose({
  refresh: fetchStats,
  setArtist: (artist) => {
    if (currentArtist.value !== artist) {
      currentArtist.value = artist
      fetchStats()
      fetchAreaThemeStats()
      emit('artist-change', artist)
    }
  }
})
</script>

<style scoped>
.stats-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.stats-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  letter-spacing: 0.02em;
}
.stats-module {
  min-height: 200px;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.stats-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: transparent;
}
.stats-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 380px;
  color: #999;
  text-align: center;
  gap: 8px;
}
.stats-empty .empty-tip {
  font-size: 12px;
  color: #ccc;
  margin-top: 4px;
}

/* ── 紧凑统计行 ── */
.stat-bar {
  display: flex;
  align-items: center;
  background: #faf8f4;
  border: 1px solid #e8e6e0;
  border-radius: 10px;
  padding: 10px 16px;
  gap: 16px;
  flex-wrap: wrap;
}
.stat-bar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.stat-total-group {
  display: flex;
  align-items: baseline;
  gap: 2px;
}
.stat-total-num {
  font-size: 28px;
  font-weight: 800;
  color: #c96442;
  font-family: 'Noto Serif SC', serif;
  line-height: 1;
}
.stat-total-unit {
  font-size: 13px;
  color: #b0a090;
  margin-left: 2px;
}
.stat-period-group {
  display: flex;
  gap: 6px;
}
.period-chip {
  font-size: 11px;
  color: #6a5a48;
  background: #ede8e0;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
}
.chip-unknown {
  color: #9a8a78;
}
.stat-bar-center {
  flex: 1;
  min-width: 0;
}
.stat-words {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
  flex-wrap: wrap;
}
.stat-words-label {
  color: #9a8a78;
  margin-right: 2px;
}
.stat-words-value {
  font-weight: 600;
  color: #4a3a28;
}
.stat-words-sep {
  color: #d0c8b8;
}
.stat-bar-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.stat-sentiment {
  display: flex;
  gap: 8px;
}
.sentiment-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #5a5a5a;
  white-space: nowrap;
}
.sentiment-chip-dot {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* ── 图表行 ── */
.chart-row {
  display: flex;
  gap: 16px;
}
.chart-col {
  flex: 1;
  min-width: 0;
  background: #ffffff;
  border: 1px solid #e8e6e0;
  border-radius: 10px;
  padding: 10px 12px 6px;
}
.chart-col-label {
  font-size: 12px;
  font-weight: 600;
  color: #8a8070;
  margin-bottom: 4px;
  letter-spacing: 0.04em;
}
.chart-col-canvas {
  width: 100%;
  height: 180px;
}

/* ── 底部行：主题占比 + 洞察 ── */
.bottom-row {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.theme-bar-compact {
  flex: 0 0 62%;
  background: #ffffff;
  border: 1px solid #e8e6e0;
  border-radius: 10px;
  padding: 12px 16px;
  min-width: 0;
}
.theme-bar-compact-label {
  font-size: 12px;
  font-weight: 600;
  color: #8a8070;
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}
.theme-bar-compact-body {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.theme-bar-compact-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tbc-label {
  width: 80px;
  font-size: 11px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}
.theme-link {
  cursor: pointer;
  transition: color 0.2s;
}
.theme-link:hover {
  color: #c96442;
}
.tbc-track {
  flex: 1;
  height: 10px;
  background: #f0ede8;
  border-radius: 4px;
  overflow: hidden;
}
.tbc-fill {
  height: 100%;
  border-radius: 4px;
  min-width: 4px;
  transform-origin: left;
  animation: barGrow 0.6s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
}
.tbc-value {
  width: 80px;
  font-size: 11px;
  font-weight: 600;
  color: #3a3a3a;
  text-align: right;
  flex-shrink: 0;
}
.tbc-pct {
  font-weight: 400;
  color: #aaa;
  margin-left: 2px;
}
@keyframes barGrow {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

.insight-compact {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  background: #faf9f7;
  border: 1px solid #e8e4da;
  border-radius: 10px;
  padding: 20px 22px;
  min-width: 0;
}
.insight-headline {
  font-size: 14px;
  font-weight: 400;
  color: #2a2a2a;
  line-height: 1.5;
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}
.headline-marker {
  font-size: 14px;
  font-weight: 800;
  color: #c96442;
  flex-shrink: 0;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}

@media (max-width: 900px) {
  .chart-row {
    flex-direction: column;
  }
  .chart-col-canvas {
    height: 150px;
  }
  .bottom-row {
    flex-direction: column;
  }
  .theme-bar-compact {
    flex: 1;
  }
  .stat-bar {
    flex-direction: column;
    align-items: flex-start;
  }
  .stat-bar-center {
    width: 100%;
  }
}
</style>
