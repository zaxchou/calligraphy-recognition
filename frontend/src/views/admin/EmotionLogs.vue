<template>
  <div class="emotion-logs">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h1 class="page-title">情绪分析日志</h1>
          <p class="page-subtitle">墨林情绪引擎 v3 — 词库基线 vs LLM 裁判全记录</p>
        </div>
        <el-button type="primary" :loading="reanalyzeAllLoading" @click="reanalyzeAll">
          <el-icon><Refresh /></el-icon> 全部重跑
        </el-button>
      </div>
    </div>

    <!-- Stats cards -->
    <el-row :gutter="16" class="stats-row" v-if="stats">
      <el-col :xs="12" :sm="8" :md="4" v-for="card in statsCards" :key="card.label">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Filter bar -->
    <el-card class="filter-card" shadow="never">
      <el-row :gutter="12" align="middle">
        <el-col :span="6">
          <el-input v-model="filters.search" placeholder="搜索标题..." clearable @clear="loadLogs" @keyup.enter="loadLogs" />
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.method" placeholder="分析方法" clearable @change="loadLogs">
            <el-option label="词库基线" value="lexicon_only" />
            <el-option label="LLM 校正" value="llm_corrected" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.polarity" placeholder="情感极性" clearable @change="loadLogs">
            <el-option label="积极" value="positive" />
            <el-option label="消极" value="negative" />
            <el-option label="中性" value="neutral" />
            <el-option label="复杂" value="ambiguous" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.artist" placeholder="画家" clearable @change="loadLogs">
            <el-option v-for="a in artists" :key="a" :label="a" :value="a" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="loadLogs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Log table -->
    <el-card class="table-card" shadow="never">
      <el-table :data="logs" v-loading="loading" stripe @row-click="showDetail" style="cursor: pointer;">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="作品" min-width="140">
          <template #default="{ row }">
            <router-link :to="`/tubi/${row.image_id}`" @click.stop class="work-link">
              {{ row.title || '未命名' }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="artist" label="画家" width="80" />
        <el-table-column label="方法" width="100">
          <template #default="{ row }">
            <el-tag :type="row.analysis_method === 'llm_corrected' ? 'success' : 'info'" size="small">
              {{ row.analysis_method === 'llm_corrected' ? 'LLM校正' : '词库' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="词库基线" width="90">
          <template #default="{ row }">
            <span v-if="row.lexicon_combined != null" :class="scoreClass(row.lexicon_combined)">
              {{ formatScore(row.lexicon_combined) }}
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="LLM Δ" width="70">
          <template #default="{ row }">
            <span v-if="row.llm_delta != null" :class="scoreClass(row.llm_delta)">
              {{ row.llm_delta > 0 ? '+' : '' }}{{ row.llm_delta?.toFixed(2) }}
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="最终分" width="80">
          <template #default="{ row }">
            <span v-if="row.vader_normalized != null" :class="scoreClass(row.vader_normalized)">
              {{ formatScore(row.vader_normalized) }}
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="极性" width="80">
          <template #default="{ row }">
            <el-tag :type="polarityType(row.polarity)" size="small">{{ polarityLabel(row.polarity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click.stop="reanalyze(row)">重分析</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" :title="`情绪分析详情 — ${detail?.title || '未命名'}`" width="900px" top="5vh">
      <div v-if="detail" class="detail-body">
        <el-descriptions :column="3" border size="small" class="meta-desc">
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="画家">{{ detail.artist }}</el-descriptions-item>
          <el-descriptions-item label="年份">{{ detail.year || '—' }}</el-descriptions-item>
          <el-descriptions-item label="方法">{{ detail.analysis_method }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ detail.analysis_version }}</el-descriptions-item>
          <el-descriptions-item label="极性">
            <el-tag :type="polarityType(detail.combined_sentiment?.polarity)" size="small">
              {{ polarityLabel(detail.combined_sentiment?.polarity) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">逐维度分析</h4>
        <el-table :data="detail.dimensions" size="small" stripe>
          <el-table-column prop="key" label="维度" width="90" />
          <el-table-column label="词库原始分" width="90">
            <template #default="{ row }">{{ row.lexicon_raw?.toFixed(2) ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="词库归一化" width="90">
            <template #default="{ row }">{{ row.lexicon_normalized?.toFixed(3) ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="置信度" width="75">
            <template #default="{ row }">{{ row.lexicon_confidence?.toFixed(2) ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="LLM 校正量" width="90">
            <template #default="{ row }">
              <span v-if="row.llm_delta != null" :class="scoreClass(row.llm_delta)">
                {{ row.llm_delta > 0 ? '+' : '' }}{{ row.llm_delta?.toFixed(2) }}
              </span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="校正后" width="80">
            <template #default="{ row }">
              <span v-if="row.llm_adjusted != null">{{ row.llm_adjusted?.toFixed(2) }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="LLM 推理" min-width="200">
            <template #default="{ row }">
              <div class="reasoning-text">{{ row.llm_reasoning || '—' }}</div>
            </template>
          </el-table-column>
        </el-table>

        <h4 class="section-title" v-if="detail.inscription_content">题跋内容（前500字）</h4>
        <div class="inscription-preview" v-if="detail.inscription_content">
          <pre>{{ detail.inscription_content }}</pre>
        </div>

        <h4 class="section-title" v-if="detail.combined_sentiment?.weights">维度权重</h4>
        <el-table v-if="detail.combined_sentiment?.weights" :data="weightRows" size="small" stripe>
          <el-table-column prop="key" label="维度" width="100" />
          <el-table-column prop="weight" label="权重" width="80" />
        </el-table>
      </div>
      <div v-else-if="detailLoading" class="loading-wrap">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { Loading, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api/adminApi'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const artists = ref([])
const stats = ref(null)

const filters = reactive({
  search: '',
  method: '',
  polarity: '',
  artist: '',
})

const detailVisible = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

const statsCards = computed(() => {
  if (!stats.value) return []
  return [
    { label: '已分析作品', value: stats.value.total_analyzed ?? '—' },
    { label: '词库基线', value: stats.value.analysis_methods?.lexicon_only ?? '—' },
    { label: 'LLM 校正', value: stats.value.analysis_methods?.llm_corrected ?? '—' },
    { label: '积极', value: stats.value.polarity_distribution?.positive ?? '—' },
    { label: '消极', value: stats.value.polarity_distribution?.negative ?? '—' },
    { label: '中性', value: stats.value.polarity_distribution?.neutral ?? '—' },
  ]
})

const weightRows = computed(() => {
  const w = detail.value?.combined_sentiment?.weights || {}
  return Object.entries(w).map(([key, weight]) => ({ key, weight: Number(weight).toFixed(2) }))
})

function formatScore(v) {
  if (v == null) return '—'
  return (v > 0 ? '+' : '') + Number(v).toFixed(3)
}

function scoreClass(v) {
  if (v > 0.1) return 'score-positive'
  if (v < -0.1) return 'score-negative'
  return 'score-neutral'
}

function polarityType(p) {
  if (p === 'positive') return 'success'
  if (p === 'negative') return 'danger'
  if (p === 'ambiguous') return 'warning'
  return 'info'
}

function polarityLabel(p) {
  const map = { positive: '积极', negative: '消极', neutral: '中性', ambiguous: '复杂' }
  return map[p] || p || '—'
}

async function loadLogs() {
  loading.value = true
  try {
    const res = await adminApi.getEmotionLogs({
      page: page.value,
      page_size: pageSize.value,
      ...filters,
    })
    logs.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    ElMessage.error('加载日志失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await adminApi.getEmotionStats()
  } catch (e) { /* ignore */ }
}

function resetFilters() {
  filters.search = ''
  filters.method = ''
  filters.polarity = ''
  filters.artist = ''
  page.value = 1
  loadLogs()
}

async function showDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await adminApi.getEmotionLogDetail(row.id)
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const reanalyzeAllLoading = ref(false)

async function reanalyze(row) {
  try {
    await ElMessageBox.confirm(
      `确定对「${row.title || '未命名'}」重新运行 LLM 情绪校正？耗时约 3-5 秒。`,
      '确认重分析',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await adminApi.reanalyzeEmotion(row.id)
    ElMessage.success('重分析完成')
    loadLogs()
    loadStats()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('重分析失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

async function reanalyzeAll() {
  try {
    await ElMessageBox.confirm(
      '将对全部记录重新运行情绪引擎 v3 分析（词库基线 + LLM 裁判）。此操作在后台执行，可能需要几分钟。',
      '确认全部重跑',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    reanalyzeAllLoading.value = true
    await adminApi.reanalyzeAllEmotion()
    ElMessage.success('批量重分析已触发，后台执行中。稍后刷新页面查看进度。')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('触发失败: ' + (e.response?.data?.detail || e.message))
    }
  } finally {
    reanalyzeAllLoading.value = false
  }
}

onMounted(() => {
  loadLogs()
  loadStats()
})
</script>

<style scoped>
.emotion-logs {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: var(--space-2xl);
}

.page-header {
  margin-bottom: var(--space-2xl);
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-h2);
  font-weight: 500;
  color: var(--near-black);
  letter-spacing: 0.06em;
  margin: 0 0 var(--space-sm) 0;
}

.page-subtitle {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  color: var(--stone-gray);
  margin: 0;
}

.stats-row {
  margin-bottom: var(--space-lg);
}

.stat-card {
  text-align: center;
  margin-bottom: 16px;
}

.stat-card :deep(.el-card__body) {
  padding: var(--space-lg);
}

.stat-value {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 24px;
  font-weight: 600;
  color: var(--near-black);
}

.stat-label {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  color: var(--stone-gray);
  margin-top: 4px;
}

.filter-card {
  margin-bottom: var(--space-lg);
}

.table-card {
  overflow-x: auto;
}

.pagination-wrap {
  margin-top: var(--space-lg);
  display: flex;
  justify-content: center;
}

.work-link {
  color: var(--cinnabar);
  text-decoration: none;
}

.work-link:hover {
  text-decoration: underline;
}

.score-positive {
  color: #67c23a;
  font-weight: 600;
}

.score-negative {
  color: #f56c6c;
  font-weight: 600;
}

.score-neutral {
  color: #909399;
}

.text-muted {
  color: #c0c4cc;
}

.detail-body {
  max-height: 70vh;
  overflow-y: auto;
}

.meta-desc {
  margin-bottom: var(--space-xl);
}

.section-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--near-black);
  margin: var(--space-xl) 0 var(--space-md) 0;
}

.reasoning-text {
  font-size: 12px;
  color: var(--stone-gray);
  line-height: 1.5;
  max-height: 60px;
  overflow-y: auto;
}

.inscription-preview pre {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 14px;
  line-height: 1.8;
  color: var(--near-black);
  background: var(--cream);
  padding: var(--space-lg);
  border-radius: var(--radius-md);
  white-space: pre-wrap;
  word-break: break-all;
}

.loading-wrap {
  display: flex;
  justify-content: center;
  padding: var(--space-3xl);
}
</style>
