<template>
  <div class="tubi-list tubi-page">
    <!-- 顶部栏：翻页居左 + 工具居右（卡片外） -->
    <div class="top-bar" v-if="total > pageSize || pagedRankings.length > 0">
      <div class="top-bar-left">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          layout="total, sizes, prev, pager, next"
          :page-sizes="[10, 20, 50, 100]"
          :pager-count="5"
          prev-text="← 上一页"
          next-text="下一页 →"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
      <div class="top-bar-right">
        <el-select v-model="selectedArtist" size="small" placeholder="筛选画家" style="width: 110px" @change="onArtistChange" clearable>
          <el-option label="全部画家" value="all" />
          <el-option v-for="name in artistOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <div class="search-box">
          <el-input v-model="searchKeyword" placeholder="搜索标题、题跋、印章..." size="small" style="width: 160px" clearable @keyup.enter="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" size="small" @click="handleSearch" :icon="Search">搜索</el-button>
        </div>
        <el-button size="small" @click="backToTubi" :icon="ArrowLeft" text>返回主页</el-button>
        <el-button v-if="isAdmin" size="small" type="warning" @click="toggleAdmin">锁定</el-button>
        <el-button v-else size="small" @click="toggleAdmin" text>管理</el-button>
      </div>
    </div>

    <!-- 标签筛选指示条 -->
    <div v-if="filterTag" class="filter-indicator">
      <span>当前筛选: <strong>{{ filterTag }}</strong></span>
      <span class="filter-count">共 {{ total }} 幅</span>
      <el-button size="small" text @click="clearTagFilter">
        <el-icon><Close /></el-icon>
        清除
      </el-button>
    </div>
    <!-- 搜索模式指示条 -->
    <div v-if="isSearchMode" class="filter-indicator search-indicator">
      <span>搜索结果: <strong>{{ searchKeyword }}</strong></span>
      <span class="filter-count">共 {{ total }} 幅</span>
      <el-button size="small" text @click="clearSearch">
        <el-icon><Close /></el-icon>
        清除搜索
      </el-button>
    </div>

    <!-- 表格卡片 -->
    <div class="list-container">
      <div class="works-table-container" v-if="pagedRankings.length > 0">
        <div class="works-table">
          <div class="works-table-header">
            <div class="table-col col-image">图片</div>
            <div class="table-col col-info">作品信息</div>
            <div class="table-col col-author">作者</div>
            <div class="table-col col-age">年龄</div>
            <div class="table-col col-year sortable" :class="{ 'is-sorted': activeSort === 'year' }" @click="sortBy('year')">
              年代
              <el-icon v-if="activeSort === 'year'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" /><ArrowUp v-else />
              </el-icon>
            </div>
            <div class="table-col col-inscription sortable" :class="{ 'is-sorted': activeSort === 'inscription' }" @click="sortBy('inscription')">
              题跋%
              <el-icon v-if="activeSort === 'inscription'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" /><ArrowUp v-else />
              </el-icon>
            </div>
            <div class="table-col col-painting sortable" :class="{ 'is-sorted': activeSort === 'painting' }" @click="sortBy('painting')">
              绘画%
              <el-icon v-if="activeSort === 'painting'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" /><ArrowUp v-else />
              </el-icon>
            </div>
            <div class="table-col col-blank sortable" :class="{ 'is-sorted': activeSort === 'blank' }" @click="sortBy('blank')">
              留白%
              <el-icon v-if="activeSort === 'blank'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" /><ArrowUp v-else />
              </el-icon>
            </div>
            <div class="table-col col-created sortable" :class="{ 'is-sorted': activeSort === 'created' }" @click="sortBy('created')">
              创建时间
              <el-icon v-if="activeSort === 'created'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" /><ArrowUp v-else />
              </el-icon>
            </div>
            <div v-if="isAdmin" class="table-col col-action">操作</div>
          </div>
          <div class="works-table-body">
            <div
              v-for="(item, index) in pagedRankings"
              :key="item.id"
              class="works-table-row"
              @click="loadHistoryItem(item)"
              :data-row-id="item.id"
            >
              <div class="table-col col-image">
                <div class="work-thumbnail">
                  <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="thumbnail-img" @error="handleImageError">
                  <div v-else class="thumbnail-placeholder">
                    <el-icon size="24"><Picture /></el-icon>
                  </div>
                </div>
              </div>
              <div class="table-col col-info">
                <div class="work-title" @click.stop="openDetailInNewWindow(item)">{{ item.title || '未命名' }}</div>
                <div v-if="isSearchMode && item.matched_fields?.length" class="match-tags">
                  <el-tag v-for="field in item.matched_fields" :key="field" size="small" :type="matchTagType(field)" class="match-tag">
                    {{ matchFieldLabel(field) }}
                  </el-tag>
                </div>
              </div>
              <div class="table-col col-author">
                <span v-if="item.artist" class="author-name">{{ item.artist }}</span>
                <span v-else class="author-name">-</span>
              </div>
              <div class="table-col col-age">
                <span v-if="getDisplayAge(item) !== null" class="age-val">{{ getDisplayAge(item) }}岁</span>
                <span v-else class="age-val">-</span>
              </div>
              <div class="table-col col-year">
                <span v-if="item.year">{{ item.year }}年</span>
                <span v-else>-</span>
              </div>
              <div class="table-col col-inscription">
                <span class="stat-val">{{ item.inscriptionPercent?.toFixed(1) }}%</span>
              </div>
              <div class="table-col col-painting">
                <span class="stat-val">{{ item.paintingPercent?.toFixed(1) }}%</span>
              </div>
              <div class="table-col col-blank">
                <span class="stat-val">{{ item.blankPercent?.toFixed(1) }}%</span>
              </div>
              <div class="table-col col-created">
                <span class="date-val">{{ item.created_at ? item.created_at.slice(0, 10) : '-' }}</span>
              </div>
              <div v-if="isAdmin" class="table-col col-action">
                <div class="action-btn-wrap" @mouseenter="openActionMenu($event)" @mouseleave="closeActionMenu">
                  <button class="action-btn" @click.stop>
                    操作<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </button>
                  <div class="action-menu" v-show="activeActionItem === item.id">
                    <div class="action-menu-item" @click.stop="openDetailInNewWindow(item)">详情</div>
                    <template v-if="isAdmin">
                      <div class="action-menu-divider"></div>
                      <div class="action-menu-item" @click.stop="editItem(item)">编辑</div>
                      <div class="action-menu-divider"></div>
                      <div class="action-menu-item action-menu-danger" @click.stop="deleteItem(item)">删除</div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-if="rankings.length === 0" class="no-data">
        <el-icon size="48"><Picture /></el-icon>
        <p>暂无数据，请先上传画作</p>
        <el-button type="primary" @click="backToTubi">返回上传</el-button>
      </div>
    </div>

    <!-- 底部翻页 -->
    <div class="list-footer" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        layout="total, sizes, prev, pager, next"
          :page-sizes="[10, 20, 50, 100]"
          :pager-count="5"
        prev-text="← 上一页"
        next-text="下一页 →"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 编辑画作信息对话框 -->
    <TubiEditDialog
      ref="editDialogRef"
      @saved="onEditSaved"
      @deleted="onEditDeleted"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ArrowLeft, ArrowUp, ArrowDown, Picture, Search, Close } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { tubiApi } from '../api'
import TubiEditDialog from '../components/tubi/TubiEditDialog.vue'
import { useAdminAuth } from '../composables/useAdminAuth'

const router = useRouter()
const route = useRoute()

const { isAuthenticated: isAdmin, login, logout } = useAdminAuth()

// 排行榜数据
const rankings = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const activeSort = ref('inscription')
const sortDirection = ref('desc')

// 前端排序名 → API 字段名映射
const SORT_FIELD_MAP = {
  inscription: 'inscription_percent',
  painting: 'painting_percent',
  blank: 'blank_percent',
  year: 'year',
  created: 'created_at',
}
const searchKeyword = ref('')
const filterTag = ref(null) // 标签筛选
const isSearchMode = ref(false)
const activeActionItem = ref(null)

let actionMenuTimer = null
function openActionMenu(e) {
  if (actionMenuTimer) clearTimeout(actionMenuTimer)
  const row = e.currentTarget.closest('[data-row-id]')
  if (row) activeActionItem.value = row.dataset.rowId
}
function closeActionMenu() {
  actionMenuTimer = setTimeout(() => {
    activeActionItem.value = null
  }, 150)
}
const selectedArtist = ref('all')

// 画家列表（从 API 获取，只显示真实存在的画家）
const artistOptions = ref([])
async function fetchArtistList() {
  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE || '/api/v1'}/content-analysis/artists`)
    const data = await res.json()
    artistOptions.value = data.artists || []
  } catch (e) {
    console.error('获取画家列表失败', e)
  }
}

// 编辑对话框 ref
const editDialogRef = ref(null)

// 画家信息配置（出生年份用于年龄↔年份互算）
const ARTISTS = {
  '李鱓': { birth: 1686, death: 1756, defaultYear: 1725 },
  '郑燮': { birth: 1693, death: 1766, defaultYear: 1730 },
  '金农': { birth: 1687, death: 1763, defaultYear: 1720 },
  '黄慎': { birth: 1687, death: 1770, defaultYear: 1720 },
  '边寿民': { birth: 1684, death: 1752, defaultYear: 1720 },
  '刘海勇': { birth: 1976, death: null, defaultYear: 2020 },
}

// 解析 tags 字段（JSON数组或字符串数组）
function parseTags(tags) {
  if (!tags) return []
  if (Array.isArray(tags)) return tags
  try {
    const parsed = JSON.parse(tags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// 合并 computed_tags 和手动 tags
function getItemAllTags(item) {
  const auto = item.computed_tags || []
  const manual = parseTags(item.tags)
  const result = [...auto]
  for (const t of manual) {
    if (!result.includes(t)) result.push(t)
  }
  return result
}

// 清除标签筛选
function clearTagFilter() {
  filterTag.value = null
  loadRankings()
}

// 当前页数据（包含标签筛选）
const pagedRankings = computed(() => {
  let list = rankings.value
  // 标签筛选（仅当前页内）
  if (filterTag.value) {
    list = list.filter(item => getItemAllTags(item).includes(filterTag.value))
  }
  return list
})

// 总数量
const total = computed(() => {
  if (isSearchMode.value) return totalCount.value
  if (filterTag.value) {
    return rankings.value.filter(item => getItemAllTags(item).includes(filterTag.value)).length
  }
  return totalCount.value
})

// 搜索处理（服务端搜索）
async function handleSearch() {
  if (!searchKeyword.value.trim()) {
    clearSearch()
    return
  }
  isSearchMode.value = true
  currentPage.value = 1
  await loadSearchResults()
}

async function loadSearchResults() {
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const response = await tubiApi.searchImages(searchKeyword.value.trim(), skip, pageSize.value)
    if (response.success) {
      const works = (response.data || []).map(item => ({
        ...item,
        inscriptionPercent: item.inscription_percent,
        paintingPercent: item.painting_percent,
        blankPercent: item.blank_percent,
        thumbnailUrl: item.thumbnail_url,
        analysisNote: item.analysis_note,
      }))
      rankings.value = works
      totalCount.value = response.total || works.length
    } else {
      ElMessage.error(response.message || '搜索失败')
    }
  } catch (error) {
    console.error('搜索失败:', error)
    ElMessage.error('搜索失败: ' + (error.message || '网络错误'))
  }
}

function clearSearch() {
  searchKeyword.value = ''
  isSearchMode.value = false
  currentPage.value = 1
  loadRankings()
  syncPageToUrl()
}

// 在新窗口打开详情
function openDetailInNewWindow(item) {
  const url = router.resolve({
    name: 'TubiDetail',
    params: { id: item.id }
  }).href
  window.open(url, '_blank')
}

// 加载历史记录项（保留用于兼容性）
async function loadHistoryItem(item) {
  openDetailInNewWindow(item)
}

// 处理图片加载错误
function handleImageError(e) {
  e.target.src = ''
  e.target.style.display = 'none'
  const placeholder = e.target.nextElementSibling
  if (placeholder) {
    placeholder.style.display = 'flex'
  }
}

// 返回题跋分析页面
function backToTubi() {
  router.push('/tubi')
}

// 根据画家和年份计算年龄
function calculateAge(year, artistName) {
  if (!year || isNaN(parseInt(year))) return null
  const artist = ARTISTS[artistName]
  if (!artist) return null
  return parseInt(year) - artist.birth
}

// 根据画家和年龄计算年份
function calculateYear(age, artistName) {
  if (!age || isNaN(parseInt(age))) return null
  const artist = ARTISTS[artistName]
  if (!artist) return null
  return artist.birth + parseInt(age)
}

function getDisplayAge(item) {
  if (!item) return null
  const computed = calculateAge(item.year, item.artist)
  if (computed !== null && computed !== undefined && !isNaN(computed)) {
    if (computed >= -50 && computed <= 150) return computed
  }
  const raw = item.age ?? item.period
  if (raw === null || raw === undefined) return null
  const m = String(raw).match(/\d+/)
  if (!m) return null
  const parsed = parseInt(m[0])
  if (isNaN(parsed)) return null
  return parsed
}

// 编辑作品
function editItem(item) {
  editDialogRef.value.open(item)
}

// 编辑保存事件处理
function onEditSaved() {
  loadRankings()
}

// 编辑删除事件处理
function onEditDeleted() {
  loadRankings()
}

// 操作下拉菜单
function handleAction(cmd, item) {
  if (cmd === 'detail') openDetailInNewWindow(item)
  else if (cmd === 'edit') editItem(item)
  else if (cmd === 'delete') deleteItem(item)
}

// 删除作品
async function deleteItem(item) {
  try {
    await ElMessageBox.confirm(`确定要删除「${item.title || '未命名'}」吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await tubiApi.deleteImage(item.id)
    if (response.success) {
      ElMessage.success('删除成功')
      // 刷新排行榜数据
      await loadRankings()
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 管理权限切换
async function toggleAdmin() {
  if (isAdmin.value) {
    logout()
    return
  }
  try {
    const pwd = await ElMessageBox.prompt('请输入管理密码', '管理验证', {
      inputType: 'password',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      closeOnClickModal: false,
    })
    if (login(pwd.value)) {
      ElMessage.success('管理验证通过')
    } else {
      ElMessage.error('密码错误')
    }
  } catch { /* 用户取消 */ }
}

// 同步页码到 URL
function syncPageToUrl() {
  const query = { ...route.query }
  if (currentPage.value > 1) query.page = String(currentPage.value)
  else delete query.page
  if (pageSize.value !== 20) query.size = String(pageSize.value)
  else delete query.size
  router.replace({ name: 'TubiList', query })
}

// 分页处理
function handleSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  if (isSearchMode.value) loadSearchResults()
  else loadRankings()
  syncPageToUrl()
}

function handleCurrentChange(current) {
  currentPage.value = current
  if (isSearchMode.value) loadSearchResults()
  else loadRankings()
  syncPageToUrl()
}

// 画家筛选
function onArtistChange() {
  isSearchMode.value = false
  searchKeyword.value = ''
  currentPage.value = 1
  loadRankings()
  syncPageToUrl()
}

// 排序处理
function sortBy(sortType) {
  if (activeSort.value === sortType) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    activeSort.value = sortType
    sortDirection.value = 'desc'
  }
  currentPage.value = 1
  loadRankings()
  syncPageToUrl()
}

// 匹配字段标签显示
function matchFieldLabel(field) {
  const labels = {
    title: '作品名',
    artist: '作者',
    inscription_content: '题跋',
    inscription_modern: '题跋(白话)',
    seal_content: '印章',
    notes: '备注',
    analysis_note: 'AI分析',
    year: '年代',
  }
  return labels[field] || field
}
function matchTagType(field) {
  const types = {
    title: '',
    inscription_content: 'success',
    inscription_modern: 'success',
    seal_content: 'warning',
    artist: 'info',
    year: 'info',
  }
  return types[field] || 'info'
}

// 排序已改为服务端排序（`loadRankings()` 传 sort_by/sort_dir 给 API）

// 总作品数（来自 API 的 total 字段）
const totalCount = ref(0)

// 加载列表数据
async function loadRankings() {
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const artistParam = selectedArtist.value !== 'all' ? selectedArtist.value : undefined
    const sortField = SORT_FIELD_MAP[activeSort.value]
    const response = await tubiApi.getAllResults(skip, pageSize.value, artistParam, sortField, sortDirection.value)
    if (response.success) {
      // 转换字段名
      const works = (response.data || []).map(item => ({
        ...item,
        inscriptionPercent: item.inscription_percent,
        paintingPercent: item.painting_percent,
        blankPercent: item.blank_percent,
        annotatedImageUrl: item.annotated_image_url,
        thumbnailUrl: item.thumbnail_url,
        analysisNote: item.analysis_note,
        created_at: item.created_at,
        updated_at: item.updated_at
      }))

      rankings.value = works
      totalCount.value = response.total || works.length
    } else {
      ElMessage.error(response.message || '加载列表失败')
    }
  } catch (error) {
    console.error('加载列表失败:', error)
    ElMessage.error('加载失败')
  }
}

// 页面挂载时加载数据
onMounted(() => {
  // 检查 URL 参数中的 tag、artist、page
  const tagFromQuery = route.query.tag
  if (tagFromQuery) {
    filterTag.value = decodeURIComponent(tagFromQuery)
  }
  const artistFromQuery = route.query.artist
  if (artistFromQuery && typeof artistFromQuery === 'string') {
    selectedArtist.value = artistFromQuery
  }
  const pageFromQuery = route.query.page
  if (pageFromQuery) {
    const p = parseInt(pageFromQuery, 10)
    if (p > 1) currentPage.value = p
  }
  const sizeFromQuery = route.query.size
  if (sizeFromQuery) {
    const s = parseInt(sizeFromQuery, 10)
    if ([10, 20, 50, 100].includes(s)) pageSize.value = s
  }
  fetchArtistList()
  loadRankings()
})
</script>

<style scoped>
.tubi-list {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

/* 页面头部 */
.tubi-header {
  text-align: center;
  margin-bottom: 32px;
}

.tubi-header h1 {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 28px;
  color: var(--near-black);
  font-weight: 500;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

.tubi-header .sub {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--stone-gray);
  letter-spacing: 0.04em;
  margin-bottom: 16px;
}

.header-ornament {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}

.ornament-line {
  width: 60px;
  height: 1px;
  background: var(--border-warm);
}

.ornament-dot {
  color: var(--cinnabar);
  font-size: 14px;
}

.list-container {
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-lg);
  background: var(--pure-white);
  overflow: hidden;
}

/* 标签筛选指示器 */
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
.search-indicator {
  background: linear-gradient(180deg, #eaf7ea 0%, #e2f0e2 100%) !important;
}

.sort-icon {
  margin-left: 2px;
  font-size: 11px;
  transition: transform 0.3s ease;
}

.search-box {
  display: flex;
  gap: 6px;
  align-items: center;
}

/* 作品表格 */
.works-table-container {
  margin: 20px 0;
}

.works-table {
  width: 100%;
  background: var(--pure-white);
}
.top-bar .el-pagination {
  --el-pagination-button-width: 32px;
  --el-pagination-button-height: 32px;
  font-size: 13px;
  flex-wrap: nowrap;
}
.top-bar :deep(.el-pagination__sizes) {
  margin-right: 4px;
}
.top-bar :deep(.el-pagination__sizes .el-select .el-input) {
  width: 90px !important;
}
.top-bar .el-pagination .el-pagination__total {
  font-size: 12px;
  color: var(--stone-gray);
  margin-right: 8px;
  line-height: 32px;
}
.top-bar :deep(.el-pagination .btn-prev),
.top-bar :deep(.el-pagination .btn-next) {
  height: 32px !important;
  min-width: 32px;
  padding: 0 6px !important;
  font-size: 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent !important;
  line-height: 32px !important;
}
.top-bar :deep(.el-pagination .el-pager li) {
  height: 32px !important;
  min-width: 32px;
  line-height: 32px !important;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
}
.top-bar :deep(.el-pagination .el-pager li.active) {
  background: var(--cinnabar);
  color: #fff;
}

.works-table-header {
  display: flex;
  background: var(--pure-white);
  border-bottom: 1px solid var(--border-cream);
  padding: 0 16px;
  font-weight: 600;
  color: var(--olive-gray);
  font-size: 11px;
  font-family: var(--font-sans);
  letter-spacing: 0.03em;
  user-select: none;
}

.works-table-header .table-col {
  padding: 6px 6px 10px;
}

.table-col.sortable {
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.table-col.sortable:hover {
  background: rgba(0,0,0,0.03);
  color: var(--near-black);
}
.table-col.sortable.is-sorted {
  color: var(--cinnabar);
}

.works-table-row {
  display: flex;
  border-bottom: 1px solid var(--border-cream);
  padding: 10px 16px;
  transition: background var(--transition-fast);
  cursor: pointer;
  align-items: center;
}
.works-table-row:last-child {
  border-bottom: none;
}
.works-table-row:hover {
  background: var(--ivory);
}

.stat-val {
  font-size: 13px;
  font-weight: 600;
  color: var(--charcoal-warm);
  font-family: var(--font-sans);
}

.date-val {
  font-size: 11px;
  color: var(--stone-gray);
  font-family: var(--font-sans);
}

.works-table-body {
  display: flex;
  flex-direction: column;
}

.works-table-row {
  display: flex;
  border-bottom: 1px solid var(--border-cream);
  padding: 16px;
  transition: all var(--transition-normal);
  cursor: pointer;
}

.works-table-row:hover {
  background: var(--parchment);
  box-shadow: var(--shadow-whisper);
}

.table-col {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--charcoal-warm);
  font-family: var(--font-sans);
}

.col-image {
  width: 80px;
  flex-shrink: 0;
}

.col-info {
  flex: 1;
  min-width: 0;
  padding: 0 12px;
  font-size: 13px;
}

.col-author {
  width: 60px;
  flex-shrink: 0;
  padding: 0 6px;
  font-size: 12px;
}
.author-name {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-weight: 500;
}

.col-age {
  width: 50px;
  flex-shrink: 0;
  justify-content: center;
  font-size: 11px;
}
.age-val {
  color: var(--stone-gray);
}

.col-year {
  width: 70px;
  flex-shrink: 0;
  justify-content: center;
}

.col-inscription {
  width: 70px;
  flex-shrink: 0;
  justify-content: center;
}

.col-painting {
  width: 70px;
  flex-shrink: 0;
  justify-content: center;
}

.col-blank {
  width: 70px;
  flex-shrink: 0;
  justify-content: center;
}

.col-created {
  width: 90px;
  flex-shrink: 0;
  justify-content: center;
}

.col-action {
  width: 100px;
  flex-shrink: 0;
  justify-content: center;
}
.col-action {
  position: relative;
}
.action-btn-wrap {
  position: relative;
  display: inline-flex;
  padding-bottom: 6px;
  margin-bottom: -6px;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  background: var(--cinnabar);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 12px;
  cursor: pointer;
  transition: background var(--transition-fast);
  white-space: nowrap;
  font-family: var(--font-sans);
  line-height: 1.4;
}
.action-btn:hover {
  background: var(--cinnabar-light);
}
.action-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 2px;
  width: 100%;
  background: #fff;
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-elevated);
  z-index: 1000;
  padding: 4px 0;
}
.action-menu-item {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--charcoal-warm);
  cursor: pointer;
  text-align: center;
  transition: background var(--transition-fast);
  font-family: var(--font-sans);
}
.action-menu-item:hover {
  background: var(--ivory);
}
.action-menu-item:first-child {
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}
.action-menu-item:last-child {
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}
.action-menu-danger {
  color: var(--error-crimson) !important;
}
.action-menu-divider {
  height: 1px;
  background: var(--border-cream);
  margin: 4px 0;
}

/* 作品缩略图 */
.work-thumbnail {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--parchment);
  border: 1px solid var(--border-warm);
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cinnabar);
  background: var(--parchment);
}

/* 作品信息 */
.work-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--near-black);
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}

.work-title:hover {
  color: var(--cinnabar);
}

.match-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.match-tag {
  font-size: 10px !important;
  padding: 0 5px !important;
  height: 18px !important;
  line-height: 18px !important;
}

/* 作品统计 */
.work-stats {
  display: flex;
  flex-direction: row;
  gap: 6px;
  flex-wrap: wrap;
}

/* 底部栏：翻页居左、工具居右 */
/* 顶部栏：翻页居左 + 工具居右 */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0 12px;
  gap: 12px;
  flex-wrap: nowrap;
}
.top-bar-left {
  flex-shrink: 0;
}
.top-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.top-bar-right .el-button {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
}
.top-bar-right :deep(.el-select__wrapper),
.top-bar-right :deep(.el-input__wrapper) {
  box-shadow: none !important;
  border: 1px solid var(--border-warm) !important;
  border-radius: var(--radius-md) !important;
  min-height: 28px !important;
}
.top-bar-right :deep(.el-select__wrapper:hover),
.top-bar-right :deep(.el-input__wrapper:hover) {
  border-color: var(--ring-deep) !important;
}
.top-bar-right :deep(.el-input__inner) {
  font-size: 12px !important;
}

/* 底部翻页 */
.list-footer {
  display: flex;
  justify-content: flex-start;
  padding: 12px 0;
}
.list-footer .el-pagination {
  --el-pagination-button-width: 36px;
  --el-pagination-button-height: 36px;
  font-size: 14px;
  font-family: var(--font-sans);
  font-weight: 500;
}
.list-footer .el-pagination .el-pagination__total {
  font-size: 13px;
  color: var(--stone-gray);
  margin-right: 12px;
  line-height: 36px;
}
.list-footer :deep(.el-pagination .btn-prev),
.list-footer :deep(.el-pagination .btn-next) {
  border: none;
  border-radius: var(--radius-md);
  background: transparent !important;
  min-width: 36px;
  height: 36px !important;
  padding: 0 10px !important;
  font-size: 13px;
  font-weight: 400;
  line-height: 36px !important;
}
.list-footer :deep(.el-pagination .btn-prev:hover),
.list-footer :deep(.el-pagination .btn-next:hover) {
  color: var(--cinnabar);
}
.list-footer :deep(.el-pagination .el-pager li) {
  border-radius: var(--radius-md);
  min-width: 36px;
  height: 36px !important;
  line-height: 36px !important;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
}
.list-footer :deep(.el-pagination .el-pager li:hover) {
  border-color: var(--border-warm);
  color: var(--cinnabar);
  background: var(--ivory);
}
.list-footer :deep(.el-pagination .el-pager li.active) {
  background: var(--cinnabar);
  color: #fff;
  font-weight: 600;
  border-color: var(--cinnabar);
}

/* 无数据提示 */
.no-data {
  text-align: center;
  padding: 60px 20px;
  color: var(--stone-gray);
  background: var(--ivory);
  border-radius: var(--radius-lg);
  margin-top: 20px;
  border: 1px solid var(--border-cream);
}

.no-data el-icon {
  margin-bottom: 16px;
  font-size: 48px;
  color: var(--cinnabar);
}

.no-data p {
  font-size: 15px;
  margin: 0 0 16px 0;
  color: var(--charcoal-warm);
  font-family: var(--font-sans);
}

/* 按钮垂直居中 */
.col-action .el-button {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
  border-radius: var(--radius-md) !important;
}

/* 表单样式 */
.form-section {
  padding: 20px;
  background: var(--ivory);
  border-bottom: 1px solid var(--border-cream);
}

.form-section:last-child {
  border-bottom: none;
}

.form-section-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 15px;
  color: var(--near-black);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-cream);
  position: relative;
}

.form-section-title::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 40px;
  height: 2px;
  background: var(--cinnabar);
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-item-half {
  flex: 1;
}

.modern-form .el-form-item {
  margin-bottom: 16px;
}

.modern-textarea .el-textarea__inner {
  font-family: var(--font-sans);
  border-radius: var(--radius-md);
  border-color: var(--border-warm);
  resize: vertical;
}

.modern-textarea .el-textarea__inner:focus {
  border-color: var(--cinnabar);
  box-shadow: 0 0 0 3px rgba(201, 100, 66, 0.1);
}

/* 按钮样式 */
.btn-cancel {
  background: var(--pure-white) !important;
  color: var(--charcoal-warm) !important;
  border: 1px solid var(--border-warm) !important;
  border-radius: var(--radius-md) !important;
}

.btn-cancel:hover {
  border-color: var(--cinnabar) !important;
  color: var(--cinnabar) !important;
}

.btn-delete {
  background: var(--error-crimson) !important;
  border-color: var(--error-crimson) !important;
  color: var(--pure-white) !important;
  border-radius: var(--radius-md) !important;
}

.btn-submit {
  background: var(--cinnabar) !important;
  border-color: var(--cinnabar) !important;
  color: var(--pure-white) !important;
  border-radius: var(--radius-md) !important;
}

.btn-submit:hover {
  background: var(--cinnabar-dark) !important;
  border-color: var(--cinnabar-dark) !important;
}

/* 弹窗 footer */
.modern-footer {
  border-top: 1px solid var(--border-cream);
  padding: 16px 20px !important;
  background: var(--ivory);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .col-age, .col-inscription, .col-painting, .col-blank {
    width: 55px;
    font-size: 10px;
  }
  .col-created {
    width: 75px;
    font-size: 10px;
  }
}

@media (max-width: 768px) {
  .top-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .top-bar-right {
    flex-wrap: wrap;
    gap: 6px;
  }
  .top-bar-left :deep(.el-pagination__sizes),
  .top-bar-left :deep(.el-pager) {
    display: none !important;
  }
  .top-bar-left :deep(.el-pagination) {
    flex-wrap: nowrap;
  }

  .works-table-container {
    overflow-x: auto;
  }
  .works-table {
    min-width: 820px;
  }

  .col-action .el-button,
  .col-action .el-dropdown .el-button {
    padding: 4px 8px !important;
    font-size: 11px !important;
  }
}
</style>
