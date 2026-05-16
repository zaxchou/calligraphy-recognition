<template>
  <div class="artist-sub-page data-dashboard">
    <div class="asp-hero">
      <h2 class="asp-hero-title">
        <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-back-link">{{ artistName }}</router-link>
      </h2>
    </div>
    <nav class="asp-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-nav-item">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="asp-nav-item">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="asp-nav-item">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="asp-nav-item">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="asp-nav-item active">分析</router-link>
    </nav>

    <div class="aa-header-actions">
      <el-select v-model="selectedArtist" size="small" @change="onArtistChange">
        <el-option v-for="artist in artistList" :key="artist" :value="artist" :label="artist" />
      </el-select>
    </div>

    <!-- 学术分析报告 -->
    <el-card shadow="never" class="aa-summary-card">
      <template #header>
        <div class="card-header-title">
          <span class="aa-insight-icon">✦</span>
          <span>学术分析报告</span>
          <el-tag v-if="summaryCached && reportData" type="success" size="small">已缓存</el-tag>
          <el-button size="small" type="primary" plain @click="generateSummary" :loading="summaryLoading" class="summary-btn">
            <el-icon><RefreshRight /></el-icon>
            {{ reportData ? '重新生成' : '生成报告' }}
          </el-button>
          <el-button v-if="reportData" size="small" plain @click="exportReportMarkdown" class="summary-btn">
            <el-icon><Download /></el-icon>导出 Markdown
          </el-button>
        </div>
      </template>
      <div v-if="summaryLoading" class="summary-loading"><el-icon class="is-loading"><Loading /></el-icon><span>正在生成学术报告，请稍候...</span></div>
      <div v-else-if="reportData" class="report-content">
        <el-tabs v-model="activeReportTab" class="report-tabs" type="border-card" :scrollable="true">
          <el-tab-pane v-for="section in reportData.sections" :key="section.id" :label="section.title" :name="section.id">
            <div v-if="section.type === 'markdown'" class="report-section-markdown" v-html="renderMarkdown(section.content)"></div>
            <el-table v-else-if="section.type === 'table'" :data="section.content.rows" size="small" class="report-table">
              <el-table-column v-for="(header, idx) in section.content.headers" :key="idx" :prop="String(idx)" :label="header" min-width="80" />
            </el-table>
            <div v-else-if="section.type === 'list'" class="report-list">
              <div v-for="(item, idx) in section.content" :key="idx" class="report-list-item">
                <div v-if="item.title" class="report-item-title">{{ item.title }}
                  <el-tag v-if="item.period" size="small" type="info">{{ item.period }}</el-tag>
                  <el-tag v-if="item.confidence !== undefined" size="small" :type="item.confidence >= 0.8 ? 'success' : item.confidence >= 0.6 ? 'warning' : 'danger'">conf={{ item.confidence.toFixed(2) }}</el-tag>
                </div>
                <div v-if="item.theme" class="report-item-meta"><span class="report-meta-label">主题：</span>{{ item.theme }}<span class="report-meta-label">情感：</span>{{ item.polarity }}（{{ item.emotion_score > 0 ? '+' : '' }}{{ item.emotion_score?.toFixed(2) }}）</div>
                <div v-if="item.text" class="report-item-text">「{{ item.text }}」</div>
                <div v-if="item.question" class="report-item-qa"><div class="report-qa-q">质疑：{{ item.question }}</div><div class="report-qa-a">回应：{{ item.answer }}</div></div>
                <div v-if="item.special_rules && item.special_rules.length" class="report-item-rules"><span class="report-rules-label">触发规则：</span>{{ item.special_rules.join('；') }}</div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <div v-else class="summary-empty"><span>点击上方按钮，基于当前统计数据生成结构化学术报告</span></div>
    </el-card>

    <el-skeleton v-if="loading" :rows="8" animated />
    <div v-else>
      <div class="aa-charts-row aa-three-col">
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>主题总体分布</span></div></template>
          <div ref="themePieChartRef" class="aa-chart-container" />
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>情感极性总体分布</span></div></template>
          <div ref="sentimentPieChartRef" class="aa-chart-container" />
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>分期作品占比</span></div></template>
          <div ref="periodPieChartRef" class="aa-chart-container" />
        </el-card>
      </div>

      <div class="aa-stats-overview">
        <div class="aa-stat-card"><div class="aa-stat-val">{{ statsData.total_count || 0 }}</div><div class="aa-stat-lbl">有题跋作品（幅）</div></div>
        <div class="aa-stat-card" v-for="ps in statsData.period_stats" :key="ps.period"><div class="aa-stat-val">{{ ps.count }}</div><div class="aa-stat-lbl">{{ ps.period }}</div><div class="aa-stat-sub">均 {{ ps.avg_char_count }} 字</div></div>
      </div>

      <div class="aa-charts-row aa-three-col">
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>主题分布（分期对比）</span></div></template>
          <div ref="themeChartRef" class="aa-chart-container" />
          <div class="aa-chart-note"><span v-for="t in THEMES" :key="t.code" class="aa-theme-link" @click="openThemeDialog(t.name)"><span class="aa-dot" :style="{background:t.color}" />{{ t.name }}</span></div>
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>情感极性分布（分期对比）</span></div></template>
          <div ref="sentimentChartRef" class="aa-chart-container" />
          <div class="aa-chart-note">积极/中性/消极情感在各时期的占比</div>
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>题跋长度分期对比</span></div></template>
          <div ref="charCountChartRef" class="aa-chart-container" />
          <div class="aa-chart-note">各期题跋平均字符数（不含标点）</div>
        </el-card>
      </div>

      <div class="aa-charts-row aa-three-col">
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>画材/题材标签统计</span></div></template>
          <div ref="materialChartRef" class="aa-chart-container" />
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>作品尺寸统计</span></div></template>
          <div ref="sizeChartRef" class="aa-chart-container" />
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>题跋闯入率</span></div></template>
          <table class="aa-inv-table">
            <thead><tr><th>主题</th><th>闯入</th><th>边角</th><th>闯入率</th></tr></thead>
            <tbody>
              <tr v-for="item in invasiveItems" :key="item.theme" :class="{'aa-highlight': item.invasive_count > 0 && item.non_invasive_count === 0}">
                <td><strong>{{ item.theme }}</strong></td><td class="aa-num">{{ item.invasive_count }}</td><td class="aa-num">{{ item.non_invasive_count }}</td>
                <td class="aa-num"><span :class="invRateClass(item.invasive_rate)">{{ (item.invasive_rate * 100).toFixed(0) }}%</span></td>
              </tr>
            </tbody>
          </table>
          <div class="aa-inv-conclusion">{{ correlationData.significant ? (correlationData.highly_significant ? '✓ 不同主题的闯入率确实不同（p<0.01）' : '✓ 不同主题的闯入率可能不同（p<0.05）') : '✗ 样本偏少，差异可能只是巧合' }}</div>
        </el-card>
      </div>

      <div class="aa-charts-row aa-two-col">
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>题跋面积分布</span></div></template>
          <div ref="areaDistChartRef" class="aa-chart-container" />
          <div class="aa-chart-note">{{ areaDistInsight || '多数作品的题跋面积集中在10-20%区间' }}</div>
        </el-card>
        <el-card shadow="hover" class="aa-chart-card">
          <template #header><div class="card-header-title"><span>画幅大小 vs 题跋占比</span></div></template>
          <div ref="areaSizeChartRef" class="aa-chart-container" />
          <div class="aa-chart-note">{{ areaSizeInsight || '画幅大小与题跋占比无明显关联' }}</div>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="themeDialogVisible" :title="`「${themeDialogData.theme_name}」相关作品`" width="90%" append-to-body>
      <div v-if="themeDialogLoading" class="aa-dialog-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
      <div v-else>
        <div class="aa-dialog-info">共 {{ themeDialogData.total }} 幅作品</div>
        <el-table :data="themeDialogData.paintings" stripe size="small" @row-click="openPaintingDetail" style="cursor:pointer">
          <el-table-column prop="title" label="作品名称" min-width="120" />
          <el-table-column prop="period" label="分期" width="70" />
          <el-table-column prop="char_count" label="字数" width="50" align="center" />
          <el-table-column label="情感" width="60" align="center"><template #default="{row}"><el-tag size="small" :type="sentimentTagType(row.sentiment)">{{ sentimentLabel(row.sentiment) }}</el-tag></template></el-table-column>
          <el-table-column prop="inscription_content" label="题跋内容（节选）" min-width="180" show-overflow-tooltip />
        </el-table>
        <div class="aa-dialog-footer" v-if="themeDialogData.total > themeDialogData.paintings?.length">
          <el-button size="small" type="primary" plain @click="loadMoreThemePaintings" :loading="themeDialogLoadingMore">加载更多（{{ themeDialogData.total - (themeDialogData.paintings?.length || 0) }} 幅待加载）</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="sentimentDialogVisible" :title="`「${sentimentDialogData.polarity_name}」作品`" width="90%" append-to-body>
      <div v-if="sentimentDialogLoading" class="aa-dialog-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
      <div v-else>
        <div class="aa-dialog-info">共 {{ sentimentDialogData.total }} 幅作品</div>
        <el-table :data="sentimentDialogData.paintings" stripe size="small" @row-click="openPaintingDetail" style="cursor:pointer">
          <el-table-column prop="title" label="作品名称" min-width="120" />
          <el-table-column prop="period" label="分期" width="70" />
          <el-table-column prop="char_count" label="字数" width="50" align="center" />
          <el-table-column prop="inscription_content" label="题跋内容（节选）" min-width="180" show-overflow-tooltip />
        </el-table>
        <div class="aa-dialog-footer" v-if="sentimentDialogData.total > sentimentDialogData.paintings?.length">
          <el-button size="small" type="primary" plain @click="loadMoreSentimentPaintings" :loading="sentimentDialogLoadingMore">加载更多（{{ sentimentDialogData.total - (sentimentDialogData.paintings?.length || 0) }} 幅待加载）</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="periodDialogVisible" :title="`「${periodDialogData.period}」作品`" width="90%" append-to-body>
      <div v-if="periodDialogLoading" class="aa-dialog-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
      <div v-else>
        <div class="aa-dialog-info">共 {{ periodDialogData.total }} 幅作品</div>
        <el-table :data="periodDialogData.paintings" stripe size="small" @row-click="openPaintingDetail" style="cursor:pointer">
          <el-table-column prop="title" label="作品名称" min-width="120" />
          <el-table-column label="情感" width="60" align="center"><template #default="{row}"><el-tag size="small" :type="sentimentTagType(row.sentiment)">{{ sentimentLabel(row.sentiment) }}</el-tag></template></el-table-column>
          <el-table-column prop="char_count" label="字数" width="50" align="center" />
          <el-table-column prop="inscription_content" label="题跋内容（节选）" min-width="180" show-overflow-tooltip />
        </el-table>
        <div class="aa-dialog-footer" v-if="periodDialogData.total > periodDialogData.paintings?.length">
          <el-button size="small" type="primary" plain @click="loadMorePeriodPaintings" :loading="periodDialogLoadingMore">加载更多（{{ periodDialogData.total - (periodDialogData.paintings?.length || 0) }} 幅待加载）</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { Loading, RefreshRight, Download } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const artistName = route.params.name

const selectedArtist = ref(artistName)
const artistList = ref([])
const loading = ref(false)
const statsData = ref({})
const correlationData = ref({})
const sizeStats = ref(null)
const summaryData = ref('')
const summaryCached = ref(false)
const summaryLoading = ref(false)
const reportData = ref(null)
const activeReportTab = ref('')

// chart refs
const themeChartRef = ref(null); const sentimentChartRef = ref(null); const charCountChartRef = ref(null)
const themePieChartRef = ref(null); const sentimentPieChartRef = ref(null); const periodPieChartRef = ref(null)
const materialChartRef = ref(null); const sizeChartRef = ref(null)
const areaDistChartRef = ref(null); const areaSizeChartRef = ref(null)

// dialogs
const themeDialogVisible = ref(false); const themeDialogLoading = ref(false); const themeDialogLoadingMore = ref(false)
const themeDialogData = ref({ paintings: [], total: 0, theme_name: '', theme_code: 0 })
let themeDialogOffset = 0
const sentimentDialogVisible = ref(false); const sentimentDialogLoading = ref(false); const sentimentDialogLoadingMore = ref(false)
const sentimentDialogData = ref({ paintings: [], total: 0, polarity: '', polarity_name: '' })
let sentimentDialogOffset = 0
const periodDialogVisible = ref(false); const periodDialogLoading = ref(false); const periodDialogLoadingMore = ref(false)
const periodDialogData = ref({ paintings: [], total: 0, period: '' })
let periodDialogOffset = 0
const THEME_DIALOG_PAGE = 5

const invasiveItems = computed(() => {
  const items = correlationData.value.invasive_analysis?.invasive_items || []
  return [...items].sort((a, b) => b.invasive_rate - a.invasive_rate)
})

const areaSizeInsight = ref('')
const areaDistInsight = ref('')

const THEMES = [
  { code: 1, name: '身世自况', color: '#c96442' },
  { code: 2, name: '咏物寄兴', color: '#547a8c' },
  { code: 3, name: '画理自叙', color: '#a65d3f' },
  { code: 4, name: '时事讽喻', color: '#4a4a5a' },
  { code: 5, name: '吉语祥瑞', color: '#8b6f8e' },
  { code: 6, name: '交游赠答', color: '#b8a47e' },
]

function sentimentLabel(p) { return { positive: '积极', negative: '消极', neutral: '中性' }[p] || p }
function sentimentTagType(p) { return { positive: 'success', negative: 'danger', neutral: 'info' }[p] || 'info' }
function invRateClass(rate) { return rate > 0.6 ? 'aa-rate-high' : rate > 0.3 ? 'aa-rate-mid' : 'aa-rate-low' }
function renderMarkdown(text) {
  if (!text) return ''
  return text.replace(/^>\s*(.+)$/gm, '<blockquote>$1</blockquote>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>')
}

function onArtistChange() {
  if (selectedArtist.value) {
    router.replace({ name: 'ArtistAnalysis', params: { name: selectedArtist.value } })
  }
}

async function fetchArtistList() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
  } catch (e) { console.error(e) }
}

async function loadStats() {
  loading.value = true
  try {
    const params = new URLSearchParams({ artist: selectedArtist.value })
    const [statsRes, corrRes, sizeStatsRes] = await Promise.all([
      fetch(`${API_BASE}/content-analysis/stats?${params}`),
      fetch(`${API_BASE}/content-analysis/correlation?${params}`),
      fetch(`${API_BASE}/content-analysis/size-stats?${params}`),
    ])
    statsData.value = await statsRes.json()
    correlationData.value = await corrRes.json()
    sizeStats.value = await sizeStatsRes.json()
    await nextTick()
    setTimeout(() => renderCharts(), 100)
  } catch (e) { ElMessage.error('加载统计数据失败: ' + e.message) }
  finally { loading.value = false }
}

async function loadCachedSummary() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/summary`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artist: selectedArtist.value, force_regenerate: false }),
    })
    const data = await res.json()
    if (data.success && data.summary) {
      summaryData.value = data.summary; summaryCached.value = data.cached || false
      if (data.report) { reportData.value = data.report; if (data.report.sections?.length) activeReportTab.value = data.report.sections[0].id }
    }
  } catch (e) {}
}

async function generateSummary() {
  summaryLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/summary`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artist: selectedArtist.value, force_regenerate: true }),
    })
    const data = await res.json()
    if (data.success) {
      summaryData.value = data.summary; reportData.value = data.report || null; summaryCached.value = false
      if (data.report?.sections?.length) activeReportTab.value = data.report.sections[0].id
      ElMessage.success('学术报告已重新生成并保存')
    } else { ElMessage.error('生成报告失败: ' + (data.error || '未知错误')) }
  } catch (e) { ElMessage.error('生成报告失败: ' + e.message) }
  finally { summaryLoading.value = false }
}

function exportReportMarkdown() {
  if (!summaryData.value) { ElMessage.warning('暂无报告可导出'); return }
  const blob = new Blob([summaryData.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob); const a = document.createElement('a')
  a.href = url; a.download = `${selectedArtist.value}题跋分析学术报告.md`; a.click(); URL.revokeObjectURL(url)
  ElMessage.success('报告已导出')
}

function getOrCreateChart(domRef) {
  if (!domRef.value) return null
  let chart = echarts.getInstanceByDom(domRef.value)
  if (!chart) chart = echarts.init(domRef.value)
  return chart
}

function renderCharts() { renderThemeChart(); renderSentimentChart(); renderCharCountChart(); renderMaterialChart(); renderSizeChart(); renderPieCharts(); renderAreaCharts() }
function renderAreaCharts() { renderAreaDistChart(); renderAreaSizeChart() }
function renderPieCharts() { renderThemePieChart(); renderSentimentPieChart(); renderPeriodPieChart() }

function renderThemePieChart() {
  if (!themePieChartRef.value) return
  const chart = getOrCreateChart(themePieChartRef)
  const themeDist = statsData.value.theme_distribution || []
  const themeTotals = {}
  themeDist.forEach(item => { themeTotals[item.theme_name] = (themeTotals[item.theme_name] || 0) + item.count })
  const data = Object.entries(themeTotals).map(([name, value]) => {
    const theme = THEMES.find(t => t.name === name)
    return { name, value, itemStyle: { color: theme?.color } }
  }).sort((a, b) => b.value - a.value)
  chart.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0, type: 'scroll' }, series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'], avoidLabelOverlap: false, itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 }, label: { show: true, formatter: '{b}\n{d}%' }, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } }, data }] })
  chart.resize()
  chart.off('click'); chart.on('click', (params) => { if (params.name) openThemeDialog(params.name) })
}

function renderSentimentPieChart() {
  if (!sentimentPieChartRef.value) return
  const chart = getOrCreateChart(sentimentPieChartRef)
  const sentDist = statsData.value.sentiment_distribution || []
  const labelToPolarity = { '积极': 'positive', '消极': 'negative', '中性': 'neutral' }
  const sentimentTotals = {}
  sentDist.forEach(item => { const l = item.polarity === 'positive' ? '积极' : item.polarity === 'negative' ? '消极' : '中性'; sentimentTotals[l] = (sentimentTotals[l] || 0) + item.count })
  const colorMap = { '积极': '#4e8cff', '消极': '#ff6b35', '中性': '#7f7f7f' }
  const data = Object.entries(sentimentTotals).map(([name, value]) => ({ name, value, itemStyle: { color: colorMap[name] } }))
  chart.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'], avoidLabelOverlap: false, itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 }, label: { show: true, formatter: '{b}\n{d}%' }, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } }, data }] })
  chart.resize()
  chart.off('click'); chart.on('click', (params) => { if (params.name) openSentimentDialog(labelToPolarity[params.name], params.name) })
}

function renderPeriodPieChart() {
  if (!periodPieChartRef.value) return
  const chart = getOrCreateChart(periodPieChartRef)
  const periodStats = statsData.value.period_stats || []
  const colorMap = { '早期': '#a65d3f', '中期': '#547a8c', '晚期': '#8b6f8e' }
  const data = periodStats.map(p => ({ name: p.period, value: p.count, itemStyle: { color: colorMap[p.period] || '#909399' } }))
  chart.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c}幅 ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'], avoidLabelOverlap: false, itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 }, label: { show: true, formatter: '{b}\n{d}%' }, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } }, data }] })
  chart.resize()
  chart.off('click'); chart.on('click', (params) => { if (params.name) openPeriodDialog(params.name) })
}

function renderThemeChart() {
  if (!themeChartRef.value) return
  const chart = getOrCreateChart(themeChartRef)
  const themeDist = statsData.value.theme_distribution || []
  const periodOrder = { '早期': 0, '中期': 1, '晚期': 2 }
  const periods = [...new Set(themeDist.map(t => t.period))].sort((a, b) => periodOrder[a] - periodOrder[b])
  const series = THEMES.map(t => ({ name: t.name, type: 'bar', stack: 'total', itemStyle: { color: t.color }, data: periods.map(p => { const item = themeDist.find(d => d.period === p && d.theme_name === t.name); return item ? parseFloat(item.percentage.toFixed(1)) : 0 }) }))
  chart.setOption({ tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params) => { let r = params[0].name + '<br/>'; params.forEach(p => { r += p.marker + ' ' + p.seriesName + ': ' + p.value + '%<br/>' }); return r } }, legend: { bottom: 0, type: 'scroll' }, grid: { left: '3%', right: '4%', bottom: '18%', top: '8%', containLabel: true }, xAxis: { type: 'category', data: periods }, yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } }, series })
  chart.resize()
}

function renderSentimentChart() {
  if (!sentimentChartRef.value) return
  const chart = getOrCreateChart(sentimentChartRef)
  const sentDist = statsData.value.sentiment_distribution || []
  const periodOrder = { '早期': 0, '中期': 1, '晚期': 2 }
  const periods = [...new Set(sentDist.map(s => s.period))].sort((a, b) => periodOrder[a] - periodOrder[b])
  const polarities = [{ key: 'negative', label: '消极', color: '#ff6b35' }, { key: 'neutral', label: '中性', color: '#7f7f7f' }, { key: 'positive', label: '积极', color: '#4e8cff' }]
  const series = polarities.map(p => ({ name: p.label, type: 'bar', itemStyle: { color: p.color }, data: periods.map(per => { const item = sentDist.find(s => s.period === per && s.polarity === p.key); return item ? parseFloat(item.percentage.toFixed(1)) : 0 }) }))
  chart.setOption({ tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { bottom: 0 }, grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true }, xAxis: { type: 'category', data: periods }, yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } }, series })
  chart.resize()
}

function renderCharCountChart() {
  if (!charCountChartRef.value) return
  const chart = getOrCreateChart(charCountChartRef)
  const periodOrder = { '早期': 0, '中期': 1, '晚期': 2 }
  const sortedStats = (statsData.value.period_stats || []).sort((a, b) => periodOrder[a.period] - periodOrder[b.period])
  chart.setOption({ tooltip: { trigger: 'axis' }, legend: { data: ['最短', '平均字数', '最长'], bottom: 0 }, grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true }, xAxis: { type: 'category', data: sortedStats.map(p => p.period) }, yAxis: { type: 'value', name: '字符数' }, series: [{ name: '最短', type: 'bar', itemStyle: { color: '#8a8070' }, data: sortedStats.map(p => p.min_char_count || 0) }, { name: '平均字数', type: 'bar', itemStyle: { color: '#c96442' }, data: sortedStats.map(p => parseFloat(p.avg_char_count.toFixed(1))) }, { name: '最长', type: 'bar', itemStyle: { color: '#a65d3f' }, data: sortedStats.map(p => p.max_char_count) }] })
  chart.resize()
}

function renderMaterialChart() {
  if (!materialChartRef.value) return
  const chart = getOrCreateChart(materialChartRef)
  const materialTags = statsData.value.material_tags || []
  if (!materialTags.length) { chart.setOption({ title: { text: '暂无画材标签数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } }); chart.resize(); return }
  const topTags = materialTags.slice(0, 15)
  const tags = topTags.map(t => t.tag).reverse(); const counts = topTags.map(t => t.count).reverse()
  const colors = ['#c96442', '#d4785a', '#e08d72', '#eba28a', '#f5b7a2']
  chart.setOption({ tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params) => `${params[0].name}<br/>出现次数：${params[0].value}次` }, grid: { left: '3%', right: '4%', bottom: '4%', top: '8%', containLabel: true }, xAxis: { type: 'value', name: '出现次数', axisLabel: { formatter: '{value}次' } }, yAxis: { type: 'category', data: tags, axisLabel: { interval: 0, width: 60, overflow: 'truncate' } }, series: [{ type: 'bar', data: counts.map((v, i) => ({ value: v, itemStyle: { color: colors[i % colors.length] } })), label: { show: true, position: 'right', formatter: '{c}次', fontSize: 11 } }] })
  chart.resize()
}

function renderSizeChart() {
  if (!sizeChartRef.value) return
  const chart = getOrCreateChart(sizeChartRef)
  const sizeDist = sizeStats.value?.size_distribution || []
  if (!sizeDist.length) { chart.setOption({ title: { text: '暂无尺寸数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } }); chart.resize(); return }
  chart.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c}幅 ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'], avoidLabelOverlap: false, itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 }, label: { show: true, formatter: '{b}\n{d}%' }, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } }, data: sizeDist.map(item => ({ name: item.category, value: item.count, itemStyle: { color: item.category === '小幅' ? '#a65d3f' : item.category === '中幅' ? '#547a8c' : '#8b6f8e' } })) }] })
  chart.resize()
}

function renderAreaDistChart() {
  if (!areaDistChartRef.value) return
  const chart = getOrCreateChart(areaDistChartRef)
  const areaDist = statsData.value?.area_distribution || []
  if (!areaDist.length) { chart.setOption({ title: { text: '暂无面积数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } }); chart.resize(); return }
  const ranges = areaDist.map(d => d.range); const inscData = areaDist.map(d => d.inscription_count); const maxIdx = inscData.indexOf(Math.max(...inscData))
  chart.setOption({ tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params) => `${params[0].name}<br/>题跋在此区间的作品: <b>${params[0].value}</b> 幅` }, grid: { left: '10%', right: '5%', bottom: '18%', top: '10%', containLabel: true }, xAxis: { type: 'category', data: ranges, axisLabel: { fontSize: 11 }, name: '题跋面积占比', nameLocation: 'middle', nameGap: 40 }, yAxis: { type: 'value', name: '作品数', nameLocation: 'middle', nameGap: 45 }, series: [{ type: 'bar', data: inscData.map((v, idx) => ({ value: v, itemStyle: { color: idx === maxIdx ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#c96442' }, { offset: 1, color: '#e8a87c' }] } : '#d4c5b5', borderRadius: [3, 3, 0, 0] } })), barWidth: '60%', label: { show: true, position: 'top', formatter: '{c}幅', fontSize: 10, color: '#666' } }] })
  chart.resize()
  const total = inscData.reduce((a, b) => a + b, 0)
  if (total > 0) areaDistInsight.value = `最多作品的题跋面积在${ranges[maxIdx]}（${((inscData[maxIdx] / total) * 100).toFixed(0)}%），${inscData[maxIdx]}幅作品集中于此`
}

const PERIOD_COLORS = [{ name: '早期', color: '#c96442' }, { name: '中期', color: '#547a8c' }, { name: '晚期', color: '#4a4a5a' }, { name: '未分期', color: '#ccc' }]

function renderAreaSizeChart() {
  if (!areaSizeChartRef.value) return
  const chart = getOrCreateChart(areaSizeChartRef)
  const corrData = statsData.value?.area_size_correlation || []
  if (!corrData.length) { chart.setOption({ title: { text: '暂无相关性数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } }); chart.resize(); return }
  const periodGroups = {}
  corrData.forEach(d => { const p = d.period || '未分期'; if (!periodGroups[p]) periodGroups[p] = []; periodGroups[p].push(d) })
  const sortedPeriods = Object.keys(periodGroups).sort((a, b) => { const o = { '早期': 0, '中期': 1, '晚期': 2 }; return (o[a] ?? 9) - (o[b] ?? 9) })
  chart.setOption({ tooltip: { formatter: (params) => { const d = params.data; return `<b>${d.title || '未命名'}</b><br/>画高 ${d.height}cm<br/>题跋占 ${d.insc.toFixed(1)}%<br/>${d.period}` } }, legend: { data: sortedPeriods.filter(p => p !== '未分期'), bottom: 0 }, grid: { left: '10%', right: '5%', bottom: '16%', top: '8%', containLabel: true }, xAxis: { type: 'value', name: '画幅高度 (cm)', nameLocation: 'middle', nameGap: 40, axisLabel: { formatter: '{value}cm' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(0,0,0,0.06)' } } }, yAxis: { type: 'value', name: '题跋占比 (%)', nameLocation: 'middle', nameGap: 50, axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(0,0,0,0.06)' } } }, series: sortedPeriods.map(pName => { const pColor = PERIOD_COLORS.find(p => p.name === pName)?.color || '#ccc'; return { name: pName, type: 'scatter', symbolSize: 10, itemStyle: { color: pColor, opacity: 0.75, borderColor: '#fff', borderWidth: 1 }, data: periodGroups[pName].map(d => ({ value: [d.artwork_height_cm, d.inscription_percent], title: d.title, height: d.artwork_height_cm, insc: d.inscription_percent, period: d.period })) } }) })
  chart.resize()
  if (corrData.length >= 10) computeAreaSizeInsight(corrData)
}

function computeAreaSizeInsight(corrData) {
  const n = corrData.length; const meanH = corrData.reduce((s, d) => s + (d.artwork_height_cm || 0), 0) / n
  const meanI = corrData.reduce((s, d) => s + (d.inscription_percent || 0), 0) / n
  let num = 0, denH = 0, denI = 0
  corrData.forEach(d => { const h = (d.artwork_height_cm || 0) - meanH; const i = (d.inscription_percent || 0) - meanI; num += h * i; denH += h * h; denI += i * i })
  const r = denH && denI ? num / Math.sqrt(denH * denI) : 0
  const absR = Math.abs(r)
  if (absR < 0.15) areaSizeInsight.value = '画幅大小与题跋占比几乎无关——无论大画小画，题跋策略始终如一'
  else if (absR < 0.3) areaSizeInsight.value = r > 0 ? '大画略多题跋，但关联不强' : '小幅作品略多题跋，但关联不强'
  else areaSizeInsight.value = r > 0 ? `大画题跋明显更多（相关系数 ${r.toFixed(2)}）` : `小幅作品题跋反而更多（相关系数 ${r.toFixed(2)}）`
}

async function openThemeDialog(themeName) {
  const theme = THEMES.find(t => t.name === themeName)
  if (!theme) return
  themeDialogVisible.value = true; themeDialogLoading.value = true
  themeDialogData.value = { paintings: [], total: 0, theme_name: themeName, theme_code: theme.code }; themeDialogOffset = 0
  try { const res = await fetch(`${API_BASE}/content-analysis/theme/${theme.code}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=0`); const data = await res.json(); if (data.success) { themeDialogData.value = data; themeDialogOffset = data.paintings.length } }
  catch (e) { ElMessage.error('加载失败: ' + e.message) }
  finally { themeDialogLoading.value = false }
}

function openPaintingDetail(row) { window.open(`/#/tubi/${row.id}`, '_blank') }

async function openSentimentDialog(polarity, polarityName) {
  sentimentDialogVisible.value = true; sentimentDialogLoading.value = true
  sentimentDialogData.value = { paintings: [], total: 0, polarity, polarity_name: polarityName }; sentimentDialogOffset = 0
  try { const res = await fetch(`${API_BASE}/content-analysis/sentiment/${polarity}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=0`); const data = await res.json(); if (data.success) { sentimentDialogData.value = data; sentimentDialogOffset = data.paintings.length } }
  catch (e) { ElMessage.error('加载失败: ' + e.message) }
  finally { sentimentDialogLoading.value = false }
}

async function loadMoreSentimentPaintings() {
  sentimentDialogLoadingMore.value = true
  try { const res = await fetch(`${API_BASE}/content-analysis/sentiment/${sentimentDialogData.value.polarity}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=${sentimentDialogOffset}`); const data = await res.json(); if (data.success) { sentimentDialogData.value.paintings.push(...data.paintings); sentimentDialogOffset += data.paintings.length } }
  catch (e) { ElMessage.error('加载更多失败: ' + e.message) }
  finally { sentimentDialogLoadingMore.value = false }
}

async function openPeriodDialog(period) {
  periodDialogVisible.value = true; periodDialogLoading.value = true
  periodDialogData.value = { paintings: [], total: 0, period }; periodDialogOffset = 0
  try { const res = await fetch(`${API_BASE}/content-analysis/period/${encodeURIComponent(period)}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=0`); const data = await res.json(); if (data.success) { periodDialogData.value = data; periodDialogOffset = data.paintings.length } }
  catch (e) { ElMessage.error('加载失败: ' + e.message) }
  finally { periodDialogLoading.value = false }
}

async function loadMorePeriodPaintings() {
  periodDialogLoadingMore.value = true
  try { const res = await fetch(`${API_BASE}/content-analysis/period/${encodeURIComponent(periodDialogData.value.period)}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=${periodDialogOffset}`); const data = await res.json(); if (data.success) { periodDialogData.value.paintings.push(...data.paintings); periodDialogOffset += data.paintings.length } }
  catch (e) { ElMessage.error('加载更多失败: ' + e.message) }
  finally { periodDialogLoadingMore.value = false }
}

async function loadMoreThemePaintings() {
  themeDialogLoadingMore.value = true
  try { const res = await fetch(`${API_BASE}/content-analysis/theme/${themeDialogData.value.theme_code}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=${themeDialogOffset}`); const data = await res.json(); if (data.success) { themeDialogData.value.paintings.push(...data.paintings); themeDialogOffset += data.paintings.length } }
  catch (e) { ElMessage.error('加载更多失败: ' + e.message) }
  finally { themeDialogLoadingMore.value = false }
}

onMounted(async () => {
  await fetchArtistList()
  if (selectedArtist.value) { loadStats(); loadCachedSummary() }
})
</script>

<style scoped>
.artist-sub-page { max-width: 1400px; margin: 0 auto; padding: 24px 20px 80px; min-height: 100vh; background: #fafaf8; }
.asp-hero { margin-bottom: 8px; }
.asp-hero-title { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-back-link:hover { color: #c45a3c; }
.asp-sub-nav { display: flex; border-bottom: 1px solid #edeae1; margin-bottom: 16px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.aa-header-actions { display: flex; justify-content: flex-end; margin-bottom: 20px; }
.aa-header-actions .el-select { width: 140px; }

/* 摘要卡片 */
.aa-summary-card { margin-bottom: 24px; border-radius: 12px; border: 1px solid #e8e6dc; background: linear-gradient(135deg, #fffdf8, #faf8f2); border-left: 4px solid #c96442; }
.aa-summary-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: 1px solid #f0eee6; }
.aa-summary-card :deep(.el-card__body) { padding: 16px 20px; }
.aa-insight-icon { color: #c96442; font-size: 16px; margin-right: 6px; }
.card-header-title { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; color: #141413; font-family: 'Noto Serif SC', serif; }
.summary-btn { margin-left: auto; display: inline-flex; align-items: center; gap: 4px; border-radius: 8px; font-weight: 500; }
.summary-loading { display: flex; align-items: center; gap: 10px; color: #87867f; padding: 8px 0; font-size: 14px; }
.summary-empty { color: #b0aeaa; font-size: 14px; padding: 8px 0; font-style: italic; }

.report-tabs { border-radius: 12px; overflow: hidden; }
.report-tabs :deep(.el-tabs__header) { background: #faf9f7; border-bottom: 1px solid #e8e4da; margin: 0; }
.report-tabs :deep(.el-tabs__item) { font-size: 13px; font-weight: 500; color: #5e5d59; height: 40px; line-height: 40px; padding: 0 16px; }
.report-tabs :deep(.el-tabs__item.is-active) { color: #c96442; font-weight: 600; background: #fff; border-radius: 8px 8px 0 0; }
.report-tabs :deep(.el-tabs__content) { padding: 16px 12px; background: #fff; }
.report-table { font-size: 13px; }
.report-section-markdown { font-size: 14px; line-height: 2; color: #3d3d3a; }
.report-section-markdown blockquote { margin: 0 0 12px; padding: 8px 16px; border-left: 3px solid #c96442; background: #faf9f7; color: #5e5d59; font-style: italic; }
.report-list-item { padding: 12px 0; border-bottom: 1px dashed #e8e4da; }
.report-list-item:last-child { border-bottom: none; }
.report-item-title { font-size: 14px; font-weight: 600; color: #141413; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.report-item-meta { font-size: 13px; color: #5e5d59; margin-bottom: 6px; }
.report-meta-label { color: #87867f; margin-right: 2px; }
.report-item-text { font-size: 13px; color: #5e5d59; font-style: italic; line-height: 1.8; padding: 4px 0; }
.report-item-qa { margin-top: 8px; padding: 8px 12px; background: #faf9f7; border-radius: 6px; }
.report-qa-q { font-size: 13px; color: #c96442; font-weight: 500; margin-bottom: 4px; }
.report-qa-a { font-size: 13px; color: #3d3d3a; line-height: 1.8; }
.report-item-rules { font-size: 12px; color: #87867f; margin-top: 6px; }
.report-rules-label { font-weight: 500; }

/* 统计 + 图表区 */
.aa-stats-overview { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.aa-stat-card { flex: 1; min-width: 140px; text-align: center; padding: 20px 16px; background: #fff; border-radius: 12px; border: 1px solid #e8e6dc; }
.aa-stat-val { font-size: 36px; font-weight: 700; color: #c96442; font-family: 'Noto Serif SC', serif; }
.aa-stat-lbl { font-size: 13px; color: #5e5d59; margin-top: 6px; font-weight: 500; }
.aa-stat-sub { font-size: 12px; color: #87867f; margin-top: 4px; }
.aa-charts-row { display: grid; gap: 20px; margin-bottom: 24px; }
.aa-three-col { grid-template-columns: repeat(3, 1fr); }
.aa-two-col { grid-template-columns: repeat(2, 1fr); }
@media (max-width: 1100px) { .aa-three-col { grid-template-columns: repeat(2, 1fr); } .aa-two-col { grid-template-columns: 1fr; } }
@media (max-width: 768px) { .aa-three-col { grid-template-columns: 1fr; } }
.aa-chart-card { width: 100%; background: #fff; border-radius: 12px; border: 1px solid #e8e6dc; }
.aa-chart-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: 1px solid #f0eee6; }
.aa-chart-container { height: 260px; width: 100%; }
.aa-chart-note { font-size: 12px; color: #87867f; margin-top: 10px; line-height: 1.5; }
.aa-theme-link { display: inline-flex; align-items: center; gap: 6px; margin-right: 12px; font-size: 12px; color: #5e5d59; cursor: pointer; }
.aa-theme-link:hover { color: #c96442; }
.aa-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }

.aa-inv-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.aa-inv-table th { text-align: left; padding: 8px 10px; background: #f5f4ed; color: #3d3d3a; font-weight: 600; font-size: 11px; }
.aa-inv-table td { padding: 6px 10px; border-bottom: 1px solid #f0eee6; font-size: 12px; }
.aa-num { text-align: right; }
.aa-highlight { background: #fdf2f0 !important; }
.aa-inv-conclusion { margin-top: 8px; padding: 6px 10px; font-size: 12px; color: #5e5d59; background: #faf9f5; border-radius: 6px; text-align: center; }
.aa-rate-high { color: #c96442; font-weight: 600; }
.aa-rate-mid { color: #b8a47e; }
.aa-rate-low { color: #87867f; }

.aa-dialog-loading { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 40px 0; color: #87867f; }
.aa-dialog-info { font-size: 14px; color: #5e5d59; margin-bottom: 12px; }
.aa-dialog-footer { margin-top: 16px; text-align: center; }
</style>
