<template>
  <div class="tag-manager-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title-group">
        <h1 class="page-title">标签管理</h1>
        <p class="page-subtitle">灵活的作品分类体系 · 多标签支持 · 筛选管理</p>
        <div class="header-ornament">
          <span class="ornament-line"></span>
          <span class="ornament-dot">◇</span>
          <span class="ornament-line"></span>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建标签
        </el-button>
        <el-button type="danger" @click="handleResetAllTags">
          <el-icon><Delete /></el-icon>
          清空所有标签
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载数据中...</span>
    </div>

    <div v-else>
      <!-- 统计栏 -->
      <div class="stats-bar">
        <div class="stat-card">
          <span class="stat-num">{{ tags.length }}</span>
          <span class="stat-label">标签总数</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ totalTagItems }}</span>
          <span class="stat-label">作品标签数</span>
        </div>
      </div>

      <!-- 标签云 -->
      <div v-if="tags.length > 0" class="tags-cloud">
        <div
          v-for="tag in sortedTags"
          :key="tag.name"
          :class="['tag-card', { selected: selectedTag === tag.name }]"
          @click="selectTag(tag.name)"
        >
          <div class="tag-info">
            <h3 class="tag-name">{{ tag.name }}</h3>
            <p class="tag-count">{{ tag.count }} 幅作品</p>
          </div>
          <div class="tag-actions">
            <el-button size="small" @click.stop="showRenameDialog(tag)">
              <el-icon><Edit /></el-icon>
              重命名
            </el-button>
            <el-button size="small" type="danger" @click.stop="confirmDeleteTag(tag.name)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>
      </div>

      <!-- 选中标签的作品列表 -->
      <div v-if="selectedTag" class="tag-detail-section">
        <div class="detail-header">
          <h3 class="detail-title">「{{ selectedTag }}」标签下的作品</h3>
          <el-button size="small" type="primary" @click="showAddItemsDialog = true">
            <el-icon><Plus /></el-icon>
            添加作品
          </el-button>
        </div>
        
        <div
          v-if="selectedTagItems.length > 0"
          class="tag-items-grid"
        >
          <div
            v-for="item in selectedTagItems"
            :key="item.id"
            class="tag-item-card"
          >
            <img
              v-if="item.thumbnail_url"
              :src="item.thumbnail_url"
              class="item-thumb"
              @error="e => e.target.style.display='none'"
            />
            <div v-else class="item-thumb-placeholder">无图</div>
            <div class="item-info">
              <span class="item-title">{{ item.title || '无名' }}</span>
            </div>
            <div class="item-actions">
              <el-button
                size="small"
                type="danger"
                @click="confirmRemoveItem(item.id)"
              >
                <el-icon><Delete /></el-icon>
                移除
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="detail-empty">
          该标签下暂无作品
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <el-icon class="empty-icon"><PriceTag /></el-icon>
        <p class="empty-text">暂无标签</p>
        <p class="empty-hint">点击上方按钮创建第一个标签</p>
      </div>
    </div>

    <!-- 新建标签弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建标签"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="70px" @submit.prevent>
        <el-form-item label="标签名称">
          <el-input
            v-model="createForm.name"
            placeholder="如：写意、工笔、精品"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createTag">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 重命名标签弹窗 -->
    <el-dialog
      v-model="showRenameDialogVisible"
      title="重命名标签"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="renameForm" label-width="70px" @submit.prevent>
        <el-form-item label="原名称">
          <span>{{ renamingTag?.name }}</span>
        </el-form-item>
        <el-form-item label="新名称">
          <el-input
            v-model="renameForm.new_name"
            placeholder="输入新名称"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="renaming" @click="renameTag">
          重命名
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加作品到标签弹窗 -->
    <el-dialog
      v-model="showAddItemsDialog"
      title="添加作品"
      width="600px"
    >
      <div class="add-items-selector">
        <div
          v-for="record in availableRecords"
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
      </div>
      <template #footer>
        <el-button @click="showAddItemsDialog = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="addItemsToTag">
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, Edit, Delete, PriceTag } from '@element-plus/icons-vue'
import { tubiApi } from '../api'

const props = defineProps({
  artist: { type: String, default: 'all' },
  libraryId: { type: Number, default: null }
})

const loading = ref(false)
const tags = ref([])
const allRecords = ref([])

// 监听作者变化，刷新数据
watch(() => props.artist, () => {
  loadData()
})

const showCreateDialog = ref(false)
const showRenameDialogVisible = ref(false)
const showAddItemsDialog = ref(false)

const createForm = ref({ name: '' })
const renameForm = ref({ new_name: '' })
const renamingTag = ref(null)

const selectedTag = ref(null)
const selectedTagItems = ref([])
const addingRecordIds = ref([])

const creating = ref(false)
const renaming = ref(false)
const adding = ref(false)

const totalTagItems = computed(() => {
  return tags.value.reduce((sum, t) => sum + t.count, 0)
})

const sortedTags = computed(() => {
  return [...tags.value].sort((a, b) => b.count - a.count)
})

const availableRecords = computed(() => {
  if (!selectedTag.value) return []
  const tagItemIds = new Set(selectedTagItems.value.map(i => i.id))
  return allRecords.value.filter(r => !tagItemIds.has(r.id))
})

async function loadData() {
  loading.value = true
  try {
    const [tagsRes, allResultsRes] = await Promise.all([
      tubiApi.getTags(props.artist, props.libraryId),
      tubiApi.getAllResults(0, 1000, props.artist, props.libraryId),
    ])
    if (tagsRes.success) tags.value = tagsRes.data
    if (allResultsRes.success) allRecords.value = allResultsRes.data
  } catch (e) {
    ElMessage.error('加载数据失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function toggleAddingRecord(id) {
  const idx = addingRecordIds.value.indexOf(id)
  if (idx >= 0) addingRecordIds.value.splice(idx, 1)
  else addingRecordIds.value.push(id)
}

async function createTag() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  creating.value = true
  try {
    await tubiApi.createTag(createForm.value.name)
    ElMessage.success('标签创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '' }
    await loadData()
  } catch (e) {
    ElMessage.error('创建失败: ' + e.message)
  } finally {
    creating.value = false
  }
}

async function selectTag(name) {
  selectedTag.value = name
  try {
    const res = await tubiApi.getTagItems(name)
    if (res.success) {
      selectedTagItems.value = res.data.items
    }
  } catch (e) {
    ElMessage.error('加载标签作品失败: ' + e.message)
  }
}

function showRenameDialog(tag) {
  renamingTag.value = tag
  renameForm.value = { new_name: tag.name }
  showRenameDialogVisible.value = true
}

async function renameTag() {
  if (!renameForm.value.new_name.trim()) {
    ElMessage.warning('请输入新名称')
    return
  }
  renaming.value = true
  try {
    await tubiApi.renameTag(renamingTag.value.name, renameForm.value.new_name)
    ElMessage.success('标签已重命名')
    showRenameDialogVisible.value = false
    if (selectedTag.value === renamingTag.value.name) {
      selectedTag.value = renameForm.value.new_name
    }
    await loadData()
    if (selectedTag.value) {
      await selectTag(selectedTag.value)
    }
  } catch (e) {
    ElMessage.error('重命名失败: ' + e.message)
  } finally {
    renaming.value = false
  }
}

async function confirmDeleteTag(name) {
  try {
    await ElMessageBox.confirm(
      `确定要删除标签「${name}」吗？\n该标签将从所有作品中移除。`,
      '删除标签',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    await tubiApi.deleteTag(name)
    ElMessage.success('标签已删除')
    if (selectedTag.value === name) {
      selectedTag.value = null
      selectedTagItems.value = []
    }
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + e.message)
    }
  }
}

async function handleResetAllTags() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有作品的标签吗？\n清空后所有自动标签将被移除，重新分析时会重新生成。',
      '清空所有标签',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'el-button--danger' }
    )
    const res = await tubiApi.resetAllTags()
    ElMessage.success(res.data?.message || '已清空所有标签')
    selectedTag.value = null
    selectedTagItems.value = []
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清空失败: ' + (e.message || ''))
    }
  }
}

async function confirmRemoveItem(id) {
  try {
    await ElMessageBox.confirm(
      '确定要将该作品移除此标签吗？',
      '移除标签',
      { confirmButtonText: '确定移除', cancelButtonText: '取消', type: 'warning' }
    )
    await tubiApi.removeItemFromTag(selectedTag.value, id)
    ElMessage.success('标签已移除')
    await selectTag(selectedTag.value)
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('移除失败: ' + e.message)
    }
  }
}

async function addItemsToTag() {
  if (addingRecordIds.value.length === 0) {
    ElMessage.warning('请选择要添加的作品')
    return
  }
  adding.value = true
  try {
    await tubiApi.addItemsToTag(selectedTag.value, addingRecordIds.value)
    ElMessage.success('标签已添加')
    showAddItemsDialog.value = false
    addingRecordIds.value = []
    await selectTag(selectedTag.value)
    await loadData()
  } catch (e) {
    ElMessage.error('添加失败: ' + e.message)
  } finally {
    adding.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.tag-manager-page {
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
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  flex: 1;
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 12px;
  padding: 16px 20px;
  text-align: center;
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

/* 标签云 */
.tags-cloud {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.tag-card {
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-card:hover {
  border-color: #d0cbc4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.tag-card.selected {
  border-color: #c96442;
  background: #fffaf5;
}

.tag-info { flex: 1; min-width: 0; }

.tag-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d1c1a;
  margin: 0 0 4px;
}

.tag-count {
  font-size: 12px;
  color: #8a8070;
  margin: 0;
}

.tag-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 标签详情区 */
.tag-detail-section {
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 12px;
  padding: 20px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0ede8;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1c1a;
  margin: 0;
}

.tag-items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.tag-item-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #faf9f5;
  border: 1px solid #e8e6dc;
  border-radius: 8px;
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

.item-info {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  color: #1d1c1a;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-actions {
  flex-shrink: 0;
}

.detail-empty {
  text-align: center;
  padding: 40px;
  color: #8a8070;
  font-size: 14px;
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
.add-items-selector {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  max-height: 300px;
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

.record-thumb {
  width: 80px;
  height: 80px;
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
</style>
