<template>
  <div class="form-section">
    <h4 class="form-section-title">选择图片</h4>
    <el-upload
      class="batch-upload-area"
      drag
      action="#"
      :auto-upload="false"
      :on-change="handleFileChange"
      :on-remove="handleFileRemove"
      :file-list="fileList"
      :limit="50"
      multiple
      accept="image/*"
      :disabled="disabled"
    >
      <el-icon class="el-icon--upload" size="56"><Upload /></el-icon>
      <div class="el-upload__text">
        拖拽图片到此处或 <em>点击选择</em>
      </div>
      <div class="el-upload__tip">
        支持选择多张图片，支持 JPG、PNG 格式
      </div>
    </el-upload>

    <div v-if="fileList.length > 0" class="batch-file-preview">
      <div class="batch-file-header">
        <div class="batch-file-count">已选择 {{ fileList.length }} 张图片</div>
        <el-button
          type="danger"
          size="small"
          plain
          @click="clearAllFiles"
          class="btn-clear-all"
        >
          清空全部
        </el-button>
      </div>
      <div class="batch-file-grid">
        <div v-for="(file, index) in fileList" :key="file.uid" class="batch-file-card">
          <div class="batch-file-thumb-wrapper">
            <img v-if="file.url" :src="file.url" class="batch-file-thumb" />
            <div v-else class="batch-file-icon">
              <el-icon size="32"><Picture /></el-icon>
            </div>
            <div class="batch-file-delete" @click.stop="removeFile(file, index)">
              <el-icon><Close /></el-icon>
            </div>
          </div>
          <div class="batch-file-info">
            <span class="batch-file-name">{{ file.name }}</span>
            <span v-if="file.size" class="batch-file-size">{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Upload, Picture, Close } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const fileList = ref([...props.modelValue])

watch(() => props.modelValue, (val) => {
  fileList.value = [...val]
}, { deep: true })

watch(fileList, (val) => {
  emit('update:modelValue', val)
}, { deep: true })

function handleFileChange(uploadFile, uploadFiles) {
  fileList.value = uploadFiles
  uploadFiles.forEach(file => {
    if (!file.url && file.raw) {
      try {
        file.url = URL.createObjectURL(file.raw)
      } catch (e) {
        console.error('生成预览URL失败:', file.name, e)
      }
    }
  })
}

function handleFileRemove(uploadFile, uploadFiles) {
  if (uploadFile.url) {
    try {
      URL.revokeObjectURL(uploadFile.url)
    } catch (e) {
      console.error('释放预览URL失败:', e)
    }
  }
  fileList.value = uploadFiles
}

function removeFile(file, index) {
  if (file.url) {
    try {
      URL.revokeObjectURL(file.url)
    } catch (e) {
      console.error('释放预览URL失败:', e)
    }
  }
  fileList.value.splice(index, 1)
}

function clearAllFiles() {
  fileList.value.forEach(file => {
    if (file.url) {
      try {
        URL.revokeObjectURL(file.url)
      } catch (e) {
        console.error('释放预览URL失败:', e)
      }
    }
  })
  fileList.value = []
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
</script>

<style scoped>
/* === Claude 风格上传区域 === */

/* 整个模块水平居中，但预览区域保持全宽 */
.form-section {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.batch-file-preview {
  width: 100%;
  align-self: stretch;
}

/* 拖拽区覆盖 */
:deep(.el-upload-dragger) {
  background: var(--ivory, #faf9f5);
  border: 2px dashed var(--border-warm, #e8e6dc);
  border-radius: var(--radius-xl, 16px);
  transition: all var(--transition-normal, 250ms ease);
}

:deep(.el-upload-dragger:hover) {
  border-color: var(--cinnabar, #c96442);
  background: var(--parchment, #f5f4ed);
}

:deep(.el-upload__text) {
  color: var(--charcoal-warm, #4d4c48);
  font-family: var(--font-sans);
  font-size: 14px;
}

:deep(.el-upload__text em) {
  color: var(--cinnabar, #c96442);
  font-weight: 500;
}

:deep(.el-upload__tip) {
  color: var(--stone-gray, #87867f);
  font-size: 12px;
}

:deep(.el-icon--upload) {
  color: var(--warm-silver, #b0aea5);
  transition: color var(--transition-fast);
}

:deep(.el-upload-dragger:hover .el-icon--upload) {
  color: var(--cinnabar, #c96442);
}

/* 预览区域 */
.batch-file-preview {
  margin-top: 24px;
  padding: 20px;
  background: var(--pure-white, #ffffff);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--border-cream, #f0eee6);
}

.batch-file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
}

.batch-file-count {
  font-size: 14px;
  color: var(--charcoal-warm, #4d4c48);
  font-family: var(--font-sans);
  font-weight: 500;
}

.btn-clear-all {
  margin: 0;
}

/* 预览网格 */
.batch-file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 14px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}

.batch-file-card {
  position: relative;
}

.batch-file-thumb-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  background: var(--parchment, #f5f4ed);
  box-shadow: var(--shadow-ring, 0px 0px 0px 1px var(--ring-warm));
  transition: box-shadow var(--transition-fast);
}

.batch-file-thumb-wrapper:hover {
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}

.batch-file-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.batch-file-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--warm-silver, #b0aea5);
}

/* 删除按钮 — 精致小红点 */
.batch-file-delete {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  background: rgba(181, 51, 51, 0.85);
  backdrop-filter: blur(4px);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  font-size: 10px;
  opacity: 0;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
  transform: scale(0.8);
}

.batch-file-thumb-wrapper:hover .batch-file-delete {
  opacity: 1;
  transform: scale(1);
}

.batch-file-delete:hover {
  background: var(--error-crimson, #b53333);
}

/* 文件信息 */
.batch-file-info {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.batch-file-name {
  font-size: 12px;
  color: var(--near-black, #141413);
  font-family: var(--font-sans);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-file-size {
  font-size: 11px;
  color: var(--stone-gray, #87867f);
  font-family: var(--font-sans);
}
</style>
