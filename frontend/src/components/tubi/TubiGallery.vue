<template>
  <el-card shadow="hover" class="gallery-card" id="gallery-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">作品库</span>
        <div class="header-actions">
          <!-- 搜索框 -->
          <el-input
            v-model="searchKeyword"
            placeholder="搜索画作..."
            size="small"
            clearable
            @keyup.enter="handleSearch"
            style="width: 180px; margin-right: 8px;"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" size="small" @click="handleSearch" :icon="Search">
            搜索
          </el-button>
          <el-tag type="info" size="small" style="margin-left: 8px;">共 {{ historyList.length }} 幅作品</el-tag>
          <el-button plain size="small" @click="showBatchUploadDialog" :icon="Plus" style="margin-left: 8px;">
            添加画作
          </el-button>
        </div>
      </div>
    </template>
    <!-- 标签筛选指示条 -->
    <div v-if="filterTag" class="filter-indicator">
      <span>当前筛选: <strong>{{ filterTag }}</strong></span>
      <span class="filter-count">共 {{ displayedHistoryList.length }} 幅（全部展开）</span>
      <el-button size="small" text @click="clearTagFilter">
        <el-icon><Close /></el-icon>
        清除
      </el-button>
    </div>
    <!-- 骨架屏（数量与默认显示一致，避免加载完成后的高度抖动） -->
    <div class="gallery-grid" v-if="loading">
      <div v-for="i in 20" :key="i" class="gallery-item gallery-skeleton">
        <div class="gallery-image-wrapper">
          <div class="skeleton-img skeleton-pulse"></div>
        </div>
        <div class="gallery-info">
          <div class="skeleton-line skeleton-pulse" style="width:80%;height:14px;margin-bottom:8px;"></div>
          <div class="skeleton-line skeleton-pulse" style="width:60%;height:11px;"></div>
        </div>
      </div>
    </div>

    <div class="gallery-grid" v-if="!loading && displayedHistoryList.length > 0">
      <div
        v-for="item in displayedHistoryList"
        :key="item.id"
        class="gallery-item"
        @click="handleItemClick(item)"
      >
        <div class="gallery-image-wrapper">
          <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="gallery-image" loading="lazy" />
          <div v-else class="gallery-image-placeholder">
            <el-icon size="32"><Picture /></el-icon>
          </div>
          <!-- 处理状态标识 -->
          <div v-if="item.status && item.status !== 'analyzed'" class="gallery-status-badge" :class="'status-' + item.status">
            <el-icon v-if="item.status === 'queued'" size="14"><Clock /></el-icon>
            <el-icon v-else-if="item.status === 'analyzing'" size="14" class="is-loading"><Loading /></el-icon>
            <el-icon v-else-if="item.status === 'error'" size="14"><Close /></el-icon>
            <el-icon v-else size="14"><Clock /></el-icon>
            <span>{{ item.status === 'queued' ? '排队中' : item.status === 'analyzing' ? '分析中' : item.status === 'error' ? '失败' : item.status }}</span>
          </div>

          <div class="gallery-actions">
            <div class="action-tl">
              <el-button plain size="small" circle class="btn-edit" @click.stop="handleEdit(item)" title="编辑">
                <el-icon><Edit /></el-icon>
              </el-button>
            </div>
            <div class="action-tr">
              <el-button type="danger" size="small" circle @click.stop="handleDelete(item)" title="删除">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <!-- 册页标识 + 面积统计（右下角叠加） -->
          <div v-if="item.album_name || item.inscriptionPercent !== undefined" class="gallery-labels">
            <span v-if="item.album_name" class="gallery-label album-label">册页</span>
            <span v-if="item.inscriptionPercent !== undefined" class="gallery-label stat-label danger">{{ item.inscriptionPercent?.toFixed(1) }}%题跋</span>
            <span v-if="item.paintingPercent > 0" class="gallery-label stat-label primary">{{ item.paintingPercent?.toFixed(1) }}%绘画</span>
          </div>
        </div>
        <div class="gallery-info">
          <div class="gallery-title">{{ item.title || '未命名' }}</div>
          <div class="gallery-meta">
            <span v-if="item.artist" class="meta-col">{{ item.artist }}</span>
            <span v-if="getDisplayAge(item) !== null" class="meta-col">{{ getDisplayAge(item) }}岁</span>
            <span v-if="item.year" class="meta-col">{{ item.year }}年</span>
          </div>
          <div class="gallery-tags" v-if="getItemAllTags(item).length > 0">
            <span v-for="tag in getItemAllTags(item)" :key="tag" class="info-tag">{{ tag }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-if="!filterTag && historyList.length > displayLimit" class="gallery-load-more">
      <el-button type="primary" link @click="handleLoadMore">
        加载更多 ({{ historyList.length - displayLimit }} 剩余)
      </el-button>
    </div>
    <div v-if="!loading && !filterTag && historyList.length <= displayLimit" class="gallery-end">
      <span class="gallery-end-text">已经到底</span>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Plus, Search, Edit, Delete, Picture, Clock, Loading, Close } from '@element-plus/icons-vue'

// Props
const props = defineProps({
  historyList: {
    type: Array,
    required: true
  },
  getDisplayAge: {
    type: Function,
    required: true
  },
  getItemAllTags: {
    type: Function,
    required: true
  },
  filterTag: {
    type: String,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['item-click', 'edit', 'delete', 'search', 'load-more', 'clear-tag-filter', 'show-batch-upload'])

// Local state
const searchKeyword = ref('')
const displayLimit = ref(20)

// Computed
const displayedHistoryList = computed(() => {
  let list = props.historyList
  // 标签筛选
  if (props.filterTag) {
    list = list.filter(item => props.getItemAllTags(item).includes(props.filterTag))
    return list // 标签筛选模式：全部展开，不限制数量
  }
  // 搜索筛选
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.trim().toLowerCase()
    list = list.filter(item => {
      return (
        (item.title && item.title.toLowerCase().includes(keyword)) ||
        (item.artist && item.artist.toLowerCase().includes(keyword)) ||
        (item.year && String(item.year).includes(keyword)) ||
        (item.notes && item.notes.toLowerCase().includes(keyword)) ||
        (item.analysisNote && item.analysisNote.toLowerCase().includes(keyword))
      )
    })
  }
  return list.slice(0, displayLimit.value)
})

// Event handlers
function handleItemClick(item) {
  emit('item-click', item)
}

function handleEdit(item) {
  emit('edit', item)
}

function handleDelete(item) {
  emit('delete', item)
}

function handleSearch() {
  emit('search', searchKeyword.value)
}

function handleLoadMore() {
  displayLimit.value += 20
  emit('load-more')
}

function clearTagFilter() {
  emit('clear-tag-filter')
}

function showBatchUploadDialog() {
  emit('show-batch-upload')
}
</script>

<style scoped>
/* ─── 骨架屏 ─── */
.gallery-skeleton .gallery-image-wrapper {
  background: var(--parchment);
}

.skeleton-img {
  width: 100%;
  height: 100%;
  background: var(--border-cream);
  border-radius: 0;
}

.skeleton-line {
  border-radius: 4px;
  background: var(--border-cream);
}

@keyframes skeletonPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.skeleton-pulse {
  animation: skeletonPulse 1.5s ease-in-out infinite;
}

.gallery-card {
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-cream);
}

.gallery-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
  gap: 16px;
}

.gallery-card .card-header .card-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}

.gallery-card .header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.filter-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: var(--ivory);
  border-bottom: 1px solid var(--border-cream);
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--charcoal-warm);
}

.filter-indicator strong {
  color: var(--cinnabar);
  font-weight: 600;
}

.filter-count {
  color: var(--stone-gray);
  font-size: 13px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px;
}

.gallery-item {
  background: var(--pure-white);
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.gallery-item:hover {
  border-color: var(--cinnabar);
  box-shadow: var(--shadow-whisper);
  transform: translateY(-2px);
}

.gallery-image-wrapper {
  position: relative;
  width: 100%;
  padding-top: 75%;
  background: var(--parchment);
}

.gallery-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gallery-image-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cinnabar);
}

.gallery-status-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-family: var(--font-sans);
}

.gallery-status-badge.status-queued {
  background: rgba(184, 164, 126, 0.9);
}

.gallery-status-badge.status-analyzing {
  background: rgba(84, 122, 140, 0.9);
}

.gallery-status-badge.status-error {
  background: rgba(181, 51, 51, 0.9);
}

.gallery-status-badge .is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.gallery-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.gallery-item:hover .gallery-actions {
  opacity: 1;
}

.gallery-labels {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
}

.gallery-label {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
  font-family: var(--font-sans);
}

.gallery-label.album-label {
  background: var(--near-black);
  color: var(--pure-white);
}

.gallery-label.stat-label.danger {
  background: var(--cinnabar);
  color: var(--pure-white);
}

.gallery-label.stat-label.primary {
  background: var(--tubi-success);
  color: var(--pure-white);
}

.gallery-info {
  padding: 12px;
}

.gallery-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--near-black);
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gallery-meta {
  font-size: 12px;
  color: var(--stone-gray);
  font-family: var(--font-sans);
  margin-bottom: 8px;
  display: flex;
  gap: 4px;
  width: 60%;
}

.meta-col {
  flex: 0 0 33.33%;
  min-width: 0;
  white-space: nowrap;
  text-align: center;
}

.meta-col:first-child {
  text-align: left;
}

.meta-col:last-child {
  text-align: right;
}

.gallery-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.info-tag {
  padding: 2px 6px;
  background: var(--warm-sand);
  color: var(--charcoal-warm);
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-family: var(--font-sans);
}

.gallery-load-more {
  text-align: center;
  padding: 16px;
}

.gallery-end {
  text-align: center;
  padding: 16px;
}

.gallery-end-text {
  color: var(--stone-gray);
  font-size: 13px;
  font-family: var(--font-sans);
}
</style>
