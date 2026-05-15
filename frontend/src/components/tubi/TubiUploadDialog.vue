<template>
  <!-- 模式选择弹窗 -->
  <TubiModeSelectionDialog
    v-model="showModeSelectionDialog"
    @confirm="confirmUploadMode"
    @cancel="showModeSelectionDialog = false"
  />

  <!-- 上传作品对话框 -->
  <el-dialog
    v-model="batchUploadDialogVisible"
    title="上传作品"
    width="700px"
    :close-on-click-modal="true"
    align-center class="modern-form-dialog batch-upload-dialog"
    :before-close="handleBatchDialogClose"
  >
    <!-- 动态 phase 组件 -->
    <component
      :is="currentPhaseComponent"
      v-if="uploadStore.phase === 'idle'"
      v-model="batchFileList"
      :upload-store="uploadStore"
      :disabled="uploadStore.phase === 'uploading'"
    />
    <component
      :is="currentPhaseComponent"
      v-else
      :upload-store="uploadStore"
      :disabled="uploadStore.phase === 'uploading'"
      @retry="retryUploadItem"
      @retry-all="retryAllFailed"
    />

    <template #footer>
      <div class="dialog-footer modern-footer">
        <!-- Idle 阶段 -->
        <template v-if="uploadStore.phase === 'idle'">
          <el-button @click="batchUploadDialogVisible = false" class="btn-cancel">
            取消
          </el-button>
          <el-button
            v-if="batchFileList.length > 0"
            type="primary"
            @click="startBatchUpload"
            class="btn-submit"
          >
            开始上传 ({{ batchFileList.length }}张)
          </el-button>
        </template>

        <!-- Uploading 阶段 -->
        <template v-else-if="uploadStore.phase === 'uploading'">
          <el-button type="danger" @click="cancelBatchUpload" class="btn-cancel">
            取消上传
          </el-button>
        </template>

        <!-- Processing 阶段 -->
        <template v-else-if="uploadStore.phase === 'enqueuing' || uploadStore.phase === 'polling'">
          <el-button @click="minimizeBatchDialog" class="btn-cancel">
            后台继续
          </el-button>
        </template>

        <!-- Completed 阶段 -->
        <template v-else-if="uploadStore.phase === 'completed'">
          <el-button type="primary" @click="closeBatchUploadDialog" class="btn-submit">
            完成
          </el-button>
        </template>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tubiApi } from '../../api'
import { useUploadStore, ITEM_STATUSES } from '../../stores/uploadStore'
import TubiModeSelectionDialog from './TubiModeSelectionDialog.vue'

// 动态加载 phase 组件
const UploadPhaseIdle = defineAsyncComponent(() => import('./UploadPhaseIdle.vue'))
const UploadPhaseUploading = defineAsyncComponent(() => import('./UploadPhaseUploading.vue'))
const UploadPhaseProcessing = defineAsyncComponent(() => import('./UploadPhaseProcessing.vue'))
const UploadPhaseCompleted = defineAsyncComponent(() => import('./UploadPhaseCompleted.vue'))

const emit = defineEmits(['uploaded', 'refresh'])

// 上传相关状态
const batchUploadDialogVisible = ref(false)
const batchFileList = ref([])
let batchUploadCancelled = false

// 模式选择弹窗
const showModeSelectionDialog = ref(false)
let pendingUploadedIds = []

// 两阶段上传 store
const {
  store: uploadStore,
  markUploaded,
  markQueued,
  markAnalyzing,
  markDone,
  markError,
  resetForRetry,
  retryAllFailed: retryAllFailedStore,
  reset: resetStore,
  restore: restoreStore,
} = useUploadStore()

// phase 组件映射
const phaseComponents = {
  idle: UploadPhaseIdle,
  uploading: UploadPhaseUploading,
  enqueuing: UploadPhaseProcessing,
  polling: UploadPhaseProcessing,
  completed: UploadPhaseCompleted
}

const currentPhaseComponent = computed(() => phaseComponents[uploadStore.phase] || UploadPhaseIdle)

// ========== 公开方法（供父组件调用） ==========

function open() {
  batchUploadDialogVisible.value = true
  batchFileList.value = []
  batchUploadCancelled = false
  resetStore()
}

// ========== 阶段一：快速上传 ==========

async function startBatchUpload() {
  if (batchFileList.value.length === 0) {
    ElMessage.warning('请先选择图片')
    return
  }

  batchUploadCancelled = false

  const files = batchFileList.value.map(f => ({
    name: f.name,
    raw: f.raw,
  }))
  const { initBatch } = useUploadStore()
  initBatch(files)

  const CONCURRENCY = 3
  const items = [...uploadStore.items]
  const newImages = []

  for (let i = 0; i < items.length; i += CONCURRENCY) {
    if (batchUploadCancelled) break

    const batch = items.slice(i, i + CONCURRENCY)
    await Promise.allSettled(batch.map(async (item) => {
      if (batchUploadCancelled) return
      try {
        const rawFile = item.rawFile
        const result = await tubiApi.uploadImage(rawFile, {})

        if (result.success) {
          markUploaded(item.id, result.data.id, result.data.url)
          newImages.push({
            id: result.data.id,
            name: item.fileName,
            url: result.data.url,
            thumbnailUrl: result.data.thumbnail_url,
            width: result.data.width,
            height: result.data.height,
            title: result.data.title,
            artist: result.data.artist,
            year: result.data.year,
            period: result.data.period,
            inscriptionPercent: undefined,
            paintingPercent: undefined,
            blankPercent: undefined,
            regions: null,
            annotatedImageUrl: null,
            sealContent: '',
          })
        } else {
          markError(item.id, 'UPLOAD_FAILED', result.detail || '上传失败')
        }
      } catch (error) {
        const code = error.message?.includes('Network Error') ? 'NETWORK_ERROR' : 'UPLOAD_FAILED'
        markError(item.id, code, error.message)
      }
    }))

    await nextTick()
  }

  if (batchUploadCancelled) {
    resetStore()
    return
  }

  // 通知父组件新上传的图片
  if (newImages.length > 0) {
    emit('uploaded', newImages)
  }

  // 阶段二：选择模式
  uploadStore.phase = 'enqueuing'
  await nextTick()

  pendingUploadedIds = uploadStore.items
    .filter(i => i.status === ITEM_STATUSES.UPLOADED && i.imageId)
    .map(i => i.imageId)

  if (pendingUploadedIds.length > 0) {
    showModeSelectionDialog.value = true
  } else {
    batchUploadDialogVisible.value = false
    resetStore()
  }
}

// ========== 阶段二：模式确认 ==========

async function confirmUploadMode(mode) {
  if (mode === 'manual') {
    uploadStore.items.forEach(item => {
      if (item.imageId) {
        markQueued(item.id, null, null)
      }
    })
    batchUploadDialogVisible.value = false
    resetStore()
    ElMessage.success('已录入完成，可前往手工标注')
    emit('refresh')
    return
  }

  try {
    const batchResult = await tubiApi.batchAutoAnalyze(pendingUploadedIds, mode)
    if (batchResult.success) {
      batchResult.data.forEach(r => {
        const item = uploadStore.items.find(i => i.imageId === r.id)
        if (item) {
          markQueued(item.id, null, null)
        }
      })
    }
  } catch (error) {
    console.error('批量入队失败，逐个入队:', error)
    for (const imageId of pendingUploadedIds) {
      try {
        await tubiApi.autoAnalyze(imageId)
        const item = uploadStore.items.find(i => i.imageId === imageId)
        if (item) markQueued(item.id, null, null)
      } catch (e) {
        const item = uploadStore.items.find(i => i.imageId === imageId)
        if (item) markError(item.id, 'QUEUE_UNAVAILABLE', e.message)
      }
    }
  }

  // 阶段三：后台轮询分析结果
  uploadStore.phase = 'polling'
  await nextTick()
  startPolling()
}

// ========== 轮询 ==========

let _pollTimer = null

function startPolling() {
  stopPolling()
  _pollTimer = setInterval(async () => {
    await pollAnalysisStatus()
  }, 5000)
}

function stopPolling() {
  if (_pollTimer) {
    clearInterval(_pollTimer)
    _pollTimer = null
  }
}

async function pollAnalysisStatus() {
  const activeItems = uploadStore.items.filter(
    i => [ITEM_STATUSES.QUEUED, ITEM_STATUSES.ANALYZING, ITEM_STATUSES.UPLOADED].includes(i.status)
  )
  if (activeItems.length === 0) {
    stopPolling()
    uploadStore.phase = 'completed'
    emit('refresh')
    if (uploadStore.doneCount > 0) {
      ElMessage.success(`分析完成，成功 ${uploadStore.doneCount} 张`)
    }
    return
  }

  const imageIds = activeItems.map(i => i.imageId).filter(Boolean)
  if (imageIds.length === 0) return

  try {
    const result = await tubiApi.batchGetStatus(imageIds)
    if (!result.success) return

    result.data.forEach(r => {
      const item = uploadStore.items.find(i => i.imageId === r.id)
      if (!item) return

      if (r.status === 'analyzed') {
        markDone(item.id)
      } else if (r.status === 'error') {
        markError(item.id, r.error_code, r.analysis_note || '分析失败')
      } else if (r.status === 'analyzing') {
        markAnalyzing(item.id)
      } else if (r.status === 'queued') {
        if (r.position !== undefined) {
          item.position = r.position
          item.estimatedWait = r.estimated_wait_seconds
        }
      }
    })
  } catch (error) {
    console.error('轮询失败:', error)
  }
}

// ========== 重试 ==========

async function retryUploadItem(item) {
  if (!item.rawFile) {
    ElMessage.warning('无法重试：文件引用已丢失，请重新选择文件上传')
    return
  }
  resetForRetry(item.id)
  try {
    const result = await tubiApi.uploadImage(item.rawFile, {})
    if (result.success) {
      markUploaded(item.id, result.data.id, result.data.url)
      try {
        await tubiApi.autoAnalyze(result.data.id)
        markQueued(item.id, null, null)
      } catch (e) {
        markError(item.id, 'QUEUE_UNAVAILABLE', e.message)
      }
    } else {
      markError(item.id, 'UPLOAD_FAILED', result.detail || '上传失败')
    }
  } catch (error) {
    markError(item.id, 'UPLOAD_FAILED', error.message)
  }
  if (uploadStore.phase === 'polling') {
    startPolling()
  }
}

async function retryAllFailed() {
  retryAllFailedStore()
  const failedItems = uploadStore.items.filter(
    i => i.status === ITEM_STATUSES.PENDING && i.rawFile
  )
  for (const item of failedItems) {
    await retryUploadItem(item)
  }
  uploadStore.phase = 'polling'
  startPolling()
}

// ========== 对话框控制 ==========

function minimizeBatchDialog() {
  batchUploadDialogVisible.value = false
}

function cancelBatchUpload() {
  batchUploadCancelled = true
  stopPolling()
  resetStore()
}

function closeBatchUploadDialog() {
  batchUploadDialogVisible.value = false
  stopPolling()
  resetStore()
}

function handleBatchDialogClose(done) {
  if (uploadStore.phase === 'uploading') {
    ElMessageBox.confirm('上传正在进行中，确定要关闭吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      batchUploadCancelled = true
      stopPolling()
      resetStore()
      done()
    }).catch(() => {})
  } else if (uploadStore.phase === 'polling' || uploadStore.phase === 'enqueuing') {
    done()
  } else {
    done()
  }
}

// 组件卸载时停止轮询
onUnmounted(() => {
  stopPolling()
})

// 恢复未完成的上传（页面刷新后断点续传）
function restore() {
  if (restoreStore()) {
    uploadStore.phase = 'polling'
    startPolling()
  }
}

onMounted(() => {
  restore()
})

defineExpose({ open, restore })
</script>

<style scoped>
/* 保留父容器样式，phase 组件内部样式已移到各自文件 */
</style>
