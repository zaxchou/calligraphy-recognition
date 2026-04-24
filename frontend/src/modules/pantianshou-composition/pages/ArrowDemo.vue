<template>
  <div class="demo-root">
    <div class="demo-header">
      <h1>起承转合分析</h1>
      <p class="sub">上传国画图片，AI 自动识别"起承转合"四个关键构图点并生成线稿分析图</p>
      <div class="header-ornament">
        <span class="ornament-line"></span>
        <span class="ornament-dot">◇</span>
        <span class="ornament-line"></span>
      </div>
    </div>

    <div class="demo-body">
      <!-- 左侧：上传 + 控制 + 调试信息 -->
      <div class="panel left-panel">
        <h2>上传图片</h2>
        <div
          class="drop-zone"
          :class="{ 'drop-over': isDragOver, 'has-img': !!previewSrc }"
          @dragover.prevent="isDragOver = true"
          @dragleave.prevent="isDragOver = false"
          @drop.prevent="onDrop"
          @click="triggerFileInput"
        >
          <input ref="fileInput" type="file" accept="image/*" class="hidden-input" @change="onFileChange" />
          <div v-if="!previewSrc" class="drop-hint">
            <div class="drop-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <div>拖拽图片到此 / 点击选择</div>
            <div class="drop-sub">支持 JPG / PNG / WEBP，最大 10MB</div>
          </div>
          <img v-else :src="previewSrc" class="thumb" />
        </div>

        <button class="btn-analyze" :disabled="!selectedFile || loading" @click="analyze">
          <span v-if="loading" class="loading-content">
            <span class="spinner"></span>
            <span>{{ progressText }}</span>
          </span>
          <span v-else>分析起承转合</span>
        </button>

        <!-- 进度条 -->
        <div v-if="loading" class="progress-wrap">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <div class="progress-time">{{ progressElapsed }}s</div>
        </div>

        <div v-if="error" class="error-box">{{ error }}</div>

        <!-- 分析结果 -->
        <div v-if="result && result.llm_analysis" class="llm-result">
          <h3>分析</h3>
          <div v-if="result.path_type" class="path-type">章法类型：<strong>{{ result.path_type }}</strong></div>
          <div v-if="result.model" class="model-name">模型：{{ result.model }}</div>
          <div class="analysis-text">{{ result.llm_analysis }}</div>
        </div>

      </div>

      <!-- 右侧：线稿分析图 -->
      <div class="panel right-panel">
        <h2>线稿分析</h2>
        <div v-if="!result" class="placeholder-hint">
          上传国画图片并点击"分析起承转合"后，<br>AI 将生成白底线稿并标注起承转合箭头
        </div>
        <div v-else class="canvas-wrap">
          <div class="img-container" :style="{ width: displayW + 'px', height: displayH + 'px' }">
            <img
              :src="result.preview_image"
              class="bg-img"
              :width="displayW"
              :height="displayH"
            />
          </div>
        </div>

        <!-- 无箭头提示 -->
        <div v-if="result && (!result.arrows || result.arrows.length === 0)" class="no-arrow-warn">
          ⚠️ 当前图像未生成箭头。可能原因：墨迹太少、方向不明、或图像为纯白/纯黑。
        </div>
      </div>
    </div>

    <!-- 历史记录区域 -->
    <div class="history-section">
      <div class="history-header">
        <h2>📋 历史记录</h2>
        <div class="history-actions">
          <label v-if="history.length > 0" class="select-all-label">
            <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
            全选
          </label>
          <button
            v-if="selectedIds.length > 0"
            class="btn-delete-batch"
            @click="batchDelete"
          >
            🗑️ 删除选中 ({{ selectedIds.length }})
          </button>
          <button
            v-if="history.length > 0 && selectedIds.length === 0"
            class="btn-clear"
            @click="clearAllHistory"
          >
            🧹 清空全部
          </button>
          <button class="btn-refresh" @click="loadHistory">🔄</button>
        </div>
      </div>

      <div v-if="historyLoading" class="history-loading">加载中...</div>
      <div v-else-if="history.length === 0" class="history-empty">暂无历史记录</div>
      <div v-else class="history-grid">
        <div
          v-for="item in history"
          :key="item.id"
          class="history-card"
          :class="{ selected: selectedIds.includes(item.id), active: activeHistoryId === item.id }"
        >
          <label class="card-checkbox">
            <input type="checkbox" :value="item.id" v-model="selectedIds" />
          </label>
          <div class="card-body" @click="loadDetail(item.id)">
            <div class="card-thumb" :style="thumbStyle(item)"></div>
            <div class="card-info">
              <div class="card-meta">
                <span class="card-path" v-if="item.path_type">{{ item.path_type }}</span>
                <span class="card-material" v-if="item.material_type">{{ item.material_type }}</span>
              </div>
              <div class="card-time">{{ formatTime(item.created_at) }}</div>
              <div class="card-filename" v-if="item.image_file_name">{{ item.image_file_name }}</div>
            </div>
          </div>
          <button class="card-delete" @click.stop="deleteSingle(item.id)" title="删除">✕</button>
        </div>
      </div>
    </div>

    <!-- 确认对话框 -->
    <div v-if="confirmDialog.show" class="dialog-overlay" @click.self="confirmDialog.show = false">
      <div class="dialog-box">
        <div class="dialog-title">{{ confirmDialog.title }}</div>
        <div class="dialog-message">{{ confirmDialog.message }}</div>
        <div class="dialog-actions">
          <button class="dialog-cancel" @click="confirmDialog.show = false">取消</button>
          <button class="dialog-confirm" @click="confirmDialog.onConfirm">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const fileInput = ref(null)
const selectedFile = ref(null)
const previewSrc = ref(null)
const isDragOver = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref(null)

// 进度状态
const progressText = ref('')
const progressPercent = ref(0)
const progressElapsed = ref(0)
let progressTimer = null
let elapsedTimer = null

// 历史记录
const history = ref([])
const historyLoading = ref(false)
const selectedIds = ref([])
const activeHistoryId = ref(null)
const confirmDialog = ref({ show: false, title: '', message: '', onConfirm: () => {} })

// 显示尺寸（限制最大宽度）
const MAX_DISPLAY = 700
const displayW = computed(() => {
  if (!result.value) return 0
  const { width, height } = result.value
  const scale = Math.min(1, MAX_DISPLAY / Math.max(width, height))
  return Math.round(width * scale)
})
const displayH = computed(() => {
  if (!result.value) return 0
  const { width, height } = result.value
  const scale = Math.min(1, MAX_DISPLAY / Math.max(width, height))
  return Math.round(height * scale)
})

const isAllSelected = computed(() =>
  history.value.length > 0 && selectedIds.value.length === history.value.length
)

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedIds.value = []
  } else {
    selectedIds.value = history.value.map(h => h.id)
  }
}

// 缩略图背景（用 CSS 背景显示）
function thumbStyle(item) {
  if (item._thumbUrl) {
    return { backgroundImage: `url(${item._thumbUrl})` }
  }
  return {}
}

function triggerFileInput() {
  fileInput.value?.click()
}

function onFileChange(e) {
  const f = e.target.files?.[0]
  if (f) setFile(f)
}

function onDrop(e) {
  isDragOver.value = false
  const f = e.dataTransfer.files?.[0]
  if (f && f.type.startsWith('image/')) setFile(f)
}

function setFile(f) {
  selectedFile.value = f
  result.value = null
  activeHistoryId.value = null
  error.value = ''
  // 预览用缩略图
  const reader = new FileReader()
  reader.onload = (ev) => { previewSrc.value = ev.target.result }
  reader.readAsDataURL(f)
}

/**
 * 压缩图片：将大图缩小到 maxSide 以内，减少上传和后端处理时间
 */
function compressImage(file, maxSide = 1500, quality = 0.85) {
  return new Promise((resolve) => {
    // 小图片不压缩
    if (file.size < 500 * 1024) { resolve(file); return }
    const img = new Image()
    img.onload = () => {
      let w = img.width, h = img.height
      if (Math.max(w, h) <= maxSide) { resolve(file); return }
      const scale = maxSide / Math.max(w, h)
      w = Math.round(w * scale)
      h = Math.round(h * scale)
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, w, h)
      canvas.toBlob(blob => {
        if (blob) {
          const compressed = new File([blob], file.name, { type: 'image/jpeg' })
          console.log(`Image compressed: ${(file.size/1024).toFixed(0)}KB → ${(blob.size/1024).toFixed(0)}KB`)
          resolve(compressed)
        } else {
          resolve(file)
        }
      }, 'image/jpeg', quality)
    }
    img.onerror = () => resolve(file)
    img.src = URL.createObjectURL(file)
  })
}

// 进度阶段配置
const PROGRESS_STAGES = [
  { at: 0,  text: '正在上传图片...',       pct: 10 },
  { at: 3,  text: '正在预处理图像，生成线稿...', pct: 25 },
  { at: 8,  text: '正在调用 Qwen VL 视觉模型分析...', pct: 40 },
  { at: 25, text: 'AI 模型推理中，请耐心等待...',     pct: 55 },
  { at: 50, text: '正在解析构图走势...',   pct: 70 },
  { at: 70, text: '正在生成线稿分析图...', pct: 85 },
  { at: 90, text: '即将完成...',           pct: 95 },
]

function startProgress() {
  const stages = PROGRESS_STAGES
  const maxTime = 180

  progressText.value = stages[0].text
  progressPercent.value = stages[0].pct
  progressElapsed.value = 0

  const startTime = Date.now()
  elapsedTimer = setInterval(() => {
    progressElapsed.value = Math.floor((Date.now() - startTime) / 1000)
  }, 1000)

  progressTimer = setInterval(() => {
    const elapsed = (Date.now() - startTime) / 1000
    // 找到当前阶段
    let stage = stages[stages.length - 1]
    for (const s of stages) {
      if (elapsed < s.at) { stage = s; break }
      stage = s
    }
    progressText.value = stage.text
    progressPercent.value = stage.pct

    // 超时警告
    if (elapsed > maxTime) {
      progressText.value = `响应超时 (${Math.floor(elapsed)}s)，建议稍后重试`
      progressPercent.value = 99
    }
  }, 1000)
}

function stopProgress() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
  progressPercent.value = 100
}

async function analyze() {
  if (!selectedFile.value || loading.value) return
  loading.value = true
  error.value = ''
  result.value = null
  activeHistoryId.value = null

  // 压缩大图
  progressText.value = '正在压缩图片...'
  progressPercent.value = 5
  const compressedFile = await compressImage(selectedFile.value)

  const fd = new FormData()
  fd.append('file', compressedFile)

  startProgress()

  try {
    const res = await axios.post('/api/v1/composition/arrow-demo-llm', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000,
    })
    console.log('[ArrowDemo] Response keys:', Object.keys(res.data))
    console.log('[ArrowDemo] arrows:', res.data.arrows?.length, 'labels:', res.data.arrow_labels)
    result.value = res.data
    // 分析完成后刷新历史记录
    await loadHistory()
  } catch (e) {
    console.error('[ArrowDemo] Request failed:', e.code, e.response?.status, e.response?.data)
    if (e.code === 'ECONNABORTED') {
      error.value = '请求超时，AI 模型响应较慢，请稍后重试'
    } else {
      error.value = e.response?.data?.detail || e.message || '请求失败'
    }
  } finally {
    stopProgress()
    setTimeout(() => { loading.value = false }, 500)
  }
}

// ---- 历史记录 ----

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await axios.get('/api/v1/composition/qczh-history', {
      params: { limit: 100, offset: 0 }
    })
    history.value = res.data.items || []
    // 为每个历史项加载缩略图
    for (const item of history.value) {
      loadThumb(item)
    }
  } catch (e) {
    console.error('[History] Load failed:', e)
  } finally {
    historyLoading.value = false
  }
}

async function loadThumb(item) {
  // 单独请求缩略图（不缓存完整记录到历史列表，避免内存问题）
  // 改为懒加载：点击时再请求
  // 这里用轻量请求只获取 preview_image
  try {
    const res = await axios.get(`/api/v1/composition/qczh-history/${item.id}`)
    item._thumbUrl = res.data.preview_image
  } catch {
    // 静默失败
  }
}

async function loadDetail(id) {
  activeHistoryId.value = id
  try {
    const res = await axios.get(`/api/v1/composition/qczh-history/${id}`)
    result.value = res.data
    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    console.error('[History] Detail failed:', e)
  }
}

function deleteSingle(id) {
  showConfirm('删除记录', '确定要删除这条分析记录吗？', async () => {
    try {
      await axios.delete(`/api/v1/composition/qczh-history/${id}`)
      history.value = history.value.filter(h => h.id !== id)
      selectedIds.value = selectedIds.value.filter(i => i !== id)
      if (activeHistoryId.value === id) {
        activeHistoryId.value = null
        // 如果当前结果也是这条，清空
        result.value = null
      }
    } catch (e) {
      console.error('[History] Delete failed:', e)
    }
  })
}

function batchDelete() {
  const count = selectedIds.value.length
  showConfirm('批量删除', `确定要删除选中的 ${count} 条记录吗？`, async () => {
    try {
      await axios.post('/api/v1/composition/qczh-history/batch-delete', {
        ids: selectedIds.value
      })
      history.value = history.value.filter(h => !selectedIds.value.includes(h.id))
      if (selectedIds.value.includes(activeHistoryId.value)) {
        activeHistoryId.value = null
        result.value = null
      }
      selectedIds.value = []
    } catch (e) {
      console.error('[History] Batch delete failed:', e)
    }
  })
}

function clearAllHistory() {
  const count = history.value.length
  showConfirm('清空全部', `确定要清空全部 ${count} 条历史记录吗？此操作不可撤销。`, async () => {
    try {
      await axios.post('/api/v1/composition/qczh-history/clear-all')
      history.value = []
      selectedIds.value = []
      activeHistoryId.value = null
      result.value = null
    } catch (e) {
      console.error('[History] Clear failed:', e)
    }
  })
}

function showConfirm(title, message, onConfirm) {
  confirmDialog.value = { show: true, title, message, onConfirm }
}

function formatTime(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const m = String(d.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${h}:${m}`
  } catch {
    return isoStr
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.demo-root {
  min-height: 100vh;
  background: var(--parchment, #f5f4ed);
  font-family: var(--font-sans, "Noto Sans SC", "Source Han Sans SC", system-ui, sans-serif);
  color: var(--near-black, #141413);
}

.demo-header {
  position: relative;
  background: radial-gradient(ellipse at 50% 30%, rgba(201, 100, 66, 0.06) 0%, transparent 60%),
              linear-gradient(180deg, var(--ivory, #faf9f5) 0%, var(--parchment, #f5f4ed) 100%);
  color: var(--near-black, #141413);
  padding: 20px 32px 16px;
  text-align: center;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
  margin-top: 0;
}

.demo-header h1 {
  margin: 0 0 4px;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  font-size: 22px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--near-black, #141413);
}

.demo-header .sub {
  margin: 0;
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  letter-spacing: 0.03em;
  line-height: 1.5;
}

.header-ornament {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 10px;
}

.ornament-line {
  width: 36px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--ring-warm, #d1cfc5), transparent);
}

.ornament-dot {
  color: var(--cinnabar, #c96442);
  font-size: 12px;
  opacity: 0.4;
}

.demo-body {
  display: flex;
  gap: 20px;
  padding: 24px 32px;
  max-width: 1400px;
  margin: 0 auto;
  align-items: stretch;
}

.panel {
  background: var(--pure-white, #fff);
  border-radius: var(--radius-lg, 12px);
  padding: 24px;
  border: 1px solid var(--border-cream, #f0eee6);
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}
.panel h2 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  border-bottom: 1px solid var(--border-cream, #f0eee6);
  padding-bottom: 12px;
  letter-spacing: 0.04em;
}

.left-panel {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-panel {
  flex: 1;
  min-height: 320px;
}

/* Drop zone */
.drop-zone {
  border: 2px dashed var(--ring-warm, #d1cfc5);
  border-radius: var(--radius-lg, 12px);
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: var(--ivory, #faf9f5);
  transition: border-color 0.2s, background 0.2s;
  overflow: hidden;
}
.drop-zone.drop-over {
  border-color: var(--cinnabar, #c96442);
  background: var(--parchment, #f5f4ed);
}
.drop-zone.has-img {
  border-style: solid;
  border-color: var(--ring-deep, #c2c0b6);
}
.drop-hint {
  text-align: center;
  color: var(--olive-gray, #5e5d59);
  font-size: 13px;
  padding: 16px;
}
.drop-icon {
  color: var(--cinnabar, #c96442);
  margin-bottom: 10px;
  opacity: 0.6;
}
.drop-sub {
  font-size: 11px;
  color: var(--warm-silver, #b0aea5);
  margin-top: 6px;
}
.thumb {
  max-width: 100%;
  max-height: 200px;
  object-fit: contain;
  display: block;
}
.hidden-input {
  display: none;
}

/* 按钮 */
.btn-analyze {
  width: 100%;
  padding: 12px;
  background: var(--cinnabar, #c96442);
  color: var(--pure-white, #fff);
  border: none;
  border-radius: var(--radius-md, 8px);
  font-size: 15px;
  font-weight: 500;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  cursor: pointer;
  letter-spacing: 0.08em;
  transition: background 0.2s, opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 44px;
}
.btn-analyze:hover:not(:disabled) {
  background: var(--cinnabar-light, #d97757);
}
.btn-analyze:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.loading-content {
  display: flex;
  align-items: center;
  gap: 8px;
}
.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2.5px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 进度条 */
.progress-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--border-warm, #e8e6dc);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--cinnabar, #c96442);
  border-radius: 2px;
  transition: width 0.5s ease;
}
.progress-time {
  font-size: 12px;
  color: var(--stone-gray, #87867f);
  min-width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* 错误 */
.error-box {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  color: var(--error-crimson, #b53333);
  border-radius: var(--radius-md, 8px);
  padding: 10px 14px;
  font-size: 13px;
}

/* Canvas */
.placeholder-hint {
  text-align: center;
  padding: 80px 20px;
  color: var(--warm-silver, #b0aea5);
  font-size: 14px;
  line-height: 1.8;
}
.canvas-wrap {
  display: flex;
  justify-content: center;
  padding: 8px;
}
.img-container {
  position: relative;
  display: inline-block;
  border: 1px solid var(--border-warm, #e8e6dc);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
  box-shadow: var(--shadow-elevated, rgba(0,0,0,0.08) 0px 8px 32px);
}
.bg-img {
  display: block;
}
.no-arrow-warn {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--ivory, #faf9f5);
  border: 1px solid var(--ring-warm, #d1cfc5);
  border-radius: var(--radius-md, 8px);
  color: var(--olive-gray, #5e5d59);
  font-size: 13px;
}

/* 分析结果 */
.llm-result {
  margin-top: 12px;
  padding: 16px;
  background: var(--ivory, #faf9f5);
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-lg, 12px);
}
.llm-result h3 {
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin: 0 0 8px;
  letter-spacing: 0.04em;
}
.path-type {
  font-size: 13px;
  color: var(--charcoal-warm, #4d4c48);
  margin-bottom: 4px;
}
.path-type strong {
  color: var(--cinnabar, #c96442);
  font-weight: 600;
}
.model-name {
  font-size: 11px;
  color: var(--warm-silver, #b0aea5);
  margin-bottom: 8px;
}
.analysis-text {
  font-size: 13px;
  color: var(--dark-warm, #3d3d3a);
  line-height: 1.7;
  white-space: pre-wrap;
}

/* ========== 历史记录区域 ========== */
.history-section {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 32px 32px;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.history-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  letter-spacing: 0.04em;
}

.history-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.select-all-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--olive-gray, #5e5d59);
  cursor: pointer;
  user-select: none;
}

.btn-delete-batch,
.btn-clear,
.btn-refresh {
  padding: 6px 14px;
  border: 1px solid var(--border-warm, #e8e6dc);
  border-radius: var(--radius-md, 8px);
  background: var(--pure-white, #fff);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--charcoal-warm, #4d4c48);
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
}
.btn-delete-batch:hover,
.btn-clear:hover {
  background: #fef2f2;
  border-color: #fca5a5;
  color: var(--error-crimson, #b53333);
}
.btn-refresh:hover {
  background: var(--ivory, #faf9f5);
  border-color: var(--cinnabar-light, #d97757);
  color: var(--cinnabar, #c96442);
}

.history-loading,
.history-empty {
  text-align: center;
  padding: 48px 20px;
  color: var(--warm-silver, #b0aea5);
  font-size: 14px;
  background: var(--pure-white, #fff);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--border-cream, #f0eee6);
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}

.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.history-card {
  position: relative;
  background: var(--pure-white, #fff);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--border-cream, #f0eee6);
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.history-card:hover {
  box-shadow: var(--shadow-elevated, rgba(0,0,0,0.08) 0px 8px 32px);
  border-color: var(--cinnabar-light, #d97757);
}
.history-card.active {
  border-color: var(--cinnabar, #c96442);
  border-width: 2px;
}
.history-card.selected {
  border-color: var(--focus-blue, #3898ec);
  background: var(--ivory, #faf9f5);
  border-width: 2px;
}

.card-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: var(--cinnabar, #c96442);
}

.card-body {
  display: flex;
  cursor: pointer;
}

.card-thumb {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  background-size: cover;
  background-position: center;
  background-color: var(--parchment, #f5f4ed);
  border-right: 1px solid var(--border-cream, #f0eee6);
}

.card-info {
  padding: 8px 10px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.card-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.card-path {
  display: inline-block;
  padding: 1px 6px;
  background: var(--ivory, #faf9f5);
  color: var(--cinnabar, #c96442);
  border-radius: var(--radius-sm, 6px);
  font-size: 11px;
  font-weight: 500;
}
.card-material {
  font-size: 11px;
  color: var(--olive-gray, #5e5d59);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-time {
  font-size: 11px;
  color: var(--stone-gray, #87867f);
}

.card-filename {
  font-size: 10px;
  color: var(--warm-silver, #b0aea5);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-delete {
  position: absolute;
  top: 4px;
  right: 6px;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--ring-warm, #d1cfc5);
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0;
}
.history-card:hover .card-delete {
  opacity: 1;
}
.card-delete:hover {
  background: #fef2f2;
  color: var(--error-crimson, #b53333);
}

/* ========== 确认对话框 ========== */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.dialog-box {
  background: var(--pure-white, #fff);
  border-radius: var(--radius-xl, 16px);
  padding: 28px;
  width: 360px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.dialog-title {
  font-size: 16px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin-bottom: 12px;
  letter-spacing: 0.04em;
}
.dialog-message {
  font-size: 14px;
  color: var(--olive-gray, #5e5d59);
  margin-bottom: 20px;
  line-height: 1.6;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.dialog-cancel,
.dialog-confirm {
  padding: 8px 20px;
  border-radius: var(--radius-md, 8px);
  font-size: 14px;
  cursor: pointer;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  transition: all 0.2s;
  border: 1px solid var(--border-warm, #e8e6dc);
}
.dialog-cancel {
  background: var(--pure-white, #fff);
  color: var(--charcoal-warm, #4d4c48);
}
.dialog-cancel:hover {
  background: var(--ivory, #faf9f5);
}
.dialog-confirm {
  background: var(--error-crimson, #b53333);
  color: var(--pure-white, #fff);
  border-color: var(--error-crimson, #b53333);
}
.dialog-confirm:hover {
  background: #c0392b;
}
</style>
