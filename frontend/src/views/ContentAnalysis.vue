<template>
  <div class="content-analysis data-dashboard">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title-group">
        <h1 class="page-title">大数据分析</h1>
        <p class="page-subtitle">分期量化统计 · 主题分布 · 词频分析 · 内容-形式关联</p>
        <div class="header-ornament">
          <span class="ornament-line"></span>
          <span class="ornament-dot">◇</span>
          <span class="ornament-line"></span>
        </div>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedArtist" size="small" class="claude-select" @change="onArtistChange">
          <el-option v-for="artist in artistList" :key="artist" :value="artist" :label="artist" />
        </el-select>
        <el-button class="claude-btn-primary" size="small" @click="router.push('/content-verify')">
          <el-icon><Edit /></el-icon>管理后台
        </el-button>
      </div>
    </div>

    <!-- AI 总结 -->
    <el-card shadow="never" class="summary-card">
      <template #header>
        <div class="card-header-title">
          <span class="header-insight-icon">✦</span>
          <span>AI 数据洞察</span>
          <span class="model-badge">qwen-plus</span>
          <el-tag v-if="summaryCached && summaryData" type="success" size="small" class="cached-tag">已缓存</el-tag>
          <el-button
            size="small"
            type="primary"
            plain
            @click="generateSummary"
            :loading="summaryLoading"
            class="summary-btn"
          >
            <el-icon><MagicStick /></el-icon>
            {{ summaryData ? '重新生成' : '生成总结' }}
          </el-button>
        </div>
      </template>
      <div v-if="summaryLoading" class="summary-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>AI 正在分析数据，请稍候...</span>
      </div>
      <div v-else-if="summaryData" class="summary-content">
        <div
          class="insight-prose"
          v-html="'<div class=\'insight-para\'>' + highlightInsight(summaryData) + '</div>'"
        />
      </div>
      <div v-else class="summary-empty">
        <span>点击上方按钮，基于当前统计数据生成专业学术洞察</span>
      </div>
    </el-card>

    <!-- 术语说明 -->
    <el-card shadow="never" class="legend-card">
      <div class="legend-grid">
        <div class="legend-item" v-for="item in LEGEND_ITEMS" :key="item.term">
          <el-tooltip :content="item.desc" placement="top" :show-after="300">
            <span class="legend-term">{{ item.term }}</span>
          </el-tooltip>
        </div>
      </div>
    </el-card>

    <el-skeleton v-if="loading" :rows="8" animated />

    <div v-else>
      <!-- 总体分布饼图 -->
      <div class="charts-row">
        <el-card shadow="hover" class="chart-card pie-card">
          <template #header>
            <div class="card-header-title">
              <span>主题总体分布</span>
            </div>
          </template>
          <div ref="themePieChartRef" class="chart-container pie-container" />
        </el-card>
        <el-card shadow="hover" class="chart-card pie-card">
          <template #header>
            <div class="card-header-title">
              <span>情感极性总体分布</span>
            </div>
          </template>
          <div ref="sentimentPieChartRef" class="chart-container pie-container" />
        </el-card>
        <el-card shadow="hover" class="chart-card pie-card">
          <template #header>
            <div class="card-header-title">
              <span>分期作品占比</span>
            </div>
          </template>
          <div ref="periodPieChartRef" class="chart-container pie-container" />
        </el-card>
      </div>

      <!-- 数据概览 -->
      <div class="stats-overview">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ statsData.total_count || 0 }}</div>
          <div class="stat-label">有题跋作品（幅）</div>
        </el-card>
        <el-card shadow="hover" class="stat-card" v-for="ps in statsData.period_stats" :key="ps.period">
          <div class="stat-value">{{ ps.count }}</div>
          <div class="stat-label">{{ ps.period }}</div>
          <div class="stat-sub">均 {{ ps.avg_char_count }} 字</div>
        </el-card>
      </div>

      <!-- 主题分布 + 情感分布 + 字数统计（一行3列） -->
      <div class="charts-row three-cols">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>主题分布（分期对比）</span>
            </div>
          </template>
          <div ref="themeChartRef" class="chart-container" />
          <div class="chart-note">
            <div class="chart-note-text">五大主题在早/中/晚期的占比变化，验证「从简到繁、从个人到社会」的演变假设</div>
            <span v-for="t in THEMES" :key="t.code" class="theme-legend-item theme-link" @click="openThemeDialog(t.name)">
              <span class="legend-dot" :style="{ background: t.color }" />{{ t.name }}
            </span>
          </div>
        </el-card>

        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>情感极性分布（分期对比）</span>
            </div>
          </template>
          <div ref="sentimentChartRef" class="chart-container" />
          <div class="chart-note">
            <div class="chart-note-text">积极/中性/消极情感在各时期的占比，验证「中期讽喻类题跋情感更消极」假设</div>
          </div>
        </el-card>

        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>题跋长度分期对比</span>
            </div>
          </template>
          <div ref="charCountChartRef" class="chart-container" />
          <div class="chart-note">
            <div class="chart-note-text">各期题跋平均字符数（不含标点），验证「早期简短、中晚期长篇」的演变规律</div>
            <div class="chart-note-text">注：晚期与早期均值差异需 t 检验验证显著性（* p&lt;0.05，** p&lt;0.01）</div>
          </div>
        </el-card>
      </div>

      <!-- 画材/题材标签统计 & 尺寸统计 & 面积-主题堆叠柱状图 -->
      <div class="charts-row">
        <el-card shadow="hover" class="chart-card material-chart-card" style="height: 420px">
          <template #header>
            <div class="card-header-title">
              <span>画材/题材标签统计</span>
            </div>
          </template>
          <div ref="materialChartRef" class="chart-container" />
          <div class="chart-note">
            从作品标题和AI分析中提取的画材标签，反映李鱓的创作题材偏好
          </div>
        </el-card>
        <el-card shadow="hover" class="chart-card size-chart-card" style="height: 420px">
          <template #header>
            <div class="card-header-title">
              <span>作品尺寸统计</span>
            </div>
          </template>
          <div ref="sizeChartRef" class="chart-container" />
          <div class="chart-note">
            李鱓作品尺寸分布（按高度），反映不同尺幅的创作比例
            小幅（&lt;70cm）/中幅（70-150cm）/大幅（&gt;150cm）
          </div>
        </el-card>
        <el-card shadow="hover" class="chart-card" style="height: 420px">
          <template #header>
            <div class="card-header-title">
              <span>面积-主题堆叠柱状图</span>
            </div>
          </template>
          <div ref="areaThemeChartRef" class="chart-container" />
          <div class="chart-note">
            不同主题下，李鱓如何分配画面空间（题跋/绘画/留白）
          </div>
        </el-card>
      </div>

      <!-- 内容-形式关联 -->
      <el-card shadow="hover" class="correlation-card">
        <template #header>
          <div class="card-header-title">
            <span>内容-形式关联分析（侵入式布局）</span>
            <el-tag v-if="correlationData.significant" type="success" size="small">
              {{ correlationData.highly_significant ? '** 显著' : '* 显著' }}
            </el-tag>
            <el-tooltip content="分析「内容激昂→侵入式布局」「内容淡雅→边角规整式」的协同规律">
              <span class="hint-icon">?</span>
            </el-tooltip>
          </div>
        </template>

        <div class="correlation-body">
          <div class="inv-table-section">
            <table class="inv-table">
              <thead>
                <tr>
                  <th>主题</th>
                  <th>侵入式布局</th>
                  <th>非侵入式</th>
                  <th>侵入率</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in invasiveItems"
                  :key="item.theme"
                  :class="{ 'highlight-row': item.invasive_count > 0 && item.non_invasive_count === 0 }"
                >
                  <td><strong>{{ item.theme }}</strong></td>
                  <td class="num">{{ item.invasive_count }}</td>
                  <td class="num">{{ item.non_invasive_count }}</td>
                  <td class="num">
                    <span :class="invRateClass(item.invasive_rate)">
                      {{ (item.invasive_rate * 100).toFixed(1) }}%
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="chi2-result">
            <div class="chi2-title">卡方检验结果</div>
            <div class="chi2-stats">
              <span class="stat-item">
                <span class="stat-name">χ²</span>
                <span class="stat-val">{{ correlationData.chi2_statistic?.toFixed(4) || '—' }}</span>
              </span>
              <span class="stat-item">
                <span class="stat-name">p 值</span>
                <span class="stat-val" :class="{ 'sig-star': correlationData.significant }">
                  {{ correlationData.p_value?.toFixed(4) || '—' }}
                  {{ correlationData.significant ? (correlationData.highly_significant ? '**' : '*') : '' }}
                </span>
              </span>
              <span class="stat-item">
                <span class="stat-name">自由度</span>
                <span class="stat-val">{{ correlationData.dof ?? '—' }}</span>
              </span>
            </div>
            <div class="chi2-note">
              {{ correlationData.significant
                ? (correlationData.highly_significant
                    ? '在1%显著性水平上，内容主题与布局形式存在显著关联（p<0.01）'
                    : '在5%显著性水平上，内容主题与布局形式存在显著关联（p<0.05）')
                : '样本量偏小，结论需谨慎解读，建议增加数据量后复验'
              }}
            </div>
          </div>
        </div>
      </el-card>

      <!-- 面积数据可视化（2列） -->
      <div class="charts-row area-charts-row">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>面积分布直方图</span>
            </div>
          </template>
          <div ref="areaDistChartRef" class="chart-container" />
          <div class="chart-note">
            题跋/绘画/留白的面积区间分布，看李鱓倾向于用多大比例题跋
          </div>
        </el-card>

        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>面积-尺寸相关性散点图</span>
            </div>
          </template>
          <div ref="areaSizeChartRef" class="chart-container" />
          <div class="chart-note">
            作品尺寸与题跋面积的关系，看大画和小画的题跋策略
          </div>
        </el-card>
      </div>
    </div>
  </div>

  <!-- 主题饼图点击弹窗 -->
<el-dialog
  v-model="themeDialogVisible"
  :title="`「${themeDialogData.theme_name}」相关作品`"
  width="90%"
  :append-to-body="true"
>
  <div v-if="themeDialogLoading" class="dialog-loading">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>加载中...</span>
  </div>
  <div v-else>
    <div class="dialog-info">共 {{ themeDialogData.total }} 幅作品</div>
    <el-table :data="themeDialogData.paintings" stripe size="small" @row-click="openPaintingDetail" style="cursor:pointer">
      <el-table-column prop="title" label="作品名称" min-width="120" />
      <el-table-column prop="period" label="分期" width="70" />
      <el-table-column prop="char_count" label="字数" width="50" align="center" />
      <el-table-column label="情感" width="60" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="sentimentTagType(row.sentiment)">{{ sentimentLabel(row.sentiment) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="inscription_content" label="题跋内容（节选）" min-width="180" show-overflow-tooltip />
    </el-table>
    <div class="dialog-footer" v-if="themeDialogData.total > themeDialogData.paintings?.length">
      <el-button size="small" type="primary" plain @click="loadMoreThemePaintings" :loading="themeDialogLoadingMore">
        加载更多（{{ themeDialogData.total - (themeDialogData.paintings?.length || 0) }} 幅待加载）
      </el-button>
</div>
  </div>
</el-dialog>

<!-- 情感极性饼图点击弹窗 -->
<el-dialog
  v-model="sentimentDialogVisible"
  :title="`「${sentimentDialogData.polarity_name}」作品`"
  width="90%"
  :append-to-body="true"
>
  <div v-if="sentimentDialogLoading" class="dialog-loading">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>加载中...</span>
  </div>
  <div v-else>
    <div class="dialog-info">共 {{ sentimentDialogData.total }} 幅作品</div>
    <el-table :data="sentimentDialogData.paintings" stripe size="small" @row-click="openPaintingDetail" style="cursor:pointer">
      <el-table-column prop="title" label="作品名称" min-width="120" />
      <el-table-column prop="period" label="分期" width="70" />
      <el-table-column prop="char_count" label="字数" width="50" align="center" />
      <el-table-column prop="inscription_content" label="题跋内容（节选）" min-width="180" show-overflow-tooltip />
    </el-table>
    <div class="dialog-footer" v-if="sentimentDialogData.total > sentimentDialogData.paintings?.length">
      <el-button size="small" type="primary" plain @click="loadMoreSentimentPaintings" :loading="sentimentDialogLoadingMore">
        加载更多（{{ sentimentDialogData.total - (sentimentDialogData.paintings?.length || 0) }} 幅待加载）
      </el-button>
    </div>
  </div>
</el-dialog>

<!-- 分期饼图点击弹窗 -->
<el-dialog
  v-model="periodDialogVisible"
  :title="`「${periodDialogData.period}」作品`"
  width="90%"
  :append-to-body="true"
>
  <div v-if="periodDialogLoading" class="dialog-loading">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>加载中...</span>
  </div>
  <div v-else>
    <div class="dialog-info">共 {{ periodDialogData.total }} 幅作品</div>
    <el-table :data="periodDialogData.paintings" stripe size="small" @row-click="openPaintingDetail" style="cursor:pointer">
      <el-table-column prop="title" label="作品名称" min-width="120" />
      <el-table-column label="情感" width="60" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="sentimentTagType(row.sentiment)">{{ sentimentLabel(row.sentiment) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="char_count" label="字数" width="50" align="center" />
      <el-table-column prop="inscription_content" label="题跋内容（节选）" min-width="180" show-overflow-tooltip />
    </el-table>
    <div class="dialog-footer" v-if="periodDialogData.total > periodDialogData.paintings?.length">
<el-button size="small" type="primary" plain @click="loadMorePeriodPaintings" :loading="periodDialogLoadingMore">
        加载更多（{{ periodDialogData.total - (periodDialogData.paintings?.length || 0) }} 幅待加载）
</el-button>
    </div>
  </div>
</el-dialog>


</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { Refresh, Edit, Download, MagicStick, Loading } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

const selectedArtist = ref('')
const artistList = ref([])
const loading = ref(false)
async function fetchArtistList() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
    // URL query 优先
    const urlArtist = route.query.artist
    let initialArtist = ''
    if (urlArtist && artistList.value.includes(urlArtist)) {
      initialArtist = urlArtist
    } else if (artistList.value.includes('李鱓')) {
      initialArtist = '李鱓'
    } else if (artistList.value.length > 0) {
      initialArtist = artistList.value[0]
    }
    if (initialArtist) {
      selectedArtist.value = initialArtist
      // 首次加载数据
      loadStats()
      loadCachedSummary()
    }
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}
const statsData = ref({})
const correlationData = ref({})
const summaryData = ref('')
const summaryCached = ref(false)
const summaryLoading = ref(false)

// 作者切换处理（下拉选择 + 初始加载共用）
function onArtistChange(newArtist) {
  if (newArtist) {
    loadStats()
    loadCachedSummary()
    router.replace({ query: { ...route.query, artist: newArtist } })
  }
}

// 主题弹窗
const themeDialogVisible = ref(false)
const themeDialogLoading = ref(false)
const themeDialogLoadingMore = ref(false)
const themeDialogData = ref({ paintings: [], total: 0, theme_name: '', theme_code: 0 })
let themeDialogOffset = 0

const sentimentDialogVisible = ref(false)
const sentimentDialogLoading = ref(false)
const sentimentDialogLoadingMore = ref(false)
const sentimentDialogData = ref({ paintings: [], total: 0, polarity: '', polarity_name: '' })
let sentimentDialogOffset = 0

const periodDialogVisible = ref(false)
const periodDialogLoading = ref(false)
const periodDialogLoadingMore = ref(false)
const periodDialogData = ref({ paintings: [], total: 0, period: '' })
let periodDialogOffset = 0

const THEME_DIALOG_PAGE = 5

const themeChartRef = ref(null)
const sentimentChartRef = ref(null)
const charCountChartRef = ref(null)
const themePieChartRef = ref(null)
const sentimentPieChartRef = ref(null)
const periodPieChartRef = ref(null)
const materialChartRef = ref(null)
const sizeChartRef = ref(null)
const sizeStats = ref(null)

const areaDistChartRef = ref(null)
const areaThemeChartRef = ref(null)
const areaSizeChartRef = ref(null)


const FEATURE_DIMENSIONS = [
  { name: '核心艺术理念', words: ['水', '墨', '笔', '气', '韵', '娱', '戏', '乐', '门户', '我法'] },
  { name: '情感与心境', words: ['狂', '悲', '喜', '愁', '叹', '酣', '畅', '傲', '倔'] },
  { name: '社会与民生', words: ['民', '农', '吏', '官', '权', '贵', '霸', '世', '俗', '贾'] },
]

const LEGEND_ITEMS = [
  { term: 'TTR', desc: 'Type-Token Ratio，词汇多样性指数 = 不同词数 / 总词数，值越高说明词汇越丰富' },
  { term: '卡方检验', desc: '统计方法，验证两组分类变量是否存在显著关联（p<0.05 时认为显著）' },
  { term: '* / **', desc: '显著性标注：* 表示 p<0.05，** 表示 p<0.01，p 值越小说明结论越可信' },
  { term: '侵入式布局', desc: '题跋侵占画面主体区域的布局方式，如「侵入画位」「喧宾夺主式」，是李鱓的标志性形式特征' },
  { term: '以俗为雅', desc: '李鱓将日常生活俗物（葱姜蒜，白菜萝卜）纳入文人画的核心美学追求' },
]

const invasiveItems = computed(() => {
  return correlationData.value.invasive_analysis?.invasive_items || []
})

onMounted(() => {
  fetchArtistList()
  // loadStats/loadCachedSummary 在 fetchArtistList 内部触发
  // 从 ArtistStatsCard 跳转过来时，自动打开主题弹窗
  const themeParam = route.query.theme
  if (themeParam) {
    nextTick(() => openThemeDialog(decodeURIComponent(String(themeParam))))
  }
})

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
    // 延迟渲染确保 DOM 完全加载
    setTimeout(() => {
      renderCharts()
    }, 100)
  } catch (e) {
    ElMessage.error('加载统计数据失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// 页面加载时自动读取缓存的总结
async function loadCachedSummary() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artist: selectedArtist.value, force_regenerate: false }),
    })
    const data = await res.json()
    if (data.success && data.summary) {
      summaryData.value = data.summary
      summaryCached.value = data.cached || false
    }
  } catch (e) {
    // 静默失败，不影响主流程
  }
}

async function generateSummary() {
  summaryLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artist: selectedArtist.value, force_regenerate: true }),
    })
    const data = await res.json()
    if (data.success) {
      summaryData.value = data.summary
      summaryCached.value = false
      ElMessage.success('总结已重新生成并保存')
    } else {
      ElMessage.error('生成总结失败: ' + (data.error || '未知错误'))
    }
  } catch (e) {
    ElMessage.error('生成总结失败: ' + e.message)
  } finally {
    summaryLoading.value = false
  }
}

function getOrCreateChart(domRef) {
  if (!domRef.value) return null
  let chart = echarts.getInstanceByDom(domRef.value)
  if (!chart) {
    chart = echarts.init(domRef.value)
  }
  return chart
}

function renderCharts() {
  renderThemeChart()
  renderSentimentChart()
  renderCharCountChart()
  renderMaterialChart()
  renderSizeChart()
  renderPieCharts()
  renderAreaCharts()
}

function renderAreaCharts() {
  renderAreaDistChart()
  renderAreaThemeChart()
  renderAreaSizeChart()
}

function renderPieCharts() {
  renderThemePieChart()
  renderSentimentPieChart()
  renderPeriodPieChart()
}

function renderThemePieChart() {
  if (!themePieChartRef.value) return
  const chart = getOrCreateChart(themePieChartRef)
  const themeDist = statsData.value.theme_distribution || []
  
  // 按主题汇总（不分期）
  const themeTotals = {}
  themeDist.forEach(item => {
    themeTotals[item.theme_name] = (themeTotals[item.theme_name] || 0) + item.count
  })
  
  const data = Object.entries(themeTotals).map(([name, value]) => {
    const theme = THEMES.find(t => t.name === name)
    return { name, value, itemStyle: { color: theme?.color } }
  }).sort((a, b) => b.value - a.value)
  
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{d}%' },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data
    }]
  })
  chart.resize()
  chart.off('click')
  chart.on('click', (params) => {
    if (params.name) openThemeDialog(params.name)
  })
}

function renderSentimentPieChart() {
  if (!sentimentPieChartRef.value) return
  const chart = getOrCreateChart(sentimentPieChartRef)
  const sentDist = statsData.value.sentiment_distribution || []
  
  // 按情感汇总（不分期）
  const labelToPolarity = { '积极': 'positive', '消极': 'negative', '中性': 'neutral' }

  const sentimentTotals = {}
  sentDist.forEach(item => {
    const label = item.polarity === 'positive' ? '积极' : item.polarity === 'negative' ? '消极' : '中性'
    sentimentTotals[label] = (sentimentTotals[label] || 0) + item.count
  })
  
  const colorMap = { '积极': '#a65d3f', '消极': '#c96442', '中性': '#8a8070' }
  const data = Object.entries(sentimentTotals).map(([name, value]) => ({
    name, value, itemStyle: { color: colorMap[name] }
  }))
  
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{d}%' },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data
    }]
  })
  chart.resize()
  chart.off('click')
  chart.on('click', (params) => {
    if (params.name) openSentimentDialog(labelToPolarity[params.name], params.name)
  })
}

function renderPeriodPieChart() {
  if (!periodPieChartRef.value) return
  const chart = getOrCreateChart(periodPieChartRef)
  const periodStats = statsData.value.period_stats || []
  
  const colorMap = { '早期': '#a65d3f', '中期': '#547a8c', '晚期': '#8b6f8e', '年代不详': '#8a8a8a', '未分期': '#8a8070' }
  const data = periodStats.map(p => ({
    name: p.period,
    value: p.count,
    itemStyle: { color: colorMap[p.period] || '#909399' }
  }))
  
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}幅 ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{d}%' },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data
    }]
  })
  chart.resize()
  chart.off('click')
  chart.on('click', (params) => {
    if (params.name) openPeriodDialog(params.name)
  })
}

function renderThemeChart() {
  if (!themeChartRef.value) return
  const chart = getOrCreateChart(themeChartRef)
  const themeDist = statsData.value.theme_distribution || []
  const periodOrder = { '早期': 0, '中期': 1, '晚期': 2, '年代不详': 3 }
  const periods = [...new Set(themeDist.map(t => t.period))].sort((a, b) => periodOrder[a] - periodOrder[b])
  const series = THEMES.map(t => ({
    name: t.name, type: 'bar', stack: 'total', itemStyle: { color: t.color },
    data: periods.map(p => {
      const item = themeDist.find(d => d.period === p && d.theme_name === t.name)
      return item ? parseFloat(item.percentage.toFixed(1)) : 0
    }),
  }))
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params) => {
      let result = params[0].name + '<br/>'
      params.forEach(p => { result += `${p.marker} ${p.seriesName}: ${p.value}%<br/>` })
      return result
    }},
    legend: { bottom: 0, type: 'scroll' },
    grid: { left: '3%', right: '4%', bottom: '18%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: periods },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series,
  })
  chart.resize()
}

function renderSentimentChart() {
  if (!sentimentChartRef.value) return
  const chart = getOrCreateChart(sentimentChartRef)
  const sentDist = statsData.value.sentiment_distribution || []
  const periodOrder = { '早期': 0, '中期': 1, '晚期': 2, '年代不详': 3 }
  const periods = [...new Set(sentDist.map(s => s.period))].sort((a, b) => periodOrder[a] - periodOrder[b])
  const polarities = [
    { key: 'negative', label: '消极', color: '#c96442' },
    { key: 'neutral', label: '中性', color: '#8a8070' },
    { key: 'positive', label: '积极', color: '#a65d3f' },
  ]
  const series = polarities.map(p => ({
    name: p.label, type: 'bar', itemStyle: { color: p.color },
    data: periods.map(per => {
      const item = sentDist.find(s => s.period === per && s.polarity === p.key)
      return item ? parseFloat(item.percentage.toFixed(1)) : 0
    }),
  }))
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: periods },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series,
  })
  chart.resize()
}

function renderCharCountChart() {
  if (!charCountChartRef.value) return
  const chart = getOrCreateChart(charCountChartRef)
  const periodOrder = { '早期': 0, '中期': 1, '晚期': 2, '年代不详': 3 }
  const sortedStats = (statsData.value.period_stats || []).sort((a, b) => periodOrder[a.period] - periodOrder[b.period])
  const periods = sortedStats.map(p => p.period)
  const avgData = sortedStats.map(p => parseFloat(p.avg_char_count.toFixed(1)))
  const maxData = sortedStats.map(p => p.max_char_count)
  const minData = sortedStats.map(p => p.min_char_count || 0)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['最短', '平均字数', '最长'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: periods },
    yAxis: { type: 'value', name: '字符数' },
    series: [
      { name: '最短', type: 'bar', itemStyle: { color: '#8a8070' }, data: minData },
      { name: '平均字数', type: 'bar', itemStyle: { color: '#c96442' }, data: avgData },
      { name: '最长', type: 'bar', itemStyle: { color: '#a65d3f' }, data: maxData },
    ],
  })
  chart.resize()
}

function renderMaterialChart() {
  if (!materialChartRef.value) return
  const chart = getOrCreateChart(materialChartRef)
  const materialTags = statsData.value.material_tags || []
  
  if (!materialTags.length) {
    chart.setOption({
      title: { text: '暂无画材标签数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
    })
    return
  }
  
  // 取前15个标签（已按频次降序），reverse后最多在上（echarts水平柱状图第一个在底部）
  const topTags = materialTags.slice(0, 15)
  const tags = topTags.map(t => t.tag).reverse()
  const counts = topTags.map(t => t.count).reverse()
  const percentages = topTags.map(t => t.percentage).reverse()

  chart.setOption({
    title: { show: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: function(params) {
        const p = params[0]
        return `${p.name}<br/>出现次数：${p.value}次<br/>占比：${percentages[p.dataIndex]}%`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '4%', top: '8%', containLabel: true },
    xAxis: { 
      type: 'value', 
      name: '出现次数',
      axisLabel: { formatter: '{value}次' }
    },
    yAxis: {
      type: 'category',
      data: tags,
      axisLabel: {
        interval: 0,
        width: 60,
        overflow: 'truncate'
      }
    },
    series: [{
      type: 'bar',
      data: counts,
      itemStyle: { 
        color: function(params) {
          // 使用朱砂色系渐变
          const colors = ['#c96442', '#d4785a', '#e08d72', '#eba28a', '#f5b7a2']
          return colors[params.dataIndex % colors.length]
        }
      },
      label: {
        show: true,
        position: 'right',
        formatter: '{c}次',
        fontSize: 11
      }
    }]
  })
  chart.resize()
}

function renderSizeChart() {
  if (!sizeChartRef.value) return
  const chart = getOrCreateChart(sizeChartRef)
  
  const sizeDist = sizeStats.value?.size_distribution || []
  if (!sizeDist.length) {
    chart.setOption({
      title: { text: '暂无尺寸数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
    })
    chart.resize()
    return
  }
  
  const data = sizeDist.map(item => ({
    name: item.category,
    value: item.count,
    itemStyle: { 
      color: item.category === '小幅' ? '#a65d3f' : 
             item.category === '中幅' ? '#547a8c' : '#8b6f8e' 
    }
  }))
  
  chart.setOption({
    title: { show: false },
    tooltip: { trigger: 'item', formatter: '{b}: {c}幅 ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{d}%' },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data
    }]
  })
  chart.resize()
}

// ============ 面积分布直方图 ============
function renderAreaDistChart() {
  if (!areaDistChartRef.value) return
  const chart = getOrCreateChart(areaDistChartRef)
  const areaDist = statsData.value?.area_distribution || []
  if (!areaDist.length) {
    chart.setOption({ title: { text: '暂无面积数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } })
    chart.resize()
    return
  }

  const ranges = areaDist.map(d => d.range)
  const inscData = areaDist.map(d => d.inscription_count)
  const paintData = areaDist.map(d => d.painting_count)
  const blankData = areaDist.map(d => d.blank_count)
  console.log('[面积分布直方图] ranges:', ranges, 'areaDist:', areaDist)

  chart.setOption({
    title: { show: false },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['题跋', '绘画', '留白'], bottom: 0 },
    grid: { left: '10%', right: '5%', bottom: '20%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: ranges, axisLabel: { fontSize: 11 }, name: '面积占比区间', nameLocation: 'middle', nameGap: 40 },
    yAxis: { type: 'value', name: '作品数', nameLocation: 'middle', nameGap: 45 },
    animationDuration: 800,
    animationEasing: 'cubicOut',
    animationDelay: function(idx) { return idx * 50 },
    series: [
      { name: '题跋', type: 'bar', itemStyle: { color: '#c96442' }, data: inscData },
      { name: '绘画', type: 'bar', itemStyle: { color: '#547a8c' }, data: paintData },
      { name: '留白', type: 'bar', itemStyle: { color: '#8a8070' }, data: blankData }
    ]
  })
  chart.resize()
}

// ============ 面积-主题堆叠柱状图 ============
function renderAreaThemeChart() {
  if (!areaThemeChartRef.value) return
  const chart = getOrCreateChart(areaThemeChartRef)
  let areaTheme = statsData.value?.area_theme_stats || []
  if (!areaTheme.length) {
    chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } })
    chart.resize()
    return
  }

  // 按题跋比例从低到高排序
  areaTheme = [...areaTheme].sort((a, b) => a.avg_inscription_percent - b.avg_inscription_percent)

  const themes = areaTheme.map(t => t.theme_name)
  const inscData = areaTheme.map(t => t.avg_inscription_percent)
  const paintData = areaTheme.map(t => t.avg_painting_percent)
  const blankData = areaTheme.map(t => t.avg_blank_percent)

  chart.setOption({
    title: { show: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: function(params) {
        let result = params[0].name + '<br/>'
        let total = 0
        params.forEach(p => {
          total += p.value
          result += `${p.marker} ${p.seriesName}: ${p.value.toFixed(1)}%<br/>`
        })
        result += `总计: ${total.toFixed(0)}%`
        return result
      }
    },
    legend: { data: ['题跋', '绘画', '留白'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '20%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: themes, axisLabel: { interval: 0, rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    animationDuration: 800,
    animationEasing: 'cubicOut',
    animationDelay: function(idx) { return idx * 50 },
    series: [
      { name: '题跋', type: 'bar', stack: 'total', itemStyle: { color: '#c96442' }, data: inscData },
      { name: '绘画', type: 'bar', stack: 'total', itemStyle: { color: '#547a8c' }, data: paintData },
      { name: '留白', type: 'bar', stack: 'total', itemStyle: { color: '#8a8070' }, data: blankData }
    ]
  })
  chart.resize()
}

// ============ 面积-尺寸相关性散点图 ============
function renderAreaSizeChart() {
  if (!areaSizeChartRef.value) return
  const chart = getOrCreateChart(areaSizeChartRef)
  const corrData = statsData.value?.area_size_correlation || []
  if (!corrData.length) {
    chart.setOption({ title: { text: '暂无相关性数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } } })
    chart.resize()
    return
  }

  const themeColorMap = {}
  THEMES.forEach(t => { themeColorMap[t.name] = t.color })

  chart.setOption({
    title: { show: false },
    tooltip: {
      formatter: function(params) {
        const d = params.data
        return `${d.title || '未命名'}<br/>` +
               `高度: ${d.height}cm<br/>` +
               `题跋占比: ${d.insc.toFixed(1)}%<br/>` +
               `时期: ${d.period}<br/>` +
               `主题: ${d.theme || '未知'}`
      }
    },
    legend: { data: THEMES.map(t => t.name), bottom: 0, type: 'scroll' },
    grid: { left: '10%', right: '5%', bottom: '24%', top: '10%', containLabel: true },
    xAxis: { type: 'value', name: '作品高度 (cm)', nameLocation: 'middle', nameGap: 45 },
    yAxis: { type: 'value', name: '题跋面积占比 (%)', max: 100, nameLocation: 'middle', nameGap: 55 },
    animationDuration: 1000,
    animationEasing: 'elasticOut',
    series: THEMES.map(t => ({
      name: t.name,
      type: 'scatter',
      symbolSize: 10,
      itemStyle: { color: t.color, opacity: 0.7 },
      data: corrData
        .filter(d => d.theme_name === t.name)
        .map(d => ({
          value: [d.artwork_height_cm, d.inscription_percent],
          title: d.title,
          height: d.artwork_height_cm,
          insc: d.inscription_percent,
          period: d.period,
          theme: d.theme_name
        }))
    })).concat([{
      name: '其他',
      type: 'scatter',
      symbolSize: 10,
      itemStyle: { color: '#8a8070', opacity: 0.7 },
      data: corrData
        .filter(d => !d.theme_name || !THEMES.find(t => t.name === d.theme_name))
        .map(d => ({
          value: [d.artwork_height_cm, d.inscription_percent],
          title: d.title,
          height: d.artwork_height_cm,
          insc: d.inscription_percent,
          period: d.period,
          theme: d.theme_name
        }))
    }])
  })
  chart.resize()
}

function invRateClass(rate) {
  if (rate > 0.6) return 'rate-high'
  if (rate > 0.3) return 'rate-mid'
  return 'rate-low'
}

const THEMES = [
  { code: 1, name: '身世自况',     color: '#c96442' },  // 朱砂（李鱓核心主题）
  { code: 2, name: '咏物寄兴',   color: '#547a8c' },  // 松石
  { code: 3, name: '画理自叙',   color: '#a65d3f' },  // 赭石
  { code: 4, name: '时事讽喻',   color: '#4a4a5a' },  // 苍墨
  { code: 5, name: '吉语祥瑞',   color: '#8b6f8e' },  // 紫藤
  { code: 6, name: '交游赠答',   color: '#b8a47e' },  // 金
]

function sentimentLabel(p) {
  return { positive: '积极', negative: '消极', neutral: '中性' }[p] || p
}
function sentimentTagType(p) {
  return { positive: 'success', negative: 'danger', neutral: 'info' }[p] || 'info'
}

async function openThemeDialog(themeName) {
  const theme = THEMES.find(t => t.name === themeName)
  if (!theme) return
  themeDialogVisible.value = true
  themeDialogLoading.value = true
  themeDialogData.value = { paintings: [], total: 0, theme_name: themeName, theme_code: theme.code }
  themeDialogOffset = 0
  try {
    const res = await fetch(
      `${API_BASE}/content-analysis/theme/${theme.code}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=0`
    )
    const data = await res.json()
    if (data.success) {
      themeDialogData.value = data
      themeDialogOffset = data.paintings.length
    }
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    themeDialogLoading.value = false
  }
}

function openPaintingDetail(row) {
  window.location.href = `/#/tubi/${row.id}`
}

async function openSentimentDialog(polarity, polarityName) {
  sentimentDialogVisible.value = true
  sentimentDialogLoading.value = true
  sentimentDialogData.value = { paintings: [], total: 0, polarity, polarity_name: polarityName }
  sentimentDialogOffset = 0
  try {
    const res = await fetch(
      `${API_BASE}/content-analysis/sentiment/${polarity}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=0`
    )
    const data = await res.json()
    if (data.success) {
      sentimentDialogData.value = data
      sentimentDialogOffset = data.paintings.length
    }
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    sentimentDialogLoading.value = false
  }
}

async function loadMoreSentimentPaintings() {
  sentimentDialogLoadingMore.value = true
  try {
    const res = await fetch(
      `${API_BASE}/content-analysis/sentiment/${sentimentDialogData.value.polarity}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=${sentimentDialogOffset}`
    )
    const data = await res.json()
    if (data.success) {
      sentimentDialogData.value.paintings.push(...data.paintings)
      sentimentDialogOffset += data.paintings.length
    }
  } catch (e) {
    ElMessage.error('加载更多失败: ' + e.message)
  } finally {
    sentimentDialogLoadingMore.value = false
  }
}

async function openPeriodDialog(period) {
  periodDialogVisible.value = true
  periodDialogLoading.value = true
  periodDialogData.value = { paintings: [], total: 0, period }
  periodDialogOffset = 0
  try {
    const res = await fetch(
      `${API_BASE}/content-analysis/period/${encodeURIComponent(period)}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=0`
    )
    const data = await res.json()
    if (data.success) {
      periodDialogData.value = data
      periodDialogOffset = data.paintings.length
    }
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    periodDialogLoading.value = false
  }
}

async function loadMorePeriodPaintings() {
  periodDialogLoadingMore.value = true
  try {
    const res = await fetch(
      `${API_BASE}/content-analysis/period/${encodeURIComponent(periodDialogData.value.period)}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=${periodDialogOffset}`
    )
    const data = await res.json()
    if (data.success) {
      periodDialogData.value.paintings.push(...data.paintings)
      periodDialogOffset += data.paintings.length
    }
  } catch (e) {
    ElMessage.error('加载更多失败: ' + e.message)
  } finally {
    periodDialogLoadingMore.value = false
  }
}

function highlightInsight(text) {
  if (!text) return ''
  // 数字 + 单位 后缀（如 60%、50幅、27年、8字）
  return text
    .replace(/\n\n/g, '</div><div class="insight-para">')
    .replace(/\n/g, '<br/>')
    .replace(/(\d+[\d\.,，]*)(%|幅|次|年|字|词|厘米)/g, '<span class="data-ref">$1</span><span class="data-unit">$2</span>')
    // 纯数字引用（如 60、50 等独立数字）
    .replace(/(\d+[\d\.,，]+)(?!<)(?![^<]*<\/span>)/g, '<span class="data-ref">$1</span>')
}

async function loadMoreThemePaintings() {
  themeDialogLoadingMore.value = true
  try {
    const res = await fetch(
      `${API_BASE}/content-analysis/theme/${themeDialogData.value.theme_code}/paintings?artist=${selectedArtist.value}&limit=${THEME_DIALOG_PAGE}&offset=${themeDialogOffset}`
    )
    const data = await res.json()
    if (data.success) {
      themeDialogData.value.paintings.push(...data.paintings)
      themeDialogOffset += data.paintings.length
    }
  } catch (e) {
    ElMessage.error('加载更多失败: ' + e.message)
  } finally {
    themeDialogLoadingMore.value = false
  }
}
</script>

<style scoped>
/* Claude 风格改造 */
.content-analysis { max-width: 1400px; margin: 0 auto; padding: 32px 24px; }
.data-dashboard { background: linear-gradient(180deg, #faf9f5 0%, #f5f4ed 100%); min-height: 100vh; }

/* 页面头部 */
.page-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: flex-start; 
  margin-bottom: 28px; 
  gap: 16px;
}
.header-title-group { flex: 1; }
.page-title { 
  font-size: 32px; 
  font-weight: 600; 
  color: #141413; 
  margin: 0 0 8px;
  font-family: "Noto Serif SC", "STKaiti", serif;
  letter-spacing: 0.02em;
}
.page-subtitle { 
  font-size: 14px; 
  color: #5e5d59; 
  margin: 0 0 12px;
  font-weight: 400;
}

/* 装饰线 */
.header-ornament {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.ornament-line {
  flex: 1;
  height: 1px;
  max-width: 80px;
  background: linear-gradient(90deg, transparent, #b8a47e, transparent);
}
.ornament-dot {
  color: #b8a47e;
  font-size: 12px;
}

/* Claude 风格按钮 */
.header-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.claude-btn {
  background: #f5f4ed;
  border: 1px solid #e8e6dc;
  color: #3d3d3a;
  font-weight: 500;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  transition: all 0.2s ease;
}
.claude-btn:hover {
  background: #fff;
  border-color: #c96442;
  color: #c96442;
}
.claude-btn-primary {
  background: #c96442;
  border: 1px solid #c96442;
  color: #fff;
  font-weight: 500;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  transition: all 0.2s ease;
}
.claude-btn-primary:hover {
  background: #a8503a;
  border-color: #a8503a;
}
.claude-select { width: 120px; }
.claude-select :deep(.el-input__wrapper) {
  background: #f5f4ed;
  box-shadow: 0 0 0 1px #e8e6dc inset;
}
.claude-select :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c96442 inset;
}
/* 术语说明卡片 */
.legend-card { 
  margin-bottom: 24px; 
  background: #fff;
  border-radius: 12px;
}
.legend-card :deep(.el-card__body) {
  padding: 16px 20px;
}
.legend-grid { display: flex; flex-wrap: wrap; gap: 12px; }
.legend-term { 
  font-size: 12px; 
  color: #c96442; 
  text-decoration: underline dotted; 
  cursor: help; 
  padding: 4px 8px;
  background: #faf9f5;
  border-radius: 4px;
  transition: all 0.2s ease;
}
.legend-term:hover {
  background: #f5f4ed;
  color: #a8503a;
}

/* 统计数据卡片 */
.stats-overview { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.stat-card { 
  flex: 1; 
  min-width: 140px; 
  text-align: center; 
  padding: 20px 16px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e8e6dc;
  transition: all 0.2s ease;
}
.stat-card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
  transform: translateY(-2px);
}
.stat-value { 
  font-size: 36px; 
  font-weight: 700; 
  color: #c96442;
  font-family: "Noto Serif SC", serif;
}
.stat-label { font-size: 13px; color: #5e5d59; margin-top: 6px; font-weight: 500; }
.stat-sub { font-size: 12px; color: #87867f; margin-top: 4px; }

/* 图表区域 */
.charts-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px; }
.area-charts-row { grid-template-columns: repeat(2, 1fr); }
@media (max-width: 1200px) { 
  .charts-row { grid-template-columns: repeat(2, 1fr); } 
  .area-charts-row { grid-template-columns: 1fr; }
}
@media (max-width: 768px) { 
  .charts-row { grid-template-columns: 1fr; } 
  .area-charts-row { grid-template-columns: 1fr; }
}

.chart-card { 
  width: 100%; 
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e8e6dc;
}
.chart-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #f0eee6;
}
.pie-card { min-height: 360px; }
.pie-container { height: 280px; }
.card-header-title { 
  font-size: 15px; 
  font-weight: 600; 
  display: flex; 
  align-items: center; 
  gap: 8px;
  color: #141413;
  font-family: "Noto Serif SC", serif;
}
.hint-icon { 
  display: inline-flex; 
  align-items: center; 
  justify-content: center; 
  width: 18px; 
  height: 18px; 
  background: #f5f4ed; 
  color: #87867f; 
  border-radius: 50%; 
  font-size: 11px; 
  cursor: help;
  transition: all 0.2s ease;
}
.hint-icon:hover {
  background: #c96442;
  color: #fff;
}
.chart-container { height: 260px; width: 100%; }
.chart-note { font-size: 12px; color: #87867f; margin-top: 10px; line-height: 1.5; }
.theme-legend-item { display: inline-flex; align-items: center; gap: 6px; margin-right: 12px; font-size: 12px; color: #5e5d59; }
.theme-link { cursor: pointer; transition: color 0.2s; }
.theme-link:hover { color: #c96442; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
.feature-words-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 768px) { .feature-words-grid { grid-template-columns: 1fr; } }
.feature-dim { 
  background: #faf9f5; 
  border-radius: 10px; 
  padding: 14px 16px;
  border: 1px solid #f0eee6;
}
.dim-label { 
  font-size: 13px; 
  font-weight: 600; 
  color: #3d3d3a; 
  margin-bottom: 10px;
  font-family: "Noto Serif SC", serif;
}
.dim-words { display: flex; flex-wrap: wrap; gap: 6px; }
.feature-word-chip { 
  display: inline-block; 
  font-size: 12px; 
  padding: 4px 10px; 
  background: #fff; 
  border-radius: 6px; 
  border: 1px solid #e8e6dc;
  color: #4d4c48;
  transition: all 0.2s ease;
}
.feature-word-chip:hover {
  background: #c96442;
  color: #fff;
  border-color: #c96442;
}
.correlation-card { 
  margin-bottom: 24px; 
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e8e6dc;
}
.correlation-body { display: grid; grid-template-columns: 1fr auto; gap: 28px; align-items: start; }
@media (max-width: 900px) { .correlation-body { grid-template-columns: 1fr; } }
.inv-table { 
  width: 100%; 
  border-collapse: collapse; 
  font-size: 13px;
  border-radius: 8px;
  overflow: hidden;
}
.inv-table th { 
  text-align: left; 
  padding: 12px 16px; 
  background: #f5f4ed; 
  color: #3d3d3a; 
  font-weight: 600;
  font-family: "Noto Serif SC", serif;
}
.inv-table td { padding: 12px 16px; border-bottom: 1px solid #f0eee6; }
.inv-table tr:hover {
  background: #faf9f5;
}
.inv-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.highlight-row { background: #fdf2f0 !important; }
.highlight-row:hover { background: #fce8e5 !important; }
.rate-high { color: #c96442; font-weight: 600; }
.rate-mid { color: #b8a47e; }
.rate-low { color: #87867f; }
.chi2-result { 
  min-width: 280px; 
  background: #faf9f5; 
  border-radius: 12px; 
  padding: 20px;
  border: 1px solid #f0eee6;
}
.chi2-title { 
  font-size: 14px; 
  font-weight: 600; 
  color: #141413; 
  margin-bottom: 16px;
  font-family: "Noto Serif SC", serif;
}
.chi2-stats { display: flex; gap: 24px; margin-bottom: 16px; }
.stat-item { display: flex; flex-direction: column; gap: 4px; }
.stat-name { font-size: 12px; color: #87867f; }
.stat-val { 
  font-size: 18px; 
  font-weight: 600; 
  font-variant-numeric: tabular-nums;
  color: #141413;
}
.stat-val.sig-star { color: #5a8a4a; }
.chi2-note { font-size: 13px; color: #5e5d59; line-height: 1.6; }

/* AI 总结卡片 */
.summary-card {
  margin-bottom: 24px;
  border-radius: 12px;
  border: 1px solid #e8e6dc;
  background: linear-gradient(135deg, #fffdf8 0%, #faf8f2 100%);
  transition: box-shadow 0.3s ease;
  border-left: 4px solid #c96442;
}
.summary-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
.summary-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #f0eee6;
}
.summary-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: var(--radius-md);
  font-weight: 500;
}
.cached-tag {
  margin-left: 8px;
}
.summary-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #87867f;
  padding: 8px 0;
  font-size: 14px;
}
.summary-content {
  padding: 8px 0;
}
.summary-empty {
  color: #b0aeaa;
  font-size: 14px;
  padding: 8px 0;
  font-style: italic;
}

/* 学术洞察风格 */
.header-insight-icon {
  color: #c96442;
  font-size: 16px;
  margin-right: 6px;
}
.model-badge {
  font-size: 11px;
  background: #f5f4ed;
  color: #87867f;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 6px;
  border: 1px solid #e8e6dc;
  font-family: 'JetBrains Mono', monospace;
}

/* 洞察正文渲染 */
.insight-prose {
  font-size: 14px;
  line-height: 2;
  color: #3d3d3a;
}
.insight-prose :deep(div.insight-para) {
  margin: 0 0 14px 0;
  text-indent: 2em;
  line-height: 2;
}
.insight-prose :deep(div.insight-para:first-of-type) {
  font-weight: 600;
  color: #141413;
  margin-bottom: 6px;
  font-size: 15px;
  border-bottom: 1px solid #f0eee6;
  padding-bottom: 10px;
  text-indent: 2em;
}
/* 数据引用高亮 - Claude 风格：琥珀色 + 暖调底色 */
.insight-prose :deep(.data-ref) {
  color: #9a5c1a;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  background: #fdf5ec;
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 15px;
}
/* 数据单位 */
.insight-prose :deep(.data-unit) {
  color: #b8860b;
  font-weight: 500;
  font-size: 14px;
}

/* 主题弹窗 */
.dialog-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: #87867f;
}
.dialog-info {
  font-size: 14px;
  color: #5e5d59;
  margin-bottom: 12px;
}
/* dialog-footer 样式已移至全局 claude-design.css */




</style>
