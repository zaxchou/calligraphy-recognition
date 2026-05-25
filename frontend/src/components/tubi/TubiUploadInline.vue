<template>
  <div class="upload-inline">
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
    </div>

    <div class="upload-body">
      <div v-if="uploadStore.phase === 'idle'">
        <UploadPhaseIdle ref="idleRef" v-model="batchFileList" :upload-store="uploadStore" />
        <div v-if="batchFileList.length > 0" class="body-actions">
          <el-button @click="clearFiles">取消</el-button>
          <el-button type="primary" @click="startBatchUpload">
            开始上传 {{ batchFileList.length }} 张
          </el-button>
        </div>
      </div>

      <div v-else class="phase-body">
        <UploadPhaseUploading
          v-if="uploadStore.phase === 'uploading'"
          :upload-store="uploadStore"
          @retry="retryUploadItem"
          @retry-all="retryAllFailed"
        />

        <div class="body-actions">
          <el-button v-if="uploadStore.phase === 'uploading'" type="danger" @click="cancelUpload">取消上传</el-button>
          <el-button v-else type="primary" @click="finishUpload">继续上传</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { tubiApi, artworkApi } from '../../api'
import { useUploadStore, ITEM_STATUSES } from '../../stores/uploadStore'

const UploadPhaseIdle = defineAsyncComponent(() => import('./UploadPhaseIdle.vue'))
const UploadPhaseUploading = defineAsyncComponent(() => import('./UploadPhaseUploading.vue'))

const props = defineProps({
  libraryId: { type: [Number, String], default: null }
})

const emit = defineEmits(['refresh'])

const batchFileList = ref([])
let batchUploadCancelled = false
const idleRef = ref(null)

function triggerFilePicker() {
  idleRef.value?.triggerFileInput()
}
defineExpose({ triggerFilePicker })

const {
  store: uploadStore,
  markUploaded, markError,
  resetForRetry, retryAllFailed: retryAllFailedStore,
  reset: resetStore, restore: restoreStore,
} = useUploadStore()

const phaseIdx = computed(() => {
  const map = { idle: 0, uploading: 1, completed: 1 }
  return map[uploadStore.phase] ?? 0
})

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
        let result
        if (props.libraryId) {
          const data = await artworkApi.upload(props.libraryId, item.rawFile, {})
          result = { success: true, data }
        } else {
          result = await tubiApi.uploadImage(item.rawFile, {})
        }
        if (result.success) markUploaded(item.id, result.data.id || result.data?.image_id, result.data?.url)
        else markError(item.id, 'UPLOAD_FAILED', result.detail || '上传失败')
      } catch { markError(item.id, 'NETWORK_ERROR', '网络错误') }
    }))
    await nextTick()
  }

  if (batchUploadCancelled) { resetStore(); return }

  const completed = uploadStore.items.filter(i => i.status === ITEM_STATUSES.UPLOADED)
  uploadStore.phase = 'idle'
  batchFileList.value = []
  emit('refresh')

  if (completed.length > 0) ElMessage.success(`已上传 ${completed.length} 件`)
}

async function retryUploadItem(item) {
  if (!item.rawFile) { ElMessage.warning('无法重试：文件引用已丢失'); return }
  resetForRetry(item.id)
  try {
    let result
    if (props.libraryId) {
      const data = await artworkApi.upload(props.libraryId, item.rawFile, {})
      result = { success: true, data }
    } else {
      result = await tubiApi.uploadImage(item.rawFile, {})
    }
    if (result.success) markUploaded(item.id, result.data.id || result.data?.image_id, result.data?.url)
    else markError(item.id, 'UPLOAD_FAILED', result.detail || '上传失败')
  } catch { markError(item.id, 'UPLOAD_FAILED', '网络错误') }
}

async function retryAllFailed() {
  retryAllFailedStore()
  for (const it of uploadStore.items.filter(i => i.status === ITEM_STATUSES.PENDING && i.rawFile))
    await retryUploadItem(it)
}

function clearFiles() { batchFileList.value = [] }
function cancelUpload() { batchUploadCancelled = true; resetStore() }
function finishUpload() { resetStore(); batchFileList.value = []
  // 重置后自动弹出文件选择框
  nextTick(() => { idleRef.value?.triggerFileInput() })
}
function restore() { restoreStore() }

onMounted(() => { restore() })
onUnmounted(() => {})
</script>

<style scoped>
.upload-inline { max-width: 720px; margin: 0 auto; }

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

.upload-body {
  background: #fff; border: 1px solid #e8e4d8;
  border-radius: 12px; padding: 28px 28px 22px;
}
.body-actions {
  display: flex; justify-content: flex-end; gap: 10px;
  padding-top: 20px; margin-top: 20px;
  border-top: 1px solid #eeece4;
}
</style>
