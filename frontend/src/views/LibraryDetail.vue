<template>
  <div class="library-detail-page">
    <!-- 面包屑 + 标题 -->
    <div class="page-header">
      <div>
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/libraries' }">作品库</el-breadcrumb-item>
          <el-breadcrumb-item>{{ library.name }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="header-title-row">
          <h1 class="page-title">{{ library.name }}</h1>
          <el-tag :type="library.visibility === 'public' ? 'success' : 'info'" size="small">
            {{ library.visibility === 'public' ? '公开' : '私有' }}
          </el-tag>
        </div>
        <p class="page-subtitle" v-if="library.artist_name || library.description">
          <template v-if="library.artist_name">{{ library.artist_name }} · </template>
          {{ library.description || '' }}
        </p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="showUploadDialog = true" :disabled="!canEdit">
          <el-icon><Upload /></el-icon> 上传作品
        </el-button>
      </div>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="作品列表" name="artworks">
        <!-- 排序筛选 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <el-select v-model="sortBy" size="small" style="width: 140px" @change="loadArtworks">
              <el-option label="上传时间" value="created_at" />
              <el-option label="画家" value="artist" />
              <el-option label="年代" value="year" />
            </el-select>
            <el-button size="small" @click="toggleOrder">
              {{ order === 'desc' ? '↓ 降序' : '↑ 升序' }}
            </el-button>
          </div>
          <div class="toolbar-right">
            <span class="artwork-count">共 {{ totalArtworks }} 件作品</span>
          </div>
        </div>

        <div v-if="artworkLoading" class="loading-wrap">
          <el-skeleton :rows="3" animated />
        </div>

        <el-empty v-else-if="artworks.length === 0" description="库内还没有作品">
          <el-button type="primary" @click="showUploadDialog = true" :disabled="!canEdit">上传作品</el-button>
        </el-empty>

        <!-- 作品网格 -->
        <div v-else class="artwork-grid">
          <div
            v-for="artwork in artworks"
            :key="artwork.id"
            class="artwork-card"
          >
            <div class="artwork-thumb" @click="openArtworkDetail(artwork)">
              <img v-if="artwork.thumbnail_url" :src="artwork.thumbnail_url" :alt="artwork.title" />
              <el-icon v-else :size="48"><Picture /></el-icon>
              <div class="artwork-status-badge" v-if="artwork.status === 'analyzing'">
                <el-icon class="is-loading"><Loading /></el-icon>
              </div>
              <div class="artwork-hover-actions" v-if="authStore.isLoggedIn">
                <el-button size="small" circle @click.stop="openSuggestEdit(artwork)" title="建议修改">
                  <el-icon><Edit /></el-icon>
                </el-button>
              </div>
            </div>
            <div class="artwork-info" @click="openArtworkDetail(artwork)">
              <h4 class="artwork-title">{{ artwork.title || artwork.filename || '未命名' }}</h4>
              <p class="artwork-meta">
                <span v-if="artwork.artist">{{ artwork.artist }}</span>
                <span v-if="artwork.year">({{ artwork.year }})</span>
              </p>
              <el-tag v-if="artwork.status === 'analyzed'" type="success" size="small">已分析</el-tag>
              <el-tag v-else-if="artwork.status === 'analyzing'" type="warning" size="small">分析中</el-tag>
              <el-tag v-else type="info" size="small">待分析</el-tag>
            </div>
            <div class="artwork-card-footer" v-if="canEdit">
              <el-button link size="small" @click.stop="handleTriggerAnalyze(artwork)">
                <el-icon><VideoPlay /></el-icon> AI分析
              </el-button>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div class="pagination-wrap" v-if="totalArtworks > pageSize">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="totalArtworks"
            layout="prev, pager, next"
            @current-change="loadArtworks"
          />
        </div>
      </el-tab-pane>

      <!-- 管理 Tab -->
      <el-tab-pane name="manage" v-if="isOwner || isMaintainer">
        <template #label>
          管理
          <el-badge v-if="pendingRequestCount > 0" :value="pendingRequestCount" class="manage-badge" />
        </template>

        <el-tabs v-model="manageTab" type="card">
          <el-tab-pane label="库信息" name="info">
            <el-form :model="editForm" label-width="100px" class="manage-form">
              <el-form-item label="名称">
                <el-input v-model="editForm.name" maxlength="100" />
              </el-form-item>
              <el-form-item label="画家">
                <el-input v-model="editForm.artist_name" maxlength="100" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="editForm.description" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="可见性">
                <el-radio-group v-model="editForm.visibility">
                  <el-radio value="private">私有</el-radio>
                  <el-radio value="public">公开</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleUpdateLibrary" :loading="saving">保存修改</el-button>
                <el-button type="danger" plain @click="handleDeleteLibrary" :disabled="library.artwork_count > 0">
                  删除作品库
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="协作者" name="collaborators">
            <div class="manage-section">
              <h3>添加协作者</h3>
              <div class="add-collab-row">
                <el-input v-model="newCollabOpenid" placeholder="输入用户 OpenID（mock_xxx）" size="small" style="width: 300px" />
                <el-select v-model="newCollabRole" size="small" style="width: 120px">
                  <el-option label="浏览者" value="viewer" />
                  <el-option label="编辑者" value="editor" />
                  <el-option label="维护者" value="maintainer" />
                </el-select>
                <el-button type="primary" size="small" @click="handleAddCollaborator">添加</el-button>
              </div>

              <h3 style="margin-top: 24px">当前协作者</h3>
              <el-table :data="collaborators" style="width: 100%" v-if="collaborators.length > 0">
                <el-table-column prop="nickname" label="昵称" />
                <el-table-column prop="role" label="角色">
                  <template #default="{ row }">
                    <el-tag v-if="row.role === 'viewer'" size="small">浏览者</el-tag>
                    <el-tag v-else-if="row.role === 'editor'" type="warning" size="small">编辑者</el-tag>
                    <el-tag v-else-if="row.role === 'maintainer'" type="danger" size="small">维护者</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button type="danger" link size="small" @click="handleRemoveCollaborator(row.user_id)">移除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="暂无协作者" :image-size="60" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="待审核" name="pending">
            <div class="manage-section">
              <div v-if="pendingRequests.length === 0">
                <el-empty description="暂无待审核的变更请求" :image-size="80" />
              </div>
              <div v-else class="request-list">
                <div v-for="req in pendingRequests" :key="req.id" class="request-card">
                  <div class="request-header">
                    <span class="request-type">
                      <el-tag v-if="req.request_type === 'edit_field'" size="small">字段修改</el-tag>
                      <el-tag v-else-if="req.request_type === 'edit_inscription'" type="warning" size="small">题跋修改</el-tag>
                      <el-tag v-else-if="req.request_type === 'adjust_region'" type="danger" size="small">区域调整</el-tag>
                      <el-tag v-else size="small">{{ req.request_type }}</el-tag>
                    </span>
                    <span class="request-meta">
                      {{ req.submitter_name }} · {{ formatTime(req.created_at) }}
                    </span>
                  </div>
                  <div class="request-body">
                    <div class="diff-row">
                      <span class="diff-label">{{ req.field_name }}:</span>
                      <span class="diff-old">{{ req.old_value || '(空)' }}</span>
                      <el-icon><ArrowRight /></el-icon>
                      <span class="diff-new">{{ req.new_value || '(空)' }}</span>
                    </div>
                    <p class="request-summary" v-if="req.change_summary">{{ req.change_summary }}</p>
                  </div>
                  <div class="request-actions">
                    <el-button type="success" size="small" @click="handleReview(req.id, 'approve')">通过</el-button>
                    <el-button type="danger" size="small" @click="handleReview(req.id, 'reject')">拒绝</el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
    </el-tabs>

    <!-- 作品详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="作品详情" size="600px">
      <template v-if="selectedArtwork">
        <div class="drawer-thumb">
          <img v-if="selectedArtwork.thumbnail_url" :src="selectedArtwork.thumbnail_url" style="max-width:100%;max-height:300px;object-fit:contain" />
        </div>
        <el-descriptions :column="2" border style="margin-top:16px">
          <el-descriptions-item label="标题">{{ selectedArtwork.title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="画家">{{ selectedArtwork.artist || '-' }}</el-descriptions-item>
          <el-descriptions-item label="年代">{{ selectedArtwork.year || '-' }}</el-descriptions-item>
          <el-descriptions-item label="时期">{{ selectedArtwork.period || '-' }}</el-descriptions-item>
          <el-descriptions-item label="画材">{{ selectedArtwork.material || '-' }}</el-descriptions-item>
          <el-descriptions-item label="装裱">{{ selectedArtwork.mounting_format || '-' }}</el-descriptions-item>
          <el-descriptions-item label="现藏地">{{ selectedArtwork.current_location || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag v-if="selectedArtwork.status === 'analyzed'" type="success" size="small">已分析</el-tag>
            <el-tag v-else-if="selectedArtwork.status === 'analyzing'" type="warning" size="small">分析中</el-tag>
            <el-tag v-else type="info" size="small">待分析</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ selectedArtwork.notes || '-' }}</el-descriptions-item>
          <el-descriptions-item label="流传" :span="2">{{ selectedArtwork.provenance || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions" style="margin-top:16px">
          <el-button type="primary" @click="showDetailDrawer = false; openSuggestEdit(selectedArtwork)">建议修改</el-button>
          <el-button @click="$router.push(`/tubi/${selectedArtwork.image_id}`)">打开完整详情</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 建议修改对话框 -->
    <el-dialog v-model="showSuggestDialog" title="建议修改" width="560px" destroy-on-close>
      <template v-if="suggestArtwork">
        <p style="margin-bottom:16px;color:var(--stone-gray)">
          您正在对 <strong>{{ suggestArtwork.title || '未命名' }}</strong> 提出修改建议，提交后由库主审核。
        </p>
        <el-form :model="suggestForm" label-position="top">
          <el-form-item label="修改字段">
            <el-select v-model="suggestForm.field_name" style="width:100%">
              <el-option label="标题" value="title" />
              <el-option label="画家" value="artist" />
              <el-option label="年代" value="year" />
              <el-option label="时期" value="period" />
              <el-option label="画材" value="material" />
              <el-option label="装裱形式" value="mounting_format" />
              <el-option label="现藏地" value="current_location" />
              <el-option label="流传经过" value="provenance" />
              <el-option label="风格标签" value="style_tags" />
              <el-option label="题材标签" value="subject_tags" />
              <el-option label="技法标签" value="technique_tags" />
              <el-option label="款识作者" value="inscription_author" />
              <el-option label="款识日期" value="inscription_date" />
              <el-option label="备注" value="notes" />
              <el-option label="题跋内容" value="inscription_content" />
            </el-select>
          </el-form-item>
          <el-form-item label="原值">
            <el-input :model-value="suggestForm.old_value" disabled />
          </el-form-item>
          <el-form-item label="新值" required>
            <el-input v-model="suggestForm.new_value" placeholder="输入修改后的值" />
          </el-form-item>
          <el-form-item label="修改说明">
            <el-input v-model="suggestForm.change_summary" type="textarea" :rows="3" placeholder="请说明修改依据，如文献出处、专家意见等" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showSuggestDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitChange" :loading="submitting">提交修改建议</el-button>
      </template>
    </el-dialog>

    <!-- 上传作品对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传作品" width="560px" destroy-on-close>
      <el-form :model="uploadForm" label-position="top">
        <el-form-item label="选择图片" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept="image/jpeg,image/png,image/bmp,image/webp"
            :on-change="handleFileChange"
            :file-list="uploadFileList"
          >
            <el-button type="primary"><el-icon><Upload /></el-icon> 选择文件</el-button>
            <template #tip>
              <div class="upload-tip">支持 JPG/PNG/BMP/WebP，最大 50MB</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="作品标题">
          <el-input v-model="uploadForm.title" placeholder="如：兰竹图" />
        </el-form-item>
        <el-form-item label="画家">
          <el-input v-model="uploadForm.artist" placeholder="如：李鱓" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="创作年份">
              <el-input-number v-model="uploadForm.year" :min="1000" :max="2100" placeholder="年份" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="画材">
              <el-input v-model="uploadForm.material" placeholder="纸本/绢本" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="uploadForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Picture, Loading, Plus, View, ArrowRight, Collection, Edit, VideoPlay } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import { libraryApi, artworkApi } from '../api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const libraryId = computed(() => parseInt(route.params.id))

// ── Library state ──
const library = ref({})
const isOwner = computed(() => library.value.owner_id === authStore.userInfo?.user_id)
const isMaintainer = ref(false)
const canEdit = computed(() => isOwner.value || isMaintainer.value)

// ── Tabs ──
const activeTab = ref('artworks')
const manageTab = ref('info')

// ── Artworks ──
const artworks = ref([])
const artworkLoading = ref(false)
const totalArtworks = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const sortBy = ref('created_at')
const order = ref('desc')

// ── Upload ──
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadFileList = ref([])
const uploadFile = ref(null)

const uploadForm = reactive({
  title: '',
  artist: library.value.artist_name || '',
  year: null,
  material: '',
  notes: '',
})

// ── Edit form ──
const editForm = reactive({
  name: '',
  artist_name: '',
  description: '',
  visibility: 'private',
})
const saving = ref(false)

// ── Collaborators ──
const collaborators = ref([])
const newCollabOpenid = ref('')
const newCollabRole = ref('viewer')

// ── Change requests ──
const pendingRequests = ref([])
const pendingRequestCount = computed(() => pendingRequests.value.length)

// ── Methods ──

async function loadLibrary() {
  try {
    const data = await libraryApi.getDetail(libraryId.value)
    library.value = data
    Object.assign(editForm, {
      name: data.name,
      artist_name: data.artist_name || '',
      description: data.description || '',
      visibility: data.visibility,
    })
    // 检查当前用户是否是 maintainer
    if (data.collaborators) {
      const me = data.collaborators.find(c => c.user_id === authStore.userInfo?.user_id)
      isMaintainer.value = me?.role === 'maintainer'
    }
  } catch (e) {
    ElMessage.error('加载作品库失败')
    router.push('/libraries')
  }
}

async function loadArtworks() {
  artworkLoading.value = true
  try {
    const data = await artworkApi.list(libraryId.value, {
      page: currentPage.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      order: order.value,
    })
    artworks.value = data.items || []
    totalArtworks.value = data.total || 0
  } catch (e) {
    ElMessage.error('加载作品列表失败')
  } finally {
    artworkLoading.value = false
  }
}

function toggleOrder() {
  order.value = order.value === 'desc' ? 'asc' : 'desc'
  loadArtworks()
}

function handleFileChange(file) {
  uploadFile.value = file.raw
}

async function handleUpload() {
  if (!uploadFile.value) {
    ElMessage.warning('请选择图片文件')
    return
  }
  uploading.value = true
  try {
    const fields = { ...uploadForm }
    Object.keys(fields).forEach(k => {
      if (fields[k] === null || fields[k] === undefined || fields[k] === '') delete fields[k]
    })
    await artworkApi.upload(libraryId.value, uploadFile.value, fields)
    ElMessage.success('上传成功')
    showUploadDialog.value = false
    uploadFile.value = null
    uploadFileList.value = []
    Object.assign(uploadForm, { title: '', artist: library.value.artist_name || '', year: null, material: '', notes: '' })
    await Promise.all([loadLibrary(), loadArtworks()])
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleUpdateLibrary() {
  saving.value = true
  try {
    await libraryApi.update(libraryId.value, editForm)
    ElMessage.success('保存成功')
    await loadLibrary()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteLibrary() {
  try {
    await ElMessageBox.confirm('确定要删除此作品库吗？此操作不可撤销。', '确认删除', { type: 'warning' })
    await libraryApi.delete(libraryId.value, true)
    ElMessage.success('已删除')
    router.push('/libraries')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function loadCollaborators() {
  try {
    const data = await libraryApi.getCollaborators(libraryId.value)
    collaborators.value = data.collaborators || []
  } catch (e) { /* ignore */ }
}

async function handleAddCollaborator() {
  if (!newCollabOpenid.value.trim()) {
    ElMessage.warning('请输入用户 OpenID')
    return
  }
  try {
    await libraryApi.addCollaborator(libraryId.value, {
      openid: newCollabOpenid.value.trim(),
      role: newCollabRole.value,
    })
    ElMessage.success('协作者添加成功')
    newCollabOpenid.value = ''
    await loadCollaborators()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  }
}

async function handleRemoveCollaborator(userId) {
  try {
    await ElMessageBox.confirm('确定要移除该协作者吗？', '确认', { type: 'warning' })
    await libraryApi.removeCollaborator(libraryId.value, userId)
    ElMessage.success('已移除')
    await loadCollaborators()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

async function loadPendingRequests() {
  try {
    const data = await libraryApi.getChangeRequests(libraryId.value, 'pending')
    pendingRequests.value = data.requests || []
  } catch (e) { /* ignore */ }
}

async function handleReview(requestId, action) {
  try {
    await libraryApi.reviewChangeRequest(requestId, { action, review_comment: '' })
    ElMessage.success(action === 'approve' ? '已通过' : '已拒绝')
    await loadPendingRequests()
    await loadArtworks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '审核失败')
  }
}

// ── Artwork detail drawer ──
const showDetailDrawer = ref(false)
const selectedArtwork = ref(null)

function openArtworkDetail(artwork) {
  selectedArtwork.value = artwork
  showDetailDrawer.value = true
}

// ── Suggest edit ──
const showSuggestDialog = ref(false)
const suggestArtwork = ref(null)
const submitting = ref(false)
const suggestForm = reactive({
  field_name: 'title',
  old_value: '',
  new_value: '',
  change_summary: '',
})

function openSuggestEdit(artwork) {
  suggestArtwork.value = artwork
  suggestForm.field_name = 'title'
  suggestForm.new_value = ''
  suggestForm.change_summary = ''
  updateSuggestOldValue()
  showSuggestDialog.value = true
}

function updateSuggestOldValue() {
  if (!suggestArtwork.value) return
  const val = suggestArtwork.value[suggestForm.field_name]
  suggestForm.old_value = val !== null && val !== undefined ? String(val) : ''
}

// Watch field_name changes to update old_value
watch(() => suggestForm.field_name, updateSuggestOldValue)

async function handleSubmitChange() {
  if (!suggestForm.new_value.trim()) {
    ElMessage.warning('请输入新值')
    return
  }
  if (suggestForm.new_value === suggestForm.old_value) {
    ElMessage.warning('新值与原值相同')
    return
  }
  submitting.value = true
  try {
    const isInscription = suggestForm.field_name === 'inscription_content'
    await libraryApi.submitChangeRequest(libraryId.value, {
      artwork_id: suggestArtwork.value.id,
      request_type: isInscription ? 'edit_inscription' : 'edit_field',
      field_name: isInscription ? null : suggestForm.field_name,
      old_value: suggestForm.old_value,
      new_value: suggestForm.new_value,
      change_summary: suggestForm.change_summary,
    })
    ElMessage.success('修改建议已提交，等待库主审核')
    showSuggestDialog.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

// ── Trigger analysis ──
async function handleTriggerAnalyze(artwork) {
  try {
    await artworkApi.triggerAnalysis(artwork.id)
    ElMessage.success('AI 分析已触发')
    await loadArtworks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '触发分析失败')
  }
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── Watch tab change to load data ──
watch(manageTab, (tab) => {
  if (tab === 'collaborators') loadCollaborators()
  if (tab === 'pending') loadPendingRequests()
})

onMounted(async () => {
  await loadLibrary()
  await loadArtworks()
})
</script>

<style scoped>
.library-detail-page {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: var(--space-3xl) var(--space-2xl);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-xl);
  flex-wrap: wrap;
  gap: var(--space-md);
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-top: var(--space-sm);
}

.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 28px;
  font-weight: 500;
  color: var(--near-black);
}

.page-subtitle {
  font-size: 14px;
  color: var(--stone-gray);
  margin-top: var(--space-sm);
}

.page-actions {
  display: flex;
  gap: var(--space-md);
  padding-top: var(--space-xl);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-lg);
  flex-wrap: wrap;
  gap: var(--space-md);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.artwork-count {
  font-size: 13px;
  color: var(--stone-gray);
}

.loading-wrap {
  padding: var(--space-4xl);
}

.artwork-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-lg);
}

.artwork-card {
  background: var(--pure-white);
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.artwork-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
}

.artwork-thumb {
  height: 200px;
  background: var(--parchment);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.artwork-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.artwork-status-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0,0,0,0.6);
  color: white;
  border-radius: 50%;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.artwork-info {
  padding: var(--space-md);
}

.artwork-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--near-black);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.artwork-meta {
  font-size: 12px;
  color: var(--stone-gray);
  margin-bottom: var(--space-sm);
}

.pagination-wrap {
  margin-top: var(--space-2xl);
  display: flex;
  justify-content: center;
}

.manage-form {
  max-width: 500px;
  padding: var(--space-lg) 0;
}

.manage-section {
  padding: var(--space-lg) 0;
}

.manage-section h3 {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  font-weight: 500;
  margin-bottom: var(--space-md);
}

.add-collab-row {
  display: flex;
  gap: var(--space-md);
  align-items: center;
}

.request-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.request-card {
  background: var(--parchment);
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
}

.request-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.request-meta {
  font-size: 12px;
  color: var(--stone-gray);
}

.diff-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
  font-size: 14px;
}

.diff-label {
  font-weight: 500;
  color: var(--near-black);
  min-width: 80px;
}

.diff-old {
  color: var(--stone-gray);
  text-decoration: line-through;
  background: rgba(220, 38, 38, 0.05);
  padding: 2px 6px;
  border-radius: 3px;
}

.diff-new {
  color: var(--cinnabar);
  background: rgba(193, 39, 45, 0.05);
  padding: 2px 6px;
  border-radius: 3px;
}

.request-summary {
  font-size: 13px;
  color: var(--olive-gray);
  margin-top: var(--space-sm);
  padding-left: 108px;
}

.request-actions {
  display: flex;
  gap: var(--space-md);
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: 1px solid var(--border-cream);
}

.upload-tip {
  font-size: 12px;
  color: var(--stone-gray);
  margin-top: 4px;
}

.manage-badge {
  margin-left: 6px;
}
</style>
