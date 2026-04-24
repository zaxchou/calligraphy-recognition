<template>
  <div class="stats-module">
    <!-- 页面标题栏 -->
    <div class="stats-header">
      <h3 class="stats-title">{{ displayArtistName }}题跋数据概览</h3>
      <el-select v-model="currentArtist" size="default" @change="onArtistChange" style="width: 120px;">
        <el-option value="all" label="全部作者" />
        <el-option
          v-for="artist in artistList"
          :key="artist"
          :label="artist"
          :value="artist"
        />
      </el-select>
    </div>

    <div class="stats-content" v-loading="loading">
      <!-- 空状态 -->
      <div v-if="!loading && totalCount === 0" class="stats-empty">
        <el-icon size="48" color="#dcdfe6"><DataAnalysis /></el-icon>
        <p>暂无分析数据</p>
        <p class="empty-tip">上传画作后将自动生成统计数据</p>
      </div>

      <!-- 三块独立卡片 -->
      <div v-else class="stats-cards-row">

        <!-- 卡片1：总量 -->
        <div class="stat-card stat-card-total">
          <div class="card-inner">
            <div class="card-label">收录画作总数</div>
            <div class="card-big-num">{{ displayTotalCount }}</div>
            <div class="card-sub">幅</div>
            <div class="card-divider"></div>
            <div class="card-meta">
              <span class="meta-item">
                <span class="meta-num">{{ periodStats.early }}</span>
                <span class="meta-label">早期</span>
              </span>
              <span class="meta-sep">·</span>
              <span class="meta-item">
                <span class="meta-num">{{ periodStats.mid }}</span>
                <span class="meta-label">中期</span>
              </span>
              <span class="meta-sep">·</span>
              <span class="meta-item">
                <span class="meta-num">{{ periodStats.late }}</span>
                <span class="meta-label">晚期</span>
              </span>
              <span v-if="periodStats.unknown > 0" class="meta-sep">·</span>
              <span v-if="periodStats.unknown > 0" class="meta-item">
                <span class="meta-num">{{ periodStats.unknown }}</span>
                <span class="meta-label">年代不详</span>
              </span>
            </div>
          </div>
        </div>

        <!-- 卡片2：题跋字数统计 -->
        <div class="stat-card">
          <div class="card-inner">
            <div class="card-section-title">题跋字数</div>
            <div class="char-stats-area" :key="barsKey + '-char'">
              <div class="char-bars">
                <div class="char-bar-group" v-for="(bar, i) in charStatBars" :key="i">
                  <div class="char-bar-label">{{ bar.label }}</div>
                  <div class="char-bar-track">
                    <div
                      class="char-bar-fill"
                      :style="{
                        width: bar.percent + '%',
                        background: bar.color
                      }"
                    ></div>
                  </div>
                  <div class="char-bar-value">{{ bar.value }}<span class="char-bar-unit">字</span></div>
                </div>
              </div>
              <div class="char-stats-meta">
                <span class="char-meta-item">
                  <span class="char-meta-num">{{ charStatsOverall.totalChars }}</span>
                  <span class="char-meta-label">总字数</span>
                </span>
                <span class="char-meta-sep">·</span>
                <span class="char-meta-item">
                  <span class="char-meta-num">{{ charStatsOverall.totalInscriptions }}</span>
                  <span class="char-meta-label">题跋条数</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 卡片3：情感极性 -->
        <div class="stat-card">
          <div class="card-inner">
            <div class="card-section-title">情感极性</div>
            <div class="sentiment-bars-area" :key="barsKey + '-sentiment'">
              <div class="sentiment-bars">
                <div class="sentiment-bar-group" v-for="(bar, i) in sentimentBars" :key="i">
                  <div class="sentiment-bar-label">{{ bar.label }}</div>
                  <div class="sentiment-bar-track">
                    <div
                      class="sentiment-bar-fill"
                      :style="{
                        width: bar.percent + '%',
                        background: bar.color
                      }"
                    ></div>
                  </div>
                  <div class="sentiment-bar-value">{{ bar.percent }}<span class="sentiment-bar-unit">%</span></div>
                </div>
              </div>
              <div class="sentiment-bars-meta">
                <div v-for="item in sentimentItems" :key="item.key" class="sentiment-meta-chip">
                  <span class="sentiment-meta-dot" :style="{ background: sentimentColors[item.key] }"></span>
                  <span class="sentiment-meta-label">{{ sentimentLabels[item.key] }}</span>
                  <span class="sentiment-meta-count">{{ item.count }}条</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- 主题占比条形图（单独一行） -->
      <div v-if="!loading && totalCount > 0" class="theme-bars-section" :key="barsKey">
        <div class="bars-header">主题占比</div>
        <div class="bars-row">
          <div v-for="(item, i) in topThemes" :key="i" class="bar-row">
            <span class="bar-label theme-link" @click="navigateToTheme(item.name)">{{ item.name }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{
                  width: item.percent + '%',
                  background: themeColors[i % themeColors.length]
                }"
              ></div>
            </div>
            <span class="bar-value">{{ item.count }}<span class="bar-pct">({{ item.percent }}%)</span></span>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'

const emit = defineEmits(['artist-change'])

const artistList = ref([])
const currentArtist = ref('李鱓')

// 标题显示名：all → 全部，其他显示画家名
const displayArtistName = computed(() => {
  return currentArtist.value === 'all' ? '全部' : currentArtist.value
})

// 从 API 动态获取作者列表
async function fetchArtistList() {
  try {
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

// 数据
const loading = ref(false)
const totalCount = ref(0)
const displayTotalCount = ref(0) // 动画显示用的计数
const themeDistribution = ref([])   // [{ theme_name, count }]
const sentimentDistribution = ref([]) // [{ polarity, count }] (已按polarity聚合)
const periodDistribution = ref([])  // [{ period, count }]
const barsKey = ref(0) // 主题占比区域 key，变化时强制重建以触发动画
let totalCountRafId = null // 数字动画 requestAnimationFrame id

// 颜色配置
const themeColors = ['#c96442', '#a65d3f', '#547a8c', '#8b6f8e', '#4a4a5a', '#b8a47e']
const sentimentColors = {
  positive: '#c96442',
  neutral: '#9090A0',
  negative: '#3A3A3A'
}
const sentimentLabels = {
  positive: '积极',
  neutral: '中性',
  negative: '消极'
}

const circumference = 2 * Math.PI * 46 // ≈ 289
const circumference2 = 2 * Math.PI * 62 // ≈ 390（用于更大的环形图）

// 分期统计
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

// 主题排行（取全部，按数量降序）
const topThemes = computed(() => {
  return [...themeDistribution.value]
    .sort((a, b) => b.count - a.count)
    .map(item => ({
      ...item,
      percent: totalCount.value > 0 ? Math.round((item.count / totalCount.value) * 100) : 0
    }))
})

// 题跋字数统计（从 period_stats 聚合整体 min/avg/max）
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

// 字数柱状图数据
const charStatBars = computed(() => {
  const s = charStatsOverall.value
  const maxVal = Math.max(s.max, 1)
  return [
    { label: '最低', value: s.min, percent: (s.min / maxVal) * 100, color: '#b8a47e' },
    { label: '平均', value: s.avg, percent: (s.avg / maxVal) * 100, color: '#c96442' },
    { label: '最高', value: s.max, percent: 100, color: '#8b6f8e' }
  ]
})

// 情感饼图 segments（纯饼图，无中心数字）
const sentimentPieSegments = computed(() => {
  const total = sentimentDistribution.value.reduce((sum, item) => sum + item.count, 0)
  if (!total) return []
  let accumulated = 0
  return sentimentDistribution.value.map(item => {
    const dash = (item.count / total) * circumference2
    const offset = -(accumulated / total) * circumference2
    accumulated += item.count
    return {
      dash,
      offset,
      color: sentimentColors[item.key] || '#ccc'
    }
  })
})

// 情感列表（含百分比）
const sentimentItems = computed(() => {
  const total = sentimentDistribution.value.reduce((sum, item) => sum + item.count, 0)
  return sentimentDistribution.value.map(item => ({
    key: item.key,
    count: item.count,
    percent: total > 0 ? Math.round((item.count / total) * 100) : 0
  }))
})

// 情感柱状图数据
const sentimentBars = computed(() => {
  return sentimentItems.value.map(item => ({
    label: sentimentLabels[item.key],
    percent: item.percent,
    color: sentimentColors[item.key]
  }))
})

// 数字递增动画
function animateTotalCount(target, duration = 900) {
  if (totalCountRafId) cancelAnimationFrame(totalCountRafId)
  const start = displayTotalCount.value
  const startTime = performance.now()

  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    // easeOutCubic
    const eased = 1 - Math.pow(1 - progress, 3)
    displayTotalCount.value = Math.round(start + (target - start) * eased)
    if (progress < 1) {
      totalCountRafId = requestAnimationFrame(step)
    }
  }
  totalCountRafId = requestAnimationFrame(step)
}

async function fetchStats() {
  loading.value = true
  try {
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'
    const resp = await fetch(`${API_BASE}/content-analysis/stats?artist=${encodeURIComponent(currentArtist.value)}`)
    const data = await resp.json()
    if (data.total_count !== undefined) {
      totalCount.value = data.total_count

      // 主题分布：直接使用
      themeDistribution.value = (data.theme_distribution || []).map(item => ({
        name: item.theme_name,
        count: item.count
      }))

      // 主题分布：API 按 period 分组返回，需按 theme_name 合并去重
      const themeMap = {}
      for (const item of (data.theme_distribution || [])) {
        if (!themeMap[item.theme_name]) {
          themeMap[item.theme_name] = 0
        }
        themeMap[item.theme_name] += item.count
      }
      themeDistribution.value = Object.entries(themeMap).map(([name, count]) => ({ name, count }))

      // 情感分布：按 polarity 聚合（原始数据按 period 分组）
      const sentimentMap = {}
      for (const item of (data.sentiment_distribution || [])) {
        if (!sentimentMap[item.polarity]) {
          sentimentMap[item.polarity] = 0
        }
        sentimentMap[item.polarity] += item.count
      }
      sentimentDistribution.value = Object.entries(sentimentMap).map(([key, count]) => ({ key, count }))

      // 分期分布（API 字段名是 period_stats）
      periodDistribution.value = data.period_stats || []

      // 大数字递增动画 + 柱状图重建动画
      animateTotalCount(totalCount.value)
      barsKey.value++
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
  emit('artist-change', currentArtist.value)
}

function navigateToTheme(themeName) {
  window.location.href = `/#/content-analysis?theme=${encodeURIComponent(themeName)}`
}

onMounted(() => {
  fetchArtistList()
  fetchStats()
})

// 暴露刷新方法
defineExpose({ 
  refresh: fetchStats,
  setArtist: (artist) => {
    if (currentArtist.value !== artist) {
      currentArtist.value = artist
      fetchStats()
      emit('artist-change', artist)
    }
  }
})
</script>

<style scoped>
/* ─── 页面标题栏 ─── */
.stats-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  height: 32px;
}

.stats-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  letter-spacing: 0.02em;
}

/* ─── 内容区 ─── */
.stats-module {
  min-height: 320px;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.stats-content {
  min-height: 280px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* ─── 空状态 ─── */
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

/* ─── 三卡片行 ─── */
.stats-cards-row {
  display: flex;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 16px;
  flex: 1;
}

/* ─── 独立卡片通用 ─── */
.stat-card {
  background: #ffffff;
  border: 1px solid #e8e6e0;
  border-radius: 12px;
  padding: 16px;
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  transition: box-shadow 0.2s ease;
}

.stat-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.07);
}

.card-inner {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* 环形图卡片的内容从顶部开始 */
.stat-card:not(.stat-card-total) .card-inner {
  align-items: flex-start;
}

/* ─── 卡片1：总量 ─── */
.stat-card-total {
  background: linear-gradient(145deg, #faf8f4 0%, #f0ece4 100%);
  border-color: #e0d9ce;
  justify-content: center;
}

.card-label {
  font-size: 12px;
  color: #8a8070;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.card-big-num {
  font-size: clamp(40px, 5.5vw, 64px);
  font-weight: 800;
  color: #c96442;
  line-height: 1;
  font-family: 'Noto Serif SC', serif;
  letter-spacing: -0.02em;
}

.card-sub {
  font-size: 14px;
  color: #b0a090;
  margin-top: 4px;
  margin-bottom: 12px;
}

.card-divider {
  width: 36px;
  height: 1px;
  background: #d0c8b8;
  margin-bottom: 12px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #8a8070;
}

.meta-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.meta-num {
  font-size: 18px;
  font-weight: 700;
  color: #5a4a38;
  line-height: 1;
}

.meta-label {
  font-size: 11px;
  color: #9a8a78;
}

.meta-sep {
  color: #c0b8a8;
  margin-bottom: 8px;
  font-size: 14px;
}

/* ─── 卡片标题 ─── */
.card-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #4a4a4a;
  letter-spacing: 0.04em;
  margin-bottom: 14px;
  align-self: flex-start;
}

/* ─── 题跋字数统计 ─── */
.char-stats-area {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.char-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.char-bar-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.char-bar-label {
  width: 36px;
  font-size: 12px;
  color: #888;
  text-align: right;
  flex-shrink: 0;
}

.char-bar-track {
  flex: 1;
  height: 22px;
  background: #f5f3ee;
  border-radius: 6px;
  overflow: hidden;
}

.char-bar-fill {
  height: 100%;
  border-radius: 6px;
  min-width: 4px;
  transform-origin: left;
  animation: barGrow 0.8s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
}

.char-bar-value {
  width: 60px;
  font-size: 15px;
  font-weight: 700;
  color: #2a2a2a;
  font-family: 'Noto Serif SC', serif;
  text-align: right;
  flex-shrink: 0;
}

.char-bar-unit {
  font-size: 11px;
  font-weight: 400;
  color: #aaa;
  margin-left: 2px;
}

.char-stats-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding-top: 10px;
  border-top: 1px solid #f0ede8;
}

.char-meta-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.char-meta-num {
  font-size: 16px;
  font-weight: 700;
  color: #5a4a38;
  font-family: 'Noto Serif SC', serif;
}

.char-meta-label {
  font-size: 11px;
  color: #9a8a78;
}

.char-meta-sep {
  color: #d0c8b8;
  font-size: 11px;
}

/* ─── 情感极性柱状图 ─── */
.sentiment-bars-area {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sentiment-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sentiment-bar-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sentiment-bar-label {
  width: 36px;
  font-size: 12px;
  color: #888;
  text-align: right;
  flex-shrink: 0;
}

.sentiment-bar-track {
  flex: 1;
  height: 22px;
  background: #f5f3ee;
  border-radius: 6px;
  overflow: hidden;
}

.sentiment-bar-fill {
  height: 100%;
  border-radius: 6px;
  min-width: 4px;
  transform-origin: left;
  animation: barGrow 0.8s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
}

.sentiment-bar-value {
  width: 50px;
  font-size: 15px;
  font-weight: 700;
  color: #2a2a2a;
  font-family: 'Noto Serif SC', serif;
  text-align: right;
  flex-shrink: 0;
}

.sentiment-bar-unit {
  font-size: 11px;
  font-weight: 400;
  color: #aaa;
  margin-left: 2px;
}

.sentiment-bars-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid #f0ede8;
}

.sentiment-meta-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #555;
  white-space: nowrap;
}

.sentiment-meta-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.sentiment-meta-label {
  color: #4a4a4a;
}

.sentiment-meta-count {
  color: #aaa;
}

/* ─── 主题占比条形图 ─── */
.theme-bars-section {
  background: #ffffff;
  border: 1px solid #e8e6e0;
  border-radius: 12px;
  padding: 21px;
}

.bars-header {
  font-size: 13px;
  font-weight: 600;
  color: #4a4a4a;
  letter-spacing: 0.04em;
  margin-bottom: 14px;
}

.bars-row {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  width: 120px;
  font-size: 12px;
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

.bar-track {
  flex: 1;
  height: 14px;
  background: #f0ede8;
  border-radius: 5px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 5px;
  min-width: 6px;
  transform-origin: left;
  animation: barGrow 0.9s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
}

@keyframes barGrow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

.bar-value {
  width: 70px;
  font-size: 12px;
  font-weight: 700;
  color: #3a3a3a;
  text-align: right;
  flex-shrink: 0;
}

.bar-pct {
  font-weight: 400;
  color: #aaa;
  margin-left: 3px;
  font-size: 11px;
}
</style>
