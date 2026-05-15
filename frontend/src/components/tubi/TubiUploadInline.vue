<template>
  <div class="upload-inline">
    <!-- 步骤指示器 -->
    <div class="steps-bar">
      <div class="step" :class="{ active: phaseIdx >= 0, done: phaseIdx > 0 }">
        <span class="step-dot">1</span>
        <span class="step-label">选择图片</span>
      </div>
      <div class="step-line" :class="{ done: phaseIdx > 0 }" />
      <div class="step" :class="{ active: phaseIdx >= 1, done: phaseIdx > 1 }">
        <span class="step-dot">2</span>
        <span class="step-label">上传</span>
      </div>
      <div class="step-line" :class="{ done: phaseIdx > 1 }" />
      <div class="step" :class="{ active: phaseIdx >= 2, done: phaseIdx > 2 }">
        <span class="step-dot">3</span>
        <span class="step-label">AI 分析</span>
      </div>
      <div class="step-line" :class="{ done: phaseIdx > 2 }" />
      <div class="step" :class="{ active: phaseIdx >= 3, done: phaseIdx > 3 }">
        <span class="step-dot">✓</span>
        <span class="step-label">完成</span>
      </div>
    </div>

    <!-- 模式选择弹窗 -->
    <TubiModeSelectionDialog
      v-model="showModeSelectionDialog"
      @confirm="confirmUploadMode"
      @cancel="showModeSelectionDialog = false"
    />

    <!-- 内容区 -->
    <div class="upload-body">
      <!-- Idle -->
      <div v-if="uploadStore.phase === 'idle'">
        <UploadPhaseIdle v-model="batchFileList" :upload-store="uploadStore" />
        <div v-if="batchFileList.length > 0" class="body-actions">
          <el-button @click="clearFiles">取消</el-button>
          <el-button type="primary" @click="startBatchUpload">
            开始上传 {{ batchFileList.length }} 张
          </el-button>
        </div>
      </div>

      <!-- Uploading / Processing / Completed -->
      <div v-else class="phase-body">
        <UploadPhaseUploading
          v-if="uploadStore.phase === 'uploading'"
          :upload-store="uploadStore"
          @retry="retryUploadItem"
          @retry-all="retryAllFailed"
        />
        <UploadPhaseProcessing
          v-else-if="uploadStore.phase === 'enqueuing' || uploadStore.phase === 'polling'"
          :upload-store="uploadStore"
          @retry="retryUploadItem"
          @retry-all="retryAllFailed"
        />
        <UploadPhaseCompleted
          v-else-if="uploadStore.phase === 'completed'"
          :upload-store="uploadStore"
          @retry-all="retryAllFailed"
        />

        <div class="body-actions">
          <template v-if="uploadStore.phase === 'uploading'">
            <el-button type="danger" @click="cancelUpload">取消上传</el-button>
          </template>
          <template v-else-if="uploadStore.phase === 'completed'">
            <el-button type="primary" @click="finishUpload">继续上传</el-button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { tubiApi } from '../../api'
import { useUploadStore, ITEM_STATUSES } from '../../stores/uploadStore'
import TubiModeSelectionDialog from './TubiModeSelectionDialog.vue'

const UploadPhaseIdle = defineAsyncComponent(() => import('./UploadPhaseIdle.vue'))
const UploadPhaseUploading = defineAsyncComponent(() => import('./UploadPhaseUploading.vue'))
const UploadPhaseProcessing = defineAsyncComponent(() => import('./UploadPhaseProcessing.vue'))
const UploadPhaseCompleted = defineAsyncComponent(() => import('./UploadPhaseCompleted.vue'))

const emit = defineEmits(['uploaded', 'refresh'])

const batchFileList = ref([])
let batchUploadCancelled = false
const showModeSelectionDialog = ref(false)
let pendingUploadedIds = []

const {
  store: uploadStore,
  markUploaded, markQueued, markAnalyzing, markDone, markError,
  resetForRetry, retryAllFailed: retryAllFailedStore,
  reset: resetStore, restore: restoreStore,
} = useUploadStore()

// 步骤索引
const phaseIdx = computed(() => {
  const map = { idle: 0, uploading: 1, enqueuing: 2, polling: 2, completed: 3 }
  return map[uploadStore.phase] ?? 0
})

// ── 上传 ──
async function startBatchUpload() {
  if (batchFileList.value.length === 0) { ElMessage.warning('请先选择图片'); return }
  batchUploadCancelled = false
  const files = batchFileList.value.map(f => ({ name: f.name, raw: f.raw }))
  const { initBatch } = useUploadStore()
  initBatch(files)

  const CONCURRENCY = 3
  const items = [...uploadStore.items]
  for (let i = 0; i < items.length; i += CONCURRENCY) {
    if (batchUploadCancelled) break
    const batch = items.slice(i, i + CONCURRENCY)
    await Promise.allSettled(batch.map(async (item) => {
      if (batchUploadCancelled) return
      try {
        const result = await tubiApi.uploadImage(item.rawFile, {})
        if (result.success) markUploaded(item.id, result.data.id, result.data.url)
        else markError(item.id, 'UPLOAD_FAILED', result.detail || '上传失败')
      } catch { markError(item.id, 'NETWORK_ERROR', '网络错误') }
    }))
    await nextTick()
  }

  if (batchUploadCancelled) { resetStore(); return }

  const completed = uploadStore.items.filter(i => i.status === ITEM_STATUSES.UPLOADED)
  if (completed.length > 0) emit('uploaded', completed.length)

  uploadStore.phase = 'enqueuing'
  await nextTick()

  pendingUploadedIds = uploadStore.items
    .filter(i => i.status === ITEM_STATUSES.UPLOADED && i.imageId)
    .map(i => i.imageId)

  if (pendingUploadedIds.length > 0) showModeSelectionDialog.value = true
  else finishUpload()
}

// ── 模式确认 ──
async function confirmUploadMode(mode) {
  if (mode === 'manual') {
    uploadStore.items.forEach(item => { if (item.imageId) markQueued(item.id, null, null) })
    finishUpload()
    ElMessage.success('已录入完成，可前往手工标注')
    return
  }
  try {
    const r = await tubiApi.batchAutoAnalyze(pendingUploadedIds, mode)
    if (r.success) r.data.forEach(x => {
      const it = uploadStore.items.find(i => i.imageId === x.id)
      if (it) markQueued(it.id, null, null)
    })
  } catch {
    for (const id of pendingUploadedIds) {
      try { await tubiApi.autoAnalyze(id); const it = uploadStore.items.find(i => i.imageId === id); if (it) markQueued(it.id, null, null) }
      catch (e) { const it = uploadStore.items.find(i => i.imageId === id); if (it) markError(it.id, 'QUEUE_UNAVAILABLE', e.message) }
    }
  }
  uploadStore.phase = 'polling'
  await nextTick()
  startPolling()
}

// ── 轮询 ──
let _pollTimer = null
function startPolling() {
  stopPolling()
  _pollTimer = setInterval(async () => {
    const active = uploadStore.items.filter(i =>
      [ITEM_STATUSES.QUEUED, ITEM_STATUSES.ANALYZING, ITEM_STATUSES.UPLOADED].includes(i.status))
    if (active.length === 0) {
      stopPolling(); uploadStore.phase = 'completed'; emit('refresh')
      if (uploadStore.doneCount > 0) ElMessage.success(`分析完成，成功 ${uploadStore.doneCount} 张`)
      return
    }
    const ids = active.map(i => i.imageId).filter(Boolean)
    if (!ids.length) return
    try {
      const r = await tubiApi.batchGetStatus(ids)
      if (!r.success) return
      r.data.forEach(x => {
        const it = uploadStore.items.find(i => i.imageId === x.id)
        if (!it) return
        if (x.status === 'analyzed') markDone(it.id)
        else if (x.status === 'error') markError(it.id, x.error_code, x.analysis_note || '分析失败')
        else if (x.status === 'analyzing') markAnalyzing(it.id)
        else if (x.status === 'queued' && x.position !== undefined) { it.position = x.position; it.estimatedWait = x.estimated_wait_seconds }
      })
    } catch {}
  }, 5000)
}
function stopPolling() { if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null } }

// ── 重试 ──
async function retryUploadItem(item) {
  if (!item.rawFile) { ElMessage.warning('无法重试：文件引用已丢失'); return }
  resetForRetry(item.id)
  try {
    const r = await tubiApi.uploadImage(item.rawFile, {})
    if (r.success) {
      markUploaded(item.id, r.data.id, r.data.url)
      try { await tubiApi.autoAnalyze(r.data.id); markQueued(item.id, null, null) }
      catch (e) { markError(item.id, 'QUEUE_UNAVAILABLE', e.message) }
    } else markError(item.id, 'UPLOAD_FAILED', r.detail || '上传失败')
  } catch { markError(item.id, 'UPLOAD_FAILED', '网络错误') }
  if (uploadStore.phase === 'polling') startPolling()
}

async function retryAllFailed() {
  retryAllFailedStore()
  for (const it of uploadStore.items.filter(i => i.status === ITEM_STATUSES.PENDING && i.rawFile))
    await retryUploadItem(it)
  uploadStore.phase = 'polling'
  startPolling()
}

function clearFiles() { batchFileList.value = [] }
function cancelUpload() { batchUploadCancelled = true; stopPolling(); resetStore() }
function finishUpload() { stopPolling(); resetStore(); batchFileList.value = [] }
function restore() { if (restoreStore()) { uploadStore.phase = 'polling'; startPolling() } }

onMounted(() => { restore() })
onUnmounted(() => { stopPolling() })
</script>

<style scoped>
.upload-inline { max-width: 720px; margin: 0 auto; }

/* ── 步骤条 ── */
.steps-bar {
  display: flex; align-items: center; justify-content: center;
  padding: 20px 0 28px; gap: 0;
}
.step {
  display: flex; align-items: center; gap: 7px;
  opacity: 0.35; transition: opacity 0.2s;
}
.step.active { opacity: 0.85; }
.step.done { opacity: 1; }
.step-dot {
  width: 22px; height: 22px; border-radius: 50%;
  background: #d0ccc0; color: #fff;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.25s;
}
.step.active .step-dot { background: #c45a3c; }
.step.done .step-dot { background: #5a8a4a; }
.step-label {
  font-size: 12px; color: #5c5346; white-space: nowrap;
}
.step-line {
  width: 32px; height: 1px; background: #d0ccc0; margin: 0 6px;
  transition: background 0.25s;
}
.step-line.done { background: #5a8a4a; }

/* ── 内容 ── */
.upload-body {
  background: #fff; border: 1px solid #e8e4d8;
  border-radius: 12px; padding: 28px 28px 22px;
}
.phase-body { }
.body-actions {
  display: flex; justify-content: flex-end; gap: 10px;
  padding-top: 20px; margin-top: 20px;
  border-top: 1px solid #eeece4;
}
</style>
