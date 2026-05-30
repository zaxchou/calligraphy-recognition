<template>
  <div class="deck" @keydown="onKey" tabindex="0" ref="deckRef">
    <!-- 几何装饰 -->
    <div class="geo-lines">
      <div class="geo-circle" style="width:35vw;height:35vw;top:-8vh;right:-8vw;"></div>
      <div class="geo-circle" style="width:20vw;height:20vw;top:15vh;right:5vw;"></div>
      <div class="geo-arc" style="width:50vw;height:50vw;bottom:-20vh;left:-15vw;"></div>
    </div>

    <!-- Slide 内容 -->
    <transition name="slide-fade" mode="out-in">
      <div class="slide" :key="currentSlide">
        <!-- 页眉 -->
        <div class="slide-top">
          <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="slide-back">← {{ artistName }}</router-link>
          <span class="slide-tag">{{ slides[currentSlide]?.id }}</span>
        </div>

        <!-- 标题区 -->
        <div class="slide-head">
          <span class="slide-num">{{ String(currentSlide + 1).padStart(2, '0') }}</span>
          <h1 class="slide-title">{{ slides[currentSlide]?.title }}</h1>
          <p class="slide-lead">{{ slides[currentSlide]?.subtitle }}</p>
        </div>

        <!-- 图表区 -->
        <div class="slide-charts" :class="slides[currentSlide]?.layout || 'two-col'">
          <div v-for="(chart, ci) in slides[currentSlide]?.charts" :key="ci" class="chart-card">
            <h3 class="chart-label">{{ chart.title }}</h3>
            <div :ref="el => setChartRef(el, currentSlide, ci)" class="chart-area"></div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 右侧导航点 -->
    <nav class="nav-dots">
      <span v-for="(s, i) in slides" :key="i" class="nav-dot" :class="{ active: i === currentSlide }" @click="goTo(i)" :title="s.title"></span>
    </nav>

    <!-- 底部页码 -->
    <div class="slide-counter">
      <button class="counter-btn" @click="prev" :disabled="currentSlide === 0">‹</button>
      <span class="counter-text">{{ String(currentSlide + 1).padStart(2, '0') }} / {{ String(slides.length).padStart(2, '0') }}</span>
      <button class="counter-btn" @click="next" :disabled="currentSlide === slides.length - 1">›</button>
    </div>

    <!-- 底部进度线 -->
    <div class="slide-progress">
      <div class="slide-progress-fill" :style="{ width: ((currentSlide + 1) / slides.length * 100) + '%' }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { PieChart, BarChart, ScatterChart, RadarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, RadarComponent, MarkLineComponent } from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import { artistRulesApi } from '@/api'

echarts.use([PieChart, BarChart, ScatterChart, RadarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, RadarComponent, MarkLineComponent, LabelLayout, UniversalTransition, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const artistName = route.params.name
const API = import.meta.env.VITE_API_BASE || '/api/v1'

const deckRef = ref(null)
const currentSlide = ref(0)
const chartRefs = {}
const chartInstances = {}

const statsData = ref(null)
const artistRules = ref(null)
const dimensionStats = ref(null)
const emotionRanking = ref(null)
const emotionTimeline = ref(null)
const sizeStatsData = ref(null)
const loadedSlides = new Set()

// ── 调色板（cartesian 风格 + 中国画配色）──
const PAL = {
  bg: '#ede8e0', bgAlt: '#e2dbd1', fg: '#1a1a1a', fg2: '#5a5a5a',
  accent: '#8a8178', line: '#b8b0a4',
  c1: '#c96442', c2: '#547a8c', c3: '#a65d3f', c4: '#4a4a5a', c5: '#8b6f8e', c6: '#b8a47e',
  pos: '#5a7d5a', neg: '#c45a3c', neu: '#8a8178',
}
const PERIOD_COLORS = { '早期': PAL.c1, '中期': PAL.c2, '晚期': PAL.c4, '未分期': PAL.line }
const THEME_COLORS = { '身世自况': PAL.c1, '咏物寄兴': PAL.c2, '画理自叙': PAL.c3, '时事讽喻': PAL.c4, '吉语祥瑞': PAL.c5, '交游赠答': PAL.c6 }

// echarts 全局主题
echarts.registerTheme('molin', {
  backgroundColor: 'transparent',
  textStyle: { color: PAL.fg2, fontFamily: 'Inter, Noto Sans SC, sans-serif' },
  title: { textStyle: { color: PAL.fg, fontFamily: 'Playfair Display, Noto Serif SC, serif' } },
  legend: { textStyle: { color: PAL.fg2 } },
  tooltip: { backgroundColor: '#fff', borderColor: PAL.line, textStyle: { color: PAL.fg } },
})

const slides = [
  { id: 'overview', title: '概览', subtitle: '该画家题跋的整体画像：作品数量、时期分布、情感基线',
    charts: [{ title: '分期作品分布' }, { title: '生命阶段情感偏移' }],
    load: loadOverview, render: renderOverview },
  { id: 'sentiment', title: '情感分析', subtitle: '情感极性分布与一生情绪变化趋势',
    charts: [{ title: '情感极性分布' }, { title: '情绪时间线（VADER 综合分）' }],
    load: loadSentiment, render: renderSentiment },
  { id: 'theme', title: '主题分析', subtitle: '哪些主题最常见？各时期主题如何变化？',
    charts: [{ title: '主题总体分布' }, { title: '主题分期对比' }],
    load: loadTheme, render: renderTheme },
  { id: 'style', title: '题跋风格', subtitle: '题跋长度和面积占比的变化规律',
    charts: [{ title: '题跋字数分期对比' }, { title: '题跋面积分布' }],
    load: loadStyle, render: renderStyle },
  { id: 'dimension', title: '印章与维度', subtitle: '各维度情感贡献 + 关键印章的情感含义',
    charts: [{ title: '引擎维度雷达图' }, { title: '印章情感规则' }],
    load: loadDimension, render: renderDimension },
  { id: 'ranking', title: '情感排行', subtitle: '情感最极端的作品——点击查看详情',
    charts: [{ title: '最消极 Top 10' }, { title: '最积极 Top 10' }],
    load: loadRanking, render: renderRanking },
  { id: 'spatial', title: '空间与形式', subtitle: '画幅大小与题跋策略的关系',
    charts: [{ title: '画幅 vs 题跋占比' }, { title: '布局形式统计' }],
    load: loadSpatial, render: renderSpatial },
  { id: 'material', title: '画材与尺寸', subtitle: '常用画材和尺幅偏好',
    charts: [{ title: '画材标签统计' }, { title: '作品尺寸分布' }],
    load: loadMaterial, render: renderMaterial },
]

// ── Chart helpers ──
function setChartRef(el, slideIdx, chartIdx) {
  const key = `${slideIdx}-${chartIdx}`
  if (el) { chartRefs[key] = el }
  else {
    if (chartInstances[key]) { chartInstances[key].dispose(); delete chartInstances[key] }
    delete chartRefs[key]
  }
}

function getChart(key) {
  const el = chartRefs[key]
  if (!el) return null
  if (chartInstances[key] && chartInstances[key].getDom() !== el) {
    chartInstances[key].dispose(); delete chartInstances[key]
  }
  if (chartInstances[key]) return chartInstances[key]
  const chart = echarts.init(el, 'molin')
  chartInstances[key] = chart
  return chart
}

function baseGrid() { return { left: '8%', right: '8%', bottom: '12%', top: '8%', containLabel: true } }

// ── 数据加载 ──
async function fetchStats() {
  if (statsData.value) return statsData.value
  const res = await fetch(`${API}/content-analysis/stats?artist=${encodeURIComponent(artistName)}`)
  statsData.value = await res.json()
  return statsData.value
}
async function fetchRules() {
  if (artistRules.value) return artistRules.value
  try { const res = await artistRulesApi.getByName(artistName); artistRules.value = res.rule || null } catch { artistRules.value = null }
  return artistRules.value
}
async function loadOverview() { await Promise.all([fetchStats(), fetchRules()]) }
async function loadSentiment() {
  await fetchStats()
  if (!emotionTimeline.value) {
    try { const res = await fetch(`${API}/content-analysis/emotion-timeline?artist=${encodeURIComponent(artistName)}`); const d = await res.json(); if (d.success) emotionTimeline.value = d } catch {}
  }
}
async function loadTheme() { await fetchStats() }
async function loadStyle() { await fetchStats() }
async function loadDimension() {
  if (!dimensionStats.value) {
    try { const res = await fetch(`${API}/content-analysis/dimension-stats?artist=${encodeURIComponent(artistName)}`); const d = await res.json(); if (d.success) dimensionStats.value = d.dimensions } catch {}
  }
  await fetchRules()
}
async function loadRanking() {
  if (!emotionRanking.value) {
    try { const res = await fetch(`${API}/content-analysis/emotion-ranking?artist=${encodeURIComponent(artistName)}&limit=10`); const d = await res.json(); if (d.success) emotionRanking.value = d } catch {}
  }
}
async function loadSpatial() { await fetchStats() }
async function loadMaterial() {
  await fetchStats()
  if (!sizeStatsData.value) {
    try { const res = await fetch(`${API}/content-analysis/size-stats?artist=${encodeURIComponent(artistName)}`); sizeStatsData.value = await res.json() } catch {}
  }
}

// ── 渲染 ──
function renderOverview() {
  const s = statsData.value; if (!s) return
  const c0 = getChart('0-0')
  if (c0) {
    const periods = (s.period_stats || []).map(p => ({ name: p.period || '未分期', value: p.count }))
    c0.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: ['35%', '65%'], center: ['50%', '50%'],
        data: periods.map(p => ({ ...p, itemStyle: { color: PERIOD_COLORS[p.name] || PAL.line } })),
        label: { show: true, formatter: '{b}\n{c}幅', fontSize: 12, color: PAL.fg2 },
        emphasis: { label: { fontSize: 14, fontWeight: 'bold' } } }]
    }); c0.resize()
  }
  const c1 = getChart('0-1')
  if (c1 && artistRules.value?.life_stages) {
    const stages = artistRules.value.life_stages
    c1.setOption({
      tooltip: { trigger: 'axis' },
      grid: baseGrid(),
      xAxis: { type: 'category', data: stages.map(s => s.name), axisLabel: { color: PAL.fg2 } },
      yAxis: { type: 'value', name: 'mood_offset', min: -1, max: 1, axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.3 } } },
      series: [{ type: 'bar', barWidth: '40%', data: stages.map(s => ({
        value: s.mood_offset ?? 0,
        itemStyle: { color: (s.mood_offset ?? 0) > 0 ? PAL.pos : (s.mood_offset ?? 0) < 0 ? PAL.neg : PAL.neu, borderRadius: [4, 4, 0, 0] }
      })), label: { show: true, position: 'top', formatter: p => (p.value > 0 ? '+' : '') + p.value.toFixed(1), fontSize: 12, color: PAL.fg } }]
    }); c1.resize()
  }
}

function renderSentiment() {
  const s = statsData.value; if (!s) return
  const c0 = getChart('1-0')
  if (c0) {
    const sentDist = s.sentiment_distribution || []
    const totals = {}; sentDist.forEach(i => { const l = i.polarity === 'positive' ? '积极' : i.polarity === 'negative' ? '消极' : '中性'; totals[l] = (totals[l] || 0) + i.count })
    c0.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: ['35%', '65%'],
        data: Object.entries(totals).map(([n, v]) => ({ name: n, value: v, itemStyle: { color: n === '积极' ? PAL.pos : n === '消极' ? PAL.neg : PAL.neu } })),
        label: { show: true, formatter: '{b}\n{d}%', fontSize: 12, color: PAL.fg2 } }]
    }); c0.resize()
  }
  const c1 = getChart('1-1')
  if (c1 && emotionTimeline.value?.points?.length) {
    const { points, trend } = emotionTimeline.value
    const groups = {}; points.forEach(p => { const per = p.period_phase || '未分期'; if (!groups[per]) groups[per] = []; groups[per].push(p) })
    const series = Object.entries(groups).map(([per, pts]) => ({
      name: per, type: 'scatter', symbolSize: 7,
      itemStyle: { color: PERIOD_COLORS[per] || PAL.line, opacity: 0.7 },
      data: pts.map(p => [p.year, p.emotion_score])
    }))
    if (trend?.length >= 2) series.push({ name: '趋势', type: 'line', showSymbol: false, lineStyle: { color: PAL.c1, width: 2, type: 'dashed' }, data: trend.map(t => [t.year, t.emotion_score]) })
    c1.setOption({
      tooltip: { trigger: 'item' }, legend: { bottom: 0, textStyle: { color: PAL.fg2 } },
      grid: baseGrid(),
      xAxis: { type: 'value', name: '年份', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      yAxis: { type: 'value', name: '情感', min: -1, max: 1, axisLabel: { color: PAL.fg2, formatter: v => (v > 0 ? '+' : '') + (v * 100).toFixed(0) + '%' }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      series
    }); c1.resize()
  }
}

function renderTheme() {
  const s = statsData.value; if (!s) return
  const c0 = getChart('2-0')
  if (c0) {
    const td = s.theme_distribution || []; const totals = {}; td.forEach(i => { totals[i.theme_name] = (totals[i.theme_name] || 0) + i.count })
    c0.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: ['35%', '65%'],
        data: Object.entries(totals).map(([n, v]) => ({ name: n, value: v, itemStyle: { color: THEME_COLORS[n] || PAL.neu } })),
        label: { show: true, formatter: '{b}\n{d}%', fontSize: 12, color: PAL.fg2 } }]
    }); c0.resize()
  }
  const c1 = getChart('2-1')
  if (c1) {
    const td = s.theme_distribution || []
    const po = { '早期': 0, '中期': 1, '晚期': 2 }
    const periods = [...new Set(td.map(t => t.period))].sort((a, b) => (po[a] ?? 9) - (po[b] ?? 9))
    c1.setOption({
      tooltip: { trigger: 'axis' }, legend: { bottom: 0, type: 'scroll', textStyle: { color: PAL.fg2 } },
      grid: baseGrid(),
      xAxis: { type: 'category', data: periods, axisLabel: { color: PAL.fg2 } },
      yAxis: { type: 'value', max: 100, axisLabel: { color: PAL.fg2, formatter: '{value}%' }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      series: Object.keys(THEME_COLORS).map(t => ({ name: t, type: 'bar', stack: 'total', itemStyle: { color: THEME_COLORS[t] },
        data: periods.map(p => { const item = td.find(d => d.period === p && d.theme_name === t); return item ? parseFloat(item.percentage.toFixed(1)) : 0 }) }))
    }); c1.resize()
  }
}

function renderStyle() {
  const s = statsData.value; if (!s) return
  const c0 = getChart('3-0')
  if (c0) {
    const po = { '早期': 0, '中期': 1, '晚期': 2 }
    const sorted = (s.period_stats || []).sort((a, b) => (po[a.period] ?? 9) - (po[b.period] ?? 9))
    c0.setOption({
      tooltip: { trigger: 'axis' }, legend: { bottom: 0, textStyle: { color: PAL.fg2 } },
      grid: baseGrid(),
      xAxis: { type: 'category', data: sorted.map(p => p.period), axisLabel: { color: PAL.fg2 } },
      yAxis: { type: 'value', name: '字符数', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      series: [
        { name: '平均', type: 'bar', itemStyle: { color: PAL.c1, borderRadius: [3, 3, 0, 0] }, data: sorted.map(p => parseFloat(p.avg_char_count.toFixed(1))) },
        { name: '最长', type: 'bar', itemStyle: { color: PAL.c3, borderRadius: [3, 3, 0, 0] }, data: sorted.map(p => p.max_char_count) }
      ]
    }); c0.resize()
  }
  const c1 = getChart('3-1')
  if (c1) {
    const ad = s.area_distribution || []
    c1.setOption({
      tooltip: { trigger: 'axis' },
      grid: baseGrid(),
      xAxis: { type: 'category', data: ad.map(d => d.range), axisLabel: { color: PAL.fg2, fontSize: 11 } },
      yAxis: { type: 'value', name: '作品数', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      series: [{ type: 'bar', data: ad.map(d => d.inscription_count), itemStyle: { color: PAL.c2, borderRadius: [3, 3, 0, 0] }, barWidth: '55%' }]
    }); c1.resize()
  }
}

function renderDimension() {
  const c0 = getChart('4-0')
  if (c0 && dimensionStats.value) {
    const dims = dimensionStats.value; const labels = Object.keys(dims)
    const values = labels.map(l => Math.abs(dims[l].mean) * 100)
    const maxVal = Math.max(...values, 10)
    c0.setOption({
      radar: { indicator: labels.map(l => ({ name: l, max: maxVal })), shape: 'polygon',
        axisLine: { lineStyle: { color: PAL.line } }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.3 } }, splitArea: { areaStyle: { color: ['rgba(138,129,120,0.03)', 'rgba(138,129,120,0.06)'] } } },
      series: [{ type: 'radar', data: [{ value: values, name: '情感强度',
        areaStyle: { color: 'rgba(201,100,66,0.12)' }, lineStyle: { color: PAL.c1, width: 2 }, itemStyle: { color: PAL.c1 } }] }]
    }); c0.resize()
  }
  const c1 = getChart('4-1')
  if (c1 && artistRules.value?.seal_rules) {
    const entries = Object.entries(artistRules.value.seal_rules).filter(([, r]) => r.score !== 0).sort((a, b) => a[1].score - b[1].score)
    if (entries.length) {
      c1.setOption({
        grid: { left: '25%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
        xAxis: { type: 'value', min: -1, max: 1, axisLabel: { color: PAL.fg2, formatter: v => (v > 0 ? '+' : '') + v.toFixed(1) }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
        yAxis: { type: 'category', data: entries.map(([n]) => n).reverse(), axisLabel: { color: PAL.fg, fontSize: 12 } },
        series: [{ type: 'bar', data: entries.map(([, r]) => ({ value: r.score, itemStyle: { color: r.score > 0 ? PAL.pos : PAL.neg, borderRadius: [0, 3, 3, 0] } })).reverse(),
          label: { show: true, position: 'right', formatter: p => (p.value > 0 ? '+' : '') + p.value.toFixed(1), fontSize: 11, color: PAL.fg } }]
      }); c1.resize()
    }
  }
}

function renderRanking() {
  if (!emotionRanking.value) return
  const negItems = (emotionRanking.value.top_negative || []).slice(0, 10)
  const posItems = (emotionRanking.value.top_positive || []).slice(0, 10)
  const c0 = getChart('5-0')
  if (c0 && negItems.length) {
    const neg = [...negItems].reverse()
    c0.setOption({
      grid: { left: '28%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
      xAxis: { type: 'value', min: -1, max: 0, axisLabel: { color: PAL.fg2, formatter: v => v.toFixed(1) }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      yAxis: { type: 'category', data: neg.map(i => i.title), axisLabel: { color: PAL.fg, fontSize: 11, width: 90, overflow: 'truncate' } },
      series: [{ type: 'bar', data: neg.map(i => ({ value: i.emotion_score, itemStyle: { color: PAL.neg, borderRadius: [0, 3, 3, 0] } })),
        label: { show: true, position: 'left', formatter: p => p.value.toFixed(2), fontSize: 10, color: PAL.fg2 } }]
    }); c0.resize(); c0.off('click')
    c0.on('click', p => { const item = neg[p.dataIndex]; if (item?.id) window.open(router.resolve({ name: 'TubiDetail', params: { id: item.id } }).href, '_blank') })
  }
  const c1 = getChart('5-1')
  if (c1 && posItems.length) {
    const pos = [...posItems].reverse()
    c1.setOption({
      grid: { left: '28%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
      xAxis: { type: 'value', min: 0, max: 1, axisLabel: { color: PAL.fg2, formatter: v => v.toFixed(1) }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      yAxis: { type: 'category', data: pos.map(i => i.title), axisLabel: { color: PAL.fg, fontSize: 11, width: 90, overflow: 'truncate' } },
      series: [{ type: 'bar', data: pos.map(i => ({ value: i.emotion_score, itemStyle: { color: PAL.pos, borderRadius: [0, 3, 3, 0] } })),
        label: { show: true, position: 'right', formatter: p => '+' + p.value.toFixed(2), fontSize: 10, color: PAL.fg2 } }]
    }); c1.resize(); c1.off('click')
    c1.on('click', p => { const item = pos[p.dataIndex]; if (item?.id) window.open(router.resolve({ name: 'TubiDetail', params: { id: item.id } }).href, '_blank') })
  }
}

function renderSpatial() {
  const s = statsData.value; if (!s) return
  const c0 = getChart('6-0')
  if (c0) {
    const cd = s.area_size_correlation || []; const groups = {}; cd.forEach(d => { const p = d.period || '未分期'; if (!groups[p]) groups[p] = []; groups[p].push(d) })
    c0.setOption({
      tooltip: { formatter: p => { if (p.seriesType === 'line') return ''; const d = p.data || {}; return `${d.title || ''}\n高${d.height || p.value?.[0] || ''}cm\n题跋${(d.insc || p.value?.[1] || 0).toFixed(1)}%` } },
      legend: { bottom: 0, textStyle: { color: PAL.fg2 } },
      grid: baseGrid(),
      xAxis: { type: 'value', name: '画幅高度 (cm)', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      yAxis: { type: 'value', name: '题跋占比 (%)', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      series: Object.entries(groups).map(([p, pts]) => ({
        name: p, type: 'scatter', symbolSize: 9,
        itemStyle: { color: PERIOD_COLORS[p] || PAL.line, opacity: 0.7 },
        data: pts.map(d => ({ value: [d.artwork_height_cm, d.inscription_percent], title: d.title, height: d.artwork_height_cm, insc: d.inscription_percent, period: d.period }))
      }))
    }); c0.resize()
  }
  const c1 = getChart('6-1')
  if (c1 && s.layout_form_distribution?.length) {
    const forms = s.layout_form_distribution.slice(0, 8)
    c1.setOption({
      grid: { left: '25%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
      xAxis: { type: 'value', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      yAxis: { type: 'category', data: forms.map(f => f.form_name).reverse(), axisLabel: { color: PAL.fg, fontSize: 11 } },
      series: [{ type: 'bar', data: forms.map(f => f.count).reverse(), itemStyle: { color: PAL.c2, borderRadius: [0, 3, 3, 0] }, label: { show: true, position: 'right', color: PAL.fg2 } }]
    }); c1.resize()
  }
}

function renderMaterial() {
  const s = statsData.value; if (!s) return
  const c0 = getChart('7-0')
  if (c0) {
    const tags = (s.material_tags || []).slice(0, 10)
    c0.setOption({
      grid: { left: '25%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
      xAxis: { type: 'value', name: '出现次数', axisLabel: { color: PAL.fg2 }, splitLine: { lineStyle: { color: PAL.line, opacity: 0.2 } } },
      yAxis: { type: 'category', data: tags.map(t => t.tag).reverse(), axisLabel: { color: PAL.fg, fontSize: 11 } },
      series: [{ type: 'bar', data: tags.map(t => t.count).reverse(), itemStyle: { color: PAL.c1, borderRadius: [0, 3, 3, 0] }, label: { show: true, position: 'right', color: PAL.fg2 } }]
    }); c0.resize()
  }
  const c1 = getChart('7-1')
  if (c1) {
    const sizeDist = sizeStatsData.value?.size_distribution || []
    if (sizeDist.length) {
      c1.setOption({
        tooltip: { trigger: 'item' },
        series: [{ type: 'pie', radius: ['35%', '65%'],
          data: sizeDist.map(item => ({ name: item.category, value: item.count, itemStyle: { color: item.category === '小幅' ? PAL.c3 : item.category === '中幅' ? PAL.c2 : PAL.c5 } })),
          label: { show: true, formatter: '{b}\n{d}%', fontSize: 12, color: PAL.fg2 } }]
      })
    } else { c1.setOption({ title: { text: '暂无尺寸数据', left: 'center', top: 'center', textStyle: { color: PAL.neu, fontSize: 14 } } }) }
    c1.resize()
  }
}

// ── 导航 ──
async function goTo(idx) {
  if (idx < 0 || idx >= slides.length) return
  currentSlide.value = idx
  await nextTick()
  const slide = slides[idx]
  if (!loadedSlides.has(idx)) { await slide.load(); loadedSlides.add(idx) }
  await nextTick()
  setTimeout(() => slide.render(), 50)
  deckRef.value?.focus()
}
function next() { goTo(currentSlide.value + 1) }
function prev() { goTo(currentSlide.value - 1) }
function onKey(e) {
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); next() }
  if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
}
function handleResize() { for (const [k, c] of Object.entries(chartInstances)) { try { c.resize() } catch { delete chartInstances[k] } } }

onMounted(() => { goTo(0); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); for (const c of Object.values(chartInstances)) c.dispose() })
</script>

<style scoped>
/* ══ Cartesian-inspired design system ══ */
.deck {
  width: 100vw; height: 100vh; position: relative;
  background: #ede8e0; color: #1a1a1a;
  font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
  overflow: hidden; outline: none;
  -webkit-font-smoothing: antialiased;
}

/* 几何装饰 */
.geo-lines { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
.geo-circle { position: absolute; border: 1px solid #b8b0a4; border-radius: 50%; opacity: 0.35; }
.geo-arc { position: absolute; border: 1px dashed #b8b0a4; border-radius: 50%; opacity: 0.2; }

/* Slide */
.slide {
  position: relative; z-index: 1;
  width: 100%; height: 100%;
  display: flex; flex-direction: column;
  padding: 3vh 5vw;
}
.slide-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 2vh;
}
.slide-back {
  font-size: 0.8vw; color: #8a8178; text-decoration: none;
  letter-spacing: 1px; text-transform: uppercase;
  transition: color 0.2s;
}
.slide-back:hover { color: #1a1a1a; }
.slide-tag {
  font-size: 0.7vw; color: #8a8178; letter-spacing: 2px;
  text-transform: uppercase; font-family: 'Courier Prime', monospace;
}

.slide-head { margin-bottom: 3vh; }
.slide-num {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-size: 6vw; font-weight: 700; color: #b8b0a4; opacity: 0.3;
  line-height: 1; display: block; margin-bottom: -1.5vh;
}
.slide-title {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-size: 2.8vw; font-weight: 600; color: #1a1a1a;
  margin: 0; line-height: 1.2;
}
.slide-lead {
  font-size: 1vw; color: #8a8178; margin: 0.8vh 0 0;
  max-width: 60vw; line-height: 1.6;
}

/* Charts */
.slide-charts { flex: 1; display: grid; gap: 2vw; min-height: 0; }
.slide-charts.two-col { grid-template-columns: 1fr 1fr; }
.chart-card {
  background: rgba(255,255,255,0.5); border: 1px solid #d4cec4;
  border-radius: 12px; padding: 1.5vw; display: flex; flex-direction: column;
}
.chart-label {
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  font-size: 0.85vw; font-weight: 600; color: #5a5a5a;
  margin: 0 0 1vh; letter-spacing: 0.5px;
}
.chart-area { flex: 1; min-height: 250px; }

/* 右侧导航点 */
.nav-dots {
  position: fixed; right: 2vw; top: 50%; transform: translateY(-50%);
  display: flex; flex-direction: column; gap: 10px; z-index: 10;
}
.nav-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #b8b0a4; cursor: pointer;
  transition: all 0.3s ease;
}
.nav-dot.active { background: #1a1a1a; transform: scale(1.4); }
.nav-dot:hover { background: #8a8178; }

/* 底部页码 */
.slide-counter {
  position: fixed; bottom: 2.5vh; right: 3vw;
  display: flex; align-items: center; gap: 12px; z-index: 10;
}
.counter-text {
  font-family: 'Courier Prime', monospace;
  font-size: 0.75rem; color: #8a8178; letter-spacing: 2px;
}
.counter-btn {
  background: none; border: 1px solid #b8b0a4; border-radius: 4px;
  width: 28px; height: 28px; font-size: 16px; color: #8a8178;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.counter-btn:hover:not(:disabled) { background: #d4cec4; color: #1a1a1a; }
.counter-btn:disabled { opacity: 0.25; cursor: default; }

/* 进度线 */
.slide-progress {
  position: fixed; bottom: 0; left: 0; right: 0;
  height: 2px; background: #d4cec4; z-index: 10;
}
.slide-progress-fill { height: 100%; background: #c96442; transition: width 0.4s ease; }

/* 切换动画 */
.slide-fade-enter-active { transition: opacity 0.35s ease, transform 0.35s ease; }
.slide-fade-leave-active { transition: opacity 0.2s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateY(12px); }
.slide-fade-leave-to { opacity: 0; }
</style>
