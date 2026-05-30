<template>
  <div class="album-manager-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title-group">
        <h1 class="page-title">册页管理</h1>
        <p class="page-subtitle">成套册页作品管理 · 顺序编排 · 批量操作</p>
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
          <span class="stat-num">{{ albums.length }}</span>
          <span class="stat-label">册页总数</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ totalItems }}</span>
          <span class="stat-label">作品总数</span>
        </div>
        <div class="stats-bar-actions">
          <el-button type="primary" size="large" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            新建册页
          </el-button>
        </div>
      </div>

      <!-- 册页列表 -->
      <div v-if="albums.length > 0" class="albums-grid">
        <div
          v-for="album in albums"
          :key="album.name"
          class="album-card"
        >
          <div class="album-card-header">
            <div class="album-cover">
              <img
                v-if="album.cover_url"
                :src="album.cover_url"
                class="cover-img"
                @error="e => e.target.style.display='none'"
              />
              <div v-else class="cover-placeholder">
                <el-icon><Picture /></el-icon>
              </div>
            </div>
            <div class="album-info">
              <h3 class="album-name">{{ album.name }}</h3>
              <p class="album-meta">
                {{ album.count }} 开
                <span v-if="album.cover_title">· {{ album.cover_title }}</span>
                <span v-if="album.year_range" class="album-year">· {{ album.year_range }}</span>
              </p>
            </div>
            <div class="album-actions">
              <el-button size="small" @click="viewAlbum(album.name)">
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button size="small" type="danger" @click="confirmDeleteAlbum(album.name)">
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
        <p class="empty-text">暂无册页</p>
        <p class="empty-hint">点击上方按钮创建第一个册页</p>
      </div>
    </div>

    <!-- 新建册页弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建册页"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="70px" @submit.prevent>
        <el-form-item label="册页名称">
          <el-input
            v-model="createForm.name"
            placeholder="如：花鸟册页十开"
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
              <span class="record-title">
                {{ record.title || '无名' }}
                <span v-if="record.year" class="record-year">({{ record.year }}年)</span>
              </span>
            </div>
            <div v-if="filteredCreateRecords.length === 0" class="empty-selector">
              没有匹配的作品
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createAlbum">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看册页详情弹窗 -->
    <el-dialog
      v-model="showViewDialog"
      :title="isEditingAlbum ? '编辑册页' : currentAlbum?.name"
      width="900px"
    >
      <div v-if="currentAlbum" class="album-detail">
        <div class="detail-header">
          <div v-if="!isEditingAlbum" class="album-name-display">
            <h2 class="album-name-title">{{ currentAlbum.name }}</h2>
          </div>
          <div v-else class="album-name-edit">
            <el-input
              v-model="editingAlbumName"
              placeholder="请输入册页名称"
              class="album-name-input"
            />
          </div>
          <div class="detail-actions">
            <template v-if="!isEditingAlbum">
              <el-button size="small" @click="startEditAlbum">
                <el-icon><Edit /></el-icon>
                重命名
              </el-button>
              <el-button size="small" @click="showAddItemsDialog = true">
                <el-icon><Plus /></el-icon>
                添加作品
              </el-button>
            </template>
            <template v-else>
              <el-button size="small" @click="cancelEditAlbum">
                取消
              </el-button>
              <el-button size="small" type="primary" :loading="renaming" @click="saveAlbumName">
                保存
              </el-button>
            </template>
          </div>
        </div>

        <div class="album-items-toolbar">
          <el-input
            v-model="albumItemsSearchKeyword"
            placeholder="搜索册页内作品..."
            clearable
            size="small"
            class="album-items-search"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <div
          v-if="filteredAlbumItems.length > 0"
          class="album-items-list"
        >
          <div
            v-for="(item, index) in filteredAlbumItems"
            :key="item.id"
            class="album-item-row"
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
            <!-- 页面角色 -->
            <el-select
              :model-value="item.page_role || ''"
              size="small"
              class="item-role-select"
              placeholder="正文"
              @change="(val) => setItemPageRole(item, val)"
            >
              <el-option label="正文" value="" />
              <el-option label="封面" value="cover" />
              <el-option label="封底" value="back_cover" />
              <el-option label="题跋页" value="inscription" />
              <el-option label="附件" value="accessory" />
              <el-option label="其他" value="other" />
            </el-select>
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
                :disabled="index === filteredAlbumItems.length - 1"
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
          {{ albumItemsSearchKeyword.trim() ? '没有匹配的作品' : '册页中暂无作品' }}
        </div>
      </div>
      <template #footer>
        <el-button @click="showViewDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 添加作品到册页弹窗 -->
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
        <el-button type="primary" :loading="adding" @click="addItemsToAlbum">
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, View, Delete, Collection, Picture, Top, Bottom, Search, Edit } from '@element-plus/icons-vue'
import { tibaApi } from '../api'

const props = defineProps({
  artist: { type: String, default: 'all' },
  libraryId: { type: Number, default: null }
})

const loading = ref(false)
const albums = ref([])
const allRecords = ref([])

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
const albumItemsSearchKeyword = ref('')

const currentAlbum = ref(null)
const currentAlbumItems = ref([])

const creating = ref(false)
const adding = ref(false)
const renaming = ref(false)

// 编辑册页名称
const isEditingAlbum = ref(false)
const editingAlbumName = ref('')

// 编辑作品标题
const editingItemId = ref(null)
const editingItemTitle = ref('')
const savingItemTitle = ref(false)

// 编辑作品年份
const editingYearItemId = ref(null)
const editingYearValue = ref('')
const savingYear = ref(false)

const totalItems = computed(() => {
  return albums.value.reduce((sum, a) => sum + a.count, 0)
})

const availableRecords = computed(() => {
  if (!currentAlbum.value) return []
  // 一个作品只能属于一个册页，只显示未归属任何册页的作品
  // 册页作品高度一般不超过70cm
  return allRecords.value.filter(r => {
    const noAlbum = !r.album_name || r.album_name === ''
    const isAlbumSize = !r.artwork_height_cm || r.artwork_height_cm <= 70
    return noAlbum && isAlbumSize
  })
})

// 过滤后的记录（新建册页用）
const filteredCreateRecords = computed(() => {
  // 册页作品：未归属任何册页 + 高度不超过70cm
  let records = allRecords.value.filter(r => {
    const noAlbum = !r.album_name || r.album_name === ''
    const isAlbumSize = !r.artwork_height_cm || r.artwork_height_cm <= 70
    return noAlbum && isAlbumSize
  })
  if (!createSearchKeyword.value.trim()) return records
  const keyword = createSearchKeyword.value.toLowerCase().trim()
  return records.filter(r =>
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

// 过滤册页内的作品（按年代升序排列）
const filteredAlbumItems = computed(() => {
  let items = [...currentAlbumItems.value]
  // 按年份升序排列（无年份的排在最后）
  items.sort((a, b) => {
    const yearA = a.year != null && a.year !== '' ? Number(a.year) : Infinity
    const yearB = b.year != null && b.year !== '' ? Number(b.year) : Infinity
    return yearA - yearB
  })
  if (!albumItemsSearchKeyword.value.trim()) return items
  const keyword = albumItemsSearchKeyword.value.toLowerCase().trim()
  return items.filter(r =>
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
  loading.value = true
  try {
    const [albumsRes, allResultsRes] = await Promise.all([
      tibaApi.getAlbums(props.artist, props.libraryId),
      tibaApi.getAllResults(0, 1000, props.artist, props.libraryId),
    ])
    if (albumsRes.success && allResultsRes.success) {
      allRecords.value = allResultsRes.data
      // 为每个册页计算年份范围（用 album_name 去 allRecords 里筛选）
      albums.value = albumsRes.data.map(album => {
        const albumItems = allRecords.value.filter(r => r.album_name === album.name)
        const years = albumItems.map(r => r.year).filter(y => y != null && y !== '')
        let year_range = null
        let sortYear = Infinity
        if (years.length > 0) {
          const minYear = Math.min(...years)
          const maxYear = Math.max(...years)
          year_range = minYear === maxYear ? `${minYear}年` : `${minYear}-${maxYear}年`
          sortYear = minYear
        }
        return { ...album, year_range, sortYear }
      }).sort((a, b) => {
        const yearA = a.sortYear != null ? a.sortYear : Infinity
        const yearB = b.sortYear != null ? b.sortYear : Infinity
        return yearA - yearB
      })
    }
  } catch (e) {
    ElMessage.error('加载数据失败: ' + e.message)
  } finally {
    loading.value = false
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

async function createAlbum() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入册页名称')
    return
  }
  creating.value = true
  try {
    const payload = { name: createForm.value.name }
    if (selectedRecordIds.value.length > 0) {
      // 转换为普通数组，避免 Vue Proxy 序列化问题
      payload.record_ids = [...selectedRecordIds.value]
    }
    console.log('发送创建册页请求，payload:', payload)
    console.log('payload.record_ids 类型:', typeof payload.record_ids, '是否数组:', Array.isArray(payload.record_ids))
    await tibaApi.createAlbum(payload)
    ElMessage.success('册页创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '' }
    selectedRecordIds.value = []
    await loadData()
  } catch (e) {
    console.error('创建册页失败，完整错误:', e)
    console.error('错误响应数据:', e.response?.data)
    console.error('错误详情:', JSON.stringify(e.response?.data?.detail, null, 2))
    const detail = e.response?.data?.detail
    const errorMsg = Array.isArray(detail) 
      ? detail.map(d => `${d.loc?.join('.') || 'field'}: ${d.msg}`).join('; ')
      : (detail || e.message)
    ElMessage.error('创建失败: ' + errorMsg)
  } finally {
    creating.value = false
  }
}

async function viewAlbum(name) {
  currentAlbum.value = albums.value.find(a => a.name === name)
  try {
    const res = await tibaApi.getAlbum(name)
    if (res.success) {
      currentAlbumItems.value = res.data.items
    }
  } catch (e) {
    ElMessage.error('加载册页详情失败: ' + e.message)
  }
  showViewDialog.value = true
}

async function confirmDeleteAlbum(name) {
  try {
    await ElMessageBox.confirm(
      `确定要删除册页「${name}」吗？\n册页中的作品不会被删除，只是移出册页。`,
      '删除册页',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    await tibaApi.deleteAlbum(name)
    ElMessage.success('册页已删除')
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
      '确定要将该作品移出册页吗？',
      '移出作品',
      { confirmButtonText: '确定移出', cancelButtonText: '取消', type: 'warning' }
    )
    await tibaApi.removeItemFromAlbum(currentAlbum.value.name, id)
    ElMessage.success('作品已移出')
    await viewAlbum(currentAlbum.value.name)
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('移出失败: ' + e.message)
    }
  }
}

async function moveItem(filteredIndex, direction) {
  // 如果有搜索过滤，先找到在原始列表中的真实索引
  const item = filteredAlbumItems.value[filteredIndex]
  const realIndex = currentAlbumItems.value.findIndex(i => i.id === item.id)
  
  const newOrder = [...currentAlbumItems.value]
  const movedItem = newOrder.splice(realIndex, 1)[0]
  newOrder.splice(realIndex + direction, 0, movedItem)
  
  try {
    await tibaApi.reorderAlbumItems(
      currentAlbum.value.name,
      newOrder.map(i => i.id)
    )
    ElMessage.success('顺序已更新')
    currentAlbumItems.value = newOrder
  } catch (e) {
    ElMessage.error('更新顺序失败: ' + e.message)
  }
}

async function addItemsToAlbum() {
  if (addingRecordIds.value.length === 0) {
    ElMessage.warning('请选择要添加的作品')
    return
  }
  adding.value = true
  try {
    await tibaApi.addItemsToAlbum(currentAlbum.value.name, addingRecordIds.value)
    ElMessage.success('作品已添加')
    showAddItemsDialog.value = false
    addingRecordIds.value = []
    await viewAlbum(currentAlbum.value.name)
    await loadData()
  } catch (e) {
    ElMessage.error('添加失败: ' + e.message)
  } finally {
    adding.value = false
  }
}

// 编辑册页名称
function startEditAlbum() {
  editingAlbumName.value = currentAlbum.value.name
  isEditingAlbum.value = true
}

function cancelEditAlbum() {
  isEditingAlbum.value = false
  editingAlbumName.value = ''
}

async function saveAlbumName() {
  if (!editingAlbumName.value.trim()) {
    ElMessage.warning('请输入册页名称')
    return
  }
  if (editingAlbumName.value.trim() === currentAlbum.value.name) {
    isEditingAlbum.value = false
    return
  }
  renaming.value = true
  try {
    await tibaApi.renameAlbum(currentAlbum.value.name, editingAlbumName.value.trim())
    ElMessage.success('册页名称已更新')
    isEditingAlbum.value = false
    // 重新加载册页数据
    await viewAlbum(editingAlbumName.value.trim())
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
  // 下一个 tick 聚焦输入框
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
    await tibaApi.updateImageInfo(item.id, { title: newTitle })
    ElMessage.success('作品名称已更新')
    // 更新本地数据
    item.title = newTitle
    // 同时更新 allRecords 中对应的数据
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
    await tibaApi.updateImageInfo(item.id, { year: yearNum })
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

async function setItemPageRole(item, role) {
  // role 来自 el-select: "" = 正文, "cover" = 封面, etc.
  // 后端 "" → page_role=NULL（清除角色）
  try {
    await tibaApi.updateImageInfo(item.id, { page_role: role || '' })
    ElMessage.success(role ? '角色已更新' : '已设为正文')
    item.page_role = role || null
    const record = allRecords.value.find(r => r.id === item.id)
    if (record) record.page_role = role || null
  } catch (e) {
    ElMessage.error('更新失败: ' + e.message)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.album-manager-page {
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

/* 册页网格 */
.albums-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.album-card {
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.2s;
}

.album-card:hover {
  border-color: #d0cbc4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.album-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.album-cover {
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

.album-info {
  flex: 1;
  min-width: 0;
}

.album-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d1c1a;
  margin: 0 0 4px;
  line-height: 1.4;
  /* 最多显示2行，超过显示省略号 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.album-meta {
  font-size: 12px;
  color: #8a8070;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.album-year {
  color: #b8a47e;
  font-weight: 500;
}

.album-actions {
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

.record-year,
.item-year {
  font-size: 11px;
  color: #8a8070;
  margin-left: 4px;
  font-weight: 400;
}

/* 册页详情 */
.album-detail {
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

.album-name-display {
  flex: 1;
}

.album-name-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d1c1a;
  font-family: "Noto Serif SC", "STKaiti", serif;
}

.album-name-edit {
  flex: 1;
}

.album-name-input {
  max-width: 400px;
}

.detail-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 册页内作品搜索工具栏 */
.album-items-toolbar {
  margin-bottom: 12px;
}

.album-items-search {
  max-width: 300px;
}

.album-items-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.album-item-row {
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
  min-width: 0;
}

.item-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #1d1c1a;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.15s;
}

.item-title:hover {
  background: #f0ede8;
}

.item-title:hover .edit-icon {
  opacity: 1;
}

.edit-icon {
  opacity: 0;
  font-size: 12px;
  color: #b8a47e;
  transition: opacity 0.15s;
}

.item-title-input {
  max-width: 300px;
}

/* 年份可编辑 */
.item-year-row {
  min-width: 0;
}

.item-year-editable {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8a8070;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  transition: all 0.15s;
  width: fit-content;
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
  padding: 2px 10px;
}

.item-year-editable.year-empty:hover {
  background: #fff5e8;
  border-color: #c96442;
}

.item-year-input {
  max-width: 100px;
}

.item-role-select {
  width: 80px;
  flex-shrink: 0;
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
