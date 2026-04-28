<template>
  <div class="image-search-panel">
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px;">
      <template #title>
        上传作品截图或照片片段，搜索库中相似作品（防止重复上传）
      </template>
    </el-alert>

    <div class="search-upload-area">
      <el-upload
        class="search-upload"
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".jpg,.jpeg,.png,.webp,.bmp"
        :on-change="onFileSelected"
      >
        <div v-if="!uploadPreview" class="upload-placeholder">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">拖拽或点击上传截图</div>
          <div class="upload-hint">支持 jpg / png / webp / bmp</div>
        </div>
        <img v-else :src="uploadPreview" class="upload-preview-img" />
      </el-upload>
      <div class="upload-actions" v-if="uploadFile">
        <el-button type="primary" @click="doSearch" :loading="searching">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
        <el-button @click="clearUpload">清除</el-button>
      </div>
    </div>

    <div v-if="hits.length > 0" class="search-results">
      <div class="results-header">
        <span class="results-title">搜索结果</span>
        <el-tag type="info" size="small">{{ totalIndexed }} 幅已索引</el-tag>
      </div>
      <div class="results-list">
        <div
          v-for="(hit, idx) in hits"
          :key="hit.id"
          class="result-row"
          :class="{ 'top-hit': idx === 0 }"
          @click="$emit('item-click', hit.id)"
        >
          <img
            :src="hit.thumbnail_url || '/placeholder.png'"
            class="result-thumb"
            @error="e => { e.target.style.display = 'none'; e.target.nextElementSibling.style.display = 'flex' }"
          />
          <div class="result-thumb-fallback" style="display:none;">
            <el-icon size="24"><Picture /></el-icon>
          </div>
          <div class="result-info">
            <div class="result-name">{{ hit.title || '未命名' }}</div>
            <div class="result-meta">
              <span>{{ hit.artist }}</span>
              <template v-if="hit.year"><span class="meta-sep">·</span><span>{{ hit.year }}</span></template>
              <template v-if="hit.album_name"><span class="meta-sep">·</span><span>{{ hit.album_name }}</span></template>
            </div>
            <div class="result-meta" v-if="hit.inscription_percent">
              题跋占比 {{ hit.inscription_percent.toFixed(1) }}%
            </div>
          </div>
          <div class="result-score" :style="{ color: hit.score > 0.995 ? '#c96442' : hit.score > 0.95 ? '#b8a47e' : '#888' }">
            {{ (hit.score * 100).toFixed(1) }}%
          </div>
        </div>
      </div>
    </div>

    <div v-if="duplicates.length > 0" class="dup-section">
      <div class="dup-header" @click="dupExpanded = !dupExpanded" style="cursor: pointer;">
        <span class="dup-title">
          <el-icon><WarningFilled /></el-icon>
          潜在重复作品 ({{ duplicates.length }} 对)
        </span>
        <el-icon><component :is="dupExpanded ? ArrowUp : ArrowDown" /></el-icon>
      </div>
      <div v-show="dupExpanded" class="dup-list">
        <div v-for="(pair, idx) in duplicates" :key="idx" class="dup-pair">
          <div class="dup-pair-item" @click="$emit('item-click', pair.a.id)">
            <img :src="pair.a.thumbnail_url" class="dup-thumb" />
            <div class="dup-name">{{ pair.a.title }}</div>
          </div>
          <div class="dup-pair-center">
            <div class="dup-score" :style="{ color: pair.score > 0.998 ? '#c96442' : '#b8a47e' }">
              {{ (pair.score * 100).toFixed(1) }}%
            </div>
            <el-icon class="dup-arrow"><Right /></el-icon>
          </div>
          <div class="dup-pair-item" @click="$emit('item-click', pair.b.id)">
            <img :src="pair.b.thumbnail_url" class="dup-thumb" />
            <div class="dup-name">{{ pair.b.title }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="search-footer">
      <el-button size="small" @click="checkDuplicates" :loading="dupLoading">
        检测重复
      </el-button>
      <el-button size="small" @click="rebuildIndex" :loading="rebuilding" type="warning" plain>
        重建索引
      </el-button>
      <span class="footer-stat">共 {{ totalIndexed }} 幅作品已索引</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Search, WarningFilled, ArrowUp, ArrowDown, Right, Picture } from '@element-plus/icons-vue'

const emit = defineEmits(['item-click'])

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

const uploadFile = ref(null)
const uploadPreview = ref('')
const searching = ref(false)
const hits = ref([])
const totalIndexed = ref(0)

const duplicates = ref([])
const dupLoading = ref(false)
const dupExpanded = ref(false)
const rebuilding = ref(false)

function onFileSelected(file) {
  uploadFile.value = file.raw
  const reader = new FileReader()
  reader.onload = (e) => {
    uploadPreview.value = e.target.result
  }
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
    const res = await fetch(`${API_BASE}/image-search/search?top_k=10`, {
      method: 'POST',
      body: fd,
    })
    const data = await res.json()
    hits.value = data.hits || []
    totalIndexed.value = data.total_indexed || 0
    if (hits.value.length === 0) {
      ElMessage.info('未找到相似作品')
    }
  } catch (e) {
    ElMessage.error('搜索失败')
    console.error(e)
  } finally {
    searching.value = false
  }
}

async function checkDuplicates() {
  dupLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/image-search/duplicates?threshold=0.995`)
    const data = await res.json()
    duplicates.value = data || []
    dupExpanded.value = true
    if (duplicates.value.length === 0) {
      ElMessage.success('未发现重复作品')
    }
  } catch (e) {
    ElMessage.error('检测失败')
    console.error(e)
  } finally {
    dupLoading.value = false
  }
}

async function rebuildIndex() {
  rebuilding.value = true
  try {
    const res = await fetch(`${API_BASE}/image-search/rebuild-index`, { method: 'POST' })
    const data = await res.json()
    totalIndexed.value = data.total || 0
    ElMessage.success(`索引重建完成：${data.total} 幅，耗时 ${data.elapsed}s`)
  } catch (e) {
    ElMessage.error('重建失败')
    console.error(e)
  } finally {
    rebuilding.value = false
  }
}
</script>

<style scoped>
.image-search-panel {
  max-width: 900px;
  margin: 0 auto;
}
.search-upload-area {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.search-upload {
  flex: 1;
}
.search-upload :deep(.el-upload-dragger) {
  min-height: 160px;
}
.upload-placeholder {
  padding: 32px 0;
  text-align: center;
}
.upload-icon {
  font-size: 40px;
  color: #c0c4cc;
}
.upload-text {
  margin-top: 8px;
  font-size: 15px;
  color: #606266;
}
.upload-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #ccc;
}
.upload-preview-img {
  max-height: 200px;
  max-width: 100%;
  object-fit: contain;
}
.upload-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}
.search-results {
  margin-bottom: 20px;
}
.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.results-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.results-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.result-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #fafaf9;
  border: 1px solid #e8e6e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.result-row.top-hit {
  background: #fdf8f4;
  border-color: #e8d4c0;
}
.result-row:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.result-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  border: 1px solid #e0ddcf;
}
.result-thumb-fallback {
  width: 56px;
  height: 56px;
  background: #f0ede8;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #c0bca8;
}
.result-info {
  flex: 1;
  min-width: 0;
}
.result-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 2px;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-meta {
  font-size: 12px;
  color: #999;
}
.meta-sep {
  color: #ddd;
  margin: 0 4px;
}
.result-score {
  font-size: 16px;
  font-weight: 700;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.dup-section {
  margin-bottom: 20px;
}
.dup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}
.dup-title {
  font-size: 14px;
  font-weight: 600;
  color: #c96442;
  display: flex;
  align-items: center;
  gap: 6px;
}
.dup-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.dup-pair {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #fdf8f4;
  border: 1px solid #f0e4d6;
  border-radius: 8px;
  transition: all 0.2s;
}
.dup-pair:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.dup-pair-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.dup-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
  border: 1px solid #e0ddcf;
}
.dup-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}
.dup-pair-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.dup-score {
  font-size: 14px;
  font-weight: 700;
}
.dup-arrow {
  color: #ccc;
}
.search-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0eee6;
}
.footer-stat {
  font-size: 12px;
  color: #999;
  margin-left: auto;
}
</style>
