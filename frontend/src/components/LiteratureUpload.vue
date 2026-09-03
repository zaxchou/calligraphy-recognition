<template>
  <el-dialog
    :model-value="true"
    width="600px"
    :close-on-click-modal="false"
    :close-on-press-escape="!uploading"
    align-center
    class="alu-dialog"
    @close="$emit('close')"
  >
    <template #header>
      <div class="alu-header">
        <span class="alu-header-icon">📄</span>
        <div class="alu-header-text">
          <span class="alu-header-title">{{ $t('c-literatureupload.t1') }}</span>
          <span class="alu-header-desc">{{ $t('c-literatureupload.t2') }}</span>
        </div>
      </div>
    </template>

    <div class="alu-body">
      <!-- 上传区域 -->
      <div class="alu-upload-area" :class="{ 'alu-upload-has-file': files.length > 0 }">
        <el-upload
          ref="uploadRef"
          drag
          multiple
          :auto-upload="false"
          accept=".pdf"
          :on-change="onFilesChange"
          :on-remove="onFileRemove"
          class="alu-upload-el"
        >
          <div class="alu-upload-inner">
            <div class="alu-upload-icon-wrap">
              <span class="alu-upload-big-icon">📄</span>
            </div>
            <div class="alu-upload-text">{{ $t('c-literatureupload.t3') }}<span class="alu-upload-link">{{ $t('c-literatureupload.t4') }}</span></div>
            <div class="alu-upload-hint">{{ $t('c-literatureupload.t5') }}</div>
          </div>
        </el-upload>
      </div>

      <!-- 文件列表 -->
      <div v-if="files.length > 0" class="alu-file-list">
        <div class="alu-file-list-header">
          <span class="alu-file-count">已选 {{ files.length }} 个文件</span>
          <span v-if="!uploading" class="alu-file-clear" @click="clearFiles">{{ $t('c-literatureupload.t6') }}</span>
        </div>
        <div class="alu-file-items">
          <div v-for="(f, i) in files" :key="f.uid" class="alu-file-item" :class="{ 'alu-file-item-done': f._done, 'alu-file-item-error': f._error }">
            <span class="alu-file-icon">📎</span>
            <span class="alu-file-name">{{ f.name }}</span>
            <span class="alu-file-size">{{ formatSize(f.size) }}</span>
            <span v-if="f._done" class="alu-file-status alu-file-status-ok">✓</span>
            <span v-else-if="f._error" class="alu-file-status alu-file-status-err">✕</span>
            <span v-else-if="f._active" class="alu-file-status alu-file-status-ing">⋯</span>
            <button v-if="!uploading && !f._done" class="alu-file-remove" @click="removeFile(i)">×</button>
          </div>
        </div>
      </div>

      <!-- 进度遮罩 -->
      <transition name="alu-fade">
        <div v-if="uploading" class="alu-progress-overlay">
          <div class="alu-progress-card">
            <div class="alu-progress-spinner"></div>
            <div class="alu-progress-text">{{ uploadStatus }}</div>
            <div class="alu-progress-bar-track">
              <div class="alu-progress-bar-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <template #footer>
      <div class="alu-footer">
        <el-button class="alu-btn alu-btn-cancel" :disabled="uploading" @click="$emit('close')">{{ $t('common.cancel') }}</el-button>
        <el-button class="alu-btn alu-btn-submit" :disabled="files.length === 0 || uploading" :loading="uploading" @click="doUpload">
          {{ uploading ? '上传中…' : '开始上传' + (files.length > 1 ? `（${files.length} 个）` : '') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/authStore'
import { translate as t } from '@/locales'

const props = defineProps({ artistId: { type: Number, required: true } })
const emit = defineEmits(['uploaded', 'close'])

const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const uploadRef = ref(null)
const files = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref('')

function onFilesChange(f, flist) {
  files.value = flist.map(f => ({ ...f, _done: false, _error: false, _active: false }))
}
function onFileRemove(f, flist) {
  files.value = flist
}
function clearFiles() {
  files.value = []
  uploadRef.value?.clearFiles()
}
function removeFile(i) {
  files.value.splice(i, 1)
}

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function doUpload() {
  if (files.value.length === 0) return
  uploading.value = true
  uploadProgress.value = 0
  uploadStatus.value = '准备上传…'

  const total = files.value.length
  let completed = 0

  for (let i = 0; i < total; i++) {
    const f = files.value[i]
    if (f._done) { completed++; continue }

    f._active = true
    uploadStatus.value = `正在上传（${i + 1}/${total}）：${f.name}`

    try {
      const fd = new FormData()
      fd.append('file', f.raw)

      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const filePct = e.loaded / e.total
            uploadProgress.value = Math.round(((completed + filePct) / total) * 90)
          }
        })
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve()
          else reject(new Error(xhr.responseText || '上传失败'))
        })
        xhr.addEventListener('error', () => reject(new Error('网络错误')))
        xhr.open('POST', `${API_BASE}/knowledge/artists/${props.artistId}/literature/upload`)
        xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
        xhr.send(fd)
      })

      f._done = true
      f._error = false
      completed++
    } catch (e) {
      f._error = true
      ElMessage.error(`「${f.name}」上传失败：${e.message}`)
    } finally {
      f._active = false
    }
  }

  if (completed === total) {
    uploadProgress.value = 100
    uploadStatus.value = '全部上传完成！'
    await new Promise(r => setTimeout(r, 800))
    ElMessage.success(`成功上传 ${completed} 个文件，正在后台解析…`)
    emit('uploaded')
  } else if (completed > 0) {
    ElMessage.warning(`${completed}/${total} 个文件上传成功，失败的请重试`)
    uploading.value = false
    uploadProgress.value = 0
  } else {
    ElMessage.error(t('c-literatureupload.s1'))
    uploading.value = false
    uploadProgress.value = 0
  }
}
</script>

<style scoped>
.alu-dialog {
  --alu-radius: 12px;
}
.alu-dialog :deep(.el-dialog__header) {
  padding: 24px 28px 0;
  border-bottom: none;
}
.alu-dialog :deep(.el-dialog__body) {
  padding: 16px 28px 4px;
  position: relative;
}
.alu-dialog :deep(.el-dialog__footer) {
  padding: 8px 28px 24px;
}

/* ─── Header ─── */
.alu-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-cream);
}
.alu-header-icon { font-size: 28px; line-height: 1; }
.alu-header-text { display: flex; flex-direction: column; gap: 2px; }
.alu-header-title { font-family: 'Noto Serif SC', 'KaiTi', serif; font-size: 17px; font-weight: 600; color: var(--near-black); }
.alu-header-desc { font-size: 12px; color: var(--stone-gray); }

/* ─── 上传区域 ─── */
.alu-body { display: flex; flex-direction: column; }
.alu-upload-area {
  border: 2px dashed var(--ring-warm);
  border-radius: var(--alu-radius);
  transition: all 0.2s;
  background: var(--ivory);
  overflow: hidden;
}
.alu-upload-area:hover { border-color: var(--cinnabar-light); background: #fdfaf7; }
.alu-upload-has-file { border-color: var(--cinnabar-light); background: #fdfaf7; }
.alu-upload-el :deep(.el-upload) { width: 100%; }
.alu-upload-el :deep(.el-upload-dragger) {
  width: 100%; height: auto; padding: 20px 0;
  border: none !important; background: transparent !important; border-radius: var(--alu-radius);
}
.alu-upload-inner { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.alu-upload-icon-wrap {
  width: 56px; height: 56px;
  background: linear-gradient(135deg, #fdf6f0, #faf0e8);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center; margin-bottom: 4px;
}
.alu-upload-big-icon { font-size: 28px; line-height: 1; }
.alu-upload-text { font-size: 14px; color: var(--charcoal-warm); }
.alu-upload-link { color: var(--cinnabar); font-weight: 500; cursor: pointer; }
.alu-upload-link:hover { color: var(--cinnabar-dark); }
.alu-upload-hint { font-size: 12px; color: var(--warm-silver); }

/* ─── 文件列表 ─── */
.alu-file-list { margin-top: 12px; }
.alu-file-list-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px;
}
.alu-file-count { font-size: 12px; color: var(--stone-gray); }
.alu-file-clear { font-size: 12px; color: var(--cinnabar); cursor: pointer; }
.alu-file-clear:hover { color: var(--cinnabar-dark); }
.alu-file-items { display: flex; flex-direction: column; gap: 4px; max-height: 200px; overflow-y: auto; }
.alu-file-item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; background: var(--parchment); border-radius: 6px; font-size: 13px;
  transition: background 0.15s;
}
.alu-file-item:hover { background: #f0ede8; }
.alu-file-item-done { background: #f0f7f0; }
.alu-file-item-error { background: #fdf0ee; }
.alu-file-icon { font-size: 14px; line-height: 1; flex-shrink: 0; }
.alu-file-name { flex: 1; color: var(--near-black); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.alu-file-size { color: var(--stone-gray); font-size: 11px; flex-shrink: 0; }
.alu-file-status { font-size: 14px; font-weight: 700; flex-shrink: 0; }
.alu-file-status-ok { color: #3cb88b; }
.alu-file-status-err { color: #e07a5f; }
.alu-file-status-ing { color: var(--cinnabar); animation: alu-pulse 0.8s infinite; }
@keyframes alu-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.alu-file-remove {
  background: none; border: none; cursor: pointer; font-size: 16px;
  color: var(--warm-silver); padding: 0 2px; line-height: 1;
}
.alu-file-remove:hover { color: var(--cinnabar); }

/* ─── Footer ─── */
.alu-footer { display: flex; justify-content: flex-end; gap: 10px; }
.alu-btn { border-radius: 8px !important; padding: 8px 22px !important; font-size: 13px !important; font-weight: 500 !important; }
.alu-btn-cancel { color: var(--stone-gray) !important; border: 1px solid var(--ring-warm) !important; background: var(--pure-white) !important; }
.alu-btn-cancel:hover { color: var(--near-black) !important; border-color: var(--ring-deep) !important; background: var(--ivory) !important; }
.alu-btn-submit { background: var(--cinnabar) !important; border-color: var(--cinnabar) !important; color: #fff !important; }
.alu-btn-submit:hover:not(:disabled) { background: var(--cinnabar-light) !important; border-color: var(--cinnabar-light) !important; }
.alu-btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* ─── 进度遮罩 ─── */
.alu-progress-overlay {
  position: absolute; inset: 0;
  background: rgba(255,255,255,0.85); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  z-index: 10; border-radius: 4px;
}
.alu-progress-card {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  padding: 28px 36px; background: var(--pure-white);
  border-radius: 14px; box-shadow: 0 4px 24px rgba(0,0,0,0.1);
}
.alu-progress-spinner {
  width: 40px; height: 40px;
  border: 3px solid var(--border-cream); border-top-color: var(--cinnabar);
  border-radius: 50%; animation: alu-spin 0.8s linear infinite;
}
@keyframes alu-spin { to { transform: rotate(360deg); } }
.alu-progress-text { font-size: 14px; color: var(--charcoal-warm); font-weight: 500; text-align: center; }
.alu-progress-bar-track { width: 200px; height: 4px; background: var(--border-cream); border-radius: 4px; overflow: hidden; }
.alu-progress-bar-fill {
  height: 100%; background: linear-gradient(90deg, var(--cinnabar), var(--cinnabar-light));
  border-radius: 4px; transition: width 0.4s ease;
}

/* ─── 过渡动画 ─── */
.alu-fade-enter-active { transition: all 0.25s ease; }
.alu-fade-leave-active { transition: all 0.15s ease; }
.alu-fade-enter-from { opacity: 0; transform: translateY(-6px); }
.alu-fade-leave-to { opacity: 0; }
</style>
