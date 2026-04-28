<template>
  <div class="verify-panel">
    <div class="filter-section">
      <div class="filter-row">
        <div class="filter-group">
          <span class="filter-label">分期</span>
          <el-radio-group v-model="filterPeriod" size="small">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="早期">早期</el-radio-button>
            <el-radio-button value="中期">中期</el-radio-button>
            <el-radio-button value="晚期">晚期</el-radio-button>
            <el-radio-button value="年代不详">年代不详</el-radio-button>
          </el-radio-group>
        </div>
        <div class="filter-group">
          <span class="filter-label">状态</span>
          <el-radio-group v-model="verifyFilter" size="small">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="unverified">未校对</el-radio-button>
            <el-radio-button value="verified">已校对</el-radio-button>
          </el-radio-group>
        </div>
        <div class="filter-group search-group">
          <span class="filter-label">搜索</span>
          <el-input
            v-model="searchKeyword"
            placeholder="作品名/年份/题跋/ID..."
            size="small"
            style="width: 200px"
            clearable
            @keyup.enter="doSearch"
            @clear="searchKeyword = ''"
          >
            <template #suffix>
              <el-icon class="search-icon" @click="doSearch"><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>
    </div>
    <div class="progress-section">
      <div class="progress-header">
        <span class="progress-title">校对进度</span>
        <span class="progress-percent">{{ Math.round((verifiedCount / Math.max(totalCount, 1)) * 100) }}%</span>
      </div>
      <el-progress :percentage="Math.round((verifiedCount / Math.max(totalCount, 1)) * 100)" :color="progressColor" :stroke-width="6" class="verify-progress" />
    </div>
    <div v-if="currentRecord" class="verify-card">
      <div class="verify-header">
        <div class="record-meta">
          <div class="record-title-wrapper">
            <h2 v-if="!isEditingTitle" class="record-title" @click="startEditTitle">
              {{ currentRecord.title || '无标题' }}
              <el-icon class="title-edit-icon"><Edit /></el-icon>
            </h2>
            <div v-else class="title-edit-inline">
              <el-input
                v-model="editTitle"
                size="large"
                placeholder="输入作品名..."
                @keyup.enter="saveTitle"
                @blur="onTitleBlur"
                ref="titleInputRef"
              />
              <el-button size="small" type="primary" @click="saveTitle" :loading="savingTitle">保存</el-button>
              <el-button size="small" @click="cancelEditTitle">取消</el-button>
            </div>
          </div>
          <div class="record-tags">
            <span class="period-tag" :class="currentRecord.period_phase">{{ currentRecord.period_phase || '未分期' }}</span>
            <span class="year-tag">{{ currentRecord.year ? currentRecord.year + '年' : '年代不详' }}</span>
            <span v-if="currentRecord.inscription_verified" class="verified-tag"><el-icon><Check /></el-icon>已校对</span>
          </div>
        </div>
        <div class="record-nav">
          <el-button plain size="small" class="btn-edit" @click="prevRecord" :disabled="currentIndex === 0"><el-icon><ArrowLeft /></el-icon>上一条</el-button>
          <span class="nav-indicator">{{ currentIndex + 1 }} / {{ filteredRecords.length }}</span>
          <el-button plain size="small" class="btn-edit" @click="nextRecord" :disabled="currentIndex === filteredRecords.length - 1">下一条<el-icon><ArrowRight /></el-icon></el-button>
          <el-button plain size="small" class="btn-edit" @click="openAnnotator"><el-icon><Edit /></el-icon>手动标注</el-button>
          <el-button plain size="small" class="btn-edit" @click="reanalyzeRecord" :loading="reanalyzing"><el-icon><Refresh /></el-icon>重分析(v5.5)</el-button>
        </div>
      </div>
      <div class="verify-body">
        <div class="verify-image-section">
          <div class="image-card" @click="showFullImage = true">
            <img v-if="imageUrl" :src="imageUrl" :alt="currentRecord.title" class="record-image" />
            <div v-else class="image-placeholder"><el-icon><Picture /></el-icon><span>无图片</span></div>
            <div class="image-overlay"><el-icon><ZoomIn /></el-icon><span>点击查看大图</span></div>
          </div>
        </div>
        <TubiImageZoomDialog v-model="showFullImage" :image-url="fullImageUrl" title="查看大图" />
        <div class="verify-text-section">
          <div class="text-card">
            <div class="card-header">
              <div class="card-title"><el-icon><Document /></el-icon>题跋文本</div>
              <el-tooltip content="请对照图片中的题跋内容进行校对"><span class="hint-icon">?</span></el-tooltip>
            </div>
            <el-input v-model="editContent" type="textarea" :rows="6" placeholder="请输入或修改题跋文本..." class="content-input" />
            <div class="char-count">字数：{{ editContent.length }}（不含标点约 {{ charCountNoPunct }}）</div>
          </div>
          <div class="text-card translation-card" v-if="(currentRecord.inscription_modern && currentRecord.inscription_modern !== currentRecord.inscription_content) || translating">
            <div class="card-header">
              <div class="card-title"><el-icon><ChatDotRound /></el-icon>现代文翻译</div>
              <span class="translation-status" :class="{ translated: currentRecord.inscription_modern, translating: translating }">{{ currentRecord.inscription_modern ? '已翻译' : (translating ? '翻译中...' : '') }}</span>
            </div>
            <div class="translation-content" :class="{ translating: translating }">{{ currentRecord.inscription_modern || '正在翻译中，请稍候...' }}</div>
          </div>
          <div class="text-card">
            <div class="card-header">
              <div class="card-title"><el-icon><Stamp /></el-icon>印章内容</div>
              <el-tooltip content="请对照图片中的印章文字进行校对，多个印章用逗号分隔"><span class="hint-icon">?</span></el-tooltip>
              <span v-if="currentRecord.seal_verified" class="verified-badge"><el-icon><Check /></el-icon>已校对</span>
            </div>
            <!-- 印章标签插入模式 -->
            <div class="seal-tag-editor">
              <div class="seal-tags-area">
                <el-tag
                  v-for="(seal, idx) in sealTags"
                  :key="idx"
                  closable
                  :type="seal.isNew ? 'success' : undefined"
                  class="seal-tag"
                  @close="removeSealTag(idx)"
                  @mouseenter="showSealPreview(seal.name)"
                  @mouseleave="hideSealPreview"
                >
                  {{ seal.name }}
                  <template v-if="sealTypeMap[seal.name]">
                    <span class="seal-tag-type">({{ sealTypeMap[seal.name] }})</span>
                  </template>
                </el-tag>
                <el-button v-if="sealTags.length > 0" type="danger" text size="small" @click="clearAllSeals" class="clear-seals-btn">清空</el-button>
                <div v-if="previewSealName && sealImageMap[previewSealName]" class="seal-preview-popup">
                  <img :src="sealImageMap[previewSealName]" class="seal-preview-img" />
                </div>
              </div>
              <div class="seal-input-row">
                <el-input v-model="sealInput" placeholder="输入印章名回车添加" size="small" style="width: 200px;" @keyup.enter="addSealInput" />
              </div>
              <div v-if="sealLibrary.length > 0" class="seal-library">
                <div class="seal-library-title">印章库（点击添加）</div>
                <div v-for="group in groupedSeals" :key="group.type" class="seal-group">
                  <div class="seal-group-header">{{ group.type }}</div>
                  <div class="seal-library-grid">
                    <div
                      v-for="s in group.seals"
                      :key="s.name"
                      class="seal-library-item"
                      :class="{ 'is-selected': sealTags.some(t => t.name === s.name) }"
                      @click="addSealFromLibrary(s.name)"
                      @mouseenter="showSealPreview(s.name)"
                      @mouseleave="hideSealPreview"
                    >
                      <div v-if="sealImageMap[s.name]" class="seal-lib-thumb"><img :src="sealImageMap[s.name]" /></div>
                      <div v-else class="seal-lib-icon"><el-icon :size="14"><Stamp /></el-icon></div>
                      <span class="seal-lib-name">{{ s.name }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="text-card">
            <div class="card-header">
              <div class="card-title"><el-icon><Document /></el-icon>AI 分析说明</div>
              <el-tooltip content="AI 生成的分析说明，可对照图片内容进行校对"><span class="hint-icon">?</span></el-tooltip>
            </div>
            <el-input v-model="editAnalysisNote" type="textarea" :rows="4" placeholder="AI 分析说明内容..." class="content-input" />
          </div>
          <div class="action-row">
            <el-button v-if="!currentRecord.inscription_verified" plain class="btn-edit btn-primary" @click="handleSave(false)" :loading="saving"><el-icon><Check /></el-icon>确认校对</el-button>
            <el-button v-else plain class="btn-edit btn-warning" @click="handleSave(true)" :loading="saving"><el-icon><RefreshRight /></el-icon>重新校对</el-button>
            <el-button plain class="btn-edit" @click="skipRecord"><el-icon><Right /></el-icon>跳过</el-button>
            <el-button v-if="currentRecord.inscription_verified && !currentRecord.inscription_modern" plain class="btn-edit btn-primary" @click="handleTranslate" :loading="translating"><el-icon><Edit /></el-icon>翻译</el-button>
            <el-button v-else-if="currentRecord.inscription_verified && currentRecord.inscription_modern" plain class="btn-edit btn-warning" @click="handleTranslate" :loading="translating"><el-icon><RefreshRight /></el-icon>重新翻译</el-button>
            <el-button v-if="currentRecord.inscription_verified" plain class="btn-edit btn-primary" @click="handleAnalyze" :loading="analyzing"><el-icon><DataAnalysis /></el-icon>重新分析</el-button>
          </div>
          <div v-if="analysisPreview" class="analysis-preview">
            <div class="preview-header"><el-icon><DataAnalysis /></el-icon>AI 分析预览</div>
            <div class="preview-tags">
              <span v-for="theme in analysisPreview.themes" :key="theme.name" class="theme-tag">{{ theme.name }}<span class="confidence">{{ Math.round(theme.confidence * 100) }}%</span></span>
              <span class="sentiment-tag" :class="analysisPreview.sentiment?.polarity">{{ polarityLabel(analysisPreview.sentiment?.polarity) }} {{ analysisPreview.sentiment?.intensity != null && !isNaN(analysisPreview.sentiment.intensity) ? `${(analysisPreview.sentiment.intensity * 100).toFixed(0)}%` : '' }}</span>
            </div>
          </div>
          <div v-else-if="currentRecord?.inscription_content" class="analysis-preview analysis-stale">
            <div class="preview-header"><el-icon><WarningFilled /></el-icon>分析已过期</div>
            <p class="stale-hint">题跋文本已修改，请点击「重新分析」更新主题与情感</p>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="暂无需要校对的内容" />
    <el-skeleton v-if="loading" :rows="6" animated />

    <!-- 搜索结果弹窗 -->
    <el-dialog
      v-model="showSearchDialog"
      :title="searchDialogTitle"
      width="640px"
      class="search-result-dialog claude-dialog"
      destroy-on-close
    >
      <div v-if="searchLoading" class="search-loading">
        <el-skeleton :rows="4" animated />
      </div>
      <div v-else-if="searchResults.length === 0" class="search-empty">
        <el-empty description="未找到匹配记录" />
      </div>
      <div v-else class="search-result-list">
        <div
          v-for="item in searchResults"
          :key="item.id"
          class="search-result-item"
          @click="onSelectSearchResult(item)"
        >
          <div class="result-thumb">
            <img v-if="item.thumbnail_path" :src="getThumbnailUrl(item.thumbnail_path)" :alt="item.title" />
            <div v-else class="thumb-placeholder"><el-icon><Picture /></el-icon></div>
          </div>
          <div class="result-info">
            <div class="result-title">{{ item.title || '无标题' }}</div>
            <div class="result-meta">
              <span v-if="item.year" class="year-badge">{{ item.year }}年</span>
              <span v-else class="year-badge">年代不详</span>
              <span v-if="item.period_phase" class="period-badge">{{ item.period_phase }}</span>
            </div>
            <div v-if="item.inscription_content" class="result-inscription">
              {{ item.inscription_content.substring(0, 40) }}{{ item.inscription_content.length > 40 ? '...' : '' }}
            </div>
          </div>
          <el-button plain size="small" class="btn-edit btn-jump" @click.stop="onSelectSearchResult(item)">
            <el-icon><Position /></el-icon>跳转
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Bottom, RefreshRight, Refresh, Right, ZoomIn, ArrowLeft, ArrowRight, Edit, Check, Document, ChatDotRound, Stamp, Picture, DataAnalysis, Search, Position, WarningFilled } from '@element-plus/icons-vue'
import TubiImageZoomDialog from '../components/tubi/TubiImageZoomDialog.vue'
import { tubiApi, sealsApi } from '../api'

const props = defineProps({
  records: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  translating: { type: Boolean, default: false },
  analyzing: { type: Boolean, default: false },
  verifiedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  baseUrl: { type: String, default: 'http://localhost:8001' },
  apiBase: { type: String, default: 'http://localhost:8001/api/v1' },
  artist: { type: String, default: 'all' },
})
const emit = defineEmits(['save', 'translate', 'analyze', 'open-annotator', 'update-title', 'reanalyze'])

const filterPeriod = ref('')
const verifyFilter = ref('unverified')
const currentIndex = ref(0)
const editContent = ref('')
const editSealContent = ref('')
const editAnalysisNote = ref('')
const showFullImage = ref(false)
const reanalyzing = ref(false)

// 印章标签模式
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'
const sealTags = ref([])
const sealInput = ref('')
const sealLibrary = ref([])
const sealImageMap = ref({})
const sealTypeMap = ref({})
const previewSealName = ref(null)

function parseSealContent(content) {
  if (!content) return []
  const cleaned = content.replace(/^作者印[：:]\s*/, '')
  return cleaned.split(/[、，,]/).map(n => n.trim()).filter(n => n).map(n => ({ name: n, isNew: false }))
}

function sealTagsToString() {
  return sealTags.value.map(t => t.name).filter(n => n).join('、') || ''
}

function removeSealTag(idx) {
  sealTags.value.splice(idx, 1)
  editSealContent.value = sealTagsToString()
}

function clearAllSeals() {
  sealTags.value = []
  editSealContent.value = ''
}

function addSealInput() {
  const name = sealInput.value.trim()
  if (!name) return
  if (sealTags.value.some(t => t.name === name)) { ElMessage.warning('该印章已添加'); return }
  sealTags.value.push({ name, isNew: true })
  editSealContent.value = sealTagsToString()
  sealInput.value = ''
}

function addSealFromLibrary(name) {
  if (sealTags.value.some(t => t.name === name)) return
  sealTags.value.push({ name, isNew: false })
  editSealContent.value = sealTagsToString()
}

function showSealPreview(name) { previewSealName.value = name }
function hideSealPreview() { previewSealName.value = null }

// 按类型分组的印章库
const groupedSeals = computed(() => {
  const groups = []
  const typeOrder = ['名章', '闲章', '收藏印']
  const grouped = {}
  for (const s of sealLibrary.value) {
    const type = s.seal_type || '名章'
    if (!grouped[type]) grouped[type] = []
    grouped[type].push(s)
  }
  for (const t of typeOrder) {
    if (grouped[t] && grouped[t].length > 0) {
      groups.push({ type: t, seals: grouped[t] })
    }
  }
  for (const t of Object.keys(grouped)) {
    if (!typeOrder.includes(t)) {
      groups.push({ type: t, seals: grouped[t] })
    }
  }
  return groups
})

async function loadSealLibrary() {
  try {
    const params = { limit: 200 }
    if (props.artist && props.artist !== 'all') params.artist = props.artist
    const res = await sealsApi.list(params)
    if (res.success) {
      sealLibrary.value = res.seals || []
      const imgMap = {}, typeMap = {}
      for (const s of sealLibrary.value) {
        if (s.images && s.images.length > 0) {
          const img = s.images[0]
          imgMap[s.name] = img.startsWith('http') ? img : `${API_BASE.replace('/api/v1', '')}${img}`
        }
        if (s.seal_type) typeMap[s.name] = s.seal_type
      }
      sealImageMap.value = imgMap
      sealTypeMap.value = typeMap
    }
  } catch (e) { console.error('加载印章库失败', e) }
}

onMounted(() => { loadSealLibrary() })

// 作品名内联编辑
const isEditingTitle = ref(false)
const editTitle = ref('')
const titleInputRef = ref(null)
const savingTitle = ref(false)

// 搜索
const searchKeyword = ref('')
const showSearchDialog = ref(false)
const searchResults = ref([])
const searchLoading = ref(false)
const searchDialogTitle = computed(() => {
  const kw = searchKeyword.value.trim()
  return kw ? `「${kw}」的搜索结果` : '搜索结果'
})

const filteredRecords = computed(() => {
  let list = props.records
  if (filterPeriod.value) list = list.filter(r => r.period_phase === filterPeriod.value)
  if (verifyFilter.value === 'verified') list = list.filter(r => r.inscription_verified)
  else if (verifyFilter.value === 'unverified') list = list.filter(r => !r.inscription_verified)
  return list
})

// 筛选条件改变时重置 currentIndex，避免显示错误记录
watch([filterPeriod, verifyFilter], () => {
  currentIndex.value = 0
})

const currentRecord = computed(() => filteredRecords.value[currentIndex.value] || null)
const imageUrl = computed(() => {
  if (!currentRecord.value) return null
  const thumb = currentRecord.value.thumbnail_path
  if (!thumb) return null
  const normalized = thumb.replace(/\\/g, '/')
  let filename
  if (normalized.includes('/thumbnails/')) filename = normalized.split('/thumbnails/').pop()
  else if (normalized.includes('\\thumbnails\\')) filename = normalized.split('\\thumbnails\\').pop()
  else filename = normalized.split('/').pop().split('\\').pop()
  return `${props.baseUrl}/static/thumbnails/${filename}`
})
const fullImageUrl = computed(() => {
  if (!currentRecord.value) return null
  const fp = currentRecord.value.filepath
  if (!fp) return null
  const normalized = fp.replace(/\\/g, '/')
  let filename
  if (normalized.includes('/uploads/')) filename = normalized.split('/uploads/').pop()
  else if (normalized.includes('\\uploads\\')) filename = normalized.split('\\uploads\\').pop()
  else filename = normalized.split('/').pop().split('\\').pop()
  return `${props.baseUrl}/static/uploads/${filename}`
})

const charCountNoPunct = computed(() => {
  if (!editContent.value) return 0
  return editContent.value.replace(/[，。！？、；：""''（）【】《》\n\s]/g, '').length
})
const analysisPreview = computed(() => {
  if (!currentRecord.value) return null
  try {
    const raw = currentRecord.value.content_analysis
    if (!raw) return null
    if (typeof raw === 'string') return JSON.parse(raw)
    return raw
  } catch { return null }
})
const progressColor = computed(() => {
  const pct = (props.verifiedCount / Math.max(props.totalCount, 1)) * 100
  if (pct < 30) return '#b8a47e'
  if (pct < 70) return '#c96442'
  return '#5a7d5a'
})


function prevRecord() { if (currentIndex.value > 0) currentIndex.value-- }
function nextRecord() { if (currentIndex.value < filteredRecords.value.length - 1) currentIndex.value++; else ElMessage.info('已是最后一条') }
function skipRecord() { nextRecord() }
async function jumpToRecordById(id) {
  if (!id) return false
  // 先在 filteredRecords 中查找
  let idx = filteredRecords.value.findIndex(r => r.id === id)
  if (idx !== -1) {
    currentIndex.value = idx
    const rec = filteredRecords.value[idx]
    ElMessage.success(`已定位到记录：${rec.title || '无标题'} (${rec.year || '未知年份'})`)
    return true
  }
  // 如果被筛选过滤了，尝试在原始 records 中找并清除筛选
  const rawRec = props.records.find(r => r.id === id)
  if (rawRec) {
    filterPeriod.value = ''
    verifyFilter.value = ''
    // 等待 filteredRecords 因筛选清除而重新计算（watch 会异步重置 currentIndex）
    await nextTick()
    idx = filteredRecords.value.findIndex(r => r.id === id)
    if (idx !== -1) {
      currentIndex.value = idx
      ElMessage.success(`已清除筛选并定位到记录：${rawRec.title || '无标题'} (${rawRec.year || '未知年份'})`)
      return true
    }
  }
  return false
}
function openAnnotator() { if (!currentRecord.value?.id) return; emit('open-annotator', currentRecord.value.id) }
function reanalyzeRecord() { if (!currentRecord.value?.id) return; emit('reanalyze', currentRecord.value.id) }

// ── 作品名内联编辑 ────────────────────────────────
function startEditTitle() {
  if (!currentRecord.value) return
  editTitle.value = currentRecord.value.title || ''
  isEditingTitle.value = true
  nextTick(() => {
    titleInputRef.value?.focus()
  })
}

async function saveTitle() {
  if (!currentRecord.value || !isEditingTitle.value) return
  const newTitle = editTitle.value.trim()
  if (!newTitle) { ElMessage.warning('作品名不能为空'); return }
  if (newTitle === currentRecord.value.title) { isEditingTitle.value = false; return }
  savingTitle.value = true
  try {
    const imageId = currentRecord.value.image_id || currentRecord.value.id
    await tubiApi.updateImageInfo(imageId, { title: newTitle })
    emit('update-title', { id: currentRecord.value.id, image_id: imageId, title: newTitle })
    ElMessage.success('作品名已更新')
  } catch (e) {
    ElMessage.error('更新失败：' + e.message)
  } finally {
    savingTitle.value = false
    isEditingTitle.value = false
  }
}

function cancelEditTitle() {
  isEditingTitle.value = false
}

function onTitleBlur() {
  // 失焦时不自动保存，等用户明确点击"保存"
}

// ── 搜索 ──────────────────────────────────────────
function getThumbnailUrl(thumbPath) {
  if (!thumbPath) return null
  const normalized = thumbPath.replace(/\\/g, '/')
  let filename
  if (normalized.includes('/thumbnails/')) filename = normalized.split('/thumbnails/').pop()
  else if (normalized.includes('\\thumbnails\\')) filename = normalized.split('\\thumbnails\\').pop()
  else filename = normalized.split('/').pop().split('\\').pop()
  return `${props.baseUrl}/static/thumbnails/${filename}`
}

async function doSearch() {
  const kw = searchKeyword.value.trim()
  if (!kw) { ElMessage.warning('请输入搜索关键词'); return }

  // 纯数字输入：优先本地精确匹配 id
  const isPureNumeric = /^\d+$/.test(kw)
  if (isPureNumeric) {
    const numericId = parseInt(kw, 10)
    const found = props.records.find(r => r.id === numericId)
    if (found) {
      const ok = await jumpToRecordById(numericId)
      if (ok) { searchKeyword.value = ''; return }
    }
  }

  // 走 API 搜索
  showSearchDialog.value = true
  searchLoading.value = true
  searchResults.value = []
  try {
    const artistParam = props.artist === 'all' ? '' : props.artist
    const params = new URLSearchParams({ keyword: kw, limit: '50' })
    if (artistParam) params.set('artist', artistParam)
    const res = await fetch(`${props.apiBase}/content-analysis/records?${params}`)
    const data = await res.json()
    searchResults.value = data.records || []
  } catch (e) {
    ElMessage.error('搜索失败: ' + e.message)
  } finally {
    searchLoading.value = false
  }
}

async function onSelectSearchResult(item) {
  if (!item?.id) return
  const ok = await jumpToRecordById(item.id)
  if (ok) {
    showSearchDialog.value = false
    searchKeyword.value = ''
    return
  }
  // 不在当前 records 中，需要刷新后重试
  showSearchDialog.value = false
  searchKeyword.value = ''
  ElMessage.info('记录不在当前列表中，请从管理页面重新加载')
}



function polarityLabel(polarity) { const map = { positive: '积极', negative: '消极', neutral: '中性' }; return map[polarity] || '未知' }
function handleSave(isReverify) { if (!currentRecord.value) return; emit('save', { id: currentRecord.value.id, inscription_content: editContent.value, seal_content: editSealContent.value, analysis_note: editAnalysisNote.value, isReverify }) }
function handleTranslate() { if (!currentRecord.value) return; emit('translate', { id: currentRecord.value.id, inscription_content: editContent.value, originalModern: currentRecord.value.inscription_modern || '' }) }
function handleAnalyze() { if (!currentRecord.value) return; emit('analyze', { id: currentRecord.value.id }) }

watch(filteredRecords, () => { if (currentIndex.value >= filteredRecords.value.length) currentIndex.value = Math.max(0, filteredRecords.value.length - 1) })
watch(currentRecord, (rec) => { if (rec) { editContent.value = rec.inscription_content || ''; editSealContent.value = rec.seal_content || ''; sealTags.value = parseSealContent(rec.seal_content || ''); editAnalysisNote.value = rec.analysis_note || '' } })
watch(() => props.artist, () => { loadSealLibrary() })
watch(() => props.records, (newRecords) => { if (newRecords.length > 0 && currentIndex.value === 0) { editContent.value = newRecords[0].inscription_content || ''; editSealContent.value = newRecords[0].seal_content || ''; sealTags.value = parseSealContent(newRecords[0].seal_content || '') } }, { immediate: true })

defineExpose({ nextRecord, jumpToRecordById })
</script>

<style scoped>
.filter-section{background:#fff;border:1px solid #e8e6dc;border-radius:12px;padding:16px 20px;margin-bottom:20px}
.filter-row{display:flex;align-items:center;gap:32px;flex-wrap:wrap}
.filter-group{display:flex;align-items:center;gap:12px}
.filter-label{font-size:13px;color:#6b6b66;font-weight:500}
.progress-section{background:#fff;border:1px solid #e8e6dc;border-radius:12px;padding:16px 20px;margin-bottom:24px}
.progress-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.progress-title{font-size:14px;font-weight:500;color:#141413}
.progress-percent{font-size:14px;font-weight:600;color:#c96442}
.verify-progress :deep(.el-progress-bar__outer){background-color:#f0efe9;border-radius:3px}
.verify-progress :deep(.el-progress-bar__inner){border-radius:3px}
.verify-card{background:#fff;border:1px solid #e8e6dc;border-radius:16px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.02)}
.verify-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid #f0efe9;flex-wrap:wrap;gap:16px}
.record-meta{display:flex;flex-direction:column;gap:10px}
.record-title-wrapper{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap}
.record-title{font-family:'Noto Serif SC',serif;font-size:20px;font-weight:600;color:#141413;margin:0;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:color .2s}
.record-title:hover{color:#c96442}
.title-edit-icon{font-size:14px;color:#b0aeaa;opacity:0;transition:color .2s,opacity .2s}
.record-title:hover .title-edit-icon{opacity:1}
.title-edit-inline{display:flex;align-items:center;gap:8px;flex:1;min-width:0}
.title-edit-inline .el-input{flex:1;min-width:200px}
.title-edit-inline .el-input :deep(.el-input__inner){font-family:'Noto Serif SC',serif;font-size:20px;font-weight:600}
.record-tags{display:flex;align-items:center;gap:8px}
.period-tag{padding:4px 10px;border-radius:6px;font-size:12px;font-weight:500;background:#f5f4ed;color:#6b6b66}
.period-tag.\65E9\671F{background:#e8f4f0;color:#5a7d5a}
.period-tag.\4E2D\671F{background:#fff8e6;color:#b8a47e}
.period-tag.\665A\671F{background:#fdf0ed;color:#c96442}
.period-tag.\5E74\4EE3\4E0D\8BE6{background:#f0f0f0;color:#8a8a8a}
.year-tag{padding:4px 10px;border-radius:6px;font-size:12px;background:#f5f4ed;color:#6b6b66}
.verified-tag{display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:500;background:#e8f4f0;color:#5a7d5a}
.record-nav{display:flex;align-items:center;gap:10px}
.nav-indicator{font-size:14px;color:#6b6b66;min-width:70px;text-align:center;font-weight:500}
.verify-body{display:grid;grid-template-columns:1fr 2fr;gap:28px}
@media(max-width:900px){.verify-body{grid-template-columns:1fr}}
.verify-image-section{display:flex;align-items:flex-start}
.image-card{width:100%;position:relative;border-radius:12px;overflow:hidden;background:#f5f4ed;cursor:zoom-in;border:1px solid #e8e6dc}
.record-image{width:100%;height:auto;display:block;object-fit:contain}
.image-placeholder{width:100%;height:300px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:#a0a096;font-size:14px}
.image-overlay{position:absolute;bottom:0;left:0;right:0;padding:12px;background:linear-gradient(transparent,rgba(0,0,0,0.5));display:flex;align-items:center;justify-content:center;gap:6px;color:#fff;font-size:13px;opacity:0;transition:opacity .2s}
.image-card:hover .image-overlay{opacity:1}
.verify-text-section{display:flex;flex-direction:column;gap:16px}
.text-card{background:#fff;border:1px solid #e8e6dc;border-radius:12px;padding:16px}
.card-header{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.card-title{display:flex;align-items:center;gap:6px;font-size:14px;font-weight:600;color:#141413}
.hint-icon{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;background:#e8e6dc;color:#6b6b66;border-radius:50%;font-size:10px;cursor:help}
.verified-badge{display:flex;align-items:center;gap:4px;margin-left:auto;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:500;background:#e8f4f0;color:#5a7d5a}
.content-input :deep(.el-textarea__inner){background:#fafaf8;border-color:#e8e6dc;font-family:'Noto Serif SC',serif;font-size:15px;line-height:1.8}
.content-input :deep(.el-textarea__inner:focus){border-color:#c96442;box-shadow:0 0 0 2px rgba(201,100,66,0.1)}
.char-count{font-size:12px;color:#a0a096;text-align:right;margin-top:6px}
.translation-card{background:#fdfcfa}
.translation-status{margin-left:auto;font-size:11px;padding:3px 8px;border-radius:4px;background:#f0efe9;color:#6b6b66}
.translation-status.translated{background:#e8f4f0;color:#5a7d5a}
.translation-status.translating{background:#fff8e6;color:#b8a47e}
.translation-content{font-size:14px;line-height:1.8;color:#3d3d3a;background:#fff;padding:14px 16px;border-radius:8px;border:1px solid #e8e6dc;white-space:pre-wrap}
.translation-content.translating{color:#a0a096;font-style:italic}
.action-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.analysis-preview{background:#f8f8f6;border:1px solid #e8e6dc;border-radius:10px;padding:14px 16px}
.analysis-preview.analysis-stale{background:#fef8e8;border-color:#e6a23c}
.preview-header{display:flex;align-items:center;gap:6px;font-size:13px;font-weight:600;color:#141413;margin-bottom:10px}
.analysis-stale .preview-header{color:#e6a23c}
.stale-hint{font-size:12px;color:#909399;margin:0;padding:0}
.preview-tags{display:flex;flex-wrap:wrap;gap:8px}
.theme-tag{padding:5px 10px;background:#fff;border:1px solid #e8e6dc;border-radius:6px;font-size:12px;color:#141413}
.theme-tag .confidence{color:#a0a096;margin-left:4px}
.sentiment-tag{padding:5px 10px;background:#fff;border:1px solid #e8e6dc;border-radius:6px;font-size:12px}
.sentiment-tag.positive{background:#e8f4f0;border-color:#5a7d5a;color:#5a7d5a}
.sentiment-tag.negative{background:#fdf0ed;border-color:#c96442;color:#c96442}
.sentiment-tag.neutral{background:#f0efe9;border-color:#b8a47e;color:#b8a47e}

/* 按钮样式 - 确保文字垂直居中 */
:deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

:deep(.el-button__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

:deep(.el-radio-button__inner){background:#fff;border-color:#e8e6dc;color:#6b6b66}
:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner){background:#141413;border-color:#141413;color:#fff;box-shadow:none}
:deep(.el-radio-button:first-child .el-radio-button__inner){border-radius:6px 0 0 6px}
:deep(.el-radio-button:last-child .el-radio-button__inner){border-radius:0 6px 6px 0}

/* 搜索框 */
.search-group :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #e8e6dc inset;
  border-radius: 6px;
}
.search-group :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #c96442 inset;
}
.search-icon {
  cursor: pointer;
  color: #c96442;
  transition: color 0.2s;
}
.search-icon:hover {
  color: #a8513a;
}

/* 搜索结果弹窗 */
.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 480px;
  overflow-y: auto;
}
.search-result-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.search-result-item:hover {
  border-color: #d97757;
  background: #faf9f5;
  box-shadow: 0 4px 16px rgba(0,0,0,0.04);
}
.result-thumb {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f5f4ed;
  display: flex;
  align-items: center;
  justify-content: center;
}
.result-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-placeholder {
  color: #b0aea5;
  font-size: 20px;
}
.result-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.result-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 15px;
  font-weight: 500;
  color: #141413;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.year-badge {
  font-size: 12px;
  color: #c96442;
  background: rgba(201,100,66,0.08);
  padding: 1px 8px;
  border-radius: 999px;
}
.period-badge {
  font-size: 12px;
  color: #87867f;
  background: #f5f4ed;
  padding: 1px 8px;
  border-radius: 999px;
}
.result-inscription {
  font-size: 12px;
  color: #87867f;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.btn-jump {
  flex-shrink: 0;
}
.search-empty {
  padding: 20px 0;
}
.search-loading {
  padding: 8px 0;
}

/* 印章标签编辑器 */
.seal-tag-editor { width: 100%; }
.seal-tags-area { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; min-height: 32px; padding: 6px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafaf8; position: relative; }
.seal-tag { cursor: default; }
.seal-tag-type { font-size: 10px; color: #999; margin-left: 2px; }
.clear-seals-btn { margin-left: auto; }
.seal-preview-popup { position: absolute; top: -110px; left: 50%; transform: translateX(-50%); z-index: 100; background: white; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.15); padding: 6px; }
.seal-preview-img { width: 96px; height: 96px; object-fit: contain; }
.seal-input-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.seal-library { border: 1px solid #ebe8e0; border-radius: 8px; padding: 8px; background: #fdfcf9; }
.seal-library-title { font-size: 12px; color: #999; margin-bottom: 6px; }
.seal-group { margin-bottom: 4px; }
.seal-group:last-child { margin-bottom: 0; }
.seal-group-header { font-size: 11px; font-weight: 600; color: #c96442; padding: 2px 0 3px 0; border-bottom: 1px dashed #ebe8e0; margin-bottom: 3px; }
.seal-library-grid { display: flex; flex-wrap: wrap; gap: 5px; }
.seal-library-item { display: flex; align-items: center; gap: 3px; padding: 3px 7px; border-radius: 5px; border: 1px solid #e0ddd5; cursor: pointer; font-size: 12px; transition: all 0.15s; background: white; }
.seal-library-item:hover { border-color: #c96442; background: #fef8f5; }
.seal-library-item.is-selected { background: #f0ebe5; border-color: #c0b8a8; opacity: 0.6; cursor: default; }
.seal-lib-thumb { width: 18px; height: 18px; border-radius: 3px; overflow: hidden; }
.seal-lib-thumb img { width: 100%; height: 100%; object-fit: cover; }
.seal-lib-icon { color: #c0b8a8; }
.seal-lib-name { color: #333; }
.seal-lib-type { font-size: 10px; color: #aaa; }
</style>
