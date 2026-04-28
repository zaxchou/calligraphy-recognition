<template>
  <div class="isp-root">
    <div class="isp-hero">
      <el-icon class="isp-hero-icon"><PictureFilled /></el-icon>
      <span class="isp-hero-title">以图搜图</span>
      <el-tag size="small" effect="plain" class="isp-hero-tag">{{ totalIndexed }} 幅已索引</el-tag>
    </div>
    <p class="isp-hero-desc">上传作品截图或照片，自动匹配库中相似作品</p>

    <div class="isp-upload-row">
      <el-upload
        class="isp-upload"
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".jpg,.jpeg,.png,.webp,.bmp"
        :on-change="onFileSelected"
      >
        <template v-if="!uploadPreview">
          <el-icon class="isp-upload-icon"><Upload /></el-icon>
          <div class="isp-upload-text">拖拽图片到这里</div>
          <div class="isp-upload-hint">JPG / PNG / WebP</div>
        </template>
        <img v-else :src="uploadPreview" class="isp-upload-preview" />
      </el-upload>
      <div class="isp-upload-actions">
        <el-button type="primary" size="large" @click="doSearch" :loading="searching" :disabled="!uploadFile">
          <el-icon><Search /></el-icon>
          开始搜索
        </el-button>
        <el-button size="small" plain @click="clearUpload" v-if="uploadFile">清除</el-button>
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
          @click="$emit('item-click', hit.id)"
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
          <span class="isp-dup-item" @click="$emit('item-click', pair.a.id)">
            <img :src="pair.a.thumbnail_url" class="isp-dup-thumb" />
            {{ pair.a.title }}
          </span>
          <span class="isp-dup-sep">{{ (pair.score * 100).toFixed(1) }}%</span>
          <span class="isp-dup-item" @click="$emit('item-click', pair.b.id)">
            <img :src="pair.b.thumbnail_url" class="isp-dup-thumb" />
            {{ pair.b.title }}
          </span>
        </div>
      </div>
    </div>

    <div class="isp-footer">
      <el-button size="small" text @click="rebuildIndex" :loading="rebuilding">重建索引</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Upload, WarningFilled, ArrowUp, ArrowDown, PictureFilled } from '@element-plus/icons-vue'

const emit = defineEmits(['item-click'])
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

const uploadFile = ref(null)
const uploadPreview = ref('')
const searching = ref(false)
const hits = ref([])
const totalIndexed = ref(0)
const duplicates = ref([])
const dupExpanded = ref(false)
const rebuilding = ref(false)

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
    const res = await fetch(`${API_BASE}/image-search/search?top_k=10`, { method: 'POST', body: fd })
    const data = await res.json()
    hits.value = data.hits || []
    totalIndexed.value = data.total_indexed || 0
    if (hits.value.length === 0) ElMessage.info('未找到相似作品')
  } catch (e) {
    ElMessage.error('搜索失败')
  } finally {
    searching.value = false
  }
}

async function fetchDuplicates() {
  try {
    const res = await fetch(`${API_BASE}/image-search/duplicates?threshold=0.995`)
    duplicates.value = await res.json() || []
  } catch { /* silent */ }
}

async function rebuildIndex() {
  rebuilding.value = true
  try {
    const res = await fetch(`${API_BASE}/image-search/rebuild-index`, { method: 'POST' })
    const data = await res.json()
    totalIndexed.value = data.total || 0
    ElMessage.success(`索引重建完成: ${data.total} 幅`)
  } catch (e) {
    ElMessage.error('重建失败')
  } finally {
    rebuilding.value = false
  }
}

onMounted(() => { fetchDuplicates() })
</script>

<style scoped>
.isp-root { max-width: 820px; margin: 0 auto; }

.isp-hero {
  display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
}
.isp-hero-icon { font-size: 22px; color: #c96442; }
.isp-hero-title { font-size: 18px; font-weight: 700; color: #1a1a1a; font-family: 'Noto Serif SC','KaiTi',serif; }
.isp-hero-tag { margin-left: 4px; }
.isp-hero-desc { font-size: 13px; color: #999; margin-bottom: 20px; }

.isp-upload-row {
  display: flex; gap: 20px; align-items: flex-start; margin-bottom: 24px;
}
.isp-upload { flex: 1; }
.isp-upload :deep(.el-upload-dragger) {
  min-height: 140px; border-radius: 12px;
}
.isp-upload-icon { font-size: 36px; color: #c0c4cc; margin-bottom: 6px; }
.isp-upload-text { font-size: 14px; color: #606266; }
.isp-upload-hint { margin-top: 4px; font-size: 12px; color: #ccc; }
.isp-upload-preview { max-height: 180px; max-width: 100%; object-fit: contain; border-radius: 8px; }
.isp-upload-actions {
  display: flex; flex-direction: column; gap: 8px; padding-top: 4px; min-width: 110px;
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

.isp-footer { text-align: center; padding-top: 8px; border-top: 1px solid #f0eee6; }
</style>
