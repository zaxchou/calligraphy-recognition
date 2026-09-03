<template>
  <div class="isp-root">
    <div class="isp-head">
      <el-tag size="small" effect="plain" class="isp-hero-tag">{{ totalIndexed }} 幅已索引</el-tag>
      <el-button size="small" text @click="rebuildIndex" :loading="rebuilding" class="isp-rebuild-btn">重建索引</el-button>
    </div>

    <div class="isp-upload-area">
      <el-upload
        ref="uploadRef"
        class="isp-upload"
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".jpg,.jpeg,.png,.webp,.bmp"
        :on-change="onFileSelected"
      >
        <template v-if="uploadPreview">
          <div class="preview-inner">
            <img :src="uploadPreview" class="preview-img-inline" />
            <div class="preview-overlay">
              <el-button class="preview-change-btn" type="primary" size="small" @click.stop="triggerUpload">更换图片</el-button>
            </div>
          </div>
        </template>
        <template v-else>
          <el-icon class="isp-upload-icon"><Upload /></el-icon>
          <div class="isp-upload-text">拖拽图片到这里</div>
          <div class="isp-upload-hint">JPG / PNG / WebP</div>
        </template>
      </el-upload>

      <div class="isp-upload-actions" v-if="uploadFile">
        <el-button type="primary" size="large" @click="doSearch" :loading="searching">
          <el-icon><Search /></el-icon>
          开始搜索
        </el-button>
        <el-button size="large" plain @click="clearUpload">清除</el-button>
      </div>
    </div>

    <div v-if="hits.length > 0" class="isp-results">
      <div class="isp-results-head">
        <span>搜索结果</span>
        <span class="isp-results-count">{{ hits.length }} 条</span>
      </div>
      <div class="isp-results-table">
        <div class="isp-r-row isp-r-header">
          <span class="isp-r-thumb"></span>
          <span class="isp-r-name">作品名称</span>
          <span class="isp-r-artist">作者</span>
          <span class="isp-r-year">年代</span>
          <span class="isp-r-sim">相似度</span>
        </div>
        <div
          v-for="(hit, idx) in hits"
          :key="hit.id"
          class="isp-r-row isp-r-body"
          :class="{ 'isp-r-top': idx === 0 }"
          @click="$emit('item-click', hit.image_id)"
        >
          <span class="isp-r-thumb">
            <img :src="hit.thumbnail_url" class="isp-r-img" @error="e => e.target.style.display='none'" />
          </span>
          <span class="isp-r-name">{{ hit.title || '未命名' }}</span>
          <span class="isp-r-artist">{{ hit.artist }}</span>
          <span class="isp-r-year">{{ hit.year || '—' }}</span>
          <span class="isp-r-sim" :class="{ 'sim-red': hit.score > 0.99, 'sim-amber': hit.score > 0.95 }">
            {{ (hit.score * 100).toFixed(1) }}%
          </span>
        </div>
      </div>
    </div>

    <div v-if="duplicates.length > 0" class="isp-dups">
      <div class="isp-dups-bar" @click="dupExpanded = !dupExpanded">
        <span class="isp-dups-label">
          <el-icon><WarningFilled /></el-icon>
          潜在重复 {{ duplicates.length }} 对
        </span>
        <el-icon><component :is="dupExpanded ? ArrowUp : ArrowDown" /></el-icon>
      </div>
      <div v-show="dupExpanded" class="isp-dups-list">
        <div v-for="(pair, idx) in duplicates" :key="idx" class="isp-dup-row">
          <span class="isp-dup-item" @click="$emit('item-click', pair.a.image_id || pair.a.id)">
            <img :src="pair.a.thumbnail_url" class="isp-dup-thumb" />
            {{ pair.a.title }}
          </span>
          <span class="isp-dup-sep">{{ (pair.score * 100).toFixed(1) }}%</span>
          <span class="isp-dup-item" @click="$emit('item-click', pair.b.image_id || pair.b.id)">
            <img :src="pair.b.thumbnail_url" class="isp-dup-thumb" />
            {{ pair.b.title }}
          </span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload, WarningFilled, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import api from '../../api'

const emit = defineEmits(['item-click'])

const uploadRef = ref(null)
const uploadFile = ref(null)
const uploadPreview = ref('')
const searching = ref(false)
const hits = ref([])
const totalIndexed = ref(0)
const duplicates = ref([])
const dupExpanded = ref(false)
const rebuilding = ref(false)

function triggerUpload() {
  uploadRef.value?.$el.querySelector('input[type=file]')?.click()
}

function onFileSelected(file) {
  uploadFile.value = file.raw
  const reader = new FileReader()
  reader.onload = (e) => { uploadPreview.value = e.target.result }
  reader.readAsDataURL(file.raw)
}

function clearUpload() {
  uploadFile.value = null
  uploadPreview.value = ''
  hits.value = []
}

async function doSearch() {
  if (!uploadFile.value) return
  searching.value = true
  try {
    const fd = new FormData()
    fd.append('image', uploadFile.value)
    const data = await api.post('/image-search/search?top_k=10', fd)
    hits.value = data.hits || []
    totalIndexed.value = data.total_indexed || 0
    if (hits.value.length === 0) ElMessage.info('未找到相似作品')
  } catch (e) {
    ElMessage.error('搜索失败')
  } finally {
    searching.value = false
  }
}

async function fetchStats() {
  try {
    const data = await api.get('/image-search/stats')
    totalIndexed.value = data.total_indexed || 0
  } catch { /* silent */ }
}

async function fetchDuplicates() {
  try {
    duplicates.value = await api.get('/image-search/duplicates?threshold=0.995') || []
  } catch { /* silent */ }
}

async function rebuildIndex() {
  try {
    await ElMessageBox.confirm(
      '重建索引需要调用 API 重新对所有作品图生成向量，耗时较长，确定要继续吗？',
      '确认重建索引',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  rebuilding.value = true
  try {
    const data = await api.post('/image-search/rebuild-index')
    totalIndexed.value = data.total || 0
    ElMessage.success(`索引重建完成: ${data.total} 幅`)
  } catch (e) {
    ElMessage.error('重建失败')
  } finally {
    rebuilding.value = false
  }
}

onMounted(() => { fetchStats(); fetchDuplicates() })
</script>

<style scoped>
.isp-root { max-width: 820px; margin: 0 auto; }

.isp-head {
  position: relative; text-align: center; margin-bottom: 16px;
}
.isp-hero-tag {
  font-size: 12px; letter-spacing: 0.3px;
  border-radius: 6px !important;
}
.isp-rebuild-btn {
  position: absolute; right: 0; top: 50%; transform: translateY(-50%);
  color: #b8b4aa !important; font-size: 12px;
}
.isp-rebuild-btn:hover {
  color: #c96442 !important;
}

.isp-upload-area {
  margin-bottom: 24px; text-align: center;
}
.isp-upload { display: inline-block; }
.isp-upload :deep(.el-upload) {
  display: block !important;
}
.isp-upload :deep(.el-upload-dragger) {
  width: 420px; min-height: 200px;
  border-radius: 16px;
  padding: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px;
  background: #fafaf8;
  border: 2px dashed #e0ddd3;
  transition: all 0.25s ease;
}
.isp-upload :deep(.el-upload-dragger:hover) {
  border-color: #c96442;
  background: #fdf8f5;
}
.isp-upload :deep(.el-upload-dragger.is-dragover) {
  border-color: #c96442;
  background: #fdf0ea;
}
.isp-upload-icon {
  font-size: 48px; color: #cac6bb; margin-bottom: 4px;
  transition: color 0.25s ease, transform 0.25s ease;
}
.isp-upload :deep(.el-upload-dragger:hover) .isp-upload-icon {
  color: #c96442; transform: translateY(-2px);
}
.isp-upload-text {
  font-size: 15px; font-weight: 500; color: #6b6b66; letter-spacing: 0.02em;
}
.isp-upload-hint {
  margin-top: 2px; font-size: 12px; color: #b8b4aa; letter-spacing: 0.5px;
}

.preview-inner {
  position: relative; width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; border-radius: 14px;
}
.preview-img-inline {
  max-width: 100%; max-height: 320px;
  object-fit: contain; border-radius: 14px;
}
.preview-overlay {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.45);
  opacity: 0; transition: opacity 0.25s ease; border-radius: 14px;
  backdrop-filter: blur(2px);
}
.preview-inner:hover .preview-overlay { opacity: 1; }
.preview-change-btn {
  height: 46px; padding: 0 32px;
  border-radius: 10px; background: #c96442;
  color: #fff; border: none; font-weight: 500;
  letter-spacing: 0.3px;
}

.isp-upload-actions {
  display: flex; flex-direction: row; justify-content: center; gap: 12px; margin-top: 20px;
}

.isp-results { margin-bottom: 20px; }
.isp-results-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; font-size: 14px; font-weight: 600; color: #303133;
}
.isp-results-count { font-weight: 400; font-size: 12px; color: #999; }
.isp-results-table { border: 1px solid #e8e6e0; border-radius: 10px; overflow: hidden; }
.isp-r-row {
  display: flex; align-items: center; gap: 12px; padding: 0 14px;
  font-size: 13px; border-bottom: 1px solid #f0eee6;
}
.isp-r-header { height: 36px; background: #faf8f4; color: #999; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; }
.isp-r-body { height: 58px; cursor: pointer; transition: background 0.15s; }
.isp-r-body:hover { background: #fdfcf9; }
.isp-r-top { background: #fef9f4; }
.isp-r-thumb { width: 46px; flex-shrink: 0; }
.isp-r-img {
  width: 46px; height: 46px; object-fit: cover; border-radius: 6px;
  border: 1px solid #e0ddcf; display: block;
}
.isp-r-name { flex: 1; font-weight: 600; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.isp-r-artist { width: 60px; color: #888; }
.isp-r-year { width: 50px; color: #aaa; font-size: 12px; }
.isp-r-sim { width: 60px; text-align: right; font-weight: 700; font-size: 15px; color: #888; font-variant-numeric: tabular-nums; }
.sim-red { color: #c96442; }
.sim-amber { color: #b8a47e; }

.isp-dups { margin-bottom: 20px; }
.isp-dups-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: #fdf8f4; border: 1px solid #f0e4d6;
  border-radius: 8px; cursor: pointer; transition: background 0.15s;
}
.isp-dups-bar:hover { background: #fdf2ec; }
.isp-dups-label { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: #c96442; }
.isp-dups-list { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.isp-dup-row {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: #fdfcf9; border: 1px solid #f0eee6; border-radius: 8px;
}
.isp-dup-item {
  flex: 1; display: flex; align-items: center; gap: 8px; cursor: pointer;
  font-size: 13px; color: #303133; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.isp-dup-thumb { width: 32px; height: 32px; object-fit: cover; border-radius: 4px; border: 1px solid #e0ddcf; flex-shrink: 0; }
.isp-dup-sep { font-size: 14px; font-weight: 700; color: #b8a47e; flex-shrink: 0; }
</style>
