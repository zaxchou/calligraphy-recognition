<template>
  <div class="seal-manager">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button v-if="!batchMode" type="primary" plain size="small" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>新增印章
        </el-button>
        <el-button v-if="!batchMode" plain size="small" @click="handleExtract" :loading="extracting">
          <el-icon><Download /></el-icon>从作品提取
        </el-button>
        <el-button v-if="!batchMode" plain size="small" @click="batchMode = true">
          <el-icon><Check /></el-icon>批量操作
        </el-button>
        <template v-if="batchMode">
          <el-button type="danger" plain size="small" :disabled="selectedIds.length === 0" @click="handleBatchDelete">
            <el-icon><Delete /></el-icon>删除选中（{{ selectedIds.length }}）
          </el-button>
          <el-button plain size="small" @click="cancelBatch">
            取消
          </el-button>
        </template>
      </div>
      <div class="toolbar-right">
        <span class="seal-count">共 {{ total }} 个印章</span>
      </div>
    </div>

    <div v-loading="loading" class="seal-grid">
      <div v-for="seal in seals" :key="seal.id" class="seal-card" :class="{ 'seal-card-selected': batchMode && selectedIds.includes(seal.id) }">
        <el-checkbox v-if="batchMode" :model-value="selectedIds.includes(seal.id)" @change="toggleSelect(seal.id)" class="seal-checkbox" />
        <div class="seal-images">
          <div v-if="seal.images && seal.images.length > 0" class="seal-thumb-wrapper">
            <img :src="getImageUrl(seal.images[0].thumb_url || seal.images[0].path || seal.images[0])" class="seal-thumb" @error="onImageError" />
          </div>
          <div v-else class="seal-thumb-placeholder">
            <el-icon :size="28"><Stamp /></el-icon>
          </div>
        </div>
        <div class="seal-info">
          <div class="seal-name">{{ seal.name }}</div>
          <div class="seal-meta">
            <span v-if="seal.artist_name" class="seal-artist">{{ seal.artist_name }}</span>
            <el-tag v-if="seal.seal_type" size="small" :type="seal.seal_type === '名章' ? undefined : 'info'" class="seal-type-tag">
              {{ seal.seal_type }}
            </el-tag>
          </div>
        </div>
        <div class="seal-actions">
          <el-tooltip content="编辑" placement="top">
            <el-button :icon="Edit" circle size="small" @click="openEdit(seal)" />
          </el-tooltip>
          <el-tooltip content="作品" placement="top">
            <el-button :icon="Picture" circle size="small" @click="openArtworks(seal)" />
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <el-button :icon="Delete" circle size="small" type="danger" @click="handleDelete(seal)" />
          </el-tooltip>
        </div>
      </div>
      <div v-if="!loading && seals.length === 0" class="empty-state">
        <el-empty description="暂无印章数据" />
      </div>
    </div>

    <el-dialog v-model="showEditDialog" :title="editingSeal ? '编辑印章' : '新增印章'" width="560px" class="claude-dialog">
      <el-form :model="editForm" label-position="top" class="modern-form">
        <el-form-item label="印章名称" required>
          <el-input v-model="editForm.name" placeholder="请输入印章名称" />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="画家" class="form-item-half">
            <el-select v-model="editForm.artist_name" placeholder="选择画家" clearable filterable allow-create style="width: 100%">
              <el-option v-for="a in artistList" :key="a" :label="a" :value="a" />
            </el-select>
          </el-form-item>
          <el-form-item label="印章类型" class="form-item-half">
            <el-select v-model="editForm.seal_type" placeholder="选择类型" style="width: 100%">
              <el-option label="名章" value="名章" />
              <el-option label="闲章" value="闲章" />
              <el-option label="收藏印" value="收藏印" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" placeholder="印章描述（可选）" />
        </el-form-item>
        <el-form-item label="来源出处">
          <el-input v-model="editForm.source" type="textarea" :rows="2" placeholder="如：上海博物馆编《中国书画家印鉴款识》（文物出版社，1987.12）" />
        </el-form-item>

        <template v-if="editingSeal">
          <el-form-item label="印章图片">
            <div class="seal-images-edit">
              <div v-for="(img, idx) in editForm.images" :key="img.id || idx" class="seal-img-item">
                <img :src="getImageUrl(img.path || img)" class="seal-img-preview" />
                <el-button type="danger" :icon="Delete" circle size="small" class="seal-img-delete" @click="removeImage(img, idx)" />
                <el-input v-model="img.description" size="small" placeholder="版本说明，如：早年使用" class="seal-img-desc" @change="saveImageDesc(img)" />
              </div>
              <div class="seal-img-upload" @click="triggerUpload">
                <el-icon :size="24"><Plus /></el-icon>
              </div>
            </div>
            <input type="file" ref="uploadInput" accept="image/*" style="display: none;" @change="handleUpload" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="印章图片">
            <div class="seal-images-edit">
              <div v-for="(pf, idx) in pendingFiles" :key="'pf-'+idx" class="seal-img-item">
                <img :src="pf.previewUrl" class="seal-img-preview" />
                <el-button type="danger" :icon="Delete" circle size="small" class="seal-img-delete" @click="removePendingFile(idx)" />
              </div>
              <div class="seal-img-upload" @click="triggerUpload">
                <el-icon :size="24"><Plus /></el-icon>
              </div>
            </div>
            <input type="file" ref="uploadInput" accept="image/*" style="display: none;" @change="handleUpload" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showArtworksDialog" :title="`使用「${artworksSealName}」的作品（${artworks.length}幅）`" width="640px" class="claude-dialog">
      <div v-loading="artworksLoading" class="artworks-list">
        <div v-for="art in artworks" :key="art.id" class="artwork-item" @click="goToArtwork(art)">
          <img v-if="art.thumbnail_path" :src="`${API_BASE.replace('/api/v1', '')}/static/${art.thumbnail_path.replace(/^data\//, '').replace(/\\/g, '/')}`" class="artwork-thumb" />
          <div v-else class="artwork-thumb-placeholder"><el-icon><Picture /></el-icon></div>
          <div class="artwork-info">
            <div class="artwork-title">{{ art.title || '未命名' }}</div>
            <div class="artwork-meta">
              <span v-if="art.artist">{{ art.artist }}</span>
              <span v-if="art.year">{{ art.year }}年</span>
              <el-tag v-if="art.status" size="small" :type="art.status === 'completed' ? 'success' : 'warning'">
                {{ art.status === 'completed' ? '已完成' : art.status }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="!artworksLoading && artworks.length === 0" class="empty-state">
          <el-empty description="暂无使用此印章的作品" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Download, Picture, Stamp, Check } from '@element-plus/icons-vue'
import { sealsApi } from '../api'
import { useRouter } from 'vue-router'

const props = defineProps({
  artist: { type: String, default: '' },
  libraryId: { type: Number, default: null }
})

const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const seals = ref([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const extracting = ref(false)

const batchMode = ref(false)
const selectedIds = ref([])

const artistList = ref([])

const showEditDialog = ref(false)
const showCreateDialog = ref(false)
const editingSeal = ref(null)
const editForm = ref({
  name: '',
  artist_name: '',
  seal_type: '名章',
  description: '',
  source: '',
  images: []
})
const uploadInput = ref(null)
const pendingFiles = ref([])

const showArtworksDialog = ref(false)
const artworksSealName = ref('')
const artworks = ref([])
const artworksLoading = ref(false)

async function loadSeals() {
  loading.value = true
  try {
    const params = { limit: 200 }
    if (props.artist && props.artist !== 'all') params.artist = props.artist
    if (props.libraryId) params.library_id = props.libraryId
    const res = await sealsApi.list(params)
    if (res.success) {
      seals.value = res.seals
      total.value = res.total
    }
  } catch (e) {
    ElMessage.error('加载印章失败: ' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function loadArtists() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

function openEdit(seal) {
  editingSeal.value = seal
  editForm.value = {
    name: seal.name,
    artist_name: seal.artist_name || '',
    seal_type: seal.seal_type || '名章',
    description: seal.description || '',
    source: seal.source || '',
    images: (seal.images || []).map(img => ({
      id: img.id || null,
      path: typeof img === 'string' ? img : (img.path || ''),
      description: typeof img === 'string' ? '' : (img.description || ''),
      sort_order: img.sort_order || 0
    }))
  }
  showEditDialog.value = true
}

async function handleSave() {
  if (!editForm.value.name?.trim()) {
    ElMessage.warning('请输入印章名称')
    return
  }

  saving.value = true
  const payload = {
    name: editForm.value.name.trim(),
    artist_name: editForm.value.artist_name || null,
    seal_type: editForm.value.seal_type || '名章',
    description: editForm.value.description || '',
    source: editForm.value.source || ''
  }

  try {
    if (editingSeal.value) {
      const res = await sealsApi.update(editingSeal.value.id, payload)
      if (res.success) {
        ElMessage.success('印章更新成功')
        showEditDialog.value = false
        await loadSeals()
      } else {
        ElMessage.error(res.message || '更新失败')
      }
    } else {
      const res = await sealsApi.create(payload)
      if (res.success) {
        ElMessage.success('印章创建成功')
        showEditDialog.value = false
        if (pendingFiles.value.length > 0 && res.id) {
          for (const pf of pendingFiles.value) {
            try {
              await sealsApi.uploadImage(res.id, pf.file, '')
            } catch (_) {}
            URL.revokeObjectURL(pf.previewUrl)
          }
          pendingFiles.value = []
        }
        await loadSeals()
      } else {
        ElMessage.error(res.message || '创建失败')
      }
    }
  } catch (error) {
    if (error.response?.status === 409) {
      try {
        await ElMessageBox.confirm(
          `印章名「${payload.name}」已存在，是否合并？合并后当前印章将被删除，所有作品中的旧名会替换为新名。`,
          '印章名冲突',
          { confirmButtonText: '合并', cancelButtonText: '取消', type: 'warning' }
        )
        payload.merge_on_conflict = true
        const mergeRes = await sealsApi.update(editingSeal.value.id, payload)
        if (mergeRes.success) {
          ElMessage.success('印章已合并')
          showEditDialog.value = false
          await loadSeals()
        }
      } catch (mergeErr) {
        if (mergeErr !== 'cancel') {
          ElMessage.error('合并失败: ' + (mergeErr.message || mergeErr))
        }
      }
    } else {
      ElMessage.error('保存失败: ' + (error.message || error))
    }
  } finally {
    saving.value = false
  }
}

async function handleDelete(seal) {
  try {
    await ElMessageBox.confirm(
      `确定要删除印章「${seal.name}」吗？所有作品中的该印章引用也会被清除。`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    const res = await sealsApi.delete(seal.id)
    if (res.success) {
      ElMessage.success(res.message || '删除成功')
      await loadSeals()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.message || e))
    }
  }
}

async function handleExtract() {
  extracting.value = true
  try {
    const res = await sealsApi.extract()
    if (res.success) {
      ElMessage.success(res.message)
      await loadSeals()
    }
  } catch (e) {
    ElMessage.error('提取失败: ' + (e.message || e))
  } finally {
    extracting.value = false
  }
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function cancelBatch() {
  batchMode.value = false
  selectedIds.value = []
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) return
  const count = selectedIds.value.length
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${count} 个印章吗？所有作品中的这些印章引用也会被清除。`,
      '批量删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    const res = await sealsApi.batchDelete(selectedIds.value)
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${count} 个印章`)
      batchMode.value = false
      selectedIds.value = []
      await loadSeals()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('批量删除失败: ' + (e.message || e))
    }
  }
}

function triggerUpload() {
  uploadInput.value?.click()
}

async function handleUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!editingSeal.value) {
    pendingFiles.value.push({
      file,
      previewUrl: URL.createObjectURL(file)
    })
    if (uploadInput.value) uploadInput.value.value = ''
    return
  }
  try {
    const res = await sealsApi.uploadImage(editingSeal.value.id, file, '')
    if (res.success) {
      editForm.value.images = (res.images || []).map(img => ({
        id: img.id,
        path: img.path,
        description: img.description || '',
        sort_order: img.sort_order || 0
      }))
      ElMessage.success('图片上传成功')
    }
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.message || e))
  } finally {
    if (uploadInput.value) uploadInput.value.value = ''
  }
}

async function saveImageDesc(img) {
  if (!editingSeal.value || !img.id) return
  try {
    await sealsApi.updateImage(editingSeal.value.id, img.id, { description: img.description || '' })
  } catch (e) {
    console.error('保存图片描述失败', e)
  }
}

async function removeImage(img, idx) {
  if (!editingSeal.value) return
  const imgId = img.id
  if (!imgId) {
    editForm.value.images.splice(idx, 1)
    return
  }
  try {
    const res = await sealsApi.deleteImage(editingSeal.value.id, imgId)
    if (res.success) {
      editForm.value.images = (res.images || []).map(i => ({
        id: i.id,
        path: i.path,
        description: i.description || '',
        sort_order: i.sort_order || 0
      }))
      ElMessage.success('图片已删除')
    }
  } catch (e) {
    ElMessage.error('删除图片失败: ' + (e.message || e))
  }
}

async function openArtworks(seal) {
  artworksSealName.value = seal.name
  showArtworksDialog.value = true
  artworksLoading.value = true
  try {
    const res = await sealsApi.artworks(seal.id)
    if (res.success) {
      artworks.value = res.artworks || []
    }
  } catch (e) {
    ElMessage.error('加载关联作品失败: ' + (e.message || e))
  } finally {
    artworksLoading.value = false
  }
}

function goToArtwork(art) {
  const route = router.resolve({ name: 'TibaDetail', params: { id: art.image_id } })
  window.open(route.href, '_blank')
}

function getImageUrl(path) {
  if (!path) return ''
  const p = typeof path === 'string' ? path : (path.path || '')
  if (!p) return ''
  if (p.startsWith('http')) return p
  return `${API_BASE.replace('/api/v1', '')}${p}`
}

function onImageError(e) {
  e.target.style.display = 'none'
}

function removePendingFile(idx) {
  const pf = pendingFiles.value[idx]
  if (pf) URL.revokeObjectURL(pf.previewUrl)
  pendingFiles.value.splice(idx, 1)
}

watch(showCreateDialog, (val) => {
  if (val) {
    editingSeal.value = null
    editForm.value = { name: '', artist_name: '', seal_type: '名章', description: '', source: '', images: [] }
    pendingFiles.value = []
    showEditDialog.value = true
    showCreateDialog.value = false
  }
})

watch(() => props.artist, () => { loadSeals() })

onMounted(async () => {
  await loadArtists()
  await loadSeals()
})
</script>

<style scoped>
.seal-manager {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-right {
  color: #888;
  font-size: 13px;
}

.seal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 12px;
  min-height: 200px;
}

.seal-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
}

.seal-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.1);
}

.seal-card-selected {
  border: 2px solid #c96442;
  background: #fdf8f6;
}

.seal-checkbox {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 1;
}

.seal-images {
  width: 100%;
  display: flex;
  justify-content: center;
  margin-bottom: 0;
}

.seal-thumb-wrapper {
  max-width: 64px;
  max-height: 64px;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid #f0ede6;
  display: flex;
  align-items: center;
  justify-content: center;
}

.seal-thumb {
  max-width: 64px;
  max-height: 64px;
  object-fit: contain;
}

.seal-thumb-placeholder {
  width: 60px;
  height: 60px;
  border-radius: 6px;
  background: #f5f3ee;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0b8a8;
}

.seal-info {
  text-align: center;
  width: 100%;
  margin-bottom: 0;
}

.seal-name {
  font-size: 12px;
  font-weight: 600;
  color: #333;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.seal-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 11px;
  color: #888;
}

.seal-type-tag {
  font-size: 10px;
}

.seal-actions {
  display: flex;
  gap: 6px;
}

.seal-actions :deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.seal-actions :deep(.el-button__content) {
  display: inline-flex;
  align-items: center;
}

.seal-images-edit {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.seal-img-item {
  position: relative;
  width: 90px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.seal-img-preview {
  width: 90px;
  height: 90px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e8e5de;
}

.seal-img-delete {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 22px;
  height: 22px;
}

.seal-img-desc {
  font-size: 11px;
}

.seal-img-desc :deep(.el-input__wrapper) {
  padding: 2px 6px;
}

.seal-img-upload {
  width: 90px;
  height: 90px;
  border: 2px dashed #d0ccc2;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0a898;
  cursor: pointer;
  transition: border-color 0.2s;
}

.seal-img-upload:hover {
  border-color: #c96442;
  color: #c96442;
}

.artworks-list {
  max-height: 400px;
  overflow-y: auto;
}

.artwork-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.artwork-item:hover {
  background: #f8f7f3;
}

.artwork-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e8e5de;
}

.artwork-thumb-placeholder {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  background: #f5f3ee;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0b8a8;
}

.artwork-info {
  flex: 1;
  min-width: 0;
}

.artwork-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artwork-meta {
  font-size: 12px;
  color: #888;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.empty-state {
  grid-column: 1 / -1;
  padding: 40px 0;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-item-half {
  flex: 1;
}

:deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

:deep(.el-button__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

</style>
