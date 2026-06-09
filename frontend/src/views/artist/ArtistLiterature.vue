<template>
  <div class="av-page">
    <header class="av-header">
      <div class="av-header-inner">
        <h1 class="av-name">
          <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="av-name-link">{{ artistName }}</router-link>
          <span class="av-name-suffix">· 文献</span>
        </h1>
      </div>
    </header>

    <nav class="av-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="av-nav-link">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="av-nav-link">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="av-nav-link">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="av-nav-link active">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="av-nav-link">分析</router-link>
    </nav>

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
        <span class="al-total" v-if="totalCount > 0">共 {{ totalCount }} 篇</span>
        <div class="al-view-toggle">
          <el-tooltip content="卡片模式" placement="top">
            <el-button size="small" :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'" text>
              <el-icon><Grid /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="列表模式" placement="top">
            <el-button size="small" :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'" text>
              <el-icon><List /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
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
    <div v-else-if="literature.length === 0" class="av-empty">
      <p>暂无关联文献</p>
    </div>
    <template v-else>
      <!-- 卡片视图 -->
      <div v-show="viewMode === 'grid'" class="al-grid">
        <div v-for="doc in literature" :key="doc.id" class="al-card" @click="openReader(doc)">
          <div class="al-card-left">
            <div class="al-card-icon">&#128214;</div>
            <div v-if="doc.chunk_count" class="al-card-chunks">{{ doc.chunk_count }} 章节</div>
          </div>
          <div class="al-card-info">
            <div class="al-card-title">{{ doc.title }}</div>
            <div class="al-card-meta">
              <span v-if="doc.author" class="al-meta-item">{{ doc.author }}</span>
              <span v-if="doc.journal" class="al-meta-item">{{ doc.journal }}</span>
              <span v-if="doc.publish_year" class="al-meta-item">{{ doc.publish_year }}</span>
            </div>
            <div v-if="doc.abstract" class="al-card-abstract">{{ doc.abstract.slice(0, 120) }}{{ doc.abstract.length > 120 ? '...' : '' }}</div>
            <div v-if="doc.keywords" class="al-card-keywords">
              <el-tag v-for="kw in parseKeywords(doc.keywords)" :key="kw" size="small" type="info" class="al-kw-tag">{{ kw }}</el-tag>
            </div>
            <div class="al-card-bottom">
              <span class="al-card-date">{{ doc.created_at?.slice(0, 10) }}</span>
              <span v-if="doc.doi" class="al-card-doi">DOI: {{ doc.doi }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 列表视图 -->
      <div v-show="viewMode === 'list'" class="al-table-wrap">
        <div class="al-table">
          <div class="al-table-header">
            <div class="al-tcol al-tcol-title">标题</div>
            <div class="al-tcol al-tcol-author">作者</div>
            <div class="al-tcol al-tcol-journal">期刊/出版社</div>
            <div class="al-tcol al-tcol-year">年份</div>
            <div class="al-tcol al-tcol-chunks">章节</div>
            <div class="al-tcol al-tcol-date">上传时间</div>
            <div class="al-tcol al-tcol-action">操作</div>
          </div>
          <div class="al-table-body">
            <div v-for="doc in literature" :key="doc.id" class="al-table-row" @click="openReader(doc)">
              <div class="al-tcol al-tcol-title">
                <div class="al-table-title">{{ doc.title }}</div>
              </div>
              <div class="al-tcol al-tcol-author">{{ doc.author || '-' }}</div>
              <div class="al-tcol al-tcol-journal">{{ doc.journal || '-' }}</div>
              <div class="al-tcol al-tcol-year">{{ doc.publish_year || '-' }}</div>
              <div class="al-tcol al-tcol-chunks">{{ doc.chunk_count || 0 }}</div>
              <div class="al-tcol al-tcol-date">{{ doc.created_at?.slice(0, 10) || '-' }}</div>
              <div class="al-tcol al-tcol-action" @click.stop>
                <el-button size="small" text @click="openReader(doc)">阅读</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="totalCount > pageSize" class="al-pagination">
        <el-pagination background layout="prev, pager, next" :total="totalCount" :page-size="pageSize" v-model:current-page="currentPage" @current-change="loadLiterature" />
      </div>
    </template>

    <!-- 上传弹窗 -->
    <LiteratureUpload v-if="showUpload && artistId" :artist-id="artistId" @uploaded="onUploaded" @close="showUpload = false" />

    <!-- 阅读弹窗 -->
    <LiteratureReader v-if="readerBook" :book="readerBook" :artist-name="artistName" @close="readerBook = null" />

    <ChatFloat v-if="artistId" :artist-id="artistId" :artist-name="artistName" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Search, ArrowDown, ArrowUp, Grid, List, Upload } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/authStore'
import LiteratureUpload from '../../components/LiteratureUpload.vue'
import LiteratureReader from '../../components/LiteratureReader.vue'
import ChatFloat from '../../components/ChatFloat.vue'

const route = useRoute()
const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = computed(() => route.params.name)
const artistId = ref(null)
const literature = ref([])
const loading = ref(true)
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = 20
const searchQuery = ref('')
const viewMode = ref('grid')
const activeSort = ref('created_at')
const sortDir = ref('desc')
const showUpload = ref(false)
const readerBook = ref(null)

const sortOptions = [
  { key: 'created_at', label: '上传时间' },
  { key: 'publish_year', label: '年份' },
  { key: 'title', label: '标题' },
]

function onSort(key) {
  if (activeSort.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { activeSort.value = key; sortDir.value = 'desc' }
  currentPage.value = 1
  loadLiterature()
}

function onSearch() { currentPage.value = 1; loadLiterature() }
function clearSearch() { searchQuery.value = ''; currentPage.value = 1; loadLiterature() }
function openReader(doc) { readerBook.value = { ...doc, artist_id: artistId.value } }
function onUploaded() { showUpload.value = false; loadLiterature() }
function parseKeywords(kw) {
  if (!kw) return []
  try { return typeof kw === 'string' ? JSON.parse(kw) : kw }
  catch { return [] }
}

async function fetchArtistId() {
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(artistName.value)}`)
    if (res.ok) {
      const data = await res.json()
      artistId.value = data.artist?.id || null
    }
  } catch (e) { console.error(e) }
}

async function loadLiterature() {
  if (!artistId.value) return
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value,
      page_size: pageSize,
      sort_by: activeSort.value,
      sort_dir: sortDir.value,
    })
    if (searchQuery.value) params.set('keyword', searchQuery.value)
    const res = await fetch(`${API_BASE}/knowledge/artists/${artistId.value}/literature?${params}`)
    if (res.ok) {
      const data = await res.json()
      literature.value = data.items || []
      totalCount.value = data.total || 0
    }
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
.av-page { max-width: var(--container-wide); margin: 0 auto; padding: 0 24px 120px; min-height: 100vh; background: #faf8f5; }
.av-loading, .av-empty { text-align: center; padding: 80px 0; color: #8a8578; font-size: 15px; }

.av-header { padding: 32px 0 12px; }
.av-header-inner { display: flex; align-items: baseline; }
.av-name { font-family: 'Noto Serif SC', serif; font-size: 24px; font-weight: 700; color: #2c2416; margin: 0; }
.av-name-link { color: #2c2416; text-decoration: none; }
.av-name-link:hover { color: #c45a3c; }
.av-name-suffix { font-weight: 400; color: #8a8578; font-size: 20px; }

.av-sub-nav { display: flex; gap: 4px; padding: 16px 0; margin-bottom: 24px; border-bottom: 1px solid #e8e3da; overflow-x: auto; }
.av-nav-link { padding: 8px 18px; font-size: 13px; color: #8c7a5c; text-decoration: none; border-radius: 6px; transition: all 0.15s; white-space: nowrap; }
.av-nav-link:hover { background: #f5f0e8; color: #3a3222; }
.av-nav-link.active { background: #fdf6f0; color: #c45a3c; font-weight: 600; }

/* ─── 工具栏 ─── */
.al-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.al-toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.al-toolbar-right { display: flex; align-items: center; gap: 8px; }
.al-total { font-size: 13px; color: #8a8578; }
.al-view-toggle { display: flex; gap: 2px; }

/* ─── 排序栏 ─── */
.al-sort-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; padding: 8px 14px; background: #f6f4ef; border-radius: 8px; flex-wrap: wrap; }
.al-sort-label { font-size: 12px; color: #8a8578; margin-right: 6px; }
.al-sort-item { font-size: 13px; color: #8c7a5c; cursor: pointer; padding: 4px 10px; border-radius: 4px; transition: all 0.15s; display: flex; align-items: center; user-select: none; }
.al-sort-item:hover { color: #3a3222; background: #edeae1; }
.al-sort-item.active { color: #c45a3c; background: #fdf6f0; font-weight: 500; }

/* ─── 卡片视图 ─── */
.al-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.al-card { display: flex; gap: 14px; background: #fff; border: 1px solid #e8e3da; border-radius: 10px; padding: 18px; cursor: pointer; transition: all 0.2s; }
.al-card:hover { border-color: #d0b898; box-shadow: 0 2px 12px rgba(0,0,0,0.05); transform: translateY(-1px); }
.al-card-left { display: flex; flex-direction: column; align-items: center; gap: 6px; flex-shrink: 0; }
.al-card-icon { font-size: 32px; }
.al-card-chunks { font-size: 11px; color: #b0a890; white-space: nowrap; }
.al-card-info { min-width: 0; flex: 1; }
.al-card-title { font-size: 14px; font-weight: 600; color: #2c2416; margin-bottom: 6px; font-family: 'Noto Serif SC', serif; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.al-card-meta { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.al-card-abstract { font-size: 12px; color: #6b6150; line-height: 1.5; margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.al-card-keywords { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.al-kw-tag { font-size: 11px; }
.al-meta-item { font-size: 12px; color: #8a8578; background: #f5f0e8; padding: 2px 8px; border-radius: 4px; }
.al-card-bottom { display: flex; justify-content: space-between; align-items: center; }
.al-card-date { font-size: 11px; color: #b0a890; }
.al-card-doi { font-size: 11px; color: #b0a890; font-family: monospace; }

/* ─── 列表视图 ─── */
.al-table-wrap { border: 1px solid #e8e3da; border-radius: 10px; overflow: hidden; background: #fff; }
.al-table { width: 100%; }
.al-table-header, .al-table-row { display: flex; align-items: center; padding: 0 14px; }
.al-table-header { background: #f6f4ef; font-size: 12px; color: #8a8578; font-weight: 500; height: 40px; border-bottom: 1px solid #e8e3da; }
.al-table-row { height: 52px; border-bottom: 1px solid #f0ede8; cursor: pointer; transition: background 0.12s; }
.al-table-row:last-child { border-bottom: none; }
.al-table-row:hover { background: #fdfaf7; }
.al-tcol { flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: #3a3222; }
.al-tcol-title { flex: 1; min-width: 0; padding: 0 8px; }
.al-table-title { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.al-tcol-author { width: 80px; color: #8a8578; }
.al-tcol-journal { width: 120px; color: #8a8578; }
.al-tcol-year { width: 60px; color: #8a8578; text-align: center; }
.al-tcol-chunks { width: 50px; text-align: center; color: #b0a890; }
.al-tcol-date { width: 90px; color: #b0a890; font-size: 12px; }
.al-tcol-action { width: 60px; justify-content: center; }

.al-pagination { margin-top: 24px; display: flex; justify-content: center; }

@media (max-width: 768px) {
  .av-page { padding: 0 16px 80px; }
  .al-grid { grid-template-columns: 1fr; }
  .al-toolbar { flex-direction: column; align-items: stretch; }
  .al-tcol-journal, .al-tcol-chunks { display: none; }
}
</style>
