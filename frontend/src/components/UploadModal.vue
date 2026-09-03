<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click="handleOverlayClick">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2 class="modal-title">
            <Upload class="title-icon" />
            {{ $t('c-uploadmodal.t1') }}
          </h2>
          <button class="close-btn" @click="closeModal">
            <X class="icon" />
          </button>
        </div>

        <div class="modal-body">
          <!-- 拖拽上传区 -->
          <div 
            class="upload-zone"
            :class="{ 
              'drag-over': isDragOver,
              'has-file': selectedFile,
              'uploading': store.uploadStatus === 'uploading'
            }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input 
              ref="fileInput"
              type="file" 
              accept=".pdf"
              class="file-input"
              @change="handleFileSelect"
            />
            
            <div v-if="!selectedFile" class="upload-placeholder">
              <FileUp class="upload-icon" />
              <p class="upload-text">{{ $t('c-uploadmodal.t2') }}</p>
              <p class="upload-hint">支持 .pdf 格式，最大 200MB</p>
            </div>
            
            <div v-else class="file-info">
              <FileText class="file-icon" />
              <div class="file-details">
                <p class="file-name">{{ selectedFile.name }}</p>
                <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
              </div>
              <button 
                v-if="store.uploadStatus !== 'uploading'"
                class="remove-file-btn"
                @click.stop="removeFile"
              >
                <X class="icon" />
              </button>
            </div>

            <!-- 上传进度 -->
            <div v-if="store.uploadStatus === 'uploading'" class="upload-progress">
              <div class="progress-bar">
                <div 
                  class="progress-fill"
                  :style="{ width: `${store.uploadProgress}%` }"
                />
              </div>
              <span class="progress-text">{{ store.uploadProgress }}%</span>
            </div>

            <!-- 后端处理进度 -->
            <div v-if="store.uploadStatus === 'processing'" class="processing-status">
              <div class="processing-steps">
                <div 
                  v-for="(step, index) in processingSteps" 
                  :key="index"
                  class="step-item"
                  :class="{
                    'step-completed': step.completed,
                    'step-active': step.active,
                    'step-waiting': !step.completed && !step.active
                  }"
                >
                  <div class="step-icon">
                    <Check v-if="step.completed" class="icon" />
                    <Loader2 v-else-if="step.active" class="icon spin" />
                    <Circle v-else class="icon" />
                  </div>
                  <div class="step-content">
                    <p class="step-name">{{ step.name }}</p>
                    <p v-if="step.active && store.processingStage" class="step-detail">
                      {{ store.processingStage }}
                    </p>
                  </div>
                </div>
              </div>
              <div class="processing-progress-bar">
                <div 
                  class="processing-progress-fill"
                  :style="{ width: `${store.processingProgress || 0}%` }"
                />
              </div>
              <p class="processing-percent">{{ store.processingProgress || 0 }}%</p>
            </div>
          </div>

          <!-- 配置选项 -->
          <div class="config-section">
            <h3 class="config-title">{{ $t('c-uploadmodal.t3') }}</h3>
            
            <div class="config-item">
              <label class="config-label">{{ $t('c-uploadmodal.t4') }}</label>
              <select v-model="config.chunkStrategy" class="config-select">
                <option value="semantic">{{ $t('c-uploadmodal.t5') }}</option>
                <option value="fixed">{{ $t('c-uploadmodal.t6') }}</option>
                <option value="sliding">{{ $t('c-uploadmodal.t7') }}</option>
              </select>
            </div>
            
            <div class="config-item">
              <label class="config-label">{{ $t('c-uploadmodal.t8') }}</label>
              <select v-model="config.chunkSize" class="config-select">
                <option :value="300">{{ $t('c-uploadmodal.t9') }}</option>
                <option :value="500">{{ $t('c-uploadmodal.t10') }}</option>
                <option :value="800">{{ $t('c-uploadmodal.t11') }}</option>
                <option :value="1000">{{ $t('c-uploadmodal.t12') }}</option>
              </select>
            </div>
            
            <!-- MinerU 解析器已默认启用 -->
          </div>

          <!-- 系列设置（跨文件定位） -->
          <div class="config-section">
            <h3 class="config-title">{{ $t('c-uploadmodal.t13') }}</h3>
            <p class="config-desc">{{ $t('c-uploadmodal.t14') }}</p>
            <div class="config-item">
              <label class="config-label">{{ $t('c-uploadmodal.t15') }}</label>
              <input v-model="config.seriesId" class="config-input" :placeholder="$t('c-uploadmodal.a1')" />
            </div>
            <div class="config-item">
              <label class="config-label">{{ $t('c-uploadmodal.t16') }}</label>
              <input v-model.number="config.pageOffset" type="number" min="1" class="config-input" :placeholder="$t('c-uploadmodal.a2')" />
            </div>
          </div>

          <!-- 错误提示 -->
          <div v-if="store.uploadError" class="error-message">
            <AlertCircle class="error-icon" />
            <span>{{ store.uploadError }}</span>
          </div>

          <!-- 成功提示 -->
          <div v-if="uploadSuccess" class="success-message">
            <CheckCircle class="success-icon" />
            <div>
              <p class="success-title">{{ $t('c-uploadmodal.t17') }}</p>
              <p class="success-text">{{ $t('c-uploadmodal.t18') }}</p>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button 
            class="cancel-btn"
            @click="closeModal"
            :disabled="store.uploadStatus === 'uploading'"
          >
            {{ $t('common.cancel') }}
          </button>
          <button 
            class="upload-submit-btn"
            :disabled="!selectedFile || store.uploadStatus === 'uploading' || uploadSuccess"
            @click="startUpload"
          >
            <Loader2 v-if="store.uploadStatus === 'uploading'" class="icon spin" />
            <span v-else>{{ uploadSuccess ? '已上传' : '开始上传' }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { 
  Upload, 
  X, 
  FileUp, 
  FileText, 
  AlertCircle, 
  CheckCircle,
  Loader2,
  Check,
  Circle
} from 'lucide-vue-next'
import { useKnowledgeStore } from '@/stores/knowledgeStore'
import { translate as t } from '@/locales'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'upload-success'])

const store = useKnowledgeStore()

// 处理步骤定义
const processingSteps = computed(() => {
  const progress = store.processingProgress || 0
  return [
    {
      name: 'PDF 解析',
      completed: progress >= 25,
      active: progress >= 0 && progress < 25
    },
    {
      name: '文本分块',
      completed: progress >= 40,
      active: progress >= 25 && progress < 40
    },
    {
      name: '文本向量化',
      completed: progress >= 70,
      active: progress >= 40 && progress < 70
    },
    {
      name: '图像提取',
      completed: progress >= 78,
      active: progress >= 70 && progress < 78
    },
    {
      name: '图像向量化',
      completed: progress >= 90,
      active: progress >= 78 && progress < 90
    },
    {
      name: '关联分析',
      completed: progress >= 100,
      active: progress >= 90 && progress < 100
    }
  ]
})

// 状态
const fileInput = ref(null)
const isDragOver = ref(false)
const selectedFile = ref(null)
const uploadSuccess = ref(false)

// 配置
const config = reactive({
  chunkStrategy: 'semantic',
  chunkSize: 500,
  parserBackend: 'mineru',
  seriesId: '',
  pageOffset: 1
})

// 方法
function triggerFileInput() {
  if (store.uploadStatus === 'uploading') return
  fileInput.value?.click()
}

function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (file) {
    validateAndSetFile(file)
  }
}

function handleDrop(event) {
  isDragOver.value = false
  const file = event.dataTransfer.files?.[0]
  if (file) {
    validateAndSetFile(file)
  }
}

function validateAndSetFile(file) {
  // 检查文件类型
  if (!file.name.endsWith('.pdf')) {
    alert(t('c-uploadmodal.s1'))
    return
  }
  
  // 检查文件大小 (200MB)
  if (file.size > 200 * 1024 * 1024) {
    alert(t('c-uploadmodal.s2'))
    return
  }
  
  selectedFile.value = file
  uploadSuccess.value = false
}

function removeFile() {
  selectedFile.value = null
  uploadSuccess.value = false
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

async function startUpload() {
  if (!selectedFile.value) return
  
  try {
    await store.uploadPdf(selectedFile.value, {
      chunkStrategy: config.chunkStrategy,
      chunkSize: config.chunkSize,
      parserBackend: config.parserBackend,
      seriesId: config.seriesId,
      pageOffset: config.pageOffset
    })
    uploadSuccess.value = true
    emit('upload-success')
    
    // 3秒后自动关闭
    setTimeout(() => {
      closeModal()
    }, 3000)
  } catch (error) {
    console.error('上传失败:', error)
  }
}

function closeModal() {
  if (store.uploadStatus === 'uploading') return
  
  emit('update:visible', false)
  
  // 重置状态
  setTimeout(() => {
    selectedFile.value = null
    uploadSuccess.value = false
    store.resetUploadStatus()
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }, 300)
}

function handleOverlayClick() {
  if (store.uploadStatus !== 'uploading') {
    closeModal()
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 监听 visible 变化
watch(() => props.visible, (newVal) => {
  if (newVal) {
    store.resetUploadStatus()
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.title-icon {
  width: 22px;
  height: 22px;
  color: #2563eb;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #f1f5f9;
  border: none;
  border-radius: 8px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #e2e8f0;
  color: #1e293b;
}

.icon {
  width: 18px;
  height: 18px;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

/* 上传区 */
.upload-zone {
  border: 2px dashed #e2e8f0;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.upload-zone:hover,
.upload-zone.drag-over {
  border-color: #2563eb;
  background: #eff6ff;
}

.upload-zone.has-file {
  padding: 24px;
  border-style: solid;
  border-color: #2563eb;
  background: #eff6ff;
}

.upload-zone.uploading {
  cursor: not-allowed;
  opacity: 0.8;
}

.file-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.upload-placeholder {
  pointer-events: none;
}

.upload-icon {
  width: 48px;
  height: 48px;
  color: #94a3b8;
  margin-bottom: 16px;
}

.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 13px;
  color: #94a3b8;
}

/* 文件信息 */
.file-info {
  display: flex;
  align-items: center;
  gap: 16px;
  pointer-events: none;
}

.file-icon {
  width: 40px;
  height: 40px;
  color: #ef4444;
  flex-shrink: 0;
}

.file-details {
  flex: 1;
  text-align: left;
  min-width: 0;
}

.file-name {
  font-size: 15px;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 13px;
  color: #64748b;
}

.remove-file-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #64748b;
  cursor: pointer;
  pointer-events: auto;
  transition: all 0.2s;
}

.remove-file-btn:hover {
  background: #fee2e2;
  border-color: #ef4444;
  color: #ef4444;
}

/* 上传进度 */
.upload-progress {
  position: absolute;
  bottom: 16px;
  left: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #2563eb;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 13px;
  font-weight: 500;
  color: #2563eb;
  min-width: 40px;
  text-align: right;
}

/* 后端处理进度 */
.processing-status {
  position: absolute;
  bottom: 16px;
  left: 24px;
  right: 24px;
  padding: 16px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
}

.processing-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background 0.2s ease;
}

.step-item.step-active {
  background: #dcfce7;
}

.step-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-icon .icon {
  width: 16px;
  height: 16px;
}

.step-completed .step-icon .icon {
  color: #16a34a;
}

.step-active .step-icon .icon {
  color: #16a34a;
  animation: spin 1s linear infinite;
}

.step-waiting .step-icon .icon {
  color: #9ca3af;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin: 0;
}

.step-completed .step-name {
  color: #166534;
}

.step-active .step-name {
  color: #166534;
  font-weight: 600;
}

.step-waiting .step-name {
  color: #9ca3af;
}

.step-detail {
  font-size: 11px;
  color: #15803d;
  margin: 2px 0 0;
}

.processing-progress-bar {
  height: 6px;
  background: #dcfce7;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}

.processing-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #16a34a, #22c55e);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.processing-percent {
  font-size: 12px;
  font-weight: 500;
  color: #16a34a;
  text-align: right;
}

/* 配置区 */
.config-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e2e8f0;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 16px;
}

.config-item {
  margin-bottom: 16px;
}

.config-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 6px;
}

.config-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition: all 0.2s;
}

.config-select:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.config-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  background: #fff;
  outline: none;
  transition: all 0.2s;
  box-sizing: border-box;
}

.config-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.config-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 10px;
  line-height: 1.5;
}

/* 消息提示 */
.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  margin-top: 16px;
  font-size: 13px;
  color: #dc2626;
}

.error-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.success-message {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #dcfce7;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  margin-top: 16px;
}

.success-icon {
  width: 20px;
  height: 20px;
  color: #16a34a;
  flex-shrink: 0;
}

.success-title {
  font-size: 14px;
  font-weight: 600;
  color: #166534;
  margin-bottom: 4px;
}

.success-text {
  font-size: 13px;
  color: #15803d;
}

/* 底部按钮 */
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.cancel-btn {
  padding: 10px 20px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.upload-submit-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  background: #2563eb;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-submit-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.upload-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
