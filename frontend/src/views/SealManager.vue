<template>
  <div class="seal-manager">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" plain size="small" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>新增印章
        </el-button>
        <el-button plain size="small" @click="handleExtract" :loading="extracting">
          <el-icon><Download /></el-icon>从作品提取
        </el-button>
      </div>
      <div class="toolbar-right">
        <span class="seal-count">共 {{ total }} 个印章</span>
      </div>
    </div>

    <!-- 卡片网格 -->
    <div v-loading="loading" class="seal-grid">
      <div v-for="seal in seals" :key="seal.id" class="seal-card">
        <div class="seal-images">
          <div v-if="seal.images && seal.images.length > 0" class="seal-thumb-wrapper">
            <img :src="getImageUrl(seal.images[0])" class="seal-thumb" @error="onImageError" />
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

    <!-- 创建/编辑弹窗 -->
    <el-dialog v-model="showEditDialog" :title="editingSeal ? '编辑印章' : '新增印章'" width="520px" class="claude-dialog">
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

        <!-- 图片管理（仅编辑模式） -->
        <template v-if="editingSeal">
          <el-form-item label="印章图片">
            <div class="seal-images-edit">
              <div v-for="(img, idx) in editForm.images" :key="idx" class="seal-img-item">
                <img :src="getImageUrl(img)" class="seal-img-preview" />
                <el-button type="danger" :icon="Delete" circle size="small" class="seal-img-delete" @click="removeImage(idx)" />
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

    <!-- 关联作品弹窗 -->
    <el-dialog v-model="showArtworksDialog" :title="`使用「${artworksSealName}」的作品`" width="640px" class="claude-dialog">
      <div v-loading="artworksLoading" class="artworks-list">
        <div v-for="art in artworks" :key="art.id" class="artwork-item" @click="goToArtwork(art)">
          <img v-if="art.thumbnail_path" :src="`${API_BASE.replace('/api/v1', '')}/static/${art.thumbnail_path.replace(/^data\\\\?/, '').replace(/\\\\/g, '/')}`" class="artwork-thumb" />
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
import { Plus, Edit, Delete, Download, Picture, Stamp } from '@element-plus/icons-vue'
import { sealsApi } from '../api'
import { useRouter } from 'vue-router'

const props = defineProps({
  artist: { type: String, default: '' }
})

const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

// 状态
const seals = ref([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const extracting = ref(false)

// 作者列表
const artistList = ref([])

// 编辑弹窗
const showEditDialog = ref(false)
const showCreateDialog = ref(false)
const editingSeal = ref(null)
const editForm = ref({
  name: '',
  artist_name: '',
  seal_type: '名章',
  description: '',
  images: []
})
const uploadInput = ref(null)

// 作品弹窗
const showArtworksDialog = ref(false)
const artworksSealName = ref('')
const artworks = ref([])
const artworksLoading = ref(false)

// 加载印章列表
async function loadSeals() {
  loading.value = true
  try {
    const params = { limit: 200 }
    if (props.artist && props.artist !== 'all') params.artist = props.artist
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

// 加载作者列表
async function loadArtists() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

// 打开编辑
function openEdit(seal) {
  editingSeal.value = seal
  editForm.value = {
    name: seal.name,
    artist_name: seal.artist_name || '',
    seal_type: seal.seal_type || '名章',
    description: seal.description || '',
    images: seal.images || []
  }
  showEditDialog.value = true
}

// 保存
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
    description: editForm.value.description || ''
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
        await loadSeals()
      } else {
        ElMessage.error(res.message || '创建失败')
      }
    }
  } catch (error) {
    if (error.response?.status === 409) {
      // 重名冲突
      try {
        await ElMessageBox.confirm(
          `印章名「${payload.name}」已存在，是否合并？合并后当前印章将被删除，所有作品中的旧名会替换为新名。`,
          '印章名冲突',
          { confirmButtonText: '合并', cancelButtonText: '取消', type: 'warning' }
        )
        // 用户选择合并
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

// 删除
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

// 从作品提取
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

// 图片上传
function triggerUpload() {
  uploadInput.value?.click()
}

async function handleUpload(event) {
  const file = event.target.files?.[0]
  if (!file || !editingSeal.value) return
  try {
    const res = await sealsApi.uploadImage(editingSeal.value.id, file)
    if (res.success) {
      editForm.value.images = res.images || []
      ElMessage.success('图片上传成功')
    }
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.message || e))
  } finally {
    if (uploadInput.value) uploadInput.value.value = ''
  }
}

async function removeImage(idx) {
  if (!editingSeal.value) return
  try {
    const res = await sealsApi.deleteImage(editingSeal.value.id, idx)
    if (res.success) {
      editForm.value.images = res.images || []
      ElMessage.success('图片已删除')
    }
  } catch (e) {
    ElMessage.error('删除图片失败: ' + (e.message || e))
  }
}

// 关联作品
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
  showArtworksDialog.value = false
  router.push(`/tubi/${art.image_id}`)
}

// 图片URL处理
function getImageUrl(path) {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return `${API_BASE.replace('/api/v1', '')}${path}`
}

function onImageError(e) {
  e.target.style.display = 'none'
}

// 监听 showCreateDialog
watch(showCreateDialog, (val) => {
  if (val) {
    editingSeal.value = null
    editForm.value = { name: '', artist_name: '', seal_type: '名章', description: '', images: [] }
    showEditDialog.value = true
    showCreateDialog.value = false
  }
})

// 监听顶部作者过滤变化
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
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  min-height: 200px;
}

.seal-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.2s, box-shadow 0.2s;
}

.seal-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.seal-images {
  width: 100%;
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.seal-thumb-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid #f0ede6;
}

.seal-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.seal-thumb-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  background: #f5f3ee;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0b8a8;
}

.seal-info {
  text-align: center;
  width: 100%;
  margin-bottom: 12px;
}

.seal-name {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.seal-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: #888;
}

.seal-type-tag {
  font-size: 11px;
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

/* 编辑弹窗图片管理 */
.seal-images-edit {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.seal-img-item {
  position: relative;
  width: 80px;
  height: 80px;
}

.seal-img-preview {
  width: 100%;
  height: 100%;
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

.seal-img-upload {
  width: 80px;
  height: 80px;
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

/* 作品列表 */
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
</style>
