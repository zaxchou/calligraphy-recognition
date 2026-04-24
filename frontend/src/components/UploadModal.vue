<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click="handleOverlayClick">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2 class="modal-title">
            <Upload class="title-icon" />
            上传 PDF 书籍
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
              <p class="upload-text">点击或拖拽 PDF 文件到此处</p>
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
              <div class="processing-spinner">
                <Loader2 class="icon spin" />
              </div>
              <div class="processing-info">
                <p class="processing-title">正在处理 PDF...</p>
                <p class="processing-stage">{{ store.processingStage || '初始化中' }}</p>
                <div class="processing-progress-bar">
                  <div 
                    class="processing-progress-fill"
                    :style="{ width: `${store.processingProgress || 0}%` }"
                  />
                </div>
                <p class="processing-percent">{{ store.processingProgress || 0 }}%</p>
              </div>
            </div>
          </div>

          <!-- 配置选项 -->
          <div class="config-section">
            <h3 class="config-title">处理配置</h3>
            
            <div class="config-item">
              <label class="config-label">分块策略</label>
              <select v-model="config.chunkStrategy" class="config-select">
                <option value="semantic">语义分块（推荐）</option>
                <option value="fixed">固定长度</option>
                <option value="sliding">滑动窗口</option>
              </select>
            </div>
            
            <div class="config-item">
              <label class="config-label">块大小</label>
              <select v-model="config.chunkSize" class="config-select">
                <option :value="300">300 字符</option>
                <option :value="500">500 字符</option>
                <option :value="800">800 字符</option>
                <option :value="1000">1000 字符</option>
              </select>
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
              <p class="success-title">上传成功！</p>
              <p class="success-text">PDF 正在后台处理中，请稍后查看</p>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button 
            class="cancel-btn"
            @click="closeModal"
            :disabled="store.uploadStatus === 'uploading'"
          >
            取消
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
import { ref, reactive, watch } from 'vue'
import { 
  Upload, 
  X, 
  FileUp, 
  FileText, 
  AlertCircle, 
  CheckCircle,
  Loader2
} from 'lucide-vue-next'
import { useKnowledgeStore } from '@/stores/knowledgeStore'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'upload-success'])

const store = useKnowledgeStore()

// 状态
const fileInput = ref(null)
const isDragOver = ref(false)
const selectedFile = ref(null)
const uploadSuccess = ref(false)

// 配置
const config = reactive({
  chunkStrategy: 'semantic',
  chunkSize: 500
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
    alert('请选择 PDF 文件')
    return
  }
  
  // 检查文件大小 (200MB)
  if (file.size > 200 * 1024 * 1024) {
    alert('文件大小不能超过 200MB')
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
      chunkSize: config.chunkSize
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
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
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
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
}

.processing-spinner {
  flex-shrink: 0;
}

.processing-spinner .icon {
  width: 28px;
  height: 28px;
  color: #16a34a;
}

.processing-info {
  flex: 1;
  min-width: 0;
}

.processing-title {
  font-size: 14px;
  font-weight: 600;
  color: #166534;
  margin-bottom: 4px;
}

.processing-stage {
  font-size: 12px;
  color: #15803d;
  margin-bottom: 8px;
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
