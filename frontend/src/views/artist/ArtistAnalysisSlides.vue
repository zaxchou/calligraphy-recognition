<template>
  <div class="deck" @keydown="onKey" tabindex="0" ref="deckRef">
    <!-- 几何装饰 -->
    <div class="geo-lines">
      <div class="geo-circle" style="width:35vw;height:35vw;top:-8vh;right:-8vw;"></div>
      <div class="geo-circle" style="width:20vw;height:20vw;top:15vh;right:5vw;"></div>
      <div class="geo-arc" style="width:50vw;height:50vw;bottom:-20vh;left:-15vw;"></div>
    </div>

    <!-- Slide 内容 -->
    <transition name="slide-fade" mode="out-in" @after-enter="onSlideEnter">
      <div class="slide" :key="currentSlide" :class="'slide-' + (slides[currentSlide]?.layout || 'split')">
        <!-- 页眉 -->
        <div class="slide-top">
          <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="slide-back">← {{ artistName }}</router-link>
          <div class="slide-top-right">
            <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'">
              {{ isFullscreen ? '⊞' : '⛶' }}
            </button>
            <span class="slide-tag">{{ slides[currentSlide]?.id }}</span>
          </div>
        </div>

        <!-- ═══ Layout: split — 左文字 + 右图表 ═══ -->
        <div v-if="slides[currentSlide]?.layout === 'split'" class="split-layout">
          <div class="split-left">
            <span class="slide-num">{{ String(currentSlide + 1).padStart(2, '0') }}</span>
            <h1 class="slide-title">{{ slides[currentSlide]?.title }}</h1>
            <p class="slide-lead">{{ slides[currentSlide]?.subtitle }}</p>
            <div class="split-insight" v-html="slides[currentSlide]?.insight || ''"></div>
            <div class="insight-tip" v-if="slides[currentSlide]?.tip">
              💡 {{ slides[currentSlide]?.tip }}
            </div>
          </div>
          <div class="split-right">
            <div v-for="(chart, ci) in slides[currentSlide]?.charts" :key="ci" class="chart-card">
              <h3 class="chart-label">{{ chart.title }}</h3>
              <div :ref="el => setChartRef(el, currentSlide, ci)" class="chart-area"></div>
            </div>
          </div>
        </div>

        <!-- ═══ Layout: wide — 上标题解说 + 下全宽图表 ═══ -->
        <div v-else class="wide-layout">
          <div class="wide-top">
            <div class="wide-head">
              <span class="slide-num">{{ String(currentSlide + 1).padStart(2, '0') }}</span>
              <h1 class="slide-title">{{ slides[currentSlide]?.title }}</h1>
              <p class="slide-lead">{{ slides[currentSlide]?.subtitle }}</p>
            </div>
            <div class="wide-insight">
              <div class="insight-body" v-html="slides[currentSlide]?.insight || ''"></div>
              <div class="insight-tip" v-if="slides[currentSlide]?.tip">
                💡 {{ slides[currentSlide]?.tip }}
              </div>
            </div>
          </div>
          <div class="wide-charts">
            <div v-for="(chart, ci) in slides[currentSlide]?.charts" :key="ci" class="chart-card">
              <h3 class="chart-label">{{ chart.title }}</h3>
              <div :ref="el => setChartRef(el, currentSlide, ci)" class="chart-area"></div>
            </div>
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
import { GridComponent, TooltipComponent, LegendComponent, RadarComponent } from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import { artistRulesApi } from '@/api'

echarts.use([PieChart, BarChart, ScatterChart, RadarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, RadarComponent, LabelLayout, UniversalTransition, CanvasRenderer])

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
const isFullscreen = ref(false)
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
  { id: 'overview', title: '概览', subtitle: '该画家题跋的整体画像',
    layout: 'split',
    charts: [{ title: '分期作品分布' }, { title: '生命阶段情感偏移' }],
    insight: `<p><strong>分期作品分布</strong>饼图告诉我们每个时期留下了多少作品——作品越多，样本越可靠。如果某个时期只有寥寥几幅，统计结论就不够可信。</p>
<p><strong>生命阶段情感偏移</strong>柱状图是关键：情感偏移值反映画家在不同时期的心境基调。正值偏乐观，负值偏沉重。这个偏移值来自画家规则——是根据历史研究和题跋分析预先设定的。</p>
<p>大多数画家呈现"早年意气风发（偏正）→ 中年转折 → 晚年归于平淡或感慨（偏负）"的规律。但也有例外——有些画家一生豁达，晚期反而更积极。这张图就是判断画家情感底色的第一步。</p>
<p>注意看<strong>权重</strong>的变化——晚期作品的权重通常更高，因为画家的技法和思想都更成熟，晚期的题跋往往更能代表其真实的内心世界。</p>`,
    tip: '如果晚期偏移值远低于早期，说明画家人生际遇对其创作情感影响很大。权重越高，该时期对整体分析的影响越大。',
    load: loadOverview, render: renderOverview },

  { id: 'sentiment', title: '情感分析', subtitle: '画作情绪的全景扫描',
    layout: 'wide',
    charts: [{ title: '情感极性分布' }, { title: '情绪时间线' }],
    insight: `<p><strong>情感极性分布</strong>饼图展示消极/中性/积极的整体比例。这个比例本身就是画家"情感DNA"的快照——有的画家七成作品是消极的，有的则大部分是积极的。</p>
<p><strong>情绪时间线</strong>散点图更有意思——每一幅画按创作年份排列，纵轴是<strong>VADER 综合情感分</strong>（八维度加权，-1到+1）。虚线是趋势线：趋势线向下说明越画越沉重，向上说明晚年更豁达，平稳说明情感基调始终如一。</p>
<p>关注散点图中的<strong>离群点</strong>——情感特别极端的作品往往对应画家人生中的重大转折。比如被贬官后的作品、丧亲之后的画作，情感分会显著下降。</p>`,
    tip: '散点图中离群最远的点，值得点开看原作——那里藏着画家最真实的瞬间。',
    load: loadSentiment, render: renderSentiment },

  { id: 'theme', title: '主题分析', subtitle: '画家在题跋中说了什么',
    layout: 'split',
    charts: [{ title: '主题总体分布' }, { title: '主题分期对比' }],
    insight: `<p>我们把题跋内容分为六大主题。<strong>身世自况</strong>是谈自己的经历和处境——仕途不顺、卖画为生、感叹人生。<strong>咏物寄兴</strong>是借画面中的花鸟山水来抒发情感，表面写竹子，实际写自己。</p>
<p><strong>画理自叙</strong>是画家谈论自己的绘画理念和技法。<strong>时事讽喻</strong>是对社会现实的评论和批评——这在清代文人画中特别常见。<strong>吉语祥瑞</strong>是祝福和祈愿。<strong>交游赠答</strong>是送给朋友的画作题跋。</p>
<p><strong>主题分期对比</strong>堆叠柱状图展示各时期主题的变化规律。如果"身世自况"在晚期大幅上升，说明画家晚年更倾向于在画中倾诉个人遭遇。如果"时事讽喻"集中在某个时期，那往往对应着当时的社会动荡。</p>
<p>六大主题的分布比例，就是理解一位画家精神世界的"地图"。</p>`,
    tip: '身世自况比例高的画家，题跋往往是理解其人生观的第一手材料，比任何传记都真实。',
    load: loadTheme, render: renderTheme },

  { id: 'style', title: '题跋风格', subtitle: '字数与面积的量化规律',
    layout: 'wide',
    charts: [{ title: '题跋字数分期对比' }, { title: '题跋面积分布' }],
    insight: `<p>题跋的<strong>长度</strong>本身就是情感信号。早期作品题跋简短，可能是"某年某月写于某地"的套路化文字；晚期题跋变长，往往是因为心中有话不吐不快。字数的变化曲线，就是画家"想说话"的欲望曲线。</p>
<p><strong>题跋面积分布</strong>图告诉我们：题跋占画面的比例集中在哪个区间。比例越大，说明画家越重视文字表达，甚至不惜"侵占"画面空间来抒发情感。有些画家晚期的题跋面积比早期大了三倍——那不是画不下，而是有太多话要说。</p>
<p>字数和面积的结合分析，能帮我们判断：这幅画的题跋是"例行公事"还是"真情流露"。</p>`,
    tip: '题跋字数突然增多的作品，往往是画家情感最充沛的时期——那里藏着他们最想说的话。',
    load: loadStyle, render: renderStyle },

  { id: 'dimension', title: '印章与维度', subtitle: '六个维度的情感贡献',
    layout: 'wide',
    charts: [{ title: '引擎维度雷达图' }, { title: '印章情感规则' }],
    insight: `<p>我们的引擎从<strong>六个维度</strong>综合评判一幅画的情感。每个维度贡献不同的情感信号，最终加权得出综合分。</p>
<p><strong>文字维度</strong>是题跋本身的情感分析，权重最大（40%）。<strong>主题维度</strong>根据主题分类施加情感偏移——时事讽喻强制偏消极，吉语祥瑞强制偏积极。<strong>印章维度</strong>读取画家盖的印章来判断情感。</p>
<p><strong>时期维度</strong>根据画家所处的人生阶段施加基线偏移。<strong>空间维度</strong>分析题跋在画面中的布局——侵入画面中央的题跋往往情感更激烈。<strong>尺寸维度</strong>根据画幅大小施加修正。</p>
<p><strong>印章情感规则</strong>图表列出该画家所有<strong>非中性印章</strong>的得分。印章是画家的"签名"——"苦李"得 -1.0 分（极度消极），因为这是用来自嘲的号；"卖画不为官"得 +1.0（极度积极），表达不向权贵低头的傲骨。</p>`,
    tip: '印章是画家主动盖上去的，是最"诚实"的情感信号——它不像题跋那样可以被反复斟酌修改。',
    load: loadDimension, render: renderDimension },

  { id: 'ranking', title: '情感排行', subtitle: '情感最极端的作品——点击查看详情',
    layout: 'split',
    charts: [{ title: '最消极 Top 10' }, { title: '最积极 Top 10' }],
    insight: `<p>上面是这位画家<strong>情感最沉重</strong>的 10 幅作品，下方是<strong>最积极乐观</strong>的 10 幅。这些是八维度综合评分的极端值——不是单一维度的偏高偏低，而是所有维度的综合判断。</p>
<p>消极作品中常见的元素：题跋出现"泣""泪""困""愁"等字眼，主题为"时事讽喻"，印章有"苦李""墨磨人"等消极符号。积极作品则常见"春""乐""寿""福"等吉语，印章有"卖画不为官""不折腰"等正面表达。</p>
<p>点击任意一条可以跳转到作品详情页，查看完整的题跋内容、每个维度的评分明细和分析推理过程。</p>`,
    tip: '对比左右两列——情感弹性越大，说明这位画家的内心世界越丰富复杂。',
    load: loadRanking, render: renderRanking },

  { id: 'spatial', title: '空间与形式', subtitle: '画幅大小与题跋策略',
    layout: 'wide',
    charts: [{ title: '画幅 vs 题跋占比' }, { title: '布局形式统计' }],
    insight: `<p><strong>画幅 vs 题跋占比</strong>散点图探索一个有趣的问题：大画和小画的题跋策略是否不同？如果散点呈水平分布，说明无论画幅大小，题跋占比始终如一——这是一种稳定的个人风格。如果大画的散点偏高，说明画家在大画上更敢写。</p>
<p><strong>布局形式统计</strong>图表展示题跋的空间布局形式。传统文人画最常见的布局是"边角规整式"——题跋规矩地写在画面边角，不打扰主体。而"穿插式"则是大胆地将文字融入画面，让书法成为构图的一部分。</p>
<p>布局形式反映的是画家的自信程度和创新意识。一个画家如果从早年的"边角式"逐渐演变为晚年的"穿插式"，说明他越来越自信，越来越不拘泥于传统规范。</p>
<p>题跋面积和布局形式的组合，能看出画家是"保守型"还是"突破型"的创作者。</p>`,
    tip: '大量使用穿插式布局的画家，在空间上有创新意识——他们把题跋当成了画的一部分，而不是附属品。',
    load: loadSpatial, render: renderSpatial },

  { id: 'material', title: '画材与尺寸', subtitle: '画了什么、用的多大的纸',
    layout: 'split',
    charts: [{ title: '画材标签统计' }, { title: '作品尺寸分布' }],
    insight: `<p><strong>画材标签统计</strong>图表统计这位画家最常画的题材和元素。在中国画的传统里，每种题材都有象征意义——竹子象征坚韧不屈，兰花象征高洁典雅，梅花象征傲骨凌霜，菊花象征隐逸淡泊。</p>
<p>题材偏好本身就是一种情感表达。一个画家如果一生都在画竹子，他可能在用竹子表达自己的人生态度。如果晚期突然开始画"枯木""残荷"，这往往是心境变化的信号——从积极向上转为感慨人生。</p>
<p><strong>作品尺寸分布</strong>饼图展示尺幅偏好。小幅作品（如册页、扇面）适合随手抒发，是日常情感的自然流露。大幅作品（如中堂、条屏）则需要郑重其事，往往是在重要场合或特殊心境下创作的。</p>
<p>尺幅的选择反映了画家的创作场景和意图。如果一个画家早期多大幅、晚期多小幅，可能说明他从"示人"转向"自娱"。</p>`,
    tip: '花鸟画家晚期突然开始大量画"枯木""残荷"，这往往是心境变化的信号——题材就是画家的心电图。',
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
let pendingSlide = null

async function goTo(idx) {
  if (idx < 0 || idx >= slides.length) return
  currentSlide.value = idx
  pendingSlide = idx
  // 数据在切换时就开始加载
  const slide = slides[idx]
  if (!loadedSlides.has(idx)) {
    slide.load().then(() => { loadedSlides.add(idx) })
  }
  deckRef.value?.focus()
}

// transition @after-enter 回调：DOM 已就绪，安全渲染图表
function onSlideEnter() {
  const idx = pendingSlide
  if (idx == null) return
  pendingSlide = null
  const slide = slides[idx]
  let retries = 0
  const tryRender = () => {
    if (loadedSlides.has(idx) || !slide.load) {
      slide.render()
    } else if (retries < 40) { // 最多等 2 秒
      retries++
      setTimeout(tryRender, 50)
    }
  }
  nextTick(() => tryRender())
}
function next() { goTo(currentSlide.value + 1) }
function prev() { goTo(currentSlide.value - 1) }
function onKey(e) {
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); next() }
  if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
  if (e.key === 'f' || e.key === 'F') { e.preventDefault(); toggleFullscreen() }
}
function handleResize() { for (const [k, c] of Object.entries(chartInstances)) { try { c.resize() } catch { delete chartInstances[k] } } }

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    deckRef.value?.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}
function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  setTimeout(() => handleResize(), 200)
}

onMounted(async () => {
  // 首页没有 transition，直接加载+渲染
  currentSlide.value = 0
  const slide = slides[0]
  await slide.load()
  loadedSlides.add(0)
  await nextTick()
  slide.render()
  deckRef.value?.focus()
  window.addEventListener('resize', handleResize)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  for (const c of Object.values(chartInstances)) c.dispose()
})
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
.geo-lines { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
.geo-circle { position: absolute; border: 1px solid #b8b0a4; border-radius: 50%; opacity: 0.35; }
.geo-arc { position: absolute; border: 1px dashed #b8b0a4; border-radius: 50%; opacity: 0.2; }

.slide {
  position: relative; z-index: 1;
  width: 100%; height: 100%;
  display: flex; flex-direction: column;
  padding: 1vh 3vw;
}
.slide-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 0.5vh; flex-shrink: 0;
}
.slide-top-right { display: flex; align-items: center; gap: 8px; }
.fullscreen-btn {
  background: none; border: 1px solid #d4cec4; border-radius: 4px;
  width: 24px; height: 24px; font-size: 14px; color: #8a8178;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.fullscreen-btn:hover { background: #d4cec4; color: #1a1a1a; }
.slide-back {
  font-size: 0.75vw; color: #8a8178; text-decoration: none;
  letter-spacing: 1px; text-transform: uppercase; transition: color 0.2s;
}
.slide-back:hover { color: #1a1a1a; }
.slide-tag {
  font-size: 0.65vw; color: #8a8178; letter-spacing: 2px;
  text-transform: uppercase; font-family: 'Courier Prime', monospace;
}

/* ── 共用排版 ── */
.slide-num {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-size: 2.5vw; font-weight: 700; color: #b8b0a4; opacity: 0.2;
  line-height: 1; display: block;
}
.slide-title {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-size: 1.6vw; font-weight: 600; color: #1a1a1a; margin: 0; line-height: 1.2;
}
.slide-lead { font-size: 0.8vw; color: #8a8178; margin: 0.2vh 0 0; line-height: 1.4; }
.insight-body { font-size: 1vw; line-height: 1.75; color: #3a3a3a; }
.insight-body :deep(p) { margin: 0 0 0.5em; }
.insight-body :deep(strong) { color: #1a1a1a; font-weight: 600; }
.insight-tip {
  padding-top: 0.5vh; border-top: 1px dashed #d4cec4;
  font-size: 0.8vw; color: #8a8178; line-height: 1.5;
}
.chart-card {
  background: rgba(255,255,255,0.5); border: 1px solid #d4cec4;
  border-radius: 8px; padding: 0.6vw 0.8vw; display: flex; flex-direction: column;
}
.chart-label {
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  font-size: 0.75vw; font-weight: 600; color: #5a5a5a;
  margin: 0 0 0.3vh; letter-spacing: 0.5px; flex-shrink: 0;
}
.chart-area { flex: 1; min-height: 120px; }

/* ═══ Layout: split — 左文字 + 右双图 ═══ */
.split-layout { flex: 1; display: flex; gap: 2vw; min-height: 0; }
.split-left {
  flex: 3.5; display: flex; flex-direction: column; justify-content: center;
  padding-right: 0.5vw;
}
.split-left .slide-num { margin-bottom: -0.5vh; }
.split-insight { margin-top: 1vh; font-size: 1vw; line-height: 1.75; color: #3a3a3a; flex: 1; overflow-y: auto; }
.split-insight :deep(p) { margin: 0 0 0.5em; }
.split-insight :deep(strong) { color: #1a1a1a; font-weight: 600; }
.split-right { flex: 6.5; display: flex; flex-direction: column; gap: 1vh; min-height: 0; }
.split-right .chart-card { flex: 1; min-height: 0; }

/* ═══ Layout: wide — 上标题+解说横条，下全宽双图 ═══ */
.wide-layout { flex: 1; display: flex; flex-direction: column; gap: 0.8vh; min-height: 0; }
.wide-top {
  flex-shrink: 0; display: flex; gap: 2vw; align-items: flex-start;
  background: rgba(255,255,255,0.3); border: 1px solid #d4cec4;
  border-radius: 8px; padding: 0.8vw 1.2vw; border-left: 3px solid #c96442;
}
.wide-head { flex: 0 0 auto; }
.wide-head .slide-num { font-size: 2vw; margin-bottom: -0.3vh; }
.wide-insight { flex: 1; font-size: 0.95vw; line-height: 1.7; color: #3a3a3a; }
.wide-insight :deep(p) { margin: 0 0 0.4em; }
.wide-insight :deep(strong) { color: #1a1a1a; font-weight: 600; }
.wide-charts { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 1vw; min-height: 0; }
.wide-charts .chart-card { min-height: 0; }

/* ── 导航 ── */
.nav-dots {
  position: fixed; right: 1.5vw; top: 50%; transform: translateY(-50%);
  display: flex; flex-direction: column; gap: 8px; z-index: 10;
}
.nav-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #b8b0a4; cursor: pointer; transition: all 0.3s ease;
}
.nav-dot.active { background: #1a1a1a; transform: scale(1.4); }
.nav-dot:hover { background: #8a8178; }
.slide-counter {
  position: fixed; bottom: 1.5vh; right: 2vw;
  display: flex; align-items: center; gap: 10px; z-index: 10;
}
.counter-text {
  font-family: 'Courier Prime', monospace;
  font-size: 0.7rem; color: #8a8178; letter-spacing: 2px;
}
.counter-btn {
  background: none; border: 1px solid #b8b0a4; border-radius: 4px;
  width: 24px; height: 24px; font-size: 14px; color: #8a8178;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.counter-btn:hover:not(:disabled) { background: #d4cec4; color: #1a1a1a; }
.counter-btn:disabled { opacity: 0.25; cursor: default; }
.slide-progress {
  position: fixed; bottom: 0; left: 0; right: 0;
  height: 2px; background: #d4cec4; z-index: 10;
}
.slide-progress-fill { height: 100%; background: #c96442; transition: width 0.4s ease; }

/* 动画 */
.slide-fade-enter-active { transition: opacity 0.35s ease, transform 0.35s ease; }
.slide-fade-leave-active { transition: opacity 0.2s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateY(12px); }
.slide-fade-leave-to { opacity: 0; }
</style>
