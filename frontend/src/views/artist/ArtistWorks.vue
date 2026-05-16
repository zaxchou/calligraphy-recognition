<template>
  <div class="artist-sub-page">
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

    <div class="aw-toolbar">
      <div class="aw-toolbar-left">
        <el-select v-model="selectedArtist" size="small" placeholder="切换画家" @change="onArtistChange" clearable style="width:140px">
          <el-option label="全部画家" value="all" />
          <el-option v-for="name in artistOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <el-input v-model="searchQuery" placeholder="搜索标题、题跋..." size="small" style="width:180px" clearable @keyup.enter="onSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button size="small" type="primary" @click="onSearch">搜索</el-button>
        <el-button size="small" @click="clearSearch" v-if="searchQuery" text>清除</el-button>
      </div>
      <div class="aw-toolbar-right">
        <span class="aw-total">共 {{ totalCount }} 件</span>
        <div class="aw-view-toggle">
          <el-tooltip content="图库模式" placement="top">
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
      </div>
    </div>

    <div v-if="loading" class="asp-loading">加载中...</div>
    <div v-else-if="works.length === 0" class="asp-empty">暂无作品数据</div>
    <template v-else>
      <div class="aw-sort-bar">
        <span class="aw-sort-label">排序：</span>
        <span v-for="s in sortOptions" :key="s.key" class="aw-sort-item" :class="{ active: activeSort === s.key }" @click="onSort(s.key)">
          {{ s.label }}
          <el-icon v-if="activeSort === s.key" style="font-size:12px;margin-left:2px">
            <ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else />
          </el-icon>
        </span>
      </div>

      <!-- 图库模式 -->
      <div v-show="viewMode === 'grid'" class="aw-grid">
        <div v-for="w in works" :key="w.id || w.db_id" class="aw-card" @click="goToWork(w)">
          <div class="aw-thumb">
            <img v-if="w.thumbnail_url || w.url" :src="w.thumbnail_url || w.url" :alt="w.title" loading="lazy" />
            <span v-else class="aw-placeholder">{{ (w.title || '?').charAt(0) }}</span>
          </div>
          <div class="aw-info">
            <div class="aw-title">{{ w.title || w.work_name || '未命名' }}</div>
            <div class="aw-year">{{ w.year || w.inscription_year || '年份不详' }}</div>
            <div v-if="w.inscription_percent !== undefined" class="aw-meta">
              <span>题跋{{ w.inscription_percent }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 列表模式 -->
      <div v-show="viewMode === 'list'" class="aw-table-wrap">
        <div class="aw-table">
          <div class="aw-table-header">
            <div class="aw-tcol aw-tcol-img">图片</div>
            <div class="aw-tcol aw-tcol-info">作品信息</div>
            <div class="aw-tcol aw-tcol-author">作者</div>
            <div class="aw-tcol aw-tcol-year sortable" :class="{ sorted: activeSort === 'year' }" @click="onSort('year')">
              年代 <el-icon v-if="activeSort === 'year'"><ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else /></el-icon>
            </div>
            <div class="aw-tcol aw-tcol-inscription sortable" :class="{ sorted: activeSort === 'inscription' }" @click="onSort('inscription')">
              题跋% <el-icon v-if="activeSort === 'inscription'"><ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else /></el-icon>
            </div>
            <div class="aw-tcol aw-tcol-painting sortable" :class="{ sorted: activeSort === 'painting' }" @click="onSort('painting')">
              绘画% <el-icon v-if="activeSort === 'painting'"><ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else /></el-icon>
            </div>
            <div class="aw-tcol aw-tcol-blank sortable" :class="{ sorted: activeSort === 'blank' }" @click="onSort('blank')">
              留白% <el-icon v-if="activeSort === 'blank'"><ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else /></el-icon>
            </div>
            <div class="aw-tcol aw-tcol-date sortable" :class="{ sorted: activeSort === 'created' }" @click="onSort('created')">
              上传时间 <el-icon v-if="activeSort === 'created'"><ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else /></el-icon>
            </div>
            <div class="aw-tcol aw-tcol-action">操作</div>
          </div>
          <div class="aw-table-body">
            <div v-for="w in works" :key="w.id || w.db_id" class="aw-table-row" @click="goToWork(w)">
              <div class="aw-tcol aw-tcol-img">
                <div class="aw-table-thumb">
                  <img v-if="w.thumbnail_url || w.url" :src="w.thumbnail_url || w.url" :alt="w.title" @error="onImgError" />
                  <span v-else class="aw-thumb-na"><el-icon><PictureFilled /></el-icon></span>
                </div>
              </div>
              <div class="aw-tcol aw-tcol-info">
                <div class="aw-table-title">{{ w.title || w.work_name || '未命名' }}</div>
              </div>
              <div class="aw-tcol aw-tcol-author">{{ w.artist || '-' }}</div>
              <div class="aw-tcol aw-tcol-year">{{ w.year ? w.year + '年' : '-' }}</div>
              <div class="aw-tcol aw-tcol-inscription">
                <span class="aw-stat-val">{{ w.inscription_percent?.toFixed(1) }}%</span>
              </div>
              <div class="aw-tcol aw-tcol-painting">
                <span class="aw-stat-val">{{ w.painting_percent?.toFixed(1) }}%</span>
              </div>
              <div class="aw-tcol aw-tcol-blank">
                <span class="aw-stat-val">{{ w.blank_percent?.toFixed(1) }}%</span>
              </div>
              <div class="aw-tcol aw-tcol-date">
                <span class="aw-date-val">{{ w.created_at ? w.created_at.slice(0, 10) : '-' }}</span>
              </div>
              <div class="aw-tcol aw-tcol-action" @click.stop>
                <el-button size="small" text @click.stop="goToWork(w)">详情</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="totalCount > pageSize" class="aw-pagination">
        <el-pagination background layout="prev, pager, next" :total="totalCount" :page-size="pageSize" v-model:current-page="currentPage" @current-change="loadWorks" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ArrowDown, ArrowUp, Grid, List, PictureFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = route.params.name
const viewMode = ref('grid')
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
  { key: 'created', label: '上传时间' },
]

const SORT_FIELD_MAP = { year: 'year', inscription: 'inscription_percent', painting: 'painting_percent', blank: 'blank_percent', created: 'created_at' }

function onSort(key) {
  if (activeSort.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { activeSort.value = key; sortDir.value = 'desc' }
  currentPage.value = 1; loadWorks()
}

function onArtistChange() {
  const val = selectedArtist.value
  if (val && val !== 'all') router.replace({ name: 'ArtistWorks', params: { name: val } })
}

function onSearch() { currentPage.value = 1; loadWorks() }
function clearSearch() { searchQuery.value = ''; currentPage.value = 1; loadWorks() }

function goToWork(w) {
  const id = w.id || w.db_id
  if (id) window.open(`/#/tubi/${id}`, '_blank')
}
function onImgError(e) { e.target.style.display = 'none' }

async function loadWorks() {
  loading.value = true
  try {
    const artistParam = selectedArtist.value && selectedArtist.value !== 'all' ? selectedArtist.value : undefined
    const skip = (currentPage.value - 1) * pageSize
    const params = new URLSearchParams({ skip, limit: pageSize })
    if (artistParam) params.set('artist', artistParam)
    if (searchQuery.value) params.set('keyword', searchQuery.value)
    const sf = SORT_FIELD_MAP[activeSort.value]
    if (sf) { params.set('sort_by', sf); params.set('sort_dir', sortDir.value) }
    const res = await fetch(`${API_BASE}/tubi/results?${params}`)
    if (res.ok) { const d = await res.json(); works.value = d.data || []; totalCount.value = d.total || 0 }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function fetchArtistOptions() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    if (res.ok) { const d = await res.json(); artistOptions.value = d.artists || [] }
  } catch (e) { console.error(e) }
}

watch(() => route.params.name, (n) => { if (n) { selectedArtist.value = n; currentPage.value = 1; loadWorks() } })

onMounted(async () => { await fetchArtistOptions(); loadWorks() })
</script>

<style scoped>
.artist-sub-page { max-width: 1200px; margin: 0 auto; padding: 24px 20px 80px; min-height: 100vh; background: #fafaf8; }
.asp-hero { margin-bottom: 8px; }
.asp-hero-title { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-back-link:hover { color: #c45a3c; }
.asp-sub-nav { display: flex; border-bottom: 1px solid #edeae1; margin-bottom: 20px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-loading, .asp-empty { text-align: center; padding: 60px 0; color: #b0a890; font-size: 15px; }

/* 工具栏 */
.aw-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.aw-toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.aw-total { font-size: 13px; color: #8a8578; margin-right: 8px; }
.aw-view-toggle { display: flex; gap: 2px; }

/* 排序栏 */
.aw-sort-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; padding: 8px 14px; background: #f6f4ef; border-radius: 8px; flex-wrap: wrap; }
.aw-sort-label { font-size: 12px; color: #8a8578; margin-right: 6px; }
.aw-sort-item { font-size: 13px; color: #8c7a5c; cursor: pointer; padding: 4px 10px; border-radius: 4px; transition: all 0.15s; display: flex; align-items: center; user-select: none; }
.aw-sort-item:hover { color: #3a3222; background: #edeae1; }
.aw-sort-item.active { color: #c45a3c; background: #fdf6f0; font-weight: 500; }

/* 图库模式 */
.aw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; }
.aw-card { background: #fff; border: 1px solid #edeae1; border-radius: 10px; overflow: hidden; cursor: pointer; transition: all 0.2s; }
.aw-card:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.08); border-color: #dbbca8; }
.aw-thumb { width: 100%; aspect-ratio: 3/4; background: #f5f3ed; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.aw-thumb img { width: 100%; height: 100%; object-fit: cover; }
.aw-placeholder { font-size: 32px; color: #d0ccc0; font-family: 'Noto Serif SC', serif; }
.aw-info { padding: 10px 12px; }
.aw-title { font-size: 13px; color: #3a3222; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px; }
.aw-year { font-size: 12px; color: #b0a890; margin-bottom: 4px; }
.aw-meta { font-size: 11px; color: #8a8578; }
.aw-meta span { background: #f5f3ed; padding: 2px 6px; border-radius: 3px; }

/* 列表模式 */
.aw-table-wrap { border: 1px solid #edeae1; border-radius: 10px; overflow: hidden; background: #fff; }
.aw-table { width: 100%; }
.aw-table-header, .aw-table-row { display: flex; align-items: center; padding: 0 12px; }
.aw-table-header { background: #f6f4ef; font-size: 12px; color: #8a8578; font-weight: 500; height: 40px; border-bottom: 1px solid #edeae1; }
.aw-table-row { height: 56px; border-bottom: 1px solid #f0ede8; cursor: pointer; transition: background 0.12s; }
.aw-table-row:last-child { border-bottom: none; }
.aw-table-row:hover { background: #fdfaf7; }
.aw-tcol { flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: #3a3222; }
.aw-tcol.sortable { cursor: pointer; user-select: none; display: flex; align-items: center; gap: 2px; }
.aw-tcol.sortable:hover { color: #c45a3c; }
.aw-tcol.sortable.sorted { color: #c45a3c; }
.aw-tcol-img { width: 60px; display: flex; align-items: center; }
.aw-table-thumb { width: 40px; height: 40px; border-radius: 4px; overflow: hidden; background: #f5f3ed; display: flex; align-items: center; justify-content: center; }
.aw-table-thumb img { width: 100%; height: 100%; object-fit: cover; }
.aw-thumb-na { color: #d0ccc0; font-size: 18px; }
.aw-tcol-info { flex: 1; min-width: 0; padding: 0 8px; }
.aw-table-title { font-size: 13px; font-weight: 500; color: #3a3222; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.aw-tcol-author { width: 80px; color: #8a8578; }
.aw-tcol-year { width: 70px; color: #8a8578; }
.aw-tcol-inscription, .aw-tcol-painting, .aw-tcol-blank { width: 65px; justify-content: center; }
.aw-stat-val { font-weight: 500; color: #c45a3c; }
.aw-tcol-date { width: 90px; color: #b0a890; font-size: 12px; }
.aw-date-val { font-size: 12px; }
.aw-tcol-action { width: 60px; justify-content: center; }

.aw-pagination { margin-top: 24px; display: flex; justify-content: center; }

@media (max-width: 768px) {
  .aw-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
  .aw-toolbar { flex-direction: column; align-items: stretch; }
  .aw-toolbar-left { flex-wrap: wrap; }
  .aw-tcol-author, .aw-tcol-year, .aw-tcol-date { display: none; }
  .aw-tcol-inscription, .aw-tcol-painting, .aw-tcol-blank { width: 50px; }
}
</style>
