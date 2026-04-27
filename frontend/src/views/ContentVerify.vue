<template>
  <div class="content-verify">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">管理后台</h1>
        <p class="page-subtitle">作品上传 · 题跋校对 · 标注图校对 · 尺寸录入 · 印章管理 · 册页管理 · 条屏管理 · 标签管理 · 作者信息</p>
      </div>
      <div class="header-center">
        <el-select v-model="selectedArtist" size="default" @change="onArtistChange" style="width: 150px;" class="claude-select">
          <el-option label="全部作者" value="all" />
          <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
        </el-select>
      </div>
      <div class="header-right">
        <div class="stats-tags">
          <span class="stat-tag">
            <span class="stat-label">已校对</span>
            <span class="stat-value">{{ verifiedCount }} / {{ totalCount }}</span>
          </span>
          <span class="stat-tag translated" v-if="translatedCount > 0">
            <span class="stat-label">已翻译</span>
            <span class="stat-value">{{ translatedCount }}</span>
          </span>
          <span class="stat-tag analyzed" v-if="analyzedCount > 0">
            <span class="stat-label">已分析</span>
            <span class="stat-value">{{ analyzedCount }}</span>
          </span>
          <span class="stat-tag annotated" v-if="annotatedCount > 0">
            <span class="stat-label">已标注</span>
            <span class="stat-value">{{ annotatedCount }}</span>
          </span>
        </div>
        <el-button plain size="small" class="btn-edit" @click="showTranslateModeDialog = true" :loading="batchTranslating">
          <el-icon><Bottom /></el-icon>翻译
        </el-button>
        <el-button plain size="small" class="btn-edit" @click="showAnalyzeModeDialog = true" :loading="analyzing">
          <el-icon><RefreshRight /></el-icon>分析
        </el-button>
        <el-button plain size="small" class="btn-edit" @click="router.push('/content-analysis')">
          <el-icon><HomeFilled /></el-icon>返回
        </el-button>
      </div>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" class="admin-tabs">
      <!-- 作品上传 -->
      <el-tab-pane label="作品上传" name="upload">
        <div class="tab-content full-tab-content upload-tab-content">
          <div class="upload-entry">
            <div class="upload-entry-icon">
              <el-icon size="64" color="#c96442"><Upload /></el-icon>
            </div>
            <h3 class="upload-entry-title">上传作品图片</h3>
            <p class="upload-entry-desc">支持批量拖拽上传，可选择直接入库、AI文本分析或AI标注图分析</p>
            <el-button type="primary" size="large" @click="openUploadDialog" class="btn-primary upload-entry-btn">
              <el-icon><Upload /></el-icon>
              开始上传
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- 题跋校对 -->
      <el-tab-pane label="题跋校对" name="verify">

    <!-- 批量翻译选项弹窗 -->
    <el-dialog
      v-model="showTranslateModeDialog"
      title="批量翻译选项"
      width="420px"
      class="translate-mode-dialog claude-dialog"
    >
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchTranslate('untranslated')">
          <div class="mode-icon"><el-icon><Bottom /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">仅翻译未翻译的</div>
            <div class="mode-desc">跳过已有翻译的记录，只翻译尚未翻译的条目</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchTranslate('all')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">重新翻译全部</div>
            <div class="mode-desc">对所有已校对记录重新翻译（会覆盖已有翻译）</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 批量翻译进度弹窗 -->
    <el-dialog
      v-model="showTranslateProgress"
      title="批量翻译进度"
      width="420px"
      :close-on-click-modal="false"
      :show-close="false"
      class="translate-progress-dialog claude-dialog"
    >
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">正在翻译：</span>
          <span class="progress-value">{{ translateProgress.current }} / {{ translateProgress.total }}</span>
        </div>
        <el-progress
          :percentage="translateProgress.percent"
          :color="translateProgressColor"
          :stroke-width="8"
          class="translate-progress-bar"
        />
        <div class="progress-status">
          <span v-if="translateProgress.status === 'translating'" class="status-text">翻译中，请稍候...</span>
          <span v-else-if="translateProgress.status === 'done'" class="status-text done">翻译完成！</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchTranslate" :disabled="translateProgress.status === 'done'">取消</el-button>
        <el-button plain class="btn-edit" @click="showTranslateProgress = false" :disabled="translateProgress.status !== 'done'">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 批量重新分析选项弹窗 -->
    <el-dialog
      v-model="showAnalyzeModeDialog"
      title="批量重新分析选项"
      width="420px"
      class="translate-mode-dialog claude-dialog"
    >
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchAnalyze('incremental')">
          <div class="mode-icon"><el-icon><Bottom /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">仅分析未校验的（增量）</div>
            <div class="mode-desc">只分析尚未完成内容分析的记录，跳过已分析的结果</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchAnalyze('full')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">重新分析全部（含已校验）</div>
            <div class="mode-desc">强制重跑所有记录的分析，会覆盖已有结果（消耗更多 API 配额）</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 批量重新分析进度弹窗 -->
    <el-dialog
      v-model="showAnalyzeProgress"
      title="批量重新分析进度"
      width="420px"
      :close-on-click-modal="false"
      :show-close="false"
      class="translate-progress-dialog claude-dialog"
    >
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">正在分析：</span>
          <span class="progress-value">{{ analyzeProgress.current }} / {{ analyzeProgress.total }}</span>
        </div>
        <el-progress
          :percentage="analyzeProgress.percent"
          :color="translateProgressColor"
          :stroke-width="8"
          class="translate-progress-bar"
        />
        <div class="progress-status">
          <span v-if="analyzeProgress.status === 'analyzing'" class="status-text">分析中，请稍候...</span>
          <span v-else-if="analyzeProgress.status === 'done'" class="status-text done">分析完成！</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchAnalyze" :disabled="analyzeProgress.status === 'done'">取消</el-button>
        <el-button plain class="btn-edit" @click="showAnalyzeProgress = false" :disabled="analyzeProgress.status !== 'done'">关闭</el-button>
      </template>
    </el-dialog>

    <VerifyPanel
      ref="verifyPanelRef"
      :records="records"
      :loading="loading"
      :saving="saving"
      :translating="translating"
      :analyzing="analyzing"
      :verified-count="verifiedCount"
      :total-count="totalCount"
      :base-url="API_BASE.replace('/api/v1', '')"
      :api-base="API_BASE"
      :artist="selectedArtist"
      @save="onSave"
      @translate="onTranslate"
      @analyze="onAnalyze"
      @open-annotator="onOpenAnnotator"
      @update-title="onTitleUpdated"
    />
      </el-tab-pane>

      <!-- 标注图校对 -->
      <el-tab-pane label="标注图校对" name="annotation">
        <div class="tab-content full-tab-content">
          <AnnotationVerify :artist="selectedArtist" />
        </div>
      </el-tab-pane>

      <!-- 尺寸录入 -->
      <el-tab-pane label="尺寸录入" name="dimensions">
        <div class="tab-content full-tab-content">
          <DimensionInput :artist="selectedArtist" />
        </div>
      </el-tab-pane>

      <!-- 印章管理 -->
      <el-tab-pane label="印章管理" name="seal">
        <div class="tab-content full-tab-content">
          <SealManager :artist="selectedArtist" />
        </div>
      </el-tab-pane>

      <!-- 册页管理 -->
      <el-tab-pane label="册页管理" name="album">
        <div class="tab-content full-tab-content">
          <AlbumManager :artist="selectedArtist" />
        </div>
      </el-tab-pane>

      <!-- 条屏管理 -->
      <el-tab-pane label="条屏管理" name="strip">
        <div class="tab-content full-tab-content">
          <StripManager :artist="selectedArtist" />
        </div>
      </el-tab-pane>

      <!-- 标签管理 -->
      <el-tab-pane label="标签管理" name="tag">
        <div class="tab-content full-tab-content">
          <TagManager :artist="selectedArtist" />
        </div>
      </el-tab-pane>

      <!-- 作者信息 -->
      <el-tab-pane label="作者信息" name="artist-info">
        <div class="tab-content full-tab-content">
          <ArtistInfoManager />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 上传弹窗 -->
    <TubiUploadDialog
      ref="uploadDialogRef"
      @uploaded="onUploaded"
      @refresh="fetchRecords"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { Bottom, RefreshRight, HomeFilled, Upload } from '@element-plus/icons-vue'
import { useBatchOperations } from '../composables/useBatchOperations'

import VerifyPanel from './VerifyPanel.vue'
import AlbumManager from './AlbumManager.vue'
import TagManager from './TagManager.vue'
import StripManager from './StripManager.vue'
import DimensionInput from './DimensionInput.vue'
import AnnotationVerify from './AnnotationVerify.vue'
import ArtistInfoManager from './ArtistInfoManager.vue'
import SealManager from './SealManager.vue'
import TubiUploadDialog from '../components/tubi/TubiUploadDialog.vue'

const router = useRouter()
const route = useRoute()

const VALID_TABS = ['upload', 'verify', 'album', 'tag', 'strip', 'dimensions', 'annotation', 'artist-info', 'seal']
const activeTab = ref(VALID_TABS.includes(route.query.tab) ? route.query.tab : 'verify')
const verifyPanelRef = ref(null)
const uploadDialogRef = ref(null)

// 切换标签时同步到 URL query（用 replace 避免污染历史）
watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

// 状态
const records = ref([])
const loading = ref(false)
const saving = ref(false)
const translating = ref(false)
const verifiedCount = ref(0)
const totalCount = ref(0)
const translatedCount = ref(0)
const analyzedCount = ref(0)
const annotatedCount = ref(0)

// 作者列表
const artistList = ref([])
const selectedArtist = ref('李鱓')

// 切换作者时同步 URL 并刷新数据
watch(selectedArtist, (newArtist, oldArtist) => {
  if (newArtist !== oldArtist) {
    router.replace({ query: { ...route.query, artist: newArtist } })
    fetchRecords()
  }
})
function onArtistChange() {
  // watch 会处理刷新
}
async function fetchArtistList() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
    // URL query 优先恢复
    const urlArtist = route.query.artist
    if (urlArtist && artistList.value.includes(urlArtist)) {
      selectedArtist.value = urlArtist
    } else if (artistList.value.length > 0 && !artistList.value.includes(selectedArtist.value)) {
      selectedArtist.value = artistList.value[0]
    }
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

// 批量操作
const {
  analyzing,
  batchTranslating,
  showAnalyzeModeDialog,
  showTranslateModeDialog,
  showAnalyzeProgress,
  showTranslateProgress,
  analyzeProgress,
  translateProgress,
  translateProgressColor,
  startBatchAnalyze,
  cancelBatchAnalyze,
  startBatchTranslate,
  cancelBatchTranslate,
} = useBatchOperations({ apiBase: API_BASE, fetchRecords, getArtist: () => selectedArtist.value })

// 生命周期
onMounted(async () => {
  await fetchArtistList()
  // fetchArtistList 可能不改变 selectedArtist（默认李鱓在列表中时），需手动触发首次加载
  fetchRecords()
})

// 方法
async function fetchRecords() {
  loading.value = true
  try {
    const artistParam = selectedArtist.value === 'all' ? '' : selectedArtist.value
    const params = new URLSearchParams({ limit: 500 })
    if (artistParam) params.set('artist', artistParam)
    const res = await fetch(`${API_BASE}/content-analysis/records?${params}`)
    const data = await res.json()
    records.value = data.records || []
    totalCount.value = data.total || records.value.length
    verifiedCount.value = data.verified_count || 0
    translatedCount.value = data.translated_count || 0
    analyzedCount.value = data.analyzed_count || 0
    annotatedCount.value = data.annotated_count || 0
  } catch (e) {
    ElMessage.error('获取记录失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function onSave(payload) {
  const { id, inscription_content, seal_content, analysis_note, isReverify } = payload
  if (!id) return
  saving.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/verify/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inscription_content, seal_content, analysis_note }),
    })
    const data = await res.json()
    if (data.success) {
      const idx = records.value.findIndex(r => r.id === id)
      if (idx !== -1) {
        records.value[idx].inscription_content = inscription_content
        records.value[idx].seal_content = seal_content
        if (!isReverify) {
          records.value[idx].inscription_verified = true
          records.value[idx].seal_verified = seal_content ? true : records.value[idx].seal_verified
          verifiedCount.value++
          ElMessage.success('校对已保存')
        } else {
          ElMessage.success('已重新校对')
        }
      }
      verifyPanelRef.value?.nextRecord()
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function onTranslate(payload) {
  const { id, inscription_content, originalModern } = payload
  if (!id) return
  translating.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/translate/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inscription_content })
    })
    const data = await res.json()
    if (data.success) {
      ElMessage.success('翻译完成')
      const idx = records.value.findIndex(r => r.id === id)
      if (idx !== -1) {
        records.value[idx].inscription_modern = data.modern
      }
      if (!originalModern) {
        translatedCount.value++
      }
    } else {
      ElMessage.error(data.message || '翻译失败')
    }
  } catch (e) {
    ElMessage.error('翻译失败: ' + e.message)
  } finally {
    translating.value = false
  }
}

async function onAnalyze(payload) {
  const { id } = payload
  if (!id) return
  analyzing.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/analyze/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_llm: true })
    })
    const data = await res.json()
    if (data.success) {
      ElMessage.success('分析完成')
      // 刷新记录数据
      await fetchRecords()
    } else {
      ElMessage.error(data.message || '分析失败')
    }
  } catch (e) {
    ElMessage.error('分析失败: ' + e.message)
  } finally {
    analyzing.value = false
  }
}

function onOpenAnnotator(id) {
  if (!id) return
  router.push(`/annotate/${id}`)
}

function onTitleUpdated({ id, image_id, title }) {
  const idx = records.value.findIndex(r => r.id === id || r.image_id === image_id)
  if (idx !== -1) {
    records.value[idx].title = title
    ElMessage.success('作品名已更新')
  }
}

// 上传完成回调
function onUploaded(newImages) {
  // 上传完成后刷新记录列表
  fetchRecords()
  ElMessage.success(`已上传 ${newImages.length} 张作品`)
}

function openUploadDialog() {
  uploadDialogRef.value?.open()
}

</script>

<style scoped>
/* Claude Design System */
.content-verify {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
  background: #fafaf8;
  min-height: 100vh;
}

/* 标签页样式 */
::deep(.admin-tabs .el-tabs__header) {
  margin-bottom: 20px;
}

::deep(.admin-tabs .el-tabs__nav-wrap::after) {
  background: #e8e6dc;
}

::deep(.admin-tabs .el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
  color: #6b6b66;
  padding: 0 20px;
  height: 44px;
  line-height: 44px;
}

::deep(.admin-tabs .el-tabs__item.is-active) {
  color: #c96442;
  font-weight: 600;
}

::deep(.admin-tabs .el-tabs__active-bar) {
  background: #c96442;
  height: 3px;
}

.tab-content {
  width: 100%;
}

.full-tab-content {
  width: 100%;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  gap: 20px;
}

.header-center {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 26px;
  font-weight: 600;
  color: #141413;
  margin: 0 0 6px;
  letter-spacing: -0.3px;
}

.page-subtitle {
  font-size: 14px;
  color: #6b6b66;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.stats-tags {
  display: flex;
  gap: 8px;
  margin-right: 8px;
}

.stat-tag {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 14px;
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 8px;
}

.stat-tag.translated {
  border-color: #c96442;
  background: #fdf8f6;
}

.stat-tag.analyzed {
  border-color: #5a7d5a;
  background: #f0f4f0;
}

.stat-tag.annotated {
  border-color: #4a7ab8;
  background: #f0f4f8;
}

.stat-label {
  font-size: 11px;
  color: #6b6b66;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #141413;
}

/* 按钮样式 - 确保文字垂直居中 */
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

.btn-edit {
  border-color: #c96442 !important;
  color: #c96442 !important;
  background: transparent !important;
}

.btn-edit:hover {
  background: #fdf8f6 !important;
  border-color: #a8513a !important;
}

.btn-edit.is-disabled {
  opacity: 0.5;
}

.btn-primary {
  background: #c96442 !important;
  color: #fff !important;
  border-color: #c96442 !important;
}

.btn-primary:hover {
  background: #a8513a !important;
  border-color: #a8513a !important;
}

.btn-warning {
  border-color: #b8a47e !important;
  color: #b8a47e !important;
}

.btn-warning:hover {
  background: #fcfbf8 !important;
}

/* Claude Dialog 样式 */
.claude-dialog :deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #e8e6dc;
}

.claude-dialog :deep(.el-dialog__title) {
  font-family: 'Noto Serif SC', serif;
  font-size: 18px;
  font-weight: 600;
  color: #141413;
}

.claude-dialog :deep(.el-dialog__body) {
  padding: 20px 24px;
}

.claude-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #e8e6dc;
}

/* 翻译选项弹窗 */
.translate-mode-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mode-option {
  display: flex;
  align-items: center;
  padding: 16px;
  border: 1px solid #e8e6dc;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.mode-option:hover {
  border-color: #c96442;
  background: #fdf8f6;
}

.mode-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: #f0f4ff;
  color: #4a6cb3;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 14px;
  font-size: 20px;
}

.mode-icon.warning {
  background: #fdf8f6;
  color: #c96442;
}

.mode-info {
  flex: 1;
}

.mode-title {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 4px;
  color: #141413;
}

.mode-desc {
  font-size: 13px;
  color: #6b6b66;
  line-height: 1.5;
}

.mode-arrow {
  color: #c0c0b8;
  font-size: 16px;
}

.mode-option:hover .mode-arrow {
  color: #c96442;
}

/* 批量翻译进度 */
.progress-body {
  padding: 8px 0;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.progress-label {
  font-size: 14px;
  color: #6b6b66;
}

.progress-value {
  font-size: 15px;
  font-weight: 600;
  color: #141413;
}

.translate-progress-bar :deep(.el-progress-bar__outer) {
  background-color: #f0efe9;
  border-radius: 3px;
}

.progress-status {
  text-align: center;
  margin-top: 14px;
}

.status-text {
  font-size: 13px;
  color: #a0a096;
}

.status-text.done {
  color: #5a7d5a;
  font-weight: 600;
}

/* 作品上传入口 */
.upload-tab-content {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.upload-entry {
  text-align: center;
  padding: 60px 40px;
  background: #fff;
  border-radius: 16px;
  border: 2px dashed #e8e6dc;
  max-width: 480px;
  width: 100%;
  transition: border-color 0.2s;
}

.upload-entry:hover {
  border-color: #c96442;
}

.upload-entry-icon {
  margin-bottom: 20px;
}

.upload-entry-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 22px;
  font-weight: 600;
  color: #141413;
  margin: 0 0 10px;
}

.upload-entry-desc {
  font-size: 14px;
  color: #87867f;
  margin: 0 0 28px;
  line-height: 1.6;
}

.upload-entry-btn {
  padding: 12px 32px;
  font-size: 16px;
  border-radius: 10px;
}
</style>
