<template>
  <div class="strip-manager-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title-group">
        <h1 class="page-title">条屏管理</h1>
        <p class="page-subtitle">大尺寸条屏作品管理 · 顺序编排 · 批量操作</p>
        <div class="header-ornament">
          <span class="ornament-line"></span>
          <span class="ornament-dot">◇</span>
          <span class="ornament-line"></span>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载数据中...</span>
    </div>

    <div v-else>
      <!-- 统计栏 + 操作按钮 -->
      <div class="stats-bar">
        <div class="stat-card">
          <span class="stat-num">{{ strips.length }}</span>
          <span class="stat-label">条屏总数</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ totalItems }}</span>
          <span class="stat-label">作品总数</span>
        </div>
        <div class="stats-bar-actions">
          <el-button type="primary" size="large" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            新建条屏
          </el-button>
        </div>
      </div>

      <!-- 条屏列表 -->
      <div v-if="strips.length > 0" class="strips-grid">
        <div
          v-for="strip in strips"
          :key="strip.name"
          class="strip-card"
        >
          <div class="strip-card-header">
            <div class="strip-cover">
              <img
                v-if="strip.cover_url"
                :src="strip.cover_url"
                class="cover-img"
                @error="e => e.target.style.display='none'"
              />
              <div v-else class="cover-placeholder">
                <el-icon><Picture /></el-icon>
              </div>
            </div>
            <div class="strip-info">
              <h3 class="strip-name">{{ strip.name }}</h3>
              <p class="strip-meta">
                {{ strip.count }} 幅
                <span v-if="strip.cover_title">· {{ strip.cover_title }}</span>
              </p>
            </div>
            <div class="strip-actions">
              <el-button size="small" @click="viewStrip(strip.name)">
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button size="small" type="danger" @click="confirmDeleteStrip(strip.name)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <el-icon class="empty-icon"><Collection /></el-icon>
        <p class="empty-text">暂无条屏</p>
        <p class="empty-hint">点击上方按钮创建第一个条屏</p>
      </div>
    </div>

    <!-- 新建条屏弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建条屏"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="70px" @submit.prevent>
        <el-form-item label="条屏名称">
          <el-input
            v-model="createForm.name"
            placeholder="如：十二条屏"
          />
        </el-form-item>
        <el-form-item label="选择作品" class="full-width-item">
          <div class="selector-toolbar">
            <el-input
              v-model="createSearchKeyword"
              placeholder="搜索作品标题..."
              clearable
              size="small"
              class="search-input"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <div class="selector-actions">
              <el-button size="small" @click="selectAllFilteredCreate">全选筛选结果</el-button>
              <el-button size="small" @click="clearSelectedCreate">取消选择</el-button>
            </div>
          </div>
          <div class="record-selector">
            <div
              v-for="record in filteredCreateRecords"
              :key="record.id"
              :class="['record-item', { selected: selectedRecordIds.includes(record.id) }]"
              @click="toggleRecord(record.id)"
            >
              <img
                v-if="record.thumbnail_url"
                :src="record.thumbnail_url"
                class="record-thumb"
                @error="e => e.target.style.display='none'"
              />
              <div v-else class="record-thumb-placeholder">无图</div>
              <span class="record-title">{{ record.title || '无名' }}</span>
            </div>
            <div v-if="filteredCreateRecords.length === 0" class="empty-selector">
              没有匹配的作品
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createStrip">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看条屏详情弹窗 -->
    <el-dialog
      v-model="showViewDialog"
      :title="isEditingStrip ? '编辑条屏' : currentStrip?.name"
      width="900px"
    >
      <div v-if="currentStrip" class="strip-detail">
        <div class="detail-header">
          <div v-if="!isEditingStrip" class="strip-name-display">
            <h2 class="strip-name-title">{{ currentStrip.name }}</h2>
          </div>
          <div v-else class="strip-name-edit">
            <el-input
              v-model="editingStripName"
              placeholder="请输入条屏名称"
              class="strip-name-input"
            />
          </div>
          <div class="detail-actions">
            <template v-if="!isEditingStrip">
              <el-button size="small" @click="startEditStrip">
                <el-icon><Edit /></el-icon>
                重命名
              </el-button>
              <el-button size="small" @click="showAddItemsDialog = true">
                <el-icon><Plus /></el-icon>
                添加作品
              </el-button>
            </template>
            <template v-else>
              <el-button size="small" @click="cancelEditStrip">
                取消
              </el-button>
              <el-button size="small" type="primary" :loading="renaming" @click="saveStripName">
                保存
              </el-button>
            </template>
          </div>
        </div>

        <div class="strip-items-toolbar">
          <el-input
            v-model="stripItemsSearchKeyword"
            placeholder="搜索条屏内作品..."
            clearable
            size="small"
            class="strip-items-search"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <div
          v-if="filteredStripItems.length > 0"
          class="strip-items-list"
        >
          <div
            v-for="(item, index) in filteredStripItems"
            :key="item.id"
            class="strip-item-row"
          >
            <span class="item-index">{{ index + 1 }}</span>
            <img
              v-if="item.thumbnail_url"
              :src="item.thumbnail_url"
              class="item-thumb"
              @error="e => e.target.style.display='none'"
            />
            <div v-else class="item-thumb-placeholder">无图</div>
            <div class="item-info-wrapper" @click.stop>
              <!-- 标题 -->
              <div class="item-title-row">
                <span
                  v-if="editingItemId !== item.id"
                  class="item-title"
                  @click="startEditItemTitle(item)"
                  title="点击修改作品名称"
                >
                  {{ item.title || '无名' }}
                  <el-icon class="edit-icon"><Edit /></el-icon>
                </span>
                <el-input
                  v-else
                  v-model="editingItemTitle"
                  size="small"
                  class="item-title-input"
                  :disabled="savingItemTitle"
                  @blur="saveItemTitle(item)"
                  @keyup.enter="saveItemTitle(item)"
                  @keyup.esc="cancelEditItemTitle"
                />
              </div>
              <!-- 年份 -->
              <div class="item-year-row">
                <span
                  v-if="editingYearItemId !== item.id"
                  class="item-year-editable"
                  :class="{ 'year-empty': !item.year }"
                  @click="startEditItemYear(item)"
                  title="点击修改年份"
                >
                  {{ item.year ? item.year + '年' : '+ 年份' }}
                  <el-icon v-if="item.year" class="edit-icon"><Edit /></el-icon>
                </span>
                <el-input
                  v-else
                  v-model="editingYearValue"
                  size="small"
                  class="item-year-input"
                  :disabled="savingYear"
                  @blur="saveItemYear(item)"
                  @keyup.enter="saveItemYear(item)"
                  @keyup.esc="cancelEditItemYear"
                />
              </div>
            </div>
            <div class="item-actions">
              <el-button
                size="small"
                :disabled="index === 0"
                @click="moveItem(index, -1)"
              >
                <el-icon><Top /></el-icon>
              </el-button>
              <el-button
                size="small"
                :disabled="index === filteredStripItems.length - 1"
                @click="moveItem(index, 1)"
              >
                <el-icon><Bottom /></el-icon>
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="confirmRemoveItem(item.id)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="detail-empty">
          {{ stripItemsSearchKeyword.trim() ? '没有匹配的作品' : '条屏中暂无作品' }}
        </div>
      </div>
      <template #footer>
        <el-button @click="showViewDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 添加作品到条屏弹窗 -->
    <el-dialog
      v-model="showAddItemsDialog"
      title="添加作品"
      width="900px"
    >
      <div class="selector-toolbar">
        <el-input
          v-model="addSearchKeyword"
          placeholder="搜索作品标题..."
          clearable
          size="small"
          class="search-input"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <div class="selector-actions">
          <el-button size="small" @click="selectAllFilteredAdd">全选筛选结果</el-button>
          <el-button size="small" @click="clearSelectedAdd">取消选择</el-button>
        </div>
      </div>
      <div class="add-items-selector">
        <div
          v-for="record in filteredAddRecords"
          :key="record.id"
          :class="['record-item', { selected: addingRecordIds.includes(record.id) }]"
          @click="toggleAddingRecord(record.id)"
        >
          <img
            v-if="record.thumbnail_url"
            :src="record.thumbnail_url"
            class="record-thumb"
            @error="e => e.target.style.display='none'"
          />
          <div v-else class="record-thumb-placeholder">无图</div>
          <span class="record-title">{{ record.title || '无名' }}</span>
        </div>
        <div v-if="filteredAddRecords.length === 0" class="empty-selector">
          没有匹配的作品
        </div>
      </div>
      <template #footer>
        <el-button @click="showAddItemsDialog = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="addItemsToStrip">
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, View, Delete, Collection, Picture, Top, Bottom, Search, Edit } from '@element-plus/icons-vue'
import { tubiApi } from '../api'

const props = defineProps({
  artist: { type: String, default: 'all' },
  libraryId: { type: Number, default: null }
})

const loading = ref(false)
const strips = ref([])
const allRecords = ref([])

// 竞态保护：只接受最新请求的结果
let loadDataToken = 0

// 监听作者变化，刷新数据
watch(() => props.artist, () => {
  loadData()
})

const showCreateDialog = ref(false)
const showViewDialog = ref(false)
const showAddItemsDialog = ref(false)

const createForm = ref({ name: '' })
const selectedRecordIds = ref([])
const addingRecordIds = ref([])

// 搜索关键词
const createSearchKeyword = ref('')
const addSearchKeyword = ref('')
const stripItemsSearchKeyword = ref('')

const currentStrip = ref(null)
const currentStripItems = ref([])

const creating = ref(false)
const adding = ref(false)
const renaming = ref(false)

// 编辑作品标题/年份
const editingItemId = ref(null)
const editingItemTitle = ref('')
const savingItemTitle = ref(false)
const editingYearItemId = ref(null)
const editingYearValue = ref('')
const savingYear = ref(false)

// 编辑条屏名称
const isEditingStrip = ref(false)
const editingStripName = ref('')

const totalItems = computed(() => {
  return strips.value.reduce((sum, s) => sum + s.count, 0)
})

// 只筛选大尺寸作品（条屏专用）
const largeSizeRecords = computed(() => {
  return allRecords.value.filter(r => {
    // 判断大尺寸：高度 >= 100cm 或 宽度 >= 100cm
    // 或者尺寸未录入（新上传图片，允许先添加到条屏再录入尺寸）
    const height = r.artwork_height_cm || 0
    const width = r.artwork_width_cm || 0
    const hasSize = r.artwork_height_cm != null && r.artwork_width_cm != null
    
    // 未录入尺寸的图片也显示，或者已录入且满足大尺寸条件
    return !hasSize || height >= 100 || width >= 100
  })
})

const availableRecords = computed(() => {
  if (!currentStrip.value) return []
  const stripItemIds = new Set(currentStripItems.value.map(i => i.id))
  return largeSizeRecords.value.filter(r => !stripItemIds.has(r.id))
})

// 过滤后的记录
const filteredCreateRecords = computed(() => {
  if (!createSearchKeyword.value.trim()) return largeSizeRecords.value
  const keyword = createSearchKeyword.value.toLowerCase().trim()
  return largeSizeRecords.value.filter(r => 
    (r.title || '').toLowerCase().includes(keyword)
  )
})

const filteredAddRecords = computed(() => {
  if (!addSearchKeyword.value.trim()) return availableRecords.value
  const keyword = addSearchKeyword.value.toLowerCase().trim()
  return availableRecords.value.filter(r => 
    (r.title || '').toLowerCase().includes(keyword)
  )
})

// 过滤条屏内的作品
const filteredStripItems = computed(() => {
  if (!stripItemsSearchKeyword.value.trim()) return currentStripItems.value
  const keyword = stripItemsSearchKeyword.value.toLowerCase().trim()
  return currentStripItems.value.filter(r => 
    (r.title || '').toLowerCase().includes(keyword)
  )
})

// 全选/取消选择函数
function selectAllFilteredCreate() {
  const filteredIds = filteredCreateRecords.value.map(r => r.id)
  selectedRecordIds.value = [...new Set([...selectedRecordIds.value, ...filteredIds])]
}

function clearSelectedCreate() {
  selectedRecordIds.value = []
}

function selectAllFilteredAdd() {
  const filteredIds = filteredAddRecords.value.map(r => r.id)
  addingRecordIds.value = [...new Set([...addingRecordIds.value, ...filteredIds])]
}

function clearSelectedAdd() {
  addingRecordIds.value = []
}

async function loadData() {
  const token = ++loadDataToken
  loading.value = true
  try {
    const [albumsRes, allResultsRes] = await Promise.all([
      tubiApi.getAlbums(props.artist, props.libraryId),
      tubiApi.getAllResults(0, 1000, props.artist, props.libraryId),
    ])
    // 竞态保护：只接受最新请求的结果
    if (token !== loadDataToken) return
    if (albumsRes.success) {
      // 条屏复用餐页API，用名字前缀区分
      strips.value = albumsRes.data.filter(a => a.name.startsWith('条屏：') || a.name.startsWith('条屏-'))
    }
    if (allResultsRes.success) allRecords.value = allResultsRes.data
  } catch (e) {
    if (token === loadDataToken) {
      ElMessage.error('加载数据失败: ' + e.message)
    }
  } finally {
    if (token === loadDataToken) {
      loading.value = false
    }
  }
}

function toggleRecord(id) {
  const idx = selectedRecordIds.value.indexOf(id)
  if (idx >= 0) selectedRecordIds.value.splice(idx, 1)
  else selectedRecordIds.value.push(id)
}

function toggleAddingRecord(id) {
  const idx = addingRecordIds.value.indexOf(id)
  if (idx >= 0) addingRecordIds.value.splice(idx, 1)
  else addingRecordIds.value.push(id)
}

async function createStrip() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入条屏名称')
    return
  }
  creating.value = true
  try {
    const payload = { name: '条屏：' + createForm.value.name }
    if (selectedRecordIds.value.length > 0) {
      payload.record_ids = [...selectedRecordIds.value]
    }
    await tubiApi.createAlbum(payload)
    ElMessage.success('条屏创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '' }
    selectedRecordIds.value = []
    await loadData()
  } catch (e) {
    const detail = e.response?.data?.detail
    const errorMsg = Array.isArray(detail) 
      ? detail.map(d => `${d.loc?.join('.') || 'field'}: ${d.msg}`).join('; ')
      : (detail || e.message)
    ElMessage.error('创建失败: ' + errorMsg)
  } finally {
    creating.value = false
  }
}

async function viewStrip(name) {
  currentStrip.value = strips.value.find(s => s.name === name)
  try {
    const res = await tubiApi.getAlbum(name)
    if (res.success) {
      currentStripItems.value = res.data.items
    }
  } catch (e) {
    ElMessage.error('加载条屏详情失败: ' + e.message)
  }
  showViewDialog.value = true
}

async function confirmDeleteStrip(name) {
  try {
    await ElMessageBox.confirm(
      `确定要删除条屏「${name}」吗？\n条屏中的作品不会被删除，只是移出条屏。`,
      '删除条屏',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    await tubiApi.deleteAlbum(name)
    ElMessage.success('条屏已删除')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + e.message)
    }
  }
}

async function confirmRemoveItem(id) {
  try {
    await ElMessageBox.confirm(
      '确定要将该作品移出条屏吗？',
      '移出作品',
      { confirmButtonText: '确定移出', cancelButtonText: '取消', type: 'warning' }
    )
    await tubiApi.removeItemFromAlbum(currentStrip.value.name, id)
    ElMessage.success('作品已移出')
    await viewStrip(currentStrip.value.name)
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('移出失败: ' + e.message)
    }
  }
}

async function moveItem(filteredIndex, direction) {
  const item = filteredStripItems.value[filteredIndex]
  const realIndex = currentStripItems.value.findIndex(i => i.id === item.id)
  
  const newOrder = [...currentStripItems.value]
  const movedItem = newOrder.splice(realIndex, 1)[0]
  newOrder.splice(realIndex + direction, 0, movedItem)
  
  try {
    await tubiApi.reorderAlbumItems(
      currentStrip.value.name,
      newOrder.map(i => i.id)
    )
    ElMessage.success('顺序已更新')
    currentStripItems.value = newOrder
  } catch (e) {
    ElMessage.error('更新顺序失败: ' + e.message)
  }
}

async function addItemsToStrip() {
  if (addingRecordIds.value.length === 0) {
    ElMessage.warning('请选择要添加的作品')
    return
  }
  adding.value = true
  try {
    await tubiApi.addItemsToAlbum(currentStrip.value.name, addingRecordIds.value)
    ElMessage.success('作品已添加')
    showAddItemsDialog.value = false
    addingRecordIds.value = []
    await viewStrip(currentStrip.value.name)
    await loadData()
  } catch (e) {
    ElMessage.error('添加失败: ' + e.message)
  } finally {
    adding.value = false
  }
}

// 编辑条屏名称
function startEditStrip() {
  editingStripName.value = currentStrip.value.name.replace(/^条屏[：\-]/, '')
  isEditingStrip.value = true
}

function cancelEditStrip() {
  isEditingStrip.value = false
  editingStripName.value = ''
}

async function saveStripName() {
  if (!editingStripName.value.trim()) {
    ElMessage.warning('请输入条屏名称')
    return
  }
  const newName = '条屏：' + editingStripName.value.trim()
  if (newName === currentStrip.value.name) {
    isEditingStrip.value = false
    return
  }
  renaming.value = true
  try {
    await tubiApi.renameAlbum(currentStrip.value.name, newName)
    ElMessage.success('条屏名称已更新')
    isEditingStrip.value = false
    await viewStrip(newName)
    await loadData()
  } catch (e) {
    ElMessage.error('重命名失败: ' + e.message)
  } finally {
    renaming.value = false
  }
}

// 编辑作品标题
function startEditItemTitle(item) {
  editingItemId.value = item.id
  editingItemTitle.value = item.title || ''
  nextTick(() => {
    const inputEl = document.querySelector('.item-title-input input')
    if (inputEl) {
      inputEl.focus()
      inputEl.select()
    }
  })
}

function cancelEditItemTitle() {
  editingItemId.value = null
  editingItemTitle.value = ''
}

async function saveItemTitle(item) {
  if (savingItemTitle.value) return
  const newTitle = editingItemTitle.value.trim()
  if (!newTitle || newTitle === item.title) {
    cancelEditItemTitle()
    return
  }
  savingItemTitle.value = true
  try {
    await tubiApi.updateImageInfo(item.id, { title: newTitle })
    ElMessage.success('作品名称已更新')
    item.title = newTitle
    const record = allRecords.value.find(r => r.id === item.id)
    if (record) record.title = newTitle
    cancelEditItemTitle()
  } catch (e) {
    ElMessage.error('更新作品名称失败: ' + e.message)
  } finally {
    savingItemTitle.value = false
  }
}

// 编辑作品年份
function startEditItemYear(item) {
  editingYearItemId.value = item.id
  editingYearValue.value = item.year ? String(item.year) : ''
  nextTick(() => {
    const inputEl = document.querySelector('.item-year-input input')
    if (inputEl) {
      inputEl.focus()
      inputEl.select()
    }
  })
}

function cancelEditItemYear() {
  editingYearItemId.value = null
  editingYearValue.value = ''
}

async function saveItemYear(item) {
  if (savingYear.value) return
  const newYear = editingYearValue.value.trim()
  if (newYear === String(item.year || '')) {
    cancelEditItemYear()
    return
  }
  savingYear.value = true
  try {
    const yearNum = newYear ? Number(newYear) : null
    await tubiApi.updateImageInfo(item.id, { year: yearNum })
    ElMessage.success('年份已更新')
    item.year = yearNum
    const record = allRecords.value.find(r => r.id === item.id)
    if (record) record.year = yearNum
    cancelEditItemYear()
  } catch (e) {
    ElMessage.error('更新年份失败: ' + e.message)
  } finally {
    savingYear.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.strip-manager-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
  background: #faf9f5;
  min-height: 100vh;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  gap: 16px;
}

.header-title-group { flex: 1; }

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #141413;
  margin: 0 0 6px;
  font-family: "Noto Serif SC", "STKaiti", serif;
}

.page-subtitle {
  font-size: 13px;
  color: #8a8070;
  margin: 0 0 10px;
}

.header-ornament {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ornament-line {
  flex: 1;
  max-width: 80px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #b8a47e, transparent);
}

.ornament-dot { color: #b8a47e; font-size: 12px; }

/* 加载状态 */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px;
  color: #8a8070;
}

/* 统计栏 */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  flex: 1;
  max-width: 200px;
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 12px;
  padding: 16px 20px;
  text-align: center;
}

.stats-bar-actions {
  margin-left: auto;
  flex-shrink: 0;
}

.stat-num {
  display: block;
  font-size: 32px;
  font-weight: 700;
  color: #c96442;
  font-family: "Noto Serif SC", serif;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: #8a8070;
}

/* 条屏网格 */
.strips-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.strip-card {
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.2s;
}

.strip-card:hover {
  border-color: #d0cbc4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.strip-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.strip-cover {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  background: #f0ede8;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0aeaa;
  font-size: 24px;
}

.strip-info {
  flex: 1;
  min-width: 0;
}

.strip-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d1c1a;
  margin: 0 0 4px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.strip-meta {
  font-size: 12px;
  color: #8a8070;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.strip-actions {
  display: flex;
  gap: 6px;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  color: #d0cbc4;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: #5e5d59;
  margin: 0 0 4px;
}

.empty-hint {
  font-size: 13px;
  color: #8a8070;
  margin: 0;
}

/* 记录选择器 */
.record-selector,
.add-items-selector {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
  max-height: 500px;
  overflow-y: auto;
  padding: 4px;
}

.record-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px;
  background: #faf9f5;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.record-item:hover {
  background: #f5f3ec;
}

.record-item.selected {
  background: #fff5e8;
  border-color: #c96442;
}

/* 让选择作品的 el-form-item 占满宽度 */
:deep(.full-width-item) {
  max-width: none !important;
  width: 100% !important;
}

:deep(.full-width-item .el-form-item__content) {
  width: 100% !important;
  flex: 1 !important;
}

/* 确保弹窗内容也能占满宽度 */
:deep(.el-dialog__body) {
  padding: 20px !important;
}

.record-selector,
.add-items-selector {
  width: 100% !important;
}

.record-thumb {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: 6px;
}

.record-thumb-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  background: #f0ede8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #b0aeaa;
}

.record-title {
  font-size: 12px;
  color: #3d3d3a;
  text-align: center;
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 条屏详情 */
.strip-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e8e6dc;
}

.strip-name-display {
  flex: 1;
}

.strip-name-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d1c1a;
  font-family: "Noto Serif SC", "STKaiti", serif;
}

.strip-name-edit {
  flex: 1;
}

.strip-name-input {
  max-width: 400px;
}

.detail-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 条屏内作品搜索工具栏 */
.strip-items-toolbar {
  margin-bottom: 12px;
}

.strip-items-search {
  max-width: 300px;
}

.strip-items-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.strip-item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: #faf9f5;
  border: 1px solid #e8e6dc;
  border-radius: 8px;
}

.item-index {
  width: 28px;
  height: 28px;
  background: #c96442;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.item-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
}

.item-thumb-placeholder {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  background: #f0ede8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #b0aeaa;
  flex-shrink: 0;
}

.item-info-wrapper {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-title-row {
  display: flex;
  align-items: center;
}

.item-title {
  font-size: 14px;
  color: #1d1c1a;
  font-weight: 500;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}

.item-title:hover {
  background: #f0ede8;
}

.item-title:hover .edit-icon {
  opacity: 1;
}

.edit-icon {
  font-size: 12px;
  color: #b8a47e;
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.item-title-input {
  max-width: 300px;
}

.item-year-row {
  display: flex;
  align-items: center;
}

.item-year-editable {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8a8070;
  padding: 1px 6px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.item-year-editable:hover {
  background: #f0ede8;
}

.item-year-editable:hover .edit-icon {
  opacity: 1;
}

.item-year-editable.year-empty {
  color: #b8a47e;
  border: 1px dashed #d0cbc4;
}

.item-year-editable.year-empty:hover {
  background: #fff5e8;
  border-color: #c96442;
}

.item-year-input {
  max-width: 120px;
}

.item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.detail-empty {
  text-align: center;
  padding: 40px;
  color: #8a8070;
  font-size: 14px;
}

/* 搜索工具栏 */
.selector-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #e8e6dc;
}

.search-input {
  flex: 1;
  max-width: 300px;
}

.selector-actions {
  display: flex;
  gap: 8px;
}

.empty-selector {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 20px;
  color: #8a8070;
  font-size: 14px;
}
</style>
