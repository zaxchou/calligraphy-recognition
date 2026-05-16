<template>
  <div class="artist-info-manager">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索画家姓名..."
          clearable
          size="small"
          style="width: 200px"
          @input="onSearchInput"
        />
        <el-select
          v-model="dynastyFilter"
          placeholder="筛选朝代"
          clearable
          size="small"
          style="width: 130px"
        >
          <el-option
            v-for="p in periods"
            :key="p"
            :label="p"
            :value="p"
          />
        </el-select>
      </div>
      <el-button type="primary" plain size="small" @click="openCreate">
        <el-icon><Plus /></el-icon>新增画家
      </el-button>
    </div>

    <!-- 画家列表（精简版） -->
    <div v-loading="loading" class="artist-list">
      <div v-for="artist in filteredArtists" :key="artist.id" class="artist-card">
        <div class="artist-row">
          <div class="artist-main">
            <span class="artist-name">{{ artist.name }}</span>
            <el-tag v-if="artist.dynasty" size="small">{{ artist.dynasty }}</el-tag>
            <el-tag v-if="artist.alias" size="small" type="info">{{ artist.alias }}</el-tag>
            <template v-if="artist.birth_year || artist.death_year">
              <el-tag size="small" type="info">
                {{ artist.birth_year || '?' }}-{{ artist.death_year || '?' }}
              </el-tag>
            </template>
            <el-tag v-if="!artist.enabled" size="small" type="danger">已禁用</el-tag>
          </div>
          <div class="artist-actions">
            <el-button size="small" @click="openEdit(artist)">编辑</el-button>
            <el-button size="small" type="primary" plain @click="handleAiFill(artist)" :loading="aiFillLoading[artist.id]">
              <el-icon><MagicStick /></el-icon>AI查询
            </el-button>
            <el-button size="small" :type="artist.enabled ? 'warning' : 'success'" plain @click="toggleEnabled(artist)">
              {{ artist.enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(artist)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-if="!loading && artists.length === 0" class="empty-state">
        <el-empty description="暂无画家数据" />
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog
      v-model="showEditDialog"
      :title="editingArtist ? '编辑画家' : '新增画家'"
      width="640px"
      class="claude-dialog"
      destroy-on-close
    >
      <el-tabs v-model="activeTab" type="border-card">
        <!-- Basic 标签页 -->
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <div class="form-row">
              <el-form-item label="画家姓名" required class="form-item-half">
                <el-input v-model="editForm.name" placeholder="如：李鱓" />
                <div v-if="editingArtist && editForm.name !== editingArtist.name" class="rename-warning">
                  ⚠️ 修改姓名将同步更新所有相关画作的作者信息
                </div>
              </el-form-item>
              <el-form-item label="字号" class="form-item-half">
                <el-input v-model="editForm.alias" placeholder="如：复堂" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="朝代" class="form-item-half">
                <el-select v-model="editForm.dynasty" filterable allow-create clearable placeholder="选择或输入朝代" style="width:100%">
                  <el-option
                    v-for="p in periods"
                    :key="p"
                    :label="p"
                    :value="p"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="籍贯" class="form-item-half">
                <el-input v-model="editForm.hometown" placeholder="如：江苏兴化" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="出生年份" class="form-item-half">
                <el-input v-model.number="editForm.birth_year" placeholder="如：1686" type="number" />
              </el-form-item>
              <el-form-item label="卒年" class="form-item-half">
                <el-input v-model.number="editForm.death_year" placeholder="如：1762" type="number" />
              </el-form-item>
            </div>
            <el-form-item label="背景简介">
              <el-input v-model="editForm.background" type="textarea" :rows="2" placeholder="画家背景简介" />
            </el-form-item>
            <el-form-item label="专长">
              <el-input v-model="editForm.specialties" placeholder="如：写意花鸟" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Bio 标签页 -->
        <el-tab-pane label="生平与头像" name="bio">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <el-form-item label="头像 URL">
              <div class="avatar-url-row">
                <el-input v-model="editForm.avatar_url" placeholder="https://..." />
                <el-avatar v-if="editForm.avatar_url" :src="editForm.avatar_url" :size="40" shape="square" style="flex-shrink:0" />
              </div>
            </el-form-item>
            <el-form-item label="生平简介">
              <el-input v-model="editForm.biography" type="textarea" :rows="4" placeholder="详细生平介绍" />
            </el-form-item>
            <el-form-item label="生平时间线">
              <div class="bio-events-list">
                <div v-for="(evt, idx) in editForm.bio_events" :key="idx" class="bio-event-item">
                  <div class="bio-event-row">
                    <el-input v-model="evt.year" placeholder="年份" size="small" style="width:80px" type="number" />
                    <el-input v-model="evt.type" placeholder="类型" size="small" style="width:100px" />
                    <el-input v-model="evt.title" placeholder="标题" size="small" style="width:140px" />
                    <el-button type="danger" size="small" plain @click="removeBioEvent(idx)">删除</el-button>
                  </div>
                  <el-input v-model="evt.description" placeholder="详细描述" size="small" style="margin-top:4px" />
                </div>
                <el-button type="primary" size="small" plain @click="addBioEvent">
                  <el-icon><Plus /></el-icon>添加事件
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Advanced 标签页 -->
        <el-tab-pane label="高级信息" name="advanced">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <el-form-item label="画派">
              <el-input v-model="editForm.art_school" placeholder="如：扬州八怪，逗号分隔" />
            </el-form-item>
            <el-form-item label="代表作">
              <el-select
                v-model="editForm.masterpieces"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="输入代表作名称后回车添加"
                style="width:100%"
              />
            </el-form-item>
            <el-form-item label="标签">
              <el-select
                v-model="editForm.tags"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="输入标签后回车添加"
                style="width:100%"
              />
            </el-form-item>
            <el-form-item label="百度百科 URL">
              <el-input v-model="editForm.baidu_url" placeholder="https://baike.baidu.com/..." />
            </el-form-item>
            <el-form-item label="推荐展示">
              <el-switch
                v-model="editForm.featured"
                :active-value="1"
                :inactive-value="0"
                active-text="推荐"
                inactive-text="不推荐"
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick } from '@element-plus/icons-vue'
import api from '@/api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const props = defineProps({
  artist: { type: Object, default: null },
  libraryId: { type: [Number, String], default: null }
})

// ── 列表状态 ──
const artists = ref([])
const loading = ref(false)
const searchQuery = ref('')
const dynastyFilter = ref('')
const periods = ref([])

// ── 编辑状态 ──
const saving = ref(false)
const aiFillLoading = reactive({})
const showEditDialog = ref(false)
const editingArtist = ref(null)
const activeTab = ref('basic')

const editForm = ref({
  name: '',
  alias: '',
  dynasty: '',
  hometown: '',
  avatar_url: '',
  birth_year: null,
  death_year: null,
  biography: '',
  background: '',
  specialties: '',
  bio_events: [],
  art_school: '',
  masterpieces: [],
  tags: [],
  baidu_url: '',
  featured: 0
})

const filteredArtists = computed(() => {
  let list = [...artists.value]
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(a => a.name.toLowerCase().includes(q))
  }
  if (dynastyFilter.value) {
    list = list.filter(a => a.dynasty === dynastyFilter.value)
  }
  list.sort((a, b) => {
    if (a.enabled && !b.enabled) return -1
    if (!a.enabled && b.enabled) return 1
    return a.id - b.id
  })
  return list
})

function parseJsonArray(val) {
  if (!val) return []
  if (Array.isArray(val)) return val
  try {
    const p = JSON.parse(val)
    return Array.isArray(p) ? p : []
  } catch { return [] }
}

async function loadArtists() {
  loading.value = true
  try {
    const data = await api.get('/artists', { params: { page_size: 200 } })
    const raw = data.artists || data || []
    artists.value = raw.map(a => ({
      ...a,
      bio_events: parseJsonArray(a.bio_events),
      masterpieces: parseJsonArray(a.masterpieces),
      tags: parseJsonArray(a.tags)
    }))
  } catch (e) {
    ElMessage.error('加载画家列表失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function loadPeriods() {
  try {
    const res = await fetch(`${API_BASE}/artists/periods`)
    const data = await res.json()
    periods.value = data.periods || data || []
  } catch (e) {
    console.warn('加载朝代列表失败', e)
  }
}

function onSearchInput() {
}

function openCreate() {
  editingArtist.value = null
  activeTab.value = 'basic'
  editForm.value = {
    name: '',
    alias: '',
    dynasty: '',
    hometown: '',
    avatar_url: '',
    birth_year: null,
    death_year: null,
    biography: '',
    background: '',
    specialties: '',
    bio_events: [],
    art_school: '',
    masterpieces: [],
    tags: [],
    baidu_url: '',
    featured: 0
  }
  showEditDialog.value = true
}

function openEdit(artist) {
  editingArtist.value = artist
  activeTab.value = 'basic'
  editForm.value = {
    name: artist.name || '',
    alias: artist.alias || '',
    dynasty: artist.dynasty || '',
    hometown: artist.hometown || '',
    avatar_url: artist.avatar_url || '',
    birth_year: artist.birth_year ?? null,
    death_year: artist.death_year ?? null,
    biography: artist.biography || '',
    background: artist.background || '',
    specialties: artist.specialties || '',
    bio_events: Array.isArray(artist.bio_events) ? artist.bio_events.map(e => ({ ...e })) : [],
    art_school: artist.art_school || '',
    masterpieces: Array.isArray(artist.masterpieces) ? [...artist.masterpieces] : [],
    tags: Array.isArray(artist.tags) ? [...artist.tags] : [],
    baidu_url: artist.baidu_url || '',
    featured: artist.featured ?? 0
  }
  showEditDialog.value = true
}

function addBioEvent() {
  editForm.value.bio_events.push({ year: '', type: '', title: '', description: '' })
}

function removeBioEvent(idx) {
  editForm.value.bio_events.splice(idx, 1)
}

async function handleSave() {
  if (!editForm.value.name?.trim()) {
    ElMessage.warning('请输入画家姓名')
    return
  }

  if (editingArtist.value && editForm.value.name !== editingArtist.value.name) {
    try {
      await ElMessageBox.confirm(
        `修改姓名将从「${editingArtist.value.name}」改为「${editForm.value.name}」，所有相关画作的作者信息也会同步更新。确认修改？`,
        '确认修改姓名',
        { confirmButtonText: '确认修改', cancelButtonText: '取消', type: 'warning' }
      )
    } catch { return }
  }

  saving.value = true
  try {
    const payload = {
      name: editForm.value.name.trim(),
      alias: editForm.value.alias,
      dynasty: editForm.value.dynasty,
      hometown: editForm.value.hometown,
      avatar_url: editForm.value.avatar_url,
      birth_year: editForm.value.birth_year || null,
      death_year: editForm.value.death_year || null,
      biography: editForm.value.biography,
      background: editForm.value.background,
      specialties: editForm.value.specialties,
      bio_events: JSON.stringify(editForm.value.bio_events),
      art_school: editForm.value.art_school,
      masterpieces: JSON.stringify(editForm.value.masterpieces),
      tags: JSON.stringify(editForm.value.tags),
      baidu_url: editForm.value.baidu_url,
      featured: editForm.value.featured
    }

    if (editingArtist.value) {
      const data = await api.put(`/artists/${editingArtist.value.id}`, payload)
      if (data.success) {
        if (editForm.value.name !== editingArtist.value.name) {
          try {
            await api.post(`/artists/${editingArtist.value.id}/sync-name`, {
              old_name: editingArtist.value.name,
              new_name: editForm.value.name
            })
          } catch (e) { console.error('同步画家姓名失败', e) }
        }
        ElMessage.success('画家信息已更新')
        showEditDialog.value = false
        await loadArtists()
      } else {
        ElMessage.error(data.detail || data.message || '保存失败')
      }
    } else {
      const data = await api.post('/artists', payload)
      if (data.success) {
        ElMessage.success('画家创建成功')
        showEditDialog.value = false
        await loadArtists()
      } else {
        ElMessage.error(data.detail || data.message || '保存失败')
      }
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function handleDelete(artist) {
  try {
    await ElMessageBox.confirm(`确定删除画家「${artist.name}」？`, '确认删除', { type: 'warning' })
    const data = await api.delete(`/artists/${artist.id}`)
    if (data.success) {
      ElMessage.success('画家已删除')
      await loadArtists()
    } else {
      ElMessage.error(data.detail || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败: ' + e.message)
  }
}

async function toggleEnabled(artist) {
  try {
    const data = await api.put(`/artists/${artist.id}`, { enabled: artist.enabled ? 0 : 1 })
    if (data.success) {
      ElMessage.success(artist.enabled ? '画家已禁用' : '画家已启用')
      await loadArtists()
    }
  } catch (e) {
    ElMessage.error('操作失败: ' + e.message)
  }
}

async function handleAiFill(artist) {
  aiFillLoading[artist.id] = true
  try {
    const data = await api.post(`/artists/${artist.id}/ai-fill`)
    if (data.success) {
      ElMessage.success(data.message || 'AI查询完成')
      await loadArtists()
    } else {
      ElMessage.error(data.detail || data.message || 'AI查询失败')
    }
  } catch (e) {
    ElMessage.error('AI查询失败: ' + e.message)
  } finally {
    aiFillLoading[artist.id] = false
  }
}

onMounted(() => {
  loadArtists()
  loadPeriods()
})
</script>

<style scoped>
.artist-info-manager { padding: 0; }
.toolbar { margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
.toolbar-left { display: flex; gap: 8px; align-items: center; }
.artist-list { display: flex; flex-direction: column; gap: 8px; min-height: 200px; }
.artist-card { background: white; border-radius: 10px; padding: 14px 18px; box-shadow: 0 1px 8px rgba(0, 0, 0, 0.05); }
.artist-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.artist-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.artist-name { font-size: 15px; font-weight: 600; color: #333; }
.artist-actions { display: flex; gap: 6px; flex-shrink: 0; }
.artist-actions :deep(.el-button) { display: inline-flex; align-items: center; justify-content: center; }
.artist-actions :deep(.el-button__content) { display: inline-flex; align-items: center; gap: 4px; }
.empty-state { padding: 40px 0; }
.form-row { display: flex; gap: 16px; }
.form-item-half { flex: 1; }
.rename-warning { font-size: 12px; color: #e6a23c; margin-top: 4px; }
.avatar-url-row { display: flex; gap: 8px; align-items: center; width: 100%; }
.avatar-url-row .el-input { flex: 1; }
.bio-events-list { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.bio-event-item { border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px; background: #fafafa; }
.bio-event-row { display: flex; gap: 6px; align-items: center; }
</style>
