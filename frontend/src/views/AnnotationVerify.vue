<template>
  <div class="annotation-verify">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">标注状态</span>
        <el-radio-group v-model="filterStatus" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="unannotated">未标注</el-radio-button>
          <el-radio-button value="annotated">已标注</el-radio-button>
        </el-radio-group>
      </div>
      <div class="filter-group search-group">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索作品名、年份、题跋内容..."
          size="small"
          clearable
          @keyup.enter="handleSearch"
          class="search-input"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button size="small" plain class="btn-edit" @click="handleSearch">
          <el-icon><Search /></el-icon>搜索
        </el-button>
        <el-button v-if="searchKeyword" size="small" plain class="btn-edit" @click="clearSearch">
          <el-icon><Close /></el-icon>清除
        </el-button>
      </div>
      <div class="stats">
        <span class="stat-item">
          <span class="stat-label">总计</span>
          <span class="stat-value">{{ totalCount }}</span>
        </span>
        <span class="stat-item annotated" v-if="annotatedCount > 0">
          <span class="stat-label">已标注</span>
          <span class="stat-value">{{ annotatedCount }}</span>
        </span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="filteredRecords.length === 0" class="empty-state">
      <el-icon size="48" color="#c0c0b8"><Picture /></el-icon>
      <p>暂无记录</p>
      <p class="empty-hint" v-if="filterStatus || searchKeyword">尝试调整筛选条件或清除搜索</p>
    </div>

    <!-- 图片网格 -->
    <div v-else class="image-grid">
      <div
        v-for="record in filteredRecords"
        :key="record.id"
        class="image-card"
        @click="openAnnotator(record)"
      >
        <div class="image-wrapper">
          <img
            :src="getThumbnailUrl(record)"
            :alt="record.title || '未命名'"
            class="thumbnail"
            loading="lazy"
            @error="onImageError"
          />
          <!-- 已标注徽章 -->
          <div v-if="record.is_manual_annotated" class="annotated-badge" title="已手动标注">
            <el-icon><Check /></el-icon>
          </div>
        </div>
        <div class="image-info">
          <h4 class="image-title" :title="record.title">{{ record.title || '未命名' }}</h4>
          <div class="image-meta">
            <span class="year">{{ record.year ? record.year + '年' : (record.period_phase || '年代不详') }}</span>
            <span v-if="record.period_phase" class="period">{{ record.period_phase }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载更多 -->
    <div v-if="hasMore && !loading" class="load-more">
      <el-button size="small" plain class="btn-edit" @click="loadMore">
        加载更多
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Close, Loading, Picture, Check } from '@element-plus/icons-vue'

const props = defineProps({
  artist: { type: String, default: 'all' },
  libraryId: { type: Number, default: null }
})

const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

// 状态
const loading = ref(false)
const records = ref([])
const totalCount = ref(0)
const annotatedCount = ref(0)
const filterStatus = ref('unannotated') // '' | 'unannotated' | 'annotated'
const searchKeyword = ref('')
const offset = ref(0)
const limit = 50
const hasMore = ref(false)

// 获取缩略图URL
function getThumbnailUrl(record) {
  const thumb = record.thumbnail_path
  if (!thumb) return '/placeholder-image.png'
  const normalized = thumb.replace(/\\/g, '/')
  let filename
  if (normalized.includes('/thumbnails/')) {
    filename = normalized.split('/thumbnails/').pop()
  } else if (normalized.includes('\\thumbnails\\')) {
    filename = normalized.split('\\thumbnails\\').pop()
  } else {
    filename = normalized.split('/').pop().split('\\').pop()
  }
  return `${API_BASE.replace('/api/v1', '')}/static/thumbnails/${filename}`
}

function onImageError(e) {
  e.target.src = '/placeholder-image.png'
}

// 加载记录
async function fetchRecords(reset = true) {
  if (reset) {
    offset.value = 0
    records.value = []
  }
  
  loading.value = true
  try {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset.value)
    })
    
    if (props.artist && props.artist !== 'all') {
      params.set('artist', props.artist)
    }
    
    if (props.libraryId) {
      params.set('library_id', String(props.libraryId))
    }
    
    if (filterStatus.value) {
      params.set('annotated_status', filterStatus.value)
    }
    
    if (searchKeyword.value.trim()) {
      params.set('keyword', searchKeyword.value.trim())
    }
    
    const url = `${API_BASE}/content-analysis/records?${params}`
    console.log('[AnnotationVerify] Fetch URL:', url)
    const res = await fetch(url)
    const data = await res.json()
    
    if (data.success !== false) {
      if (reset) {
        records.value = data.records || []
      } else {
        records.value.push(...(data.records || []))
      }
      totalCount.value = data.total || records.value.length
      annotatedCount.value = data.annotated_count || 0
      hasMore.value = (data.records || []).length === limit
    } else {
      ElMessage.error(data.message || '获取记录失败')
    }
  } catch (e) {
    ElMessage.error('获取记录失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// 加载更多
async function loadMore() {
  offset.value += limit
  await fetchRecords(false)
}

// 搜索
function handleSearch() {
  fetchRecords(true)
}

function clearSearch() {
  searchKeyword.value = ''
  fetchRecords(true)
}

// 打开标注编辑器
function openAnnotator(record) {
  window.open(`/#/annotate/${record.image_id}`, '_blank')
}

// 筛选变化时重新加载
watch([filterStatus], () => {
  fetchRecords(true)
})

// 作者变化时重新加载
watch(() => props.artist, () => {
  fetchRecords(true)
})

// 初始加载
onMounted(() => {
  fetchRecords(true)
})

// 本地筛选（二次过滤）
const filteredRecords = computed(() => {
  let list = records.value
  
  // 本地搜索过滤
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter(r => {
      const titleMatch = r.title?.toLowerCase().includes(kw)
      const yearMatch = String(r.year || '').includes(kw)
      const contentMatch = r.inscription_content?.toLowerCase().includes(kw)
      return titleMatch || yearMatch || contentMatch
    })
  }
  
  return list
})
</script>

<style scoped>
.annotation-verify {
  padding: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  background: var(--bg-color, #fff);
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-label {
  font-size: 14px;
  color: var(--text-secondary, #6b6b66);
  font-weight: 500;
}

.search-group {
  flex: 1;
  max-width: 400px;
}

.search-input {
  width: 100%;
}

:deep(.search-input .el-input__wrapper) {
  border-radius: 8px;
}

.stats {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 6px;
  background: var(--tag-bg, #f5f4ed);
  border: 1px solid var(--border-color, #e4e7ed);
}

.stat-item.annotated {
  background: #e8f4f0;
  border-color: #5a7d5a;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary, #6b6b66);
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #141413);
}

.stat-item.annotated .stat-value {
  color: #5a7d5a;
}

/* 加载状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-secondary, #6b6b66);
  gap: 12px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: var(--text-secondary, #6b6b66);
  gap: 12px;
}

.empty-hint {
  font-size: 13px;
  color: var(--text-tertiary, #9b9b96);
}

/* 图片网格 */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.image-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border-radius: 6px;
  overflow: hidden;
  background: var(--bg-color, #fff);
  border: 1px solid var(--border-color, #e4e7ed);
}

.image-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.08);
}

.image-wrapper {
  position: relative;
  aspect-ratio: 3/4;
  overflow: hidden;
  background: var(--bg-secondary, #f5f4ed);
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.image-card:hover .thumbnail {
  transform: scale(1.02);
}

/* 已标注徽章 - 绿色打勾 */
.annotated-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  background: #5a8a4a;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  z-index: 10;
}

/* 图片信息 */
.image-info {
  padding: 6px 8px;
}

.image-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary, #141413);
  margin: 0 0 3px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.image-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-secondary, #6b6b66);
}

.period {
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--tag-bg, #f5f4ed);
  font-size: 10px;
}

/* 加载更多 */
.load-more {
  display: flex;
  justify-content: center;
  padding: 20px;
}

/* 按钮样式 */
:deep(.btn-edit) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

:deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
