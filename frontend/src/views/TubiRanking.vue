<template>
  <div class="tubi-ranking">
    <h1 class="page-title">作品列表</h1>
    <p class="page-subtitle">按题画比、题跋比或绘画比排序的作品列表</p>

    <!-- 作品表格 -->
    <el-card shadow="hover" class="ranking-list-card">
      <template #header>
        <div class="card-header">
          <div class="header-nav">
            <el-button 
              :type="activeSort === 'tubi' ? 'primary' : 'default'" 
              size="small" 
              @click="sortBy('tubi')"
            >
              题画比
              <el-icon v-if="activeSort === 'tubi'" class="sort-icon">
                <ArrowDown v-if="sortDirection === 'desc'" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
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
          </div>
          <div class="header-actions">
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
                <div class="work-title">{{ item.title || '未命名' }}</div>
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
                  <el-tag size="small" type="success" v-if="item.paintingPercent !== undefined">绘画 {{ item.paintingPercent?.toFixed(1) }}%</el-tag>
                  <el-tag size="small" type="info" v-if="item.tubiRatio !== undefined">题画比 {{ item.tubiRatio.toFixed(2) }}</el-tag>
                </div>
              </div>
              <div class="table-col col-action">
                <el-button type="primary" size="small" @click.stop="loadHistoryItem(item)">
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
    <el-dialog
      v-model="editDialogVisible"
      title="编辑画作信息"
      width="600px"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
      modal
      class="modern-form-dialog"
    >
      <div class="form-section">
        <h4 class="form-section-title">基本信息</h4>
        <el-form :model="editForm" label-position="top" class="modern-form">
          <div class="form-row">
            <el-form-item label="画作标题" class="form-item-half">
              <el-input v-model="editForm.title" placeholder="请输入画作标题" />
            </el-form-item>
            <el-form-item label="作者姓名" class="form-item-half">
              <el-select v-model="editForm.artist" placeholder="请选择作者" style="width: 100%" @change="onEditArtistChange">
                <el-option label="李鱓" value="李鱓" />
                <el-option label="郑燮" value="郑燮" />
              </el-select>
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="创作年代" class="form-item-half">
              <el-input v-model.number="editForm.year" placeholder="如：1725" @change="onEditYearChange" />
            </el-form-item>
            <el-form-item label="作者年龄" class="form-item-half">
              <el-input v-model.number="editForm.age" placeholder="如：39" @change="onEditAgeChange">
                <template #append>岁</template>
              </el-input>
            </el-form-item>
          </div>
        </el-form>
      </div>

      <div class="form-section">
        <h4 class="form-section-title">区域占比数据 (%)</h4>
        <el-form :model="editForm" label-position="top" class="modern-form">
          <div class="form-row">
            <el-form-item label="题跋区域" class="form-item-third">
              <el-input-number 
                v-model="editForm.inscriptionPercent" 
                :min="0" 
                :max="100" 
                :precision="1"
                placeholder="0.0"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="绘画区域" class="form-item-third">
              <el-input-number 
                v-model="editForm.paintingPercent" 
                :min="0" 
                :max="100" 
                :precision="1"
                placeholder="0.0"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="留白区域" class="form-item-third">
              <el-input-number 
                v-model="editForm.blankPercent" 
                :min="0" 
                :max="100" 
                :precision="1"
                placeholder="0.0"
                style="width: 100%"
              />
            </el-form-item>
          </div>
        </el-form>
      </div>

      <div class="form-section">
        <h4 class="form-section-title">分析说明</h4>
        <el-form :model="editForm" label-position="top" class="modern-form">
          <el-form-item label="AI分析说明">
            <el-input 
              v-model="editForm.analysisNote" 
              type="textarea" 
              :rows="4" 
              placeholder="请输入AI分析说明内容"
              class="modern-textarea"
            />
          </el-form-item>
          <el-form-item label="备注信息">
            <el-input 
              v-model="editForm.notes" 
              type="textarea" 
              :rows="3" 
              placeholder="请输入备注信息"
              class="modern-textarea"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer modern-footer">
          <el-button @click="editDialogVisible = false" class="btn-cancel">取消</el-button>
          <el-button type="primary" @click="saveEdit" class="btn-submit">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ArrowLeft, ArrowUp, ArrowDown, Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { tubiApi } from '../api'

const router = useRouter()

// 排行榜数据
const rankings = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const activeSort = ref('tubi') // tubi, inscription, painting, year
const sortDirection = ref('desc') // asc, desc

// 编辑对话框
const editDialogVisible = ref(false)

// 编辑表单
const editForm = reactive({
  id: '',
  title: '',
  artist: '',
  year: '',
  age: '',
  notes: '',
  analysisNote: '',
  inscriptionPercent: 0,
  paintingPercent: 0,
  blankPercent: 0
})

// 画家信息配置
const ARTISTS = {
  '李鱓': { birth: 1686, death: 1756, defaultYear: 1725 },
  '郑燮': { birth: 1693, death: 1766, defaultYear: 1730 }
}

// 计算总数量
const total = computed(() => {
  return rankings.value.length
})

// 分页数据
const pagedRankings = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return rankings.value.slice(start, end)
})

// 加载历史记录项
async function loadHistoryItem(item) {
  try {
    const response = await tubiApi.getAnalysisResult(item.id)
    if (response.success) {
      const data = response.data

      // 创建图片对象
      const historyImage = {
        id: data.id,
        name: data.name || '历史记录',
        url: data.url,
        thumbnailUrl: data.thumbnail_url || data.url,
        width: data.width,
        height: data.height,
        title: data.title,
        artist: data.artist,
        year: data.year,
        period: data.period,
        inscriptionPercent: data.inscription_percent,
        paintingPercent: data.painting_percent,
        blankPercent: data.blank_percent,
        regions: data.regions,
        positionAnalysis: data.position_analysis,
        annotatedImageUrl: data.annotated_image_url,
        analysisNote: data.analysis_note
      }

      // 导航到题跋分析页面并传递参数
      router.push({
        path: '/tubi',
        query: { id: item.id }
      })
    } else {
      ElMessage.error(response.message || '加载失败')
    }
  } catch (error) {
    console.error('加载历史记录项失败:', error)
    ElMessage.error('加载失败')
  }
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

// 编辑表单：作者变化时更新年份和年龄
function onEditArtistChange(artist) {
  const artistInfo = ARTISTS[artist]
  if (artistInfo) {
    editForm.year = artistInfo.defaultYear
    editForm.age = calculateAge(artistInfo.defaultYear, artist)
  }
}

// 编辑表单：年份变化时自动计算年龄
function onEditYearChange(year) {
  if (year && !isNaN(parseInt(year))) {
    editForm.age = calculateAge(year, editForm.artist)
  }
}

// 编辑表单：年龄变化时自动计算年份
function onEditAgeChange(age) {
  if (age && !isNaN(parseInt(age))) {
    editForm.year = calculateYear(age, editForm.artist)
  }
}

// 编辑作品
function editItem(item) {
  editForm.id = item.id
  editForm.title = item.title || ''
  editForm.artist = item.artist || ''
  editForm.year = item.year || ''
  editForm.age = getDisplayAge(item) ?? ''
  editForm.notes = item.notes || ''
  editForm.analysisNote = item.analysisNote || item.analysis_note || ''
  editForm.inscriptionPercent = item.inscriptionPercent || item.inscription_percent || 0
  editForm.paintingPercent = item.paintingPercent || item.painting_percent || 0
  editForm.blankPercent = item.blankPercent || item.blank_percent || 0
  editDialogVisible.value = true
}

// 保存编辑
async function saveEdit() {
  try {
    const response = await tubiApi.updateImageInfo(editForm.id, {
      title: editForm.title,
      artist: editForm.artist,
      year: editForm.year ? parseInt(editForm.year) : null,
      age: editForm.age ? parseInt(editForm.age) : null,
      notes: editForm.notes,
      analysis_note: editForm.analysisNote,
      inscription_percent: parseFloat(editForm.inscriptionPercent) || 0,
      painting_percent: parseFloat(editForm.paintingPercent) || 0,
      blank_percent: parseFloat(editForm.blankPercent) || 0
    })

    if (response.success) {
      ElMessage.success('保存成功')
      editDialogVisible.value = false
      // 刷新排行榜数据
      await loadRankings()
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  }
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
  
  if (activeSort.value === 'tubi') {
    rankings.value.sort((a, b) => (b.tubiRatio - a.tubiRatio) * direction)
  } else if (activeSort.value === 'inscription') {
    rankings.value.sort((a, b) => (b.inscriptionPercent - a.inscriptionPercent) * direction)
  } else if (activeSort.value === 'painting') {
    rankings.value.sort((a, b) => (b.paintingPercent - a.paintingPercent) * direction)
  } else if (activeSort.value === 'year') {
    rankings.value.sort((a, b) => {
      const yearA = parseInt(a.year) || 0
      const yearB = parseInt(b.year) || 0
      return (yearB - yearA) * direction
    })
  }
  currentPage.value = 1 // 重置到第一页
}

// 加载排行榜数据
async function loadRankings() {
  try {
    const response = await tubiApi.getAllResults()
    if (response.success) {
      // 转换字段名并计算题画比
      const works = (response.data || []).map(item => ({
        ...item,
        inscriptionPercent: item.inscription_percent,
        paintingPercent: item.painting_percent,
        blankPercent: item.blank_percent,
        annotatedImageUrl: item.annotated_image_url,
        thumbnailUrl: item.thumbnail_url,
        analysisNote: item.analysis_note
      }))

      // 计算每个作品的题画比
      const rankedWorks = works
        .filter(item => {
          return item.inscriptionPercent !== undefined && 
                 item.paintingPercent !== undefined && 
                 item.paintingPercent > 0
        })
        .map(item => {
          const tubiRatio = item.inscriptionPercent / item.paintingPercent
          return {
            ...item,
            tubiRatio: tubiRatio
          }
        })

      rankings.value = rankedWorks
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
  loadRankings()
})
</script>

<style scoped>
.tubi-ranking {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  text-align: center;
  font-size: 28px;
  margin-bottom: 8px;
  color: #D8860B;
  font-weight: 600;
}

.page-subtitle {
  text-align: center;
  font-size: 14px;
  color: #666;
  margin-bottom: 24px;
}

.ranking-list-card {
  margin-bottom: 20px;
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
}

.sort-icon {
  margin-left: 4px;
  font-size: 12px;
  transition: transform 0.3s ease;
}

/* 按钮样式 */
.el-button {
  display: flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
}

.header-actions {
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
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.works-table-header {
  display: flex;
  background: #f8f9fa;
  border-bottom: 2px solid #e9ecef;
  padding: 12px 16px;
  font-weight: 600;
  color: #333;
}

.works-table-body {
  display: flex;
  flex-direction: column;
}

.works-table-row {
  display: flex;
  border-bottom: 1px solid #e9ecef;
  padding: 16px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.works-table-row:hover {
  background: #f8f9fa;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.table-col {
  display: flex;
  align-items: center;
}

.col-image {
  width: 100px;
  flex-shrink: 0;
}

.col-info {
  flex: 1;
  min-width: 0;
  padding: 0 16px;
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
  width: 300px;
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
  width: 80px;
  height: 80px;
  border-radius: 4px;
  overflow: hidden;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
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
  color: #D8860B;
  background: #f8f9fa;
}

/* 作品信息 */
.work-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.work-meta {
  font-size: 14px;
  color: #666;
  display: flex;
  gap: 12px;
}

/* 作品统计 */
.work-stats {
  display: flex;
  flex-direction: row;
  gap: 8px;
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
  color: #D8860B;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  margin-top: 20px;
}

.no-data el-icon {
  margin-bottom: 16px;
  font-size: 48px;
}

.no-data p {
  font-size: 16px;
  margin: 0 0 16px 0;
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
