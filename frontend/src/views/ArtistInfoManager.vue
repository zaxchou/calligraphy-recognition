<template>
  <div class="artist-info-manager">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input v-model="searchQuery" placeholder="搜索画家姓名..." clearable size="small" style="width:200px" @input="onSearchInput" @clear="onSearchInput" />
        <el-select v-model="dynastyFilter" placeholder="筛选朝代" clearable size="small" style="width:130px" @change="onDynastyChange">
          <el-option v-for="p in periods" :key="p" :label="p" :value="p" />
        </el-select>
      </div>
      <el-button type="primary" plain size="small" @click="openCreate"><el-icon><Plus /></el-icon>新增画家</el-button>
    </div>

    <div v-loading="loading" class="artist-list">
      <div v-for="artist in artists" :key="artist.id" class="artist-card">
        <div class="artist-row">
          <div class="artist-main">
            <el-avatar v-if="artist.avatar_url" :src="artist.avatar_url" :size="36" shape="square" />
            <el-avatar v-else :size="36" shape="square" style="background:#c45a3c">{{ artist.name?.charAt(0) || '?' }}</el-avatar>
            <span class="artist-name">{{ artist.name }}</span>
            <el-tag v-if="artist.dynasty" size="small">{{ artist.dynasty }}</el-tag>
            <el-tag v-if="artist.alias" size="small" type="info">{{ artist.alias }}</el-tag>
            <template v-if="artist.birth_year || artist.death_year">
              <el-tag size="small" type="info">{{ artist.birth_year || '?' }}-{{ artist.death_year || '?' }}</el-tag>
            </template>
            <el-tag v-if="!artist.enabled" size="small" type="danger">已禁用</el-tag>
            <el-tag v-if="artist.featured" size="small" type="warning">推荐</el-tag>
          </div>
          <div class="artist-actions">
            <el-button size="small" @click="openEdit(artist)">编辑</el-button>
            <el-button size="small" type="primary" plain @click="handleAiFill(artist)">AI补充</el-button>
            <el-button size="small" :type="artist.enabled ? 'warning' : 'success'" plain @click="toggleEnabled(artist)">
              {{ artist.enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(artist)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-if="!loading && artists.length === 0" class="empty-state"><el-empty description="暂无画家数据" /></div>
    </div>

    <div v-if="totalArtists > pageSize" class="pagination-bar">
      <el-pagination background layout="total, prev, pager, next" :total="totalArtists"
        :page-size="pageSize" :current-page="currentPage" @current-change="onPageChange" />
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/api'

const router = useRouter()

const props = defineProps({
  artist: { type: Object, default: null },
  libraryId: { type: [Number, String], default: null }
})

const artists = ref([])
const loading = ref(false)
const searchQuery = ref('')
const dynastyFilter = ref('')
const periods = ref([])
const currentPage = ref(1)
const totalArtists = ref(0)
const pageSize = 20
let searchTimer = null

function parseJsonArray(val) {
  if (!val) return []
  if (Array.isArray(val)) return val
  try { const p = JSON.parse(val); return Array.isArray(p) ? p : [] }
  catch { return [] }
}

async function loadArtists(pageOverride = null) {
  loading.value = true
  try {
    const page = pageOverride || currentPage.value
    const params = { page, page_size: pageSize }
    if (searchQuery.value.trim()) params.keyword = searchQuery.value.trim()
    if (dynastyFilter.value) params.dynasty = dynastyFilter.value
    const data = await api.get('/artists', { params })
    totalArtists.value = data.total || 0
    const raw = data.artists || []
    artists.value = raw.map(a => ({
      ...a,
      bio_events: parseJsonArray(a.bio_events),
      masterpieces: parseJsonArray(a.masterpieces),
      tags: parseJsonArray(a.tags),
      art_chronology: parseJsonArray(a.art_chronology),
      character_relations: parseJsonArray(a.character_relations),
      anecdotes: parseJsonArray(a.anecdotes),
      published_works: parseJsonArray(a.published_works),
      references: parseJsonArray(a.references),
      gallery_images: parseJsonArray(a.gallery_images)
    }))
  } catch (e) {
    ElMessage.error('加载画家列表失败: ' + e.message)
  } finally { loading.value = false }
}

async function loadPeriods() {
  try {
    const data = await api.get('/artists/periods')
    periods.value = data.periods || data || []
  } catch (e) { console.warn('加载朝代列表失败', e) }
}

function openCreate() {
  router.push('/admin/artist/new/edit')
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { currentPage.value = 1; loadArtists(1) }, 300)
}

function onDynastyChange() {
  currentPage.value = 1
  loadArtists(1)
}

function onPageChange(page) {
  currentPage.value = page
  loadArtists(page)
}

function openEdit(artist) {
  router.push(`/admin/artist/${encodeURIComponent(artist.name)}/edit`)
}

async function handleDelete(artist) {
  try {
    await ElMessageBox.confirm(`确定删除画家「${artist.name}」？`, '确认删除', { type: 'warning' })
    const data = await api.delete(`/artists/${artist.id}`)
    if (data.success) {
      ElMessage.success('画家已删除')
      await loadArtists(currentPage.value)
    } else { ElMessage.error(data.detail || '删除失败') }
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败: ' + e.message) }
}

async function toggleEnabled(artist) {
  try {
    const data = await api.put(`/artists/${artist.id}`, { enabled: artist.enabled ? 0 : 1 })
    if (data.success) {
      ElMessage.success(artist.enabled ? '画家已禁用' : '画家已启用')
      await loadArtists(currentPage.value)
    }
  } catch (e) { ElMessage.error('操作失败: ' + e.message) }
}

async function handleAiFill(artist) {
  try {
    const data = await api.post(`/artists/${artist.id}/ai-fill`)
    if (data.success) {
      ElMessage.success(data.message || 'AI查询完成')
      await loadArtists(currentPage.value)
    } else { ElMessage.error(data.detail || data.message || 'AI查询失败') }
  } catch (e) { ElMessage.error('AI查询失败: ' + e.message) }
}

onMounted(() => { loadArtists(); loadPeriods() })
</script>

<style scoped>
.artist-info-manager { padding: 0; }
.toolbar { margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.artist-list { display: flex; flex-direction: column; gap: 8px; min-height: 200px; }
.artist-card { background: white; border-radius: 10px; padding: 14px 18px; box-shadow: 0 1px 8px rgba(0,0,0,0.05); }
.artist-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.artist-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.artist-name { font-size: 15px; font-weight: 600; color: #333; }
.artist-actions { display: flex; gap: 6px; flex-shrink: 0; flex-wrap: wrap; }
.artist-actions :deep(.el-button) { display: inline-flex; align-items: center; justify-content: center; }
.artist-actions :deep(.el-button__content) { display: inline-flex; align-items: center; gap: 4px; }
.empty-state { padding: 40px 0; }
.pagination-bar { display: flex; justify-content: center; margin-top: 20px; }
.form-row { display: flex; gap: 16px; flex-wrap: wrap; }
.form-item-half { flex: 1; min-width: 160px; }
.rename-warning { font-size: 12px; color: #e6a23c; margin-top: 4px; }
.avatar-url-row { display: flex; gap: 8px; align-items: center; width: 100%; }
.array-editor { width: 100%; display: flex; flex-direction: column; gap: 4px; }
.array-editor-hint { font-size: 12px; color: #909399; margin: 0 0 8px 0; }
.array-editor-empty { font-size: 12px; color: #c0c4cc; text-align: center; padding: 20px; margin: 0; }
.array-item { border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px 12px; background: #fafafa; }
.array-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.array-item-index { font-size: 11px; color: #909399; font-weight: 600; }
.array-item-fields { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
