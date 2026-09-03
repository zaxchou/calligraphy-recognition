<template>
  <div class="al-page">
    <!-- 工具栏 -->
    <div class="al-toolbar">
      <div class="al-toolbar-left">
        <el-input v-model="searchQuery" placeholder="搜索标题、作者..." size="small" style="width:200px" clearable @keyup.enter="onSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button size="small" type="primary" @click="onSearch">搜索</el-button>
        <el-button size="small" @click="clearSearch" v-if="searchQuery" text>清除</el-button>
      </div>
      <div class="al-toolbar-right">
        <el-button v-if="authStore.isEditor || authStore.isAdmin" size="small" type="primary" @click="showUpload = true">
          <el-icon style="margin-right:4px"><Upload /></el-icon>上传文献
        </el-button>
      </div>
    </div>

    <div class="al-sort-bar">
      <span class="al-sort-label">排序：</span>
      <span v-for="s in sortOptions" :key="s.key" class="al-sort-item" :class="{ active: activeSort === s.key }" @click="onSort(s.key)">
        {{ s.label }}
        <el-icon v-if="activeSort === s.key" style="font-size:12px;margin-left:2px">
          <ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else />
        </el-icon>
      </span>
    </div>

    <div v-if="loading" class="av-loading">加载中...</div>
    <div v-else-if="literature.length === 0" class="av-empty"><p>暂无关联文献</p></div>
    <template v-else>
      <!-- 统计栏 -->
      <div class="al-stats-bar">
        <span class="al-stat-item"><span class="al-stat-num">{{ totalCount }}</span><span class="al-stat-label">篇文献</span></span>
        <span class="al-stat-divider"></span>
        <span class="al-stat-item"><span class="al-stat-num">{{ literature.filter(d => d.source_type).length }}</span><span class="al-stat-label">已分类</span></span>
        <span class="al-stat-divider"></span>
        <span class="al-stat-item"><span class="al-stat-num">{{ literature.reduce((s, d) => s + (d.chunk_count || 0), 0) }}</span><span class="al-stat-label">章节</span></span>
        <span class="al-stat-divider"></span>
        <span class="al-stat-item" v-if="authStore.isEditor">
          <el-popconfirm title="确定删除 full_md 为空的无效文献？" @confirm="deleteEmptyDocs">
            <template #reference><span class="al-stat-clean">清空无效记录</span></template>
          </el-popconfirm>
        </span>
      </div>

      <!-- 卡片列表 -->
      <div class="al-list">
        <div v-for="doc in literature" :key="doc.id" class="al-card" @click="openReader(doc)">
          <div class="al-card-left">
            <div class="al-card-title-row">
              <span class="al-card-title">{{ doc.title || '（无标题）' }}</span>
              <el-tag v-if="doc.source_type" size="small" class="al-type-tag">{{ doc.source_type }}</el-tag>
            </div>
            <div class="al-card-meta">
              <span class="al-card-meta-item">{{ doc.author || '-' }}</span>
              <span class="al-card-meta-sep">|</span>
              <span class="al-card-meta-item">{{ doc.journal || '-' }}</span>
              <span class="al-card-meta-sep">|</span>
              <span class="al-card-meta-item">{{ doc.publish_year || '-' }}</span>
            </div>
            <div v-if="doc.keywords" class="al-card-kw">
              <span v-for="kw in parseKeywords(doc.keywords).slice(0, 4)" :key="kw" class="al-kw-dot">{{ kw }}</span>
              <span v-if="parseKeywords(doc.keywords).length > 4" class="al-kw-more">+{{ parseKeywords(doc.keywords).length - 4 }}</span>
            </div>
          </div>
          <div class="al-card-right">
            <span class="al-chunk-num">{{ doc.chunk_count || 0 }}</span><span class="al-chunk-label">节</span>
            <span class="al-card-date">{{ doc.created_at?.slice(0, 10) }}</span>
            <el-button size="small" class="al-card-btn" @click.stop="openReader(doc)">阅读</el-button>
          </div>
        </div>
      </div>

      <!-- 翻页 -->
      <div v-if="totalCount > pageSize" class="al-pagination-wrap">
        <button class="al-page-btn" :disabled="currentPage <= 1" @click="currentPage--; loadLiterature()">‹</button>
        <template v-for="p in pageNumbers" :key="p">
          <span v-if="p === '...'" class="al-page-dots">…</span>
          <button v-else class="al-page-btn" :class="{ active: p === currentPage }" @click="currentPage = p; loadLiterature()">{{ p }}</button>
        </template>
        <button class="al-page-btn" :disabled="currentPage >= Math.ceil(totalCount / pageSize)" @click="currentPage++; loadLiterature()">›</button>
      </div>
    </template>

    <LiteratureUpload v-if="showUpload && artistId" :artist-id="artistId" @uploaded="onUploaded" @close="showUpload = false" />
    <ChatFloat v-if="artistId" :artist-id="artistId" :artist-name="artistName" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ArrowDown, ArrowUp, Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/authStore'
import LiteratureUpload from '../../components/LiteratureUpload.vue'
import ChatFloat from '../../components/ChatFloat.vue'
import api from '../../api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const artistName = computed(() => route.params.name)
const artistId = ref(null)
const literature = ref([])
const loading = ref(true)
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = 20
const searchQuery = ref('')
const activeSort = ref('created_at')
const sortDir = ref('desc')
const showUpload = ref(false)

const sortOptions = [
  { key: 'created_at', label: '上传时间' },
  { key: 'publish_year', label: '年份' },
  { key: 'title', label: '标题' },
  { key: 'source_type', label: '类型' },
]

const pageNumbers = computed(() => {
  const total = Math.ceil(totalCount.value / pageSize)
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = []
  const c = currentPage.value
  if (c > 3) { pages.push(1); if (c > 4) pages.push('...') }
  for (let i = Math.max(1, c - 1); i <= Math.min(total, c + 1); i++) pages.push(i)
  if (c < total - 2) { if (c < total - 3) pages.push('...'); pages.push(total) }
  return pages
})

function onSort(key) {
  if (activeSort.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { activeSort.value = key; sortDir.value = 'desc' }
  currentPage.value = 1
  loadLiterature()
}

function onSearch() { currentPage.value = 1; loadLiterature() }
function clearSearch() { searchQuery.value = ''; currentPage.value = 1; loadLiterature() }
function openReader(doc) {
  router.push({ name: 'ArtistLiteratureReader', params: { name: artistName.value, bookId: doc.id } })
}
function onUploaded() { showUpload.value = false; loadLiterature() }
function parseKeywords(kw) {
  if (!kw) return []
  try { return typeof kw === 'string' ? JSON.parse(kw) : kw }
  catch { return [] }
}

async function deleteEmptyDocs() {
  const ids = literature.value.filter(d => !d.full_md_length && !d.chunk_count).map(d => d.id)
  if (!ids.length) return
  let done = 0
  for (const id of ids) {
    try {
      await api.delete(`/knowledge/artists/${artistId.value}/literature/${id}`)
      done++
    } catch (_) {}
  }
  if (done) { ElMessage.success(`已删除 ${done} 篇无效文献`); loadLiterature() }
}

async function fetchArtistId() {
  try {
    const data = await api.get(`/artists/by-name/${encodeURIComponent(artistName.value)}`)
    artistId.value = data.artist?.id || null
  } catch (e) { console.error(e) }
}

async function loadLiterature() {
  if (!artistId.value) { loading.value = false; return }
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value, page_size: pageSize,
      sort_by: activeSort.value, sort_dir: sortDir.value,
    })
    if (searchQuery.value) params.set('keyword', searchQuery.value)
    const data = await api.get(`/knowledge/artists/${artistId.value}/literature?${params}`)
    literature.value = data.items || []
    totalCount.value = data.total || 0
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

watch(() => route.params.name, () => { fetchArtistId().then(loadLiterature) })

onMounted(async () => {
  await fetchArtistId()
  await loadLiterature()
})
</script>

<style scoped>
.av-loading, .av-empty { text-align: center; padding: 80px 0; color: #8a8578; font-size: 15px; }

/* ─── 工具栏 ─── */
.al-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.al-toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.al-toolbar-right { display: flex; align-items: center; gap: 8px; }

/* ─── 排序栏 ─── */
.al-sort-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; padding: 8px 14px; background: #f6f4ef; border-radius: 8px; flex-wrap: wrap; }
.al-sort-label { font-size: 12px; color: #8a8578; margin-right: 6px; }
.al-sort-item { font-size: 13px; color: #8c7a5c; cursor: pointer; padding: 4px 10px; border-radius: 4px; transition: all 0.15s; display: flex; align-items: center; user-select: none; }
.al-sort-item:hover { color: #3a3222; background: #edeae1; }
.al-sort-item.active { color: #c45a3c; background: #fdf6f0; font-weight: 500; }

/* ─── 统计栏 ─── */
.al-stats-bar { display: flex; align-items: center; gap: 10px; padding: 8px 14px; margin-bottom: 12px; background: #fff; border: 1px solid #e8e3da; border-radius: 8px; font-size: 12px; }
.al-stat-item { display: flex; align-items: baseline; gap: 3px; }
.al-stat-num { font-weight: 600; color: #c45a3c; font-size: 14px; font-variant-numeric: tabular-nums; }
.al-stat-label { color: #8a8578; font-size: 11px; }
.al-stat-divider { width: 1px; height: 14px; background: #e8e3da; }
.al-stat-clean { color: #b0a890; font-size: 11px; cursor: pointer; text-decoration: underline dashed; text-underline-offset: 2px; }
.al-stat-clean:hover { color: #c45a3c; }

/* ─── 卡片列表 ─── */
.al-list { display: flex; flex-direction: column; gap: 6px; }
.al-card {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: #fff; border: 1px solid #e8e3da; border-radius: 8px;
  cursor: pointer; transition: all 0.12s;
}
.al-card:hover { border-color: #d4cfc5; box-shadow: 0 1px 4px rgba(0,0,0,0.03); }

.al-card-left { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.al-card-title-row { display: flex; align-items: center; gap: 6px; }
.al-card-title { font-weight: 500; color: #2c2416; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.al-type-tag { font-size: 10px; flex-shrink: 0; border: none !important; background: #fdf6f0 !important; color: #c45a3c !important; border-radius: 3px; padding: 0 5px; height: 18px; line-height: 18px; }
.al-card-meta { display: flex; align-items: center; gap: 4px; font-size: 11px; color: #8a8578; }
.al-card-meta-sep { color: #ddd8d0; }
.al-card-meta-item { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 120px; }

.al-card-kw { display: flex; flex-wrap: wrap; gap: 3px; }
.al-kw-dot { font-size: 10px; color: #b0a890; background: #f6f4ef; padding: 1px 6px; border-radius: 2px; }
.al-kw-more { font-size: 10px; color: #c45a3c; padding: 1px 3px; }

.al-card-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; margin-left: 14px; }
.al-card-chunks { display: flex; align-items: baseline; gap: 2px; min-width: 32px; text-align: right; }
.al-chunk-num { font-size: 14px; font-weight: 600; color: #c45a3c; font-variant-numeric: tabular-nums; }
.al-chunk-label { font-size: 10px; color: #b0a890; }
.al-card-date { font-size: 11px; color: #b0a890; white-space: nowrap; }
.al-card-btn { font-size: 11px !important; padding: 2px 10px !important; }

/* ─── 翻页 ─── */
.al-pagination-wrap { margin-top: 28px; display: flex; align-items: center; justify-content: center; gap: 4px; }
.al-page-btn {
  min-width: 32px; height: 32px; padding: 0 8px; border: 1px solid #e0dcd4; border-radius: 6px;
  background: #fff; color: #6a6258; font-size: 13px; cursor: pointer;
  transition: all 0.12s; display: flex; align-items: center; justify-content: center; user-select: none;
}
.al-page-btn:hover:not(:disabled):not(.active) { border-color: #c45a3c; color: #c45a3c; background: #fdfaf7; }
.al-page-btn.active { border-color: #c45a3c; background: #c45a3c; color: #fff; font-weight: 500; }
.al-page-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.al-page-dots { min-width: 24px; text-align: center; color: #b0a890; font-size: 13px; user-select: none; }

@media (max-width: 768px) {
  .al-toolbar { flex-direction: column; align-items: stretch; }
  .al-card-meta-item { max-width: 80px; }
}
</style>
