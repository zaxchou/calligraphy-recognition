<template>
  <div class="av-page">
    <header class="av-header">
      <div class="av-header-inner">
        <h1 class="av-name">
          <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="av-name-link">{{ artistName }}</router-link>
          <span class="av-name-suffix">· 作品</span>
        </h1>
      </div>
    </header>

    <nav class="av-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="av-nav-link">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="av-nav-link active">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="av-nav-link">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="av-nav-link">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="av-nav-link">分析</router-link>
    </nav>

    <!-- 分类 + 工具栏 -->
    <div class="aw-toolbar">
      <div class="aw-toolbar-left">
        <div class="aw-type-tabs">
          <span class="aw-type-tab" :class="{ active: workTypeFilter === '' }" @click="setWorkType('')">全部</span>
          <span class="aw-type-tab" :class="{ active: workTypeFilter === '画作' }" @click="setWorkType('画作')">画作</span>
          <span class="aw-type-tab" :class="{ active: workTypeFilter === '书法' }" @click="setWorkType('书法')">书法</span>
          <span class="aw-type-tab" :class="{ active: workTypeFilter === '篆刻' }" @click="setWorkType('篆刻')">篆刻</span>
        </div>
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

    <div class="aw-sort-bar">
      <span class="aw-sort-label">排序：</span>
      <span v-for="s in sortOptions" :key="s.key" class="aw-sort-item" :class="{ active: activeSort === s.key }" @click="onSort(s.key)">
        {{ s.label }}
        <el-icon v-if="activeSort === s.key" style="font-size:12px;margin-left:2px">
          <ArrowDown v-if="sortDir === 'desc'" /><ArrowUp v-else />
        </el-icon>
      </span>
    </div>

    <div v-if="loading" class="av-loading">加载中...</div>
    <div v-else-if="works.length === 0" class="av-empty">暂无作品数据</div>
    <template v-else>
      <!-- 图库模式（照搬 TubiGallery 样式） -->
      <div v-show="viewMode === 'grid'" class="aw-grid">
        <div v-for="w in works" :key="w.id || w.db_id" class="aw-card" @click="goToWork(w)">
          <div class="aw-image-wrapper">
            <img v-if="w.thumbnail_url || w.url" :src="w.thumbnail_url || w.url" :alt="w.title" class="aw-image" loading="lazy" />
            <div v-else class="aw-image-placeholder"><el-icon size="24"><Picture /></el-icon></div>
            <!-- 处理状态标识 -->
            <div v-if="w.status && w.status !== 'analyzed'" class="aw-status-badge" :class="'status-' + w.status">
              <el-icon v-if="w.status === 'queued'" size="10"><Clock /></el-icon>
              <el-icon v-else-if="w.status === 'analyzing'" size="10" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="w.status === 'error'" size="10"><Close /></el-icon>
              <el-icon v-else size="10"><Clock /></el-icon>
              <span>{{ w.status === 'queued' ? '排队中' : w.status === 'analyzing' ? '分析中' : w.status === 'error' ? '失败' : w.status }}</span>
            </div>
            <!-- 类型标识 -->
            <div v-if="w.work_type === '书法'" class="aw-type-badge">
              <span>书法</span>
            </div>
            <div v-if="w.work_type === '篆刻'" class="aw-type-badge seal-type">
              <span>篆刻</span>
            </div>
            <!-- 页面角色角标 -->
            <div v-if="w.page_role" class="aw-role-badge" :class="'role-' + w.page_role">
              <span>{{ roleBadge(w.page_role) }}</span>
            </div>
            <!-- 面积统计（右下角） -->
            <div v-if="w.inscription_percent !== undefined || w.painting_percent > 0" class="aw-labels">
              <span v-if="w.inscription_percent !== undefined" class="aw-label stat-danger">{{ w.inscription_percent?.toFixed(1) }}%题跋</span>
              <span v-if="w.painting_percent > 0" class="aw-label stat-primary">{{ w.painting_percent?.toFixed(1) }}%绘画</span>
            </div>
          </div>
          <div class="aw-info">
            <div class="aw-title">{{ w.title || '未命名' }}</div>
            <div class="aw-meta">
              <span v-if="w.year" class="meta-col">{{ w.year }}年</span>
              <span v-if="w.artist" class="meta-col">{{ w.artist }}</span>
            </div>
            <div class="aw-tags" v-if="getTags(w).length > 0">
              <span v-for="tag in getTags(w).slice(0, 3)" :key="tag" class="info-tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 列表模式（保持不变） -->
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ArrowDown, ArrowUp, Grid, List, PictureFilled, Picture, Clock, Loading, Close } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = computed(() => route.params.name)

const ROLE_BADGE = { cover: '封', back_cover: '底', inscription: '跋', accessory: '附', other: '他' }
function roleBadge(role) { return ROLE_BADGE[role] || '他' }
const viewMode = ref('grid')
const works = ref([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = 24
const loading = ref(true)
const searchQuery = ref('')
const activeSort = ref('year')
const sortDir = ref('desc')
const workTypeFilter = ref('')

const sortOptions = [
  { key: 'year', label: '年代' },
  { key: 'inscription', label: '题跋比' },
  { key: 'painting', label: '绘画比' },
  { key: 'blank', label: '留白比' },
  { key: 'created', label: '上传时间' },
]

const SORT_FIELD_MAP = { year: 'year', inscription: 'inscription_percent', painting: 'painting_percent', blank: 'blank_percent', created: 'created_at' }

function getTags(w) {
  let tags = []
  if (w.computed_tags && Array.isArray(w.computed_tags)) tags = tags.concat(w.computed_tags)
  if (w.tags) {
    try {
      const parsed = JSON.parse(w.tags)
      if (Array.isArray(parsed)) tags = tags.concat(parsed)
    } catch {
      console.warn('[ArtistWorks] tags JSON parse failed:', w.tags)
    }
  }
  return [...new Set(tags)]
}

function setWorkType(type) {
  workTypeFilter.value = type
  currentPage.value = 1
  loadWorks()
}

function onSort(key) {
  if (activeSort.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { activeSort.value = key; sortDir.value = 'desc' }
  currentPage.value = 1; loadWorks()
}

function onSearch() { currentPage.value = 1; loadWorks() }
function clearSearch() { searchQuery.value = ''; currentPage.value = 1; loadWorks() }

function goToWork(w) {
  const id = w.id || w.db_id
  if (id) {
    const resolved = router.resolve({ name: 'TubiDetail', params: { id } })
    window.open(resolved.href, '_blank')
  }
}
function onImgError(e) {
  e.target.style.display = 'none'
  const placeholder = e.target.nextElementSibling
  if (placeholder && placeholder.classList.contains('aw-thumb-na')) {
    placeholder.style.display = 'flex'
  }
}

async function loadWorks() {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize
    const params = new URLSearchParams({ skip, limit: pageSize })
    params.set('artist', artistName.value)
    if (searchQuery.value) params.set('keyword', searchQuery.value)
    if (workTypeFilter.value) params.set('work_type', workTypeFilter.value)
    const sf = SORT_FIELD_MAP[activeSort.value]
    if (sf) { params.set('sort_by', sf); params.set('sort_dir', sortDir.value) }
    const res = await fetch(`${API_BASE}/tubi/results?${params}`)
    if (res.ok) { const d = await res.json(); works.value = d.data || []; totalCount.value = d.total || 0 }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

watch(() => route.params.name, (n) => { if (n) { currentPage.value = 1; loadWorks() } })
onMounted(() => { loadWorks() })
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

/* ─── 分类 Tab ─── */
.aw-type-tabs { display: flex; gap: 4px; }
.aw-type-tab { padding: 5px 14px; font-size: 13px; color: #8c7a5c; cursor: pointer; border-radius: 6px; transition: all 0.15s; user-select: none; }
.aw-type-tab:hover { background: #f5f0e8; color: #3a3222; }
.aw-type-tab.active { background: #c45a3c; color: #fff; font-weight: 500; }

.aw-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.aw-toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.aw-total { font-size: 13px; color: #8a8578; }
.aw-view-toggle { display: flex; gap: 2px; }

.aw-sort-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; padding: 8px 14px; background: #f6f4ef; border-radius: 8px; flex-wrap: wrap; }
.aw-sort-label { font-size: 12px; color: #8a8578; margin-right: 6px; }
.aw-sort-item { font-size: 13px; color: #8c7a5c; cursor: pointer; padding: 4px 10px; border-radius: 4px; transition: all 0.15s; display: flex; align-items: center; user-select: none; }
.aw-sort-item:hover { color: #3a3222; background: #edeae1; }
.aw-sort-item.active { color: #c45a3c; background: #fdf6f0; font-weight: 500; }

/* ─── 图库模式（TubiGallery 风格） ─── */
.aw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
.aw-card { background: #fff; border: 1px solid #e8e3da; border-radius: 8px; overflow: hidden; cursor: pointer; transition: all 0.2s; }
.aw-card:hover { border-color: #c45a3c; box-shadow: 0 2px 12px rgba(0,0,0,0.06); transform: translateY(-2px); }
.aw-image-wrapper { position: relative; width: 100%; aspect-ratio: 3/4; background: #f5f3ed; }
.aw-image { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
.aw-image-placeholder { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: #c45a3c; }

/* 状态角标 */
.aw-status-badge { position: absolute; top: 4px; left: 4px; display: flex; align-items: center; gap: 3px; padding: 2px 6px; background: rgba(0,0,0,0.7); color: #fff; border-radius: 3px; font-size: 10px; }
.aw-status-badge.status-queued { background: rgba(184,164,126,0.9); }
.aw-status-badge.status-analyzing { background: rgba(84,122,140,0.9); }
.aw-status-badge.status-error { background: rgba(181,51,51,0.9); }
.aw-status-badge .is-loading { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 类型标识（书法） */
.aw-type-badge { position: absolute; top: 4px; right: 4px; z-index: 2; }
.aw-type-badge span { display: inline-block; padding: 1px 5px; background: #5a7a8c; color: #fff; border-radius: 3px; font-size: 9px; font-weight: 500; }
.aw-type-badge.seal-type span { background: #8b6f8e; }

/* 页面角色角标 */
.aw-role-badge { position: absolute; top: 24px; right: 4px; z-index: 2; }
.aw-role-badge span { display: inline-block; padding: 1px 5px; color: #fff; border-radius: 3px; font-size: 9px; font-weight: 500; }
.aw-role-badge.role-cover span { background: #8b6914; }
.aw-role-badge.role-back_cover span { background: #666; }
.aw-role-badge.role-accessory span { background: #2c6e8f; }
.aw-role-badge.role-inscription span { background: #7b4a8b; }
.aw-role-badge.role-other span { background: #999; }

/* 面积标签 */
.aw-labels { position: absolute; bottom: 4px; right: 4px; display: flex; gap: 3px; }
.aw-label { padding: 1px 5px; border-radius: 3px; font-size: 9px; font-weight: 500; }
.aw-label.stat-danger { background: #c45a3c; color: #fff; }
.aw-label.stat-primary { background: #5a8c7a; color: #fff; }

.aw-info { padding: 6px 8px 8px; }
.aw-title { font-size: 12px; font-weight: 600; color: #2c2416; font-family: 'Noto Serif SC', serif; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.aw-meta { font-size: 10px; color: #8a8578; margin-bottom: 4px; display: flex; gap: 3px; width: 100%; }
.meta-col { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: center; }
.meta-col:first-child { text-align: left; }
.meta-col:last-child { text-align: right; }
.aw-tags { display: flex; flex-wrap: wrap; gap: 3px; max-height: 36px; overflow: hidden; }
.info-tag { padding: 1px 5px; background: #f5f3ed; color: #3a3222; border-radius: 3px; font-size: 9px; white-space: nowrap; }

/* ─── 列表模式 ─── */
.aw-table-wrap { border: 1px solid #e8e3da; border-radius: 10px; overflow: hidden; background: #fff; }
.aw-table { width: 100%; }
.aw-table-header, .aw-table-row { display: flex; align-items: center; padding: 0 12px; }
.aw-table-header { background: #f6f4ef; font-size: 12px; color: #8a8578; font-weight: 500; height: 40px; border-bottom: 1px solid #e8e3da; }
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
.aw-thumb-na { color: #c0b8a8; font-size: 18px; }
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
  .av-page { padding: 0 16px 80px; }
  .aw-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 8px; }
  .aw-toolbar { flex-direction: column; align-items: stretch; }
  .aw-toolbar-left { flex-wrap: wrap; }
  .aw-tcol-author, .aw-tcol-year, .aw-tcol-date { display: none; }
  .aw-tcol-inscription, .aw-tcol-painting, .aw-tcol-blank { width: 50px; }
  .aw-type-tabs { order: -1; }
}
</style>
