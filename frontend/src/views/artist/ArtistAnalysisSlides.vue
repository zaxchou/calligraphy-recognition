<template>
  <div class="slides" @keydown="onKey" tabindex="0" ref="slidesRef">
    <!-- 顶部导航 -->
    <header class="slides-header">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="slides-back">← {{ artistName }}</router-link>
      <span class="slides-title">{{ slides[currentSlide]?.title }}</span>
      <span class="slides-page">{{ currentSlide + 1 }} / {{ slides.length }}</span>
    </header>

    <!-- 进度条 -->
    <div class="slides-progress">
      <div class="slides-progress-fill" :style="{ width: ((currentSlide + 1) / slides.length * 100) + '%' }"></div>
    </div>

    <!-- Slide 内容 -->
    <div class="slides-body">
      <div class="slide">
        <div class="slide-header">
          <h1 class="slide-title">{{ slides[currentSlide]?.title }}</h1>
          <p class="slide-subtitle">{{ slides[currentSlide]?.subtitle }}</p>
        </div>
        <div class="slide-charts" :class="slides[currentSlide]?.layout || 'two-col'">
          <div v-for="(chart, ci) in slides[currentSlide]?.charts" :key="ci" class="slide-chart-wrap">
            <h3 class="slide-chart-title">{{ chart.title }}</h3>
            <div :ref="el => setChartRef(el, currentSlide, ci)" class="slide-chart-area"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部控制 -->
    <footer class="slides-footer">
      <button class="slides-nav" @click="prev" :disabled="currentSlide === 0">‹ 上一页</button>
      <div class="slides-dots">
        <span v-for="(_, i) in slides" :key="i" class="slides-dot" :class="{ active: i === currentSlide }" @click="goTo(i)"></span>
      </div>
      <button class="slides-nav" @click="next" :disabled="currentSlide === slides.length - 1">下一页 ›</button>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts/core'
import { PieChart, BarChart, ScatterChart, RadarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, RadarComponent, MarkLineComponent } from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import { artistRulesApi } from '@/api'

echarts.use([PieChart, BarChart, ScatterChart, RadarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, RadarComponent, MarkLineComponent, LabelLayout, UniversalTransition, CanvasRenderer])

const route = useRoute()
const artistName = route.params.name
const API = import.meta.env.VITE_API_BASE || '/api/v1'

const slidesRef = ref(null)
const currentSlide = ref(0)
const chartRefs = {}
const chartInstances = {}

// 数据缓存
const statsData = ref(null)
const artistRules = ref(null)
const dimensionStats = ref(null)
const emotionRanking = ref(null)
const emotionTimeline = ref(null)
const loadedSlides = new Set()

const PERIOD_COLORS = { '早期': '#c96442', '中期': '#547a8c', '晚期': '#4a4a5a', '未分期': '#ccc' }
const THEME_COLOR_MAP = { '身世自况': '#c96442', '咏物寄兴': '#547a8c', '画理自叙': '#a65d3f', '时事讽喻': '#4a4a5a', '吉语祥瑞': '#8b6f8e', '交游赠答': '#b8a47e' }

const slides = [
  { id: 'overview', title: '概览', subtitle: '该画家题跋的整体画像：作品数量、时期分布、情感基线', layout: 'two-col',
    charts: [{ title: '基础数据' }, { title: '生命阶段' }],
    load: loadOverview, render: renderOverview },
  { id: 'sentiment', title: '情感分析', subtitle: '情感极性分布与一生情绪变化趋势', layout: 'two-col',
    charts: [{ title: '情感极性分布' }, { title: '情绪时间线' }],
    load: loadSentiment, render: renderSentiment },
  { id: 'theme', title: '主题分析', subtitle: '哪些主题最常见？各时期主题如何变化？', layout: 'two-col',
    charts: [{ title: '主题总体分布' }, { title: '主题分期对比' }],
    load: loadTheme, render: renderTheme },
  { id: 'style', title: '题跋风格', subtitle: '题跋长度和面积占比的变化规律', layout: 'two-col',
    charts: [{ title: '题跋字数分期对比' }, { title: '题跋面积分布' }],
    load: loadStyle, render: renderStyle },
  { id: 'dimension', title: '印章与维度', subtitle: '各维度情感贡献 + 关键印章的情感含义', layout: 'two-col',
    charts: [{ title: '引擎维度雷达图' }, { title: '印章情感规则' }],
    load: loadDimension, render: renderDimension },
  { id: 'ranking', title: '情感排行', subtitle: '情感最极端的作品，点击查看详情', layout: 'two-col',
    charts: [{ title: '最消极 Top 10' }, { title: '最积极 Top 10' }],
    load: loadRanking, render: renderRanking },
  { id: 'spatial', title: '空间与形式', subtitle: '画幅大小与题跋策略的关系', layout: 'two-col',
    charts: [{ title: '画幅 vs 题跋占比' }, { title: '题跋闯入率' }],
    load: loadSpatial, render: renderSpatial },
  { id: 'material', title: '画材与尺寸', subtitle: '常用画材和尺幅偏好', layout: 'two-col',
    charts: [{ title: '画材标签统计' }, { title: '作品尺寸分布' }],
    load: loadMaterial, render: renderMaterial },
]

function setChartRef(el, slideIdx, chartIdx) {
  const key = `${slideIdx}-${chartIdx}`
  if (el) {
    chartRefs[key] = el
  } else {
    // DOM 被销毁，清理旧 echarts 实例
    if (chartInstances[key]) {
      chartInstances[key].dispose()
      delete chartInstances[key]
    }
    delete chartRefs[key]
  }
}

function getChart(key) {
  const el = chartRefs[key]
  if (!el) return null
  // 如果实例还在但 DOM 已换（key 相同但元素不同），先销毁
  if (chartInstances[key] && chartInstances[key].getDom() !== el) {
    chartInstances[key].dispose()
    delete chartInstances[key]
  }
  if (chartInstances[key]) return chartInstances[key]
  const chart = echarts.init(el)
  chartInstances[key] = chart
  return chart
}

// ── 数据加载 ──
async function fetchStats() {
  if (statsData.value) return statsData.value
  const res = await fetch(`${API}/content-analysis/stats?artist=${encodeURIComponent(artistName)}`)
  statsData.value = await res.json()
  return statsData.value
}

async function fetchRules() {
  if (artistRules.value) return artistRules.value
  try {
    const res = await artistRulesApi.getByName(artistName)
    artistRules.value = res.rule || null
  } catch { artistRules.value = null }
  return artistRules.value
}

async function loadOverview() {
  await Promise.all([fetchStats(), fetchRules()])
}

async function loadSentiment() {
  await fetchStats()
  if (!emotionTimeline.value) {
    try {
      const res = await fetch(`${API}/content-analysis/emotion-timeline?artist=${encodeURIComponent(artistName)}`)
      const data = await res.json()
      if (data.success) emotionTimeline.value = data
    } catch {}
  }
}

async function loadTheme() { await fetchStats() }
async function loadStyle() { await fetchStats() }

async function loadDimension() {
  if (!dimensionStats.value) {
    try {
      const res = await fetch(`${API}/content-analysis/dimension-stats?artist=${encodeURIComponent(artistName)}`)
      const data = await res.json()
      if (data.success) dimensionStats.value = data.dimensions
    } catch {}
  }
  await fetchRules()
}

async function loadRanking() {
  if (!emotionRanking.value) {
    try {
      const res = await fetch(`${API}/content-analysis/emotion-ranking?artist=${encodeURIComponent(artistName)}&limit=10`)
      const data = await res.json()
      if (data.success) emotionRanking.value = data
    } catch {}
  }
}

async function loadSpatial() { await fetchStats() }
async function loadMaterial() { await fetchStats() }

// ── 渲染 ──
function renderOverview() {
  const s = statsData.value
  if (!s) return
  const c0 = getChart('0-0')
  if (c0) {
    const periods = (s.period_stats || []).map(p => ({ name: p.period || '未分期', value: p.count }))
    c0.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: ['40%', '70%'], data: periods.map(p => ({ ...p, itemStyle: { color: PERIOD_COLORS[p.name] || '#ccc' } })),
        label: { show: true, formatter: '{b}\n{c}幅 ({d}%)' } }]
    })
    c0.resize()
  }
  const c1 = getChart('0-1')
  if (c1 && artistRules.value?.life_stages) {
    const stages = artistRules.value.life_stages
    c1.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '10%', right: '5%', bottom: '15%', top: '10%' },
      xAxis: { type: 'category', data: stages.map(s => s.name) },
      yAxis: { type: 'value', name: 'mood_offset', min: -1, max: 1 },
      series: [{ type: 'bar', data: stages.map(s => ({
        value: s.mood_offset ?? 0,
        itemStyle: { color: (s.mood_offset ?? 0) > 0 ? '#67c23a' : (s.mood_offset ?? 0) < 0 ? '#f56c6c' : '#909399' }
      })), label: { show: true, position: 'top', formatter: p => (p.value > 0 ? '+' : '') + p.value.toFixed(1) } }]
    })
    c1.resize()
  }
}

function renderSentiment() {
  const s = statsData.value
  if (!s) return
  const c0 = getChart('1-0')
  if (c0) {
    const sentDist = s.sentiment_distribution || []
    const totals = {}
    sentDist.forEach(item => { const l = item.polarity === 'positive' ? '积极' : item.polarity === 'negative' ? '消极' : '中性'; totals[l] = (totals[l] || 0) + item.count })
    const colorMap = { '积极': '#4e8cff', '消极': '#ff6b35', '中性': '#7f7f7f' }
    c0.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: ['40%', '70%'], data: Object.entries(totals).map(([n, v]) => ({ name: n, value: v, itemStyle: { color: colorMap[n] } })),
        label: { show: true, formatter: '{b}\n{d}%' } }]
    })
    c0.resize()
  }
  const c1 = getChart('1-1')
  if (c1 && emotionTimeline.value?.points?.length) {
    const { points, trend } = emotionTimeline.value
    const groups = {}
    points.forEach(p => { const per = p.period_phase || '未分期'; if (!groups[per]) groups[per] = []; groups[per].push(p) })
    const series = Object.entries(groups).map(([per, pts]) => ({
      name: per, type: 'scatter', symbolSize: 8,
      itemStyle: { color: PERIOD_COLORS[per] || '#ccc', opacity: 0.8 },
      data: pts.map(p => [p.year, p.emotion_score])
    }))
    if (trend?.length >= 2) series.push({ name: '趋势', type: 'line', showSymbol: false, lineStyle: { color: '#c96442', width: 2, type: 'dashed' }, data: trend.map(t => [t.year, t.emotion_score]) })
    c1.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      grid: { left: '8%', right: '5%', bottom: '14%', top: '5%' },
      xAxis: { type: 'value', name: '年份' },
      yAxis: { type: 'value', name: '情感', min: -1, max: 1, axisLabel: { formatter: v => (v > 0 ? '+' : '') + (v * 100).toFixed(0) + '%' } },
      series
    })
    c1.resize()
  }
}

function renderTheme() {
  const s = statsData.value
  if (!s) return
  const c0 = getChart('2-0')
  if (c0) {
    const themeDist = s.theme_distribution || []
    const totals = {}
    themeDist.forEach(item => { totals[item.theme_name] = (totals[item.theme_name] || 0) + item.count })
    c0.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: ['40%', '70%'], data: Object.entries(totals).map(([n, v]) => ({ name: n, value: v, itemStyle: { color: THEME_COLOR_MAP[n] || '#909399' } })),
        label: { show: true, formatter: '{b}\n{d}%' } }]
    })
    c0.resize()
  }
  const c1 = getChart('2-1')
  if (c1) {
    const themeDist = s.theme_distribution || []
    const periodOrder = { '早期': 0, '中期': 1, '晚期': 2 }
    const periods = [...new Set(themeDist.map(t => t.period))].sort((a, b) => (periodOrder[a] ?? 9) - (periodOrder[b] ?? 9))
    const themes = Object.keys(THEME_COLOR_MAP)
    c1.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, type: 'scroll' },
      grid: { left: '3%', right: '4%', bottom: '18%', top: '5%', containLabel: true },
      xAxis: { type: 'category', data: periods },
      yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
      series: themes.map(t => ({ name: t, type: 'bar', stack: 'total', itemStyle: { color: THEME_COLOR_MAP[t] },
        data: periods.map(p => { const item = themeDist.find(d => d.period === p && d.theme_name === t); return item ? parseFloat(item.percentage.toFixed(1)) : 0 }) }))
    })
    c1.resize()
  }
}

function renderStyle() {
  const s = statsData.value
  if (!s) return
  const c0 = getChart('3-0')
  if (c0) {
    const periodOrder = { '早期': 0, '中期': 1, '晚期': 2 }
    const sorted = (s.period_stats || []).sort((a, b) => (periodOrder[a.period] ?? 9) - (periodOrder[b.period] ?? 9))
    c0.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: '8%', right: '5%', bottom: '14%', top: '5%', containLabel: true },
      xAxis: { type: 'category', data: sorted.map(p => p.period) },
      yAxis: { type: 'value', name: '字符数' },
      series: [
        { name: '平均', type: 'bar', itemStyle: { color: '#c96442' }, data: sorted.map(p => parseFloat(p.avg_char_count.toFixed(1))) },
        { name: '最长', type: 'bar', itemStyle: { color: '#a65d3f' }, data: sorted.map(p => p.max_char_count) }
      ]
    })
    c0.resize()
  }
  const c1 = getChart('3-1')
  if (c1) {
    const areaDist = s.area_distribution || []
    c1.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '10%', right: '5%', bottom: '15%', top: '5%', containLabel: true },
      xAxis: { type: 'category', data: areaDist.map(d => d.range), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '作品数' },
      series: [{ type: 'bar', data: areaDist.map(d => d.inscription_count), itemStyle: { color: '#c96442', borderRadius: [3, 3, 0, 0] }, barWidth: '60%' }]
    })
    c1.resize()
  }
}

function renderDimension() {
  const c0 = getChart('4-0')
  if (c0 && dimensionStats.value) {
    const dims = dimensionStats.value
    const labels = Object.keys(dims)
    const values = labels.map(l => Math.abs(dims[l].mean) * 100)
    const maxVal = Math.max(...values, 10)
    c0.setOption({
      radar: { indicator: labels.map(l => ({ name: l, max: maxVal })), shape: 'polygon' },
      series: [{ type: 'radar', data: [{ value: values, name: '情感强度',
        areaStyle: { color: 'rgba(201,100,66,0.15)' }, lineStyle: { color: '#c96442', width: 2 }, itemStyle: { color: '#c96442' } }] }]
    })
    c0.resize()
  }
  // 印章规则用 HTML 渲染（不用 echarts），在 chart area 外处理
}

function renderRanking() {
  if (!emotionRanking.value) return
  const c0 = getChart('5-0')
  if (c0) {
    const neg = (emotionRanking.value.top_negative || []).slice(0, 10).reverse()
    c0.setOption({
      grid: { left: '30%', right: '10%', bottom: '5%', top: '5%' },
      xAxis: { type: 'value', min: -1, max: 0, axisLabel: { formatter: v => v.toFixed(1) } },
      yAxis: { type: 'category', data: neg.map(i => i.title), axisLabel: { fontSize: 11, width: 100, overflow: 'truncate' } },
      series: [{ type: 'bar', data: neg.map(i => ({ value: i.emotion_score, itemStyle: { color: '#f56c6c' } })),
        label: { show: true, position: 'left', formatter: p => p.value.toFixed(2), fontSize: 11 } }]
    })
    c0.resize()
  }
  const c1 = getChart('5-1')
  if (c1) {
    const pos = (emotionRanking.value.top_positive || []).slice(0, 10).reverse()
    c1.setOption({
      grid: { left: '30%', right: '10%', bottom: '5%', top: '5%' },
      xAxis: { type: 'value', min: 0, max: 1, axisLabel: { formatter: v => v.toFixed(1) } },
      yAxis: { type: 'category', data: pos.map(i => i.title), axisLabel: { fontSize: 11, width: 100, overflow: 'truncate' } },
      series: [{ type: 'bar', data: pos.map(i => ({ value: i.emotion_score, itemStyle: { color: '#67c23a' } })),
        label: { show: true, position: 'right', formatter: p => '+' + p.value.toFixed(2), fontSize: 11 } }]
    })
    c1.resize()
  }
}

function renderSpatial() {
  const s = statsData.value
  if (!s) return
  const c0 = getChart('6-0')
  if (c0) {
    const corrData = s.area_size_correlation || []
    const groups = {}
    corrData.forEach(d => { const p = d.period || '未分期'; if (!groups[p]) groups[p] = []; groups[p].push(d) })
    c0.setOption({
      tooltip: { formatter: p => `${p.data?.title || ''}\n高${p.value[0]}cm\n题跋${p.value[1].toFixed(1)}%` },
      legend: { bottom: 0 },
      grid: { left: '10%', right: '5%', bottom: '14%', top: '5%', containLabel: true },
      xAxis: { type: 'value', name: '画幅高度 (cm)' },
      yAxis: { type: 'value', name: '题跋占比 (%)' },
      series: Object.entries(groups).map(([p, pts]) => ({
        name: p, type: 'scatter', symbolSize: 10,
        itemStyle: { color: PERIOD_COLORS[p] || '#ccc', opacity: 0.75 },
        data: pts.map(d => [d.artwork_height_cm, d.inscription_percent])
      }))
    })
    c0.resize()
  }
  const c1 = getChart('6-1')
  if (c1 && s.layout_form_distribution?.length) {
    const forms = s.layout_form_distribution.slice(0, 8)
    c1.setOption({
      grid: { left: '25%', right: '5%', bottom: '5%', top: '5%' },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: forms.map(f => f.form_name).reverse() },
      series: [{ type: 'bar', data: forms.map(f => f.count).reverse(), itemStyle: { color: '#547a8c' }, label: { show: true, position: 'right' } }]
    })
    c1.resize()
  }
}

function renderMaterial() {
  const s = statsData.value
  if (!s) return
  const c0 = getChart('7-0')
  if (c0) {
    const tags = (s.material_tags || []).slice(0, 10)
    c0.setOption({
      grid: { left: '25%', right: '5%', bottom: '5%', top: '5%' },
      xAxis: { type: 'value', name: '出现次数' },
      yAxis: { type: 'category', data: tags.map(t => t.tag).reverse() },
      series: [{ type: 'bar', data: tags.map(t => t.count).reverse(), itemStyle: { color: '#c96442' }, label: { show: true, position: 'right' } }]
    })
    c0.resize()
  }
  const c1 = getChart('7-1')
  if (c1) {
    // 尺寸数据需要从 size-stats 获取，先用 placeholder
    c1.setOption({ title: { text: '尺寸数据加载中...', left: 'center', top: 'center', textStyle: { color: '#999' } } })
    c1.resize()
  }
}

// ── 导航 ──
async function goTo(idx) {
  if (idx < 0 || idx >= slides.length) return
  currentSlide.value = idx
  await nextTick()
  const slide = slides[idx]
  // 每次进入 slide 都加载数据（如果还没加载）
  if (!loadedSlides.has(idx)) {
    await slide.load()
    loadedSlides.add(idx)
  }
  // DOM 每次切换都会重建，所以每次都要等 nextTick 后重新渲染
  await nextTick()
  setTimeout(() => slide.render(), 50)
  slidesRef.value?.focus()
}

function next() { goTo(currentSlide.value + 1) }
function prev() { goTo(currentSlide.value - 1) }

function onKey(e) {
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); next() }
  if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
}

function handleResize() {
  for (const chart of Object.values(chartInstances)) chart.resize()
}

onMounted(() => {
  goTo(0)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  for (const chart of Object.values(chartInstances)) chart.dispose()
})
</script>

<style scoped>
.slides {
  width: 100vw; height: 100vh; display: flex; flex-direction: column;
  background: #faf8f5; outline: none; overflow: hidden;
  font-family: 'Noto Serif SC', serif;
}

.slides-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 32px; background: #fff; border-bottom: 1px solid #e8e3da;
  flex-shrink: 0;
}
.slides-back { color: #8c7a5c; text-decoration: none; font-size: 14px; }
.slides-back:hover { color: #c45a3c; }
.slides-title { font-size: 15px; font-weight: 600; color: #333; }
.slides-page { font-size: 13px; color: #999; font-family: monospace; }

.slides-progress { height: 3px; background: #e8e3da; flex-shrink: 0; }
.slides-progress-fill { height: 100%; background: #c96442; transition: width 0.3s; }

.slides-body { flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px 48px; overflow: hidden; }

.slide { width: 100%; max-width: 1200px; }
.slide-header { text-align: center; margin-bottom: 24px; }
.slide-title { font-size: 28px; font-weight: 700; color: #2c2416; margin: 0 0 8px; }
.slide-subtitle { font-size: 15px; color: #8a8578; margin: 0; }

.slide-charts { display: grid; gap: 24px; }
.slide-charts.two-col { grid-template-columns: 1fr 1fr; }
.slide-chart-wrap { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #e8e6dc; }
.slide-chart-title { font-size: 14px; font-weight: 600; color: #555; margin: 0 0 12px; }
.slide-chart-area { height: 320px; }

.slides-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 32px; background: #fff; border-top: 1px solid #e8e3da;
  flex-shrink: 0;
}
.slides-nav {
  background: none; border: 1px solid #e8e3da; border-radius: 8px;
  padding: 8px 20px; font-size: 14px; color: #555; cursor: pointer;
  font-family: 'Noto Serif SC', serif;
}
.slides-nav:hover:not(:disabled) { background: #f5f0e8; color: #333; }
.slides-nav:disabled { opacity: 0.3; cursor: default; }

.slides-dots { display: flex; gap: 8px; }
.slides-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #ddd;
  cursor: pointer; transition: all 0.2s;
}
.slides-dot.active { background: #c96442; width: 24px; border-radius: 4px; }
</style>
