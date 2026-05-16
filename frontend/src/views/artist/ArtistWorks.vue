<template>
  <div class="artist-sub-page">
    <!-- 头部：艺术家名 + 子导航 -->
    <div class="asp-hero">
      <h2 class="asp-hero-title">
        <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-back-link">{{ artistName }}</router-link>
      </h2>
    </div>
    <nav class="asp-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-nav-item">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="asp-nav-item active">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="asp-nav-item">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="asp-nav-item">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="asp-nav-item">分析</router-link>
    </nav>

    <!-- 工具栏：画家筛选 + 搜索 + 排序 -->
    <div class="aw-toolbar">
      <div class="aw-toolbar-left">
        <el-select v-model="selectedArtist" size="small" placeholder="切换画家" @change="onArtistChange" clearable style="width:140px">
          <el-option label="全部画家" value="all" />
          <el-option v-for="name in artistOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <el-input v-model="searchQuery" placeholder="搜索作品标题..." size="small" style="width:200px" clearable @keyup.enter="onSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button size="small" type="primary" @click="onSearch">搜索</el-button>
      </div>
      <div class="aw-toolbar-right">
        <span class="aw-total">共 {{ totalCount }} 件作品</span>
      </div>
    </div>

    <div v-if="loading" class="asp-loading">加载中...</div>
    <div v-else-if="works.length === 0" class="asp-empty">暂无作品数据</div>
    <template v-else>
      <!-- 排序标签 -->
      <div class="aw-sort-bar">
        <span class="aw-sort-label">排序：</span>
        <span v-for="s in sortOptions" :key="s.key" class="aw-sort-item" :class="{ active: activeSort === s.key }" @click="onSort(s.key)">
          {{ s.label }}
          <el-icon v-if="activeSort === s.key" style="font-size:12px;margin-left:2px">
            <ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else />
          </el-icon>
        </span>
      </div>

      <!-- 作品网格 -->
      <div class="aw-grid">
        <div v-for="w in works" :key="w.id || w.db_id" class="aw-card" @click="goToWork(w)">
          <div class="aw-thumb">
            <img v-if="w.thumbnail_url || w.url" :src="w.thumbnail_url || w.url" :alt="w.title" loading="lazy" />
            <span v-else class="aw-placeholder">{{ (w.title || '?').charAt(0) }}</span>
          </div>
          <div class="aw-info">
            <div class="aw-title">{{ w.title || w.work_name || '未命名' }}</div>
            <div class="aw-year">{{ w.year || w.inscription_year || '年份不详' }}</div>
            <div v-if="w.inscription_percent !== undefined" class="aw-meta">
              <span class="aw-meta-item">题跋 {{ w.inscription_percent }}%</span>
              <span class="aw-meta-item">绘画 {{ w.painting_percent }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="totalCount > pageSize" class="aw-pagination">
        <el-pagination background layout="prev, pager, next" :total="totalCount" :page-size="pageSize" v-model:current-page="currentPage" @current-change="loadWorks" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ArrowDown, ArrowUp } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = route.params.name
const works = ref([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = 30
const loading = ref(true)
const selectedArtist = ref(artistName)
const searchQuery = ref('')
const activeSort = ref('year')
const sortDir = ref('desc')
const artistOptions = ref([])

const sortOptions = [
  { key: 'year', label: '年代' },
  { key: 'inscription', label: '题跋比' },
  { key: 'painting', label: '绘画比' },
  { key: 'blank', label: '留白比' },
  { key: 'created', label: '创建时间' },
]

const SORT_FIELD_MAP = { year: 'year', inscription: 'inscription_percent', painting: 'painting_percent', blank: 'blank_percent', created: 'created_at' }

function onSort(key) {
  if (activeSort.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { activeSort.value = key; sortDir.value = 'desc' }
  currentPage.value = 1
  loadWorks()
}

function onArtistChange() {
  const val = selectedArtist.value
  if (val && val !== 'all') router.replace({ name: 'ArtistWorks', params: { name: val } })
  else router.replace({ name: 'ArtistWorks', params: { name: artistName } })
}

function onSearch() {
  currentPage.value = 1
  loadWorks()
}

function goToWork(w) {
  const id = w.id || w.db_id
  if (id) window.open(`/#/tubi/${id}`, '_blank')
}

async function loadWorks() {
  loading.value = true
  try {
    const artistParam = selectedArtist.value && selectedArtist.value !== 'all' ? selectedArtist.value : undefined
    const skip = (currentPage.value - 1) * pageSize
    const params = new URLSearchParams({ skip, limit: pageSize })
    if (artistParam) params.set('artist', artistParam)
    if (searchQuery.value) params.set('keyword', searchQuery.value)
    const sortField = SORT_FIELD_MAP[activeSort.value]
    if (sortField) { params.set('sort_by', sortField); params.set('sort_dir', sortDir.value) }
    const res = await fetch(`${API_BASE}/tubi/results?${params}`)
    if (res.ok) {
      const data = await res.json()
      works.value = data.data || []
      totalCount.value = data.total || 0
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function fetchArtistOptions() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    if (res.ok) {
      const data = await res.json()
      artistOptions.value = data.artists || []
    }
  } catch (e) { console.error(e) }
}

watch(() => route.params.name, (newName) => {
  if (newName) { selectedArtist.value = newName; currentPage.value = 1; loadWorks() }
})

onMounted(async () => {
  await fetchArtistOptions()
  loadWorks()
})
</script>

<style scoped>
.artist-sub-page { max-width: 1200px; margin: 0 auto; padding: 24px 20px 80px; min-height: 100vh; background: #fafaf8; }
.asp-hero { margin-bottom: 8px; }
.asp-hero-title { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-back-link:hover { color: #c45a3c; }
.asp-sub-nav { display: flex; gap: 0; border-bottom: 1px solid #edeae1; margin-bottom: 24px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-loading, .asp-empty { text-align: center; padding: 60px 0; color: #b0a890; font-size: 15px; }
.aw-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 12px; flex-wrap: wrap; }
.aw-toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.aw-total { font-size: 13px; color: #8a8578; }
.aw-sort-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 20px; padding: 8px 12px; background: #f6f4ef; border-radius: 8px; flex-wrap: wrap; }
.aw-sort-label { font-size: 12px; color: #8a8578; margin-right: 4px; }
.aw-sort-item { font-size: 13px; color: #8c7a5c; cursor: pointer; padding: 4px 10px; border-radius: 4px; transition: all 0.15s; display: flex; align-items: center; }
.aw-sort-item:hover { color: #3a3222; background: #edeae1; }
.aw-sort-item.active { color: #c45a3c; background: #fdf6f0; font-weight: 500; }
.aw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.aw-card { background: #fff; border: 1px solid #edeae1; border-radius: 10px; overflow: hidden; cursor: pointer; transition: all 0.2s; }
.aw-card:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.08); border-color: #dbbca8; }
.aw-thumb { width: 100%; aspect-ratio: 3/4; background: #f5f3ed; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.aw-thumb img { width: 100%; height: 100%; object-fit: cover; }
.aw-placeholder { font-size: 32px; color: #d0ccc0; font-family: 'Noto Serif SC', serif; }
.aw-info { padding: 12px 14px; }
.aw-title { font-size: 14px; color: #3a3222; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px; }
.aw-year { font-size: 12px; color: #b0a890; margin-bottom: 4px; }
.aw-meta { display: flex; gap: 8px; font-size: 11px; color: #8a8578; }
.aw-meta-item { background: #f5f3ed; padding: 2px 6px; border-radius: 3px; }
.aw-pagination { margin-top: 28px; display: flex; justify-content: center; }
@media (max-width: 768px) {
  .aw-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
  .aw-toolbar { flex-direction: column; align-items: stretch; }
  .aw-toolbar-left { flex-wrap: wrap; }
}
</style>
