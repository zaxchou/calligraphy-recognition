<template>
  <div class="content-verify">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">管理后台</h1>
        <p class="page-subtitle"></p>
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
      </div>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" class="admin-tabs">
      <!-- 题跋校对 -->
      <el-tab-pane label="题跋校对" name="verify">

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
      @reanalyze="onReanalyze"
    />
    <div v-if="records.length < totalCount" class="load-more-bar">
      <el-button size="small" @click="loadMoreRecords" :loading="loadingMore">
        加载更多（{{ records.length }} / {{ totalCount }}）
      </el-button>
    </div>
      </el-tab-pane>

      <!-- 标注图校对 -->
      <el-tab-pane label="标注图校对" name="annotation">
        <div class="tab-content full-tab-content">
          <AnnotationVerify :artist="selectedArtist" :libraryId="selectedLibraryId" :key="'av-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 尺寸录入 -->
      <el-tab-pane label="尺寸录入" name="dimensions">
        <div class="tab-content full-tab-content">
          <DimensionInput :artist="selectedArtist" :libraryId="selectedLibraryId" :key="'dim-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 印章管理 -->
      <el-tab-pane label="印章管理" name="seal">
        <div class="tab-content full-tab-content">
          <SealManager :artist="selectedArtist" :libraryId="selectedLibraryId" :key="'seal-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 册页管理 -->
      <el-tab-pane label="册页管理" name="album">
        <div class="tab-content full-tab-content">
          <AlbumManager :artist="selectedArtist" :libraryId="selectedLibraryId" :key="'album-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 条屏管理 -->
      <el-tab-pane label="条屏管理" name="strip">
        <div class="tab-content full-tab-content">
          <StripManager :artist="selectedArtist" :libraryId="selectedLibraryId" :key="'strip-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 标签管理 -->
      <el-tab-pane label="标签管理" name="tag">
        <div class="tab-content full-tab-content">
          <TagManager :artist="selectedArtist" :libraryId="selectedLibraryId" :key="'tag-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 书画家信息 -->
      <el-tab-pane label="书画家信息" name="artist-info">
        <div class="tab-content full-tab-content">
          <ArtistInfoManager />
        </div>
      </el-tab-pane>

      <!-- 画家规则 -->
      <el-tab-pane label="画家规则" name="artist-rules">
        <div class="tab-content full-tab-content">
          <ArtistRulesManager :artist="selectedArtist" :key="'rules-'+selectedLibraryId" />
        </div>
      </el-tab-pane>

      <!-- 作品查重 -->
      <el-tab-pane label="作品查重" name="image-search">
        <div class="tab-content full-tab-content">
          <ImageSearchPanel @item-click="onImageSearchItemClick" />
        </div>
      </el-tab-pane>

      <!-- 系统概览（仅管理员可见） -->
      <el-tab-pane v-if="isAdmin" label="系统概览" name="dashboard">
        <div class="tab-content full-tab-content">
          <AdminDashboard />
        </div>
      </el-tab-pane>

      <!-- 用户管理（仅管理员可见） -->
      <el-tab-pane v-if="isAdmin" label="用户管理" name="users">
        <div class="tab-content full-tab-content">
          <AdminUsers />
        </div>
      </el-tab-pane>

      <!-- 系统配置（仅管理员可见） -->
      <el-tab-pane v-if="isAdmin" label="系统信息" name="config">
        <div class="tab-content full-tab-content">
          <AdminSettings />
        </div>
      </el-tab-pane>

      <!-- 变更请求（仅管理员/编辑可见） -->
      <el-tab-pane v-if="isAdmin || isEditor" label="变更请求" name="change-requests">
        <div class="tab-content full-tab-content">
          <div class="change-requests-panel">
            <el-radio-group v-model="crViewMode" size="small" style="margin-bottom:16px;">
              <el-radio-button value="pending">待审核</el-radio-button>
              <el-radio-button value="mine">我的提交</el-radio-button>
            </el-radio-group>

            <!-- 待审核视图 -->
            <template v-if="crViewMode === 'pending'">
              <div class="cr-header">
                <h3>待审核变更请求</h3>
                <div class="cr-header-actions">
                  <el-tag v-if="pendingRequests.length > 0" type="warning" effect="dark">
                    {{ pendingRequests.length }} 条待审核
                  </el-tag>
                  <el-button v-if="selectedCrIds.length > 0" size="small" type="success" @click="batchApprove" :loading="batchReviewing">
                    批量通过 ({{ selectedCrIds.length }})
                  </el-button>
                  <el-button v-if="selectedCrIds.length > 0" size="small" type="danger" @click="batchReject" :loading="batchReviewing">
                    批量拒绝 ({{ selectedCrIds.length }})
                  </el-button>
                </div>
              </div>
              <el-table :data="pendingRequests" v-loading="loadingRequests" style="width: 100%" stripe size="small" @selection-change="onCrSelectionChange">
                <el-table-column type="selection" width="40" />
                <el-table-column prop="library_name" label="画库" width="110" show-overflow-tooltip />
                <el-table-column label="作品" min-width="120" show-overflow-tooltip>
                  <template #default="{ row }">
                    <el-link v-if="row.artwork_image_id" type="primary" :underline="false" @click="$router.push(`/tiba/${row.artwork_image_id}`)">
                      {{ row.artwork_title || '未命名' }}
                    </el-link>
                    <span v-else>{{ row.artwork_title || '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="field_name" label="字段" width="80" />
                <el-table-column label="旧值 → 新值" min-width="200">
                  <template #default="{ row }">
                    <div class="cr-diff-inline">
                      <template v-if="row.field_name === 'annotation_regions'">
                        <el-tag size="small" type="warning" effect="plain">标注图</el-tag>
                        <span style="color:#999;margin:0 4px;">→</span>
                        <el-tag size="small" type="warning" effect="plain">标注图</el-tag>
                        <el-button text size="small" type="primary" @click="showDiff(row)" style="margin-left:6px;">查看对比</el-button>
                      </template>
                      <template v-else>
                        <span class="cr-diff-old">{{ row.old_value || '-' }}</span>
                        <el-icon><Right /></el-icon>
                        <span class="cr-diff-new">{{ row.new_value || '-' }}</span>
                        <el-button text size="small" type="primary" @click="showDiff(row)" style="margin-left:6px;">对比</el-button>
                      </template>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="change_summary" label="摘要" width="120" show-overflow-tooltip />
                <el-table-column prop="submitter_name" label="提交者" width="80" />
                <el-table-column prop="created_at" label="时间" width="150" />
                <el-table-column label="操作" width="160" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="success" plain @click="approveRequest(row)" :loading="reviewingId === row.id">
                      通过
                    </el-button>
                    <el-button size="small" type="danger" plain @click="rejectRequest(row)" :loading="reviewingId === row.id">
                      拒绝
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!loadingRequests && pendingRequests.length === 0" description="暂无待审核的变更请求" />
            </template>

            <!-- 我的提交视图 -->
            <template v-if="crViewMode === 'mine'">
              <div class="cr-header">
                <h3>我的提交</h3>
                <div class="cr-header-actions">
                  <el-radio-group v-model="myCrStatusFilter" size="small">
                    <el-radio-button value="">全部</el-radio-button>
                    <el-radio-button value="pending">待审核</el-radio-button>
                    <el-radio-button value="approved">已通过</el-radio-button>
                    <el-radio-button value="rejected">已驳回</el-radio-button>
                  </el-radio-group>
                  <el-button size="small" circle text @click="loadMyRequests" :loading="loadingMyRequests" style="margin-left:8px;">
                    <el-icon><Refresh /></el-icon>
                  </el-button>
                </div>
              </div>
              <el-table :data="myRequests" v-loading="loadingMyRequests" style="width: 100%" stripe size="small">
                <el-table-column prop="library_name" label="画库" width="110" show-overflow-tooltip />
                <el-table-column label="作品" min-width="120" show-overflow-tooltip>
                  <template #default="{ row }">
                    <el-link v-if="row.artwork_image_id" type="primary" :underline="false" @click="$router.push(`/tiba/${row.artwork_image_id}`)">
                      {{ row.artwork_title || '未命名' }}
                    </el-link>
                    <span v-else>{{ row.artwork_title || '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="field_name" label="字段" width="80" />
                <el-table-column label="旧值 → 新值" min-width="200">
                  <template #default="{ row }">
                    <div class="cr-diff-inline">
                      <template v-if="row.field_name === 'annotation_regions'">
                        <el-tag size="small" type="warning" effect="plain">标注图</el-tag>
                        <span style="color:#999;margin:0 4px;">→</span>
                        <el-tag size="small" type="warning" effect="plain">标注图</el-tag>
                        <el-button text size="small" type="primary" @click="showDiff(row)" style="margin-left:6px;">查看对比</el-button>
                      </template>
                      <template v-else>
                        <span class="cr-diff-old">{{ row.old_value || '-' }}</span>
                        <el-icon><Right /></el-icon>
                        <span class="cr-diff-new">{{ row.new_value || '-' }}</span>
                        <el-button text size="small" type="primary" @click="showDiff(row)" style="margin-left:6px;">对比</el-button>
                      </template>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="change_summary" label="摘要" width="120" show-overflow-tooltip />
                <el-table-column label="状态" width="90">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'" size="small" effect="plain">
                      {{ row.status === 'approved' ? '已通过' : row.status === 'rejected' ? '已驳回' : '待审核' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="审核意见" width="160" show-overflow-tooltip>
                  <template #default="{ row }">{{ row.review_comment || (row.status === 'pending' ? '等待审核' : '无') }}</template>
                </el-table-column>
                <el-table-column label="审核人" width="80">
                  <template #default="{ row }">{{ row.reviewer_name || '-' }}</template>
                </el-table-column>
                <el-table-column prop="created_at" label="提交时间" width="150" />
                <el-table-column prop="reviewed_at" label="审核时间" width="150" />
              </el-table>
              <el-empty v-if="!loadingMyRequests && myRequests.length === 0" description="暂无提交记录" />
            </template>
          </div>
        </div>
      </el-tab-pane>
      <!-- 作品库管理 -->
      <el-tab-pane label="作品库管理" name="libraries">
        <div class="tab-content full-tab-content">
          <LibraryManage />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- diff 对比对话框 -->
    <el-dialog v-model="showDiffDialog" :title="diffRow?.field_name === 'annotation_regions' ? '标注图差异对比' : '差异对比'" width="720px" destroy-on-close>
      <div v-if="diffRow">
        <template v-if="diffRow.field_name === 'annotation_regions'">
          <div style="padding:24px 0;text-align:center;">
            <el-icon :size="48" style="color:#e6a23c;"><WarningFilled /></el-icon>
            <p style="margin-top:16px;font-size:15px;color:#333;">标注图变更</p>
            <p style="margin-top:8px;color:#999;font-size:13px;">
              此请求修改了作品的标注区域。点击下方按钮在新标签页中预览新标注区域的效果。
            </p>
            <el-button type="primary" style="margin-top:16px;" @click="previewAnnotationRegions(diffRow)">
              在新窗口预览新标注
            </el-button>
          </div>
        </template>
        <template v-else>
          <div class="diff-container">
            <div class="diff-panel">
              <h4 class="diff-panel-title diff-panel-old">原值</h4>
              <div class="diff-panel-content" v-html="$sanitize(renderDiffSegments(diffOldSegments))"></div>
            </div>
            <div class="diff-arrow"><el-icon size="20"><Right /></el-icon></div>
            <div class="diff-panel">
              <h4 class="diff-panel-title diff-panel-new">新值</h4>
              <div class="diff-panel-content" v-html="$sanitize(renderDiffSegments(diffNewSegments))"></div>
            </div>
          </div>
        </template>
      </div>
      <div class="diff-meta" v-if="diffRow">
        <p><strong>修改字段：</strong>{{ diffRow.field_name }}</p>
        <p><strong>修改说明：</strong>{{ diffRow.change_summary || '无' }}</p>
        <p><strong>提交者：</strong>{{ diffRow.submitter_name }}</p>
      </div>
    </el-dialog>

    <!-- 拒绝原因对话框 -->
    <el-dialog v-model="showRejectDialog" title="拒绝原因" width="420px" destroy-on-close>
      <p style="margin-bottom:12px;color:#666;">驳回此变更请求时需要填写原因：</p>
      <el-input v-model="rejectReason" type="textarea" :rows="4" placeholder="请填写拒绝原因" />
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="danger" @click="confirmReject" :loading="reviewingId !== null">确认拒绝</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed, inject, defineAsyncComponent, provide } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { Refresh, Right, WarningFilled } from '@element-plus/icons-vue'

import VerifyPanel from './VerifyPanel.vue'
import { useAuthStore } from '../stores/authStore'
import api, { libraryApi } from '../api/index.js'
import { computeDiff } from '../utils/diff'
// 懒加载非首屏组件
const AlbumManager = defineAsyncComponent(() => import('./AlbumManager.vue'))
const TagManager = defineAsyncComponent(() => import('./TagManager.vue'))
const StripManager = defineAsyncComponent(() => import('./StripManager.vue'))
const DimensionInput = defineAsyncComponent(() => import('./DimensionInput.vue'))
const AnnotationVerify = defineAsyncComponent(() => import('./AnnotationVerify.vue'))
const ArtistInfoManager = defineAsyncComponent(() => import('./ArtistInfoManager.vue'))
const ArtistRulesManager = defineAsyncComponent(() => import('./ArtistRulesManager.vue'))
const SealManager = defineAsyncComponent(() => import('./SealManager.vue'))
const ImageSearchPanel = defineAsyncComponent(() => import('../components/tiba/ImageSearchPanel.vue'))
const AdminDashboard = defineAsyncComponent(() => import('./admin/Dashboard.vue'))
const AdminUsers = defineAsyncComponent(() => import('./admin/Users.vue'))
const AdminSettings = defineAsyncComponent(() => import('./admin/Settings.vue'))
const LibraryManage = defineAsyncComponent(() => import('./admin/LibraryManage.vue'))

function escapeHtml(str) {
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}
function renderDiffSegments(segments) {
  const parts = (segments || []).map(s => {
    if (s.type === 'same') return `<span class="diff-same">${escapeHtml(s.text)}</span>`
    if (s.type === 'added') return `<span class="diff-added">${escapeHtml(s.text)}</span>`
    if (s.type === 'removed') return `<span class="diff-removed">${escapeHtml(s.text)}</span>`
    return escapeHtml(s.text)
  })
  return `<span class="diff-text">${parts.join('')}</span>`
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)
const isEditor = computed(() => authStore.isEditor)

const VALID_TABS = ['verify', 'album', 'tag', 'strip', 'dimensions', 'annotation', 'artist-info', 'artist-rules', 'seal', 'image-search', 'dashboard', 'users', 'config', 'change-requests', 'libraries']
const activeTab = ref(VALID_TABS.includes(route.query.tab) ? route.query.tab : 'libraries')
const verifyPanelRef = ref(null)
// 切换标签时同步到 URL query（用 replace 避免污染历史）
watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})
// 反向同步：侧边栏/URL 变化 → 切换标签
watch(() => route.query.tab, (tab) => {
  const t = Array.isArray(tab) ? tab[0] : tab
  if (t && VALID_TABS.includes(t) && t !== activeTab.value) {
    activeTab.value = t
  }
})

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

// ── 注入 AdminLayout 共享状态 ──
const adminAccessibleLibraries = inject('adminAccessibleLibraries', ref([]))
const adminSelectedLibraryId = inject('adminSelectedLibraryId', ref(null))
const adminLibStats = inject('adminLibStats', null)

// 监听侧边栏作品库切换 → 同步
watch(adminSelectedLibraryId, (newLibId) => {
  if (newLibId && newLibId !== selectedLibraryId.value) {
    selectedLibraryId.value = newLibId
    // 自动将作者下拉设为当前作品库的画家
    const lib = adminAccessibleLibraries.value.find(l => l.id === newLibId)
    if (lib && lib.artist_name && artistList.value.includes(lib.artist_name)) {
      selectedArtist.value = lib.artist_name
      router.replace({ query: { ...route.query, artist: lib.artist_name, lib_id: newLibId } })
    }
    fetchRecords()
  }
})

// ── 状态 ──
const records = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const saving = ref(false)
const translating = ref(false)
const analyzing = ref(false)
const verifiedCount = ref(0)
const totalCount = ref(0)
const translatedCount = ref(0)
const analyzedCount = ref(0)
const annotatedCount = ref(0)
const selectedLibraryId = ref(null)
const selectedArtist = ref('all')
const artistList = ref([])
const verifyFilterState = ref('unverified')
provide('verifyFilterState', verifyFilterState)

// 筛选变化时重新加载
watch(verifyFilterState, () => { fetchRecords() })

// URL → artist 同步（浏览器后退/前进时刷新）
watch(() => route.query.artist, (newArtist) => {
  const artist = Array.isArray(newArtist) ? newArtist[0] : newArtist
  if (artist && artist !== selectedArtist.value) {
    selectedArtist.value = artist
    fetchRecords()
  }
})

// URL → lib_id 同步（侧边栏切换作品库时刷新）
watch(() => route.query.lib_id, (newLibId) => {
  const id = Array.isArray(newLibId) ? parseInt(newLibId[0]) : parseInt(newLibId)
  if (id && id !== selectedLibraryId.value) {
    selectedLibraryId.value = id
    fetchRecords()
  }
})

function onArtistChange() {
  router.replace({ query: { ...route.query, artist: selectedArtist.value } })
  fetchRecords()
}
async function fetchArtistList() {
  try {
    const data = await api.get('/content-analysis/artists')
    artistList.value = data.artists || []
    const urlArtist = route.query.artist
    if (urlArtist === 'all') {
      selectedArtist.value = 'all'
    } else if (urlArtist && artistList.value.includes(urlArtist)) {
      selectedArtist.value = urlArtist
    } else if (artistList.value.length > 0) {
      selectedArtist.value = 'all'
    }
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

// 变更请求审核
const crViewMode = ref('pending')
const pendingRequests = ref([])
const loadingRequests = ref(false)
const reviewingId = ref(null)
const selectedCrIds = ref([])
const batchReviewing = ref(false)
// 我的提交
const myRequests = ref([])
const loadingMyRequests = ref(false)
const myCrStatusFilter = ref('')
// diff
const showDiffDialog = ref(false)
const diffRow = ref(null)

const diffOldSegments = computed(() => {
  if (!diffRow.value) return []
  return computeDiff(diffRow.value.old_value, diffRow.value.new_value).filter(s => s.type !== 'added')
})
const diffNewSegments = computed(() => {
  if (!diffRow.value) return []
  return computeDiff(diffRow.value.old_value, diffRow.value.new_value).filter(s => s.type !== 'removed')
})
// reject
const showRejectDialog = ref(false)
const rejectReason = ref('')
const rejectTarget = ref(null)

watch(activeTab, (tab) => {
  if (tab === 'change-requests') {
    loadChangeRequests()
    loadMyRequests()
  }
}, { immediate: true })

watch(myCrStatusFilter, () => {
  loadMyRequests()
})

watch(crViewMode, (mode) => {
  if (mode === 'mine') loadMyRequests()
})

function onCrSelectionChange(rows) {
  selectedCrIds.value = rows.map(r => r.id)
}

function showDiff(row) {
  diffRow.value = row
  showDiffDialog.value = true
}

function previewAnnotationRegions(row) {
  const imageId = row.artwork_image_id
  if (!imageId) {
    ElMessage.warning('无法获取作品图片ID')
    return
  }
  let newValue = row.new_value || '[]'
  if (typeof newValue !== 'string') {
    newValue = JSON.stringify(newValue)
  }
  const encoded = encodeURIComponent(newValue)
  window.open(`/#/annotate/${imageId}?mode=review&regions=${encoded}`, '_blank')
}

async function loadChangeRequests() {
  loadingRequests.value = true
  try {
    const resp = await libraryApi.getAllChangeRequests('pending')
    pendingRequests.value = resp.requests || []
  } catch (e) {
    console.error('获取变更请求失败', e)
  } finally {
    loadingRequests.value = false
  }
}

async function loadMyRequests() {
  loadingMyRequests.value = true
  try {
    const resp = await libraryApi.getMyChangeRequests(myCrStatusFilter.value || undefined)
    myRequests.value = resp.requests || []
  } catch (e) {
    console.error('获取我的提交失败', e)
    ElMessage.error('获取我的提交失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loadingMyRequests.value = false
  }
}

async function approveRequest(row) {
  reviewingId.value = row.id
  try {
    await libraryApi.reviewChangeRequest(row.id, { action: 'approve', review_comment: '' })
    ElMessage.success('已通过')
    pendingRequests.value = pendingRequests.value.filter(r => r.id !== row.id)
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    reviewingId.value = null
  }
}

function rejectRequest(row) {
  rejectTarget.value = row
  rejectReason.value = ''
  showRejectDialog.value = true
}

async function confirmReject() {
  if (!rejectReason.value.trim()) {
    ElMessage.warning('请填写拒绝原因')
    return
  }
  const row = rejectTarget.value
  if (!row) return
  reviewingId.value = row.id
  try {
    await libraryApi.reviewChangeRequest(row.id, { action: 'reject', review_comment: rejectReason.value })
    ElMessage.success('已拒绝')
    pendingRequests.value = pendingRequests.value.filter(r => r.id !== row.id)
    showRejectDialog.value = false
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    reviewingId.value = null
  }
}

async function batchApprove() {
  batchReviewing.value = true
  const ids = [...selectedCrIds.value]
  let ok = 0
  for (const id of ids) {
    try {
      await libraryApi.reviewChangeRequest(id, { action: 'approve', review_comment: '' })
      ok++
    } catch (e) {
      console.error('批量通过失败 id=%d: %s', id, e.message)
    }
  }
  ElMessage.success(`批量通过 ${ok}/${ids.length}`)
  selectedCrIds.value = []
  batchReviewing.value = false
  loadChangeRequests()
}

async function batchReject() {
  batchReviewing.value = true
  const ids = [...selectedCrIds.value]
  let ok = 0
  for (const id of ids) {
    try {
      await libraryApi.reviewChangeRequest(id, { action: 'reject', review_comment: '批量拒绝' })
      ok++
    } catch (e) {
      console.error('批量拒绝失败 id=%d: %s', id, e.message)
    }
  }
  ElMessage.success(`批量拒绝 ${ok}/${ids.length}`)
  selectedCrIds.value = []
  batchReviewing.value = false
  loadChangeRequests()
}

// 生命周期
onMounted(async () => {
  await fetchArtistList()
  // 首次加载时，如果左侧已选了作品库，同步作者下拉
  if (selectedLibraryId.value) {
    const lib = adminAccessibleLibraries.value.find(l => l.id === selectedLibraryId.value)
    if (lib && lib.artist_name && artistList.value.includes(lib.artist_name)) {
      selectedArtist.value = lib.artist_name
    }
  }
  fetchRecords()
})

// 方法
async function fetchRecords() {
  loading.value = true
  try {
    const artistParam = selectedArtist.value === 'all' ? '' : selectedArtist.value
    const isUnverified = verifyFilterState.value === 'unverified'
    const isVerified = verifyFilterState.value === 'verified'
    const params = new URLSearchParams({
      limit: isUnverified ? 500 : 50,
      offset: 0,
    })
    if (artistParam) params.set('artist', artistParam)
    if (selectedLibraryId.value) params.set('library_id', String(selectedLibraryId.value))
    if (isUnverified) params.set('unverified_only', 'true')
    if (isVerified) params.set('verified_only', 'true')
    const data = await api.get(`/content-analysis/records?${params}`)
    records.value = data.records || []
    totalCount.value = data.total || records.value.length
    verifiedCount.value = data.verified_count || 0
    translatedCount.value = data.translated_count || 0
    analyzedCount.value = data.analyzed_count || 0
    annotatedCount.value = data.annotated_count || 0
    // 同步到侧边栏
    if (adminLibStats) {
      adminLibStats.verified = verifiedCount.value
      adminLibStats.total = totalCount.value
      adminLibStats.translated = translatedCount.value
      adminLibStats.analyzed = analyzedCount.value
      adminLibStats.annotated = annotatedCount.value
    }
  } catch (e) {
    ElMessage.error('获取记录失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function loadMoreRecords() {
  if (records.value.length >= totalCount.value) return
  loadingMore.value = true
  try {
    const artistParam = selectedArtist.value === 'all' ? '' : selectedArtist.value
    const params = new URLSearchParams({ limit: 50, offset: records.value.length })
    if (artistParam) params.set('artist', artistParam)
    if (selectedLibraryId.value) params.set('library_id', String(selectedLibraryId.value))
    const data = await api.get(`/content-analysis/records?${params}`)
    records.value.push(...(data.records || []))
  } catch (e) {
    ElMessage.error('加载更多失败: ' + e.message)
  } finally {
    loadingMore.value = false
  }
}

async function onSave(payload) {
  const { id, inscription_content, seal_content, analysis_note, isReverify } = payload
  if (!id) return
  saving.value = true
  try {
    const data = await api.post(`/content-analysis/verify/${id}`, {
      inscription_content, seal_content, analysis_note,
    })
    if (data.success) {
      const idx = records.value.findIndex(r => r.id === id)
      if (idx !== -1) {
        records.value[idx].inscription_content = inscription_content
        records.value[idx].seal_content = seal_content
        if (!isReverify) {
          records.value[idx].inscription_verified = true
          records.value[idx].seal_verified = seal_content ? true : records.value[idx].seal_verified
          verifiedCount.value++
        }
        if (data.analysis_status === 'refreshed') {
          records.value[idx].content_analysis = data.content_analysis
          records.value[idx].theme_tags = data.theme_tags ? data.theme_tags.split(',') : []
          if (!isReverify) {
            ElMessage.success('校对已保存，分析已同步更新')
          } else {
            ElMessage.success('已重新校对，分析已同步更新')
          }
        } else if (data.analysis_status === 'stale') {
          records.value[idx].content_analysis = null
          records.value[idx].theme_tags = []
          if (!isReverify) {
            ElMessage.success('校对已保存')
          } else {
            ElMessage.success('已重新校对')
          }
          ElMessage.warning('题跋分析已过期，请点击「重新分析」更新')
        } else {
          if (!isReverify) {
            ElMessage.success('校对已保存')
          } else {
            ElMessage.success('已重新校对')
          }
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
    const data = await api.post(`/content-analysis/translate/${id}`, { inscription_content })
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
    const data = await api.post(`/content-analysis/analyze/${id}`, { use_llm: true })
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

async function onReanalyze(recordId) {
  try {
    const data = await api.post(`/content-analysis/reanalyze-one/${recordId}`)
    if (data.success) {
      if (data.llm_fixed) {
        ElMessage.success(`分析完成！DeepSeek修正: ${data.llm_detail}`)
      } else if (data.llm_error) {
        ElMessage.warning(`分析完成（LLM调用失败: ${data.llm_error.slice(0, 50)}），使用规则引擎结果`)
      } else {
        ElMessage.success('分析完成！')
      }
      fetchRecords()
    } else {
      ElMessage.error(data.detail || '分析失败')
    }
  } catch (err) {
    ElMessage.error('分析失败: ' + (err.message || err))
  }
}

function onTitleUpdated({ id, image_id, title }) {
  const idx = records.value.findIndex(r => r.id === id || r.image_id === image_id)
  if (idx !== -1) {
    records.value[idx].title = title
    ElMessage.success('作品名已更新')
  }
}

function onImageSearchItemClick(recordId) {
  const route = router.resolve({ name: 'TibaDetail', params: { id: recordId } })
  window.open(route.href, '_blank')
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

/* ── 变更请求审核面板 ── */
.change-requests-panel {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.cr-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.cr-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #3a3a3a;
}
.cr-old-value {
  color: #999;
  text-decoration: line-through;
  margin-right: 4px;
}
.cr-new-value {
  color: #67c23a;
  font-weight: 500;
  margin-left: 4px;
}
.cr-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
/* diff 对比 */
.diff-container {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.diff-panel {
  flex: 1;
  border: 1px solid #e8e4da;
  border-radius: 6px;
  overflow: hidden;
}
.diff-panel-title {
  margin: 0;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  background: #f5f3ef;
  border-bottom: 1px solid #e8e4da;
}
.diff-panel-old { color: #999; background: #f8f8f8; }
.diff-panel-new { color: #333; background: #f0f9eb; }
.diff-panel-content {
  padding: 12px;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
  min-height: 60px;
  max-height: 300px;
  overflow-y: auto;
}
.diff-text {
  font-family: inherit;
}
.diff-same {
  color: #333;
}
.diff-added {
  background: #fff3cd;
  color: #856404;
  border-radius: 2px;
  padding: 1px 0;
}
.diff-removed {
  background: #f8d7da;
  color: #721c24;
  border-radius: 2px;
  padding: 1px 0;
  text-decoration: line-through;
}
.diff-arrow {
  display: flex;
  align-items: center;
  padding-top: 40px;
  color: #999;
}
.diff-meta {
  padding: 12px 16px;
  background: #fafaf8;
  border-radius: 6px;
  border: 1px solid #e8e4da;
}
.diff-meta p {
  margin: 4px 0;
  font-size: 13px;
  color: #555;
}
.load-more-bar {
  text-align: center;
  padding: 16px 0 8px;
}
</style>
