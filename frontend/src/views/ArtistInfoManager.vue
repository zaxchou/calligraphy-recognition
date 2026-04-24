<template>
  <div class="artist-info-manager">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" plain size="small" @click="openCreate">
        <el-icon><Plus /></el-icon>新增画家
      </el-button>
    </div>

    <!-- 画家列表 -->
    <div v-loading="loading" class="artist-list">
      <div v-for="artist in artists" :key="artist.id" class="artist-card">
        <div class="artist-header">
          <div class="artist-name">{{ artist.name }}</div>
          <el-tag v-if="artist.birth_year" size="small" type="info">{{ artist.birth_year }}年生</el-tag>
          <el-tag v-if="!artist.enabled" size="small" type="danger">已禁用</el-tag>
        </div>
        <div v-if="artist.background" class="artist-background">{{ artist.background }}</div>
        <div class="artist-details">
          <div v-if="artist.sentiment_note" class="detail-item">
            <span class="detail-label">情感倾向：</span>{{ artist.sentiment_note }}
          </div>
          <div v-if="artist.theme_note" class="detail-item">
            <span class="detail-label">主题倾向：</span>{{ artist.theme_note }}
          </div>
          <div v-if="artist.specialties" class="detail-item">
            <span class="detail-label">专长：</span>{{ artist.specialties }}
          </div>
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
      <div v-if="!loading && artists.length === 0" class="empty-state">
        <el-empty description="暂无画家数据" />
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog v-model="showEditDialog" :title="editingArtist ? '编辑画家' : '新增画家'" width="560px" class="claude-dialog">
      <el-form :model="editForm" label-position="top" class="modern-form">
        <div class="form-row">
          <el-form-item label="画家姓名" required class="form-item-half">
            <el-input v-model="editForm.name" placeholder="如：李鱓" />
          </el-form-item>
          <el-form-item label="出生年份" class="form-item-half">
            <el-input v-model.number="editForm.birth_year" placeholder="如：1686" />
          </el-form-item>
        </div>
        <el-form-item label="背景简介">
          <el-input v-model="editForm.background" type="textarea" :rows="2" placeholder="画家背景简介" />
        </el-form-item>
        <el-form-item label="情感倾向说明">
          <el-input v-model="editForm.sentiment_note" type="textarea" :rows="2" placeholder="如：晚年多悲凉之感" />
        </el-form-item>
        <el-form-item label="主题倾向说明">
          <el-input v-model="editForm.theme_note" type="textarea" :rows="2" placeholder="如：善画花鸟虫鱼" />
        </el-form-item>
        <el-form-item label="主题别名（逗号分隔）">
          <el-input v-model="editForm.theme_aliases" placeholder="如：花鸟,虫鱼,兰竹" />
        </el-form-item>
        <el-form-item label="专长">
          <el-input v-model="editForm.specialties" placeholder="如：写意花鸟" />
        </el-form-item>
        <el-form-item label="关键词规则（JSON）">
          <el-input v-model="editForm.keyword_rules" type="textarea" :rows="3" placeholder='{"positive": ["..."], "negative": ["..."]}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick } from '@element-plus/icons-vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

const artists = ref([])
const loading = ref(false)
const saving = ref(false)
const aiFillLoading = reactive({})

const showEditDialog = ref(false)
const editingArtist = ref(null)
const editForm = ref({
  name: '',
  birth_year: null,
  background: '',
  sentiment_note: '',
  theme_note: '',
  theme_aliases: '',
  specialties: '',
  keyword_rules: ''
})

async function loadArtists() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/artists`)
    const data = await res.json()
    artists.value = data.artists || data || []
  } catch (e) {
    ElMessage.error('加载画家列表失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingArtist.value = null
  editForm.value = {
    name: '', birth_year: null, background: '', sentiment_note: '',
    theme_note: '', theme_aliases: '', specialties: '', keyword_rules: ''
  }
  showEditDialog.value = true
}

function openEdit(artist) {
  editingArtist.value = artist
  editForm.value = {
    name: artist.name,
    birth_year: artist.birth_year,
    background: artist.background || '',
    sentiment_note: artist.sentiment_note || '',
    theme_note: artist.theme_note || '',
    theme_aliases: artist.theme_aliases || '',
    specialties: artist.specialties || '',
    keyword_rules: artist.keyword_rules || ''
  }
  showEditDialog.value = true
}

async function handleSave() {
  if (!editForm.value.name?.trim()) {
    ElMessage.warning('请输入画家姓名')
    return
  }
  saving.value = true
  try {
    const url = editingArtist.value
      ? `${API_BASE}/artists/${editingArtist.value.id}`
      : `${API_BASE}/artists`
    const method = editingArtist.value ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value)
    })
    const data = await res.json()
    if (data.success) {
      ElMessage.success(editingArtist.value ? '画家信息已更新' : '画家创建成功')
      showEditDialog.value = false
      await loadArtists()
    } else {
      ElMessage.error(data.detail || data.message || '保存失败')
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
    const res = await fetch(`${API_BASE}/artists/${artist.id}`, { method: 'DELETE' })
    const data = await res.json()
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
    const res = await fetch(`${API_BASE}/artists/${artist.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: artist.enabled ? 0 : 1 })
    })
    const data = await res.json()
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
    const res = await fetch(`${API_BASE}/artists/${artist.id}/ai-fill`, { method: 'POST' })
    const data = await res.json()
    if (data.success) {
      ElMessage.success('AI查询完成，信息已填充')
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

onMounted(() => loadArtists())
</script>

<style scoped>
.artist-info-manager {
  padding: 0;
}

.toolbar {
  margin-bottom: 20px;
}

.artist-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}

.artist-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.artist-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.artist-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.artist-background {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  line-height: 1.5;
}

.artist-details {
  margin-bottom: 12px;
}

.detail-item {
  font-size: 13px;
  color: #555;
  margin-bottom: 4px;
}

.detail-label {
  color: #888;
  font-size: 12px;
}

.artist-actions {
  display: flex;
  gap: 8px;
}

.artist-actions :deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.artist-actions :deep(.el-button__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.empty-state {
  padding: 40px 0;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-item-half {
  flex: 1;
}
</style>
