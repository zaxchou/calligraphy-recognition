<template>
  <div class="tubi-ranking tubi-page">
    <!-- 页面标题 -->
    <div class="tubi-header">
      <h1>作品列表</h1>
      <p class="sub">多维度作品排序与筛选</p>
      <div class="header-ornament">
        <span class="ornament-line"></span>
        <span class="ornament-dot">◇</span>
        <span class="ornament-line"></span>
      </div>
    </div>

    <!-- 作品表格 -->
    <el-card shadow="hover" class="ranking-list-card">
      <!-- 标签筛选指示条 -->
      <div v-if="filterTag" class="filter-indicator">
        <span>当前筛选: <strong>{{ filterTag }}</strong></span>
        <span class="filter-count">共 {{ total }} 幅</span>
        <el-button size="small" text @click="clearTagFilter">
          <el-icon><Close /></el-icon>
          清除
        </el-button>
      </div>
      <template #header>
        <div class="card-header">
          <div class="header-nav">
            <el-button 
              :type="activeSort === 'inscription' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('inscription')"
            >
              题跋比
              <el-icon v-if="activeSort === 'inscription'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
            <el-button 
              :type="activeSort === 'painting' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('painting')"
            >
              绘画比
              <el-icon v-if="activeSort === 'painting'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
            <el-button 
              :type="activeSort === 'blank' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('blank')"
            >
              留白比
              <el-icon v-if="activeSort === 'blank'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
            <el-button 
              :type="activeSort === 'year' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('year')"
            >
              年代
              <el-icon v-if="activeSort === 'year'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
            <el-button 
              :type="activeSort === 'created' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('created')"
            >
              创建时间
              <el-icon v-if="activeSort === 'created'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
            <el-button 
              :type="activeSort === 'updated' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('updated')"
            >
              更新时间
              <el-icon v-if="activeSort === 'updated'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
          </div>
          <div class="header-actions">
            <div class="search-box">
              <el-input 
                v-model="searchKeyword" 
                placeholder="搜索标题、作者、年代..." 
                size="small" 
                style="width: 200px"
                clearable
                @keyup.enter="handleSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <el-button type="primary" size="small" @click="handleSearch" :icon="Search">
                搜索
              </el-button>
            </div>
            <el-tag type="info" size="small">共 {{ total }} 幅作品</el-tag>
            <el-button type="primary" size="small" @click="backToTubi" :icon="ArrowLeft">
              返回题跋分析
            </el-button>
          </div>
        </div>
      </template>

      <!-- 作品表格 -->
      <div class="works-table-container" v-if="pagedRankings.length > 0">
        <div class="works-table">
          <div class="works-table-header">
            <div class="table-col col-image">图片</div>
            <div class="table-col col-info">作品信息</div>
            <div class="table-col col-author">作者</div>
            <div class="table-col col-year">年代</div>
            <div class="table-col col-stats">占比数据</div>
            <div class="table-col col-action">操作</div>
          </div>
          <div class="works-table-body">
            <div 
              v-for="(item, index) in pagedRankings" 
              :key="item.id"
              class="works-table-row"
              @click="loadHistoryItem(item)"
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
              </div>
              <div class="table-col col-author">
                <span v-if="item.artist">{{ item.artist }}{{ getDisplayAge(item) !== null ? ` ${getDisplayAge(item)}岁` : '' }}</span>
                <span v-else>-</span>
              </div>
              <div class="table-col col-year">
                <span v-if="item.year">{{ item.year }}年</span>
                <span v-else>-</span>
              </div>
              <div class="table-col col-stats">
                <div class="work-stats">
                  <el-tag size="small" type="primary">题跋 {{ item.inscriptionPercent?.toFixed(1) }}%</el-tag>
                  <el-tag size="small" type="success">绘画 {{ item.paintingPercent?.toFixed(1) }}%</el-tag>
                  <el-tag size="small" type="info">留白 {{ item.blankPercent?.toFixed(1) }}%</el-tag>
                </div>
              </div>
              <div class="table-col col-action">
                <el-button type="primary" size="small" @click.stop="openDetailInNewWindow(item)">
                  详情
                </el-button>
                <el-button type="warning" size="small" @click.stop="editItem(item)">
                  编辑
                </el-button>
                <el-button type="danger" size="small" @click.stop="deleteItem(item)">
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination-container" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>

      <!-- 无数据提示 -->
      <div v-if="rankings.length === 0" class="no-data">
        <el-icon size="48"><Picture /></el-icon>
        <p>暂无数据，请先上传画作</p>
        <el-button type="primary" @click="backToTubi">返回上传</el-button>
      </div>
    </el-card>

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

const router = useRouter()
const route = useRoute()

// 排行榜数据
const rankings = ref([])
const allRankings = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const activeSort = ref('inscription') // inscription, painting, blank, year, created, updated
const sortDirection = ref('asc') // asc, desc
const searchKeyword = ref('')
const filterTag = ref(null) // 标签筛选

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
  handleSearch() // 重新应用搜索和排序
}

// 分页数据（包含标签筛选）
const pagedRankings = computed(() => {
  let list = rankings.value
  
  // 标签筛选
  if (filterTag.value) {
    list = list.filter(item => getItemAllTags(item).includes(filterTag.value))
  }
  
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return list.slice(start, end)
})

// 总数量（包含标签筛选）
const total = computed(() => {
  let list = rankings.value
  if (filterTag.value) {
    list = list.filter(item => getItemAllTags(item).includes(filterTag.value))
  }
  return list.length
})

// 搜索处理
function handleSearch() {
  if (!searchKeyword.value.trim()) {
    rankings.value = [...allRankings.value]
  } else {
    const keyword = searchKeyword.value.trim().toLowerCase()
    rankings.value = allRankings.value.filter(item => {
      return (
        (item.title && item.title.toLowerCase().includes(keyword)) ||
        (item.artist && item.artist.toLowerCase().includes(keyword)) ||
        (item.year && String(item.year).includes(keyword)) ||
        (item.notes && item.notes.toLowerCase().includes(keyword)) ||
        (item.analysisNote && item.analysisNote.toLowerCase().includes(keyword))
      )
    })
  }
  currentPage.value = 1
  sortRankings()
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

// 分页处理
function handleSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
}

function handleCurrentChange(current) {
  currentPage.value = current
}

// 排序处理
function sortBy(sortType) {
  if (activeSort.value === sortType) {
    // 切换排序方向
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    // 新的排序类型，默认使用倒序
    activeSort.value = sortType
    sortDirection.value = 'desc'
  }
  sortRankings()
}

// 排序函数
function sortRankings() {
  const direction = sortDirection.value === 'asc' ? 1 : -1
  
  if (activeSort.value === 'inscription') {
    rankings.value.sort((a, b) => ((b.inscriptionPercent || 0) - (a.inscriptionPercent || 0)) * direction)
  } else if (activeSort.value === 'painting') {
    rankings.value.sort((a, b) => ((b.paintingPercent || 0) - (a.paintingPercent || 0)) * direction)
  } else if (activeSort.value === 'blank') {
    rankings.value.sort((a, b) => ((b.blankPercent || 0) - (a.blankPercent || 0)) * direction)
  } else if (activeSort.value === 'year') {
    rankings.value.sort((a, b) => {
      const yearA = parseInt(a.year) || 0
      const yearB = parseInt(b.year) || 0
      return (yearB - yearA) * direction
    })
  } else if (activeSort.value === 'created') {
    rankings.value.sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0
      return (dateB - dateA) * direction
    })
  } else if (activeSort.value === 'updated') {
    rankings.value.sort((a, b) => {
      const dateA = a.updated_at ? new Date(a.updated_at).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0)
      const dateB = b.updated_at ? new Date(b.updated_at).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0)
      return (dateB - dateA) * direction
    })
  }
  currentPage.value = 1 // 重置到第一页
}

// 加载排行榜数据
async function loadRankings() {
  try {
    const response = await tubiApi.getAllResults()
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

      // 保存所有数据（用于搜索）
      allRankings.value = works
      rankings.value = works
      sortRankings() // 应用当前排序
    } else {
      ElMessage.error(response.message || '加载排行榜失败')
    }
  } catch (error) {
    console.error('加载排行榜失败:', error)
    ElMessage.error('加载失败')
  }
}

// 页面挂载时加载数据
onMounted(() => {
  // 检查 URL 参数中的 tag
  const tagFromQuery = route.query.tag
  if (tagFromQuery) {
    filterTag.value = decodeURIComponent(tagFromQuery)
  }
  loadRankings()
})
</script>

<style scoped>
.tubi-ranking {
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
  font-family: var(--font-serif);
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

.ranking-list-card {
  margin-bottom: 20px;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-nav {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.header-nav .el-button,
.header-actions .el-button {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
}

.sort-icon {
  margin-left: 4px;
  font-size: 12px;
  transition: transform 0.3s ease;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-box {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 作品表格 */
.works-table-container {
  margin: 20px 0;
}

.works-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--pure-white);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-whisper);
  border: 1px solid var(--border-cream);
}

.works-table-header {
  display: flex;
  background: var(--ivory);
  border-bottom: 1px solid var(--border-cream);
  padding: 12px 16px;
  font-weight: 500;
  color: var(--charcoal-warm);
  font-size: 12px;
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
  width: 100px;
  flex-shrink: 0;
}

.col-info {
  flex: 1;
  min-width: 0;
  padding: 0 16px;
  font-size: 14px;
}

.col-author {
  width: 100px;
  flex-shrink: 0;
  padding: 0 16px;
}

.col-year {
  width: 100px;
  flex-shrink: 0;
  padding: 0 16px;
}

.col-stats {
  width: 320px;
  flex-shrink: 0;
  padding: 0 16px;
}

.col-action {
  width: 240px;
  flex-shrink: 0;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
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

/* 作品统计 */
.work-stats {
  display: flex;
  flex-direction: row;
  gap: 6px;
  flex-wrap: wrap;
}

/* 分页 */
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 24px;
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
  font-family: var(--font-serif);
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
@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .header-nav {
    width: 100%;
    justify-content: space-between;
  }
  
  .header-actions {
    width: 100%;
    justify-content: space-between;
  }
  
  .works-table-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .table-col {
    width: 100%;
    justify-content: flex-start;
    padding: 0;
  }
  
  .col-image {
    width: 100%;
  }
  
  .col-info {
    padding: 0;
  }
  
  .col-author {
    width: 100%;
    padding: 0;
  }
  
  .col-year {
    width: 100%;
    padding: 0;
  }
  
  .col-stats {
    width: 100%;
    padding: 0;
  }
  
  .col-action {
    width: 100%;
    justify-content: flex-start;
    gap: 8px;
  }
  
  .work-stats {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
