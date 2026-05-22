<template>
  <div class="idle-upload">
    <!-- Hero drop zone -->
    <div class="drop-zone" :class="{ 'has-files': fileList.length > 0 }">
      <el-upload
        ref="uploadRef"
        class="drop-zone-upload"
        drag
        action="#"
        :auto-upload="false"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :on-exceed="handleExceed"
        :file-list="fileList"
        :limit="50"
        multiple
        accept="image/*"
        :disabled="disabled"
      >
        <div class="drop-zone-inner">
          <div class="drop-icon-wrap">
            <el-icon class="drop-icon"><PictureFilled /></el-icon>
          </div>
          <p class="drop-title">拖拽图片到此处</p>
          <p class="drop-subtitle">或 <span class="drop-link">点击选择文件</span></p>
          <p class="drop-hint">支持 JPG / PNG，每次最多 50 张</p>
        </div>
      </el-upload>
    </div>

    <!-- 文件列表 -->
    <div v-if="fileList.length > 0" class="file-section">
      <div class="file-section-hd">
        <span class="file-count">已选择 <strong>{{ fileList.length }}</strong> 张图片</span>
        <button class="file-clear" @click="clearAllFiles">清空全部</button>
      </div>
      <div class="file-grid">
        <div
          v-for="(file, index) in fileList"
          :key="file.uid"
          class="file-card"
        >
          <div class="file-thumb">
            <img v-if="file.url" :src="file.url" />
            <el-icon v-else class="file-thumb-icon"><Picture /></el-icon>
            <button class="file-remove" @click.stop="removeFile(file, index)" title="移除">
              <el-icon><Close /></el-icon>
            </button>
            <span class="file-index">{{ index + 1 }}</span>
          </div>
          <div class="file-meta">
            <span class="file-name" :title="file.name">{{ file.name }}</span>
            <span v-if="file.size" class="file-size">{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Picture, PictureFilled, Close } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])
const uploadRef = ref(null)
const fileList = ref([...props.modelValue])

watch(() => props.modelValue, (v) => { fileList.value = [...v] }, { deep: true })
watch(fileList, (v) => { emit('update:modelValue', v) }, { deep: true })

function handleExceed(_files, uploadFiles) {
  ElMessage.warning(`一次最多上传 50 张，当前已选 ${uploadFiles.length} 张，超出部分已自动忽略。请分批次上传。`)
}
function handleFileChange(_f, uploadFiles) {
  fileList.value = uploadFiles
  uploadFiles.forEach(f => {
    if (!f.url && f.raw) { try { f.url = URL.createObjectURL(f.raw) } catch {} }
  })
}
function handleFileRemove(f, uploadFiles) {
  if (f.url) { try { URL.revokeObjectURL(f.url) } catch {} }
  fileList.value = uploadFiles
}
function removeFile(file, idx) {
  if (file.url) { try { URL.revokeObjectURL(file.url) } catch {} }
  fileList.value.splice(idx, 1)
}
function clearAllFiles() {
  fileList.value.forEach(f => { if (f.url) try { URL.revokeObjectURL(f.url) } catch {} })
  fileList.value = []
  // 同步清除 el-upload 内部状态
  uploadRef.value?.clearFiles()
}
function formatFileSize(bytes) {
  if (!bytes) return ''
  const k = 1024; const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}
</script>

<style scoped>
.idle-upload {
  max-width: 680px;
  margin: 0 auto;
}

/* ── Drop zone ── */
.drop-zone {
  transition: all 0.3s ease;
}
.drop-zone.has-files {
  margin-bottom: 24px;
}

:deep(.el-upload) { width: 100%; }
:deep(.el-upload-dragger) {
  width: 100%; height: auto; min-height: 200px;
  padding: 48px 24px;
  background: #fafaf8;
  border: 2px dashed #d9d6cc;
  border-radius: 14px;
  transition: all 0.25s ease;
  display: flex; align-items: center; justify-content: center;
}
:deep(.el-upload-dragger:hover) {
  border-color: #c45a3c;
  background: #f7f3eb;
}

.drop-zone-inner { text-align: center; }
.drop-icon-wrap {
  display: inline-flex; align-items: center; justify-content: center;
  width: 56px; height: 56px; border-radius: 50%;
  background: rgba(196, 90, 60, 0.06);
  margin-bottom: 14px;
}
.drop-icon { font-size: 26px; color: #c45a3c; }
.drop-title {
  font-size: 15px; color: #3a3222; margin: 0 0 6px;
  font-family: 'Noto Serif SC', serif;
}
.drop-subtitle {
  font-size: 13px; color: #8c7a5c; margin: 0 0 10px;
}
.drop-link { color: #c45a3c; font-weight: 500; }
.drop-hint { font-size: 11px; color: #b0a890; margin: 0; }

/* ── File section ── */
.file-section {
  background: #fff; border: 1px solid #e8e4d8;
  border-radius: 12px; overflow: hidden;
}
.file-section-hd {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid #eeece4;
}
.file-count { font-size: 13px; color: #5c5346; }
.file-count strong { color: #3a3222; }
.file-clear {
  background: none; border: none; color: #b0a890; font-size: 12px;
  cursor: pointer; padding: 4px 8px; border-radius: 4px;
  transition: all 0.15s;
}
.file-clear:hover { color: #e05a3c; background: #fef0ec; }

/* ── Grid ── */
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 14px; padding: 18px;
}
.file-card {
  background: #faf9f5; border-radius: 10px;
  overflow: hidden; transition: box-shadow 0.2s;
}
.file-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.06); }

/* Thumb */
.file-thumb {
  position: relative; width: 100%; aspect-ratio: 1;
  background: #f0ebe0; overflow: hidden;
}
.file-thumb img {
  width: 100%; height: 100%; object-fit: cover;
  transition: transform 0.3s;
}
.file-card:hover .file-thumb img { transform: scale(1.04); }
.file-thumb-icon {
  position: absolute; inset: 0; margin: auto;
  font-size: 32px; color: #c8bd9e;
}
.file-index {
  position: absolute; top: 6px; left: 6px;
  width: 20px; height: 20px; border-radius: 50%;
  background: rgba(0,0,0,0.45); color: #fff;
  font-size: 11px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.file-remove {
  position: absolute; top: 6px; right: 6px;
  width: 22px; height: 22px; border-radius: 50%;
  background: rgba(220, 60, 40, 0.85); color: #fff;
  border: none; cursor: pointer; font-size: 10px;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transform: scale(0.8);
  transition: all 0.18s ease;
}
.file-card:hover .file-remove { opacity: 1; transform: scale(1); }
.file-remove:hover { background: #d03030; }

/* Meta */
.file-meta { padding: 8px 10px; }
.file-name {
  display: block; font-size: 11px; color: #3a3222;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.file-size { font-size: 10px; color: #b0a890; }
</style>
