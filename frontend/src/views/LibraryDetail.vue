<template>
  <div class="library-detail-page">
    <!-- 面包屑 + 标题 -->
    <div class="page-header" v-if="!embedded">
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
    </div>

    <!-- 文件名格式提示 -->
    <el-alert v-if="showUploadArea" type="info" :closable="false" show-icon class="filename-tip">
      <template #title>
        推荐文件名格式：<code>清_李鱓_兰竹图_1750.jpg</code>
        按下划线分割：朝代_作者_作品名_年份，系统将自动提取元数据
      </template>
    </el-alert>

    <!-- 批量上传区域 -->
    <div v-if="showUploadArea" class="inline-upload-area">
      <div class="upload-area-header">
        <h3>批量上传作品</h3>
        <el-button size="small" text @click="showUploadArea = false">
          <el-icon><Close /></el-icon> 收起
        </el-button>
      </div>
      <TubiUploadInline
        :library-id="libraryId"
        @refresh="onUploadRefresh"
      />
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="作品列表" name="artworks">
        <!-- 统一工具栏 -->
        <div class="toolbar unified-toolbar">
          <div class="toolbar-left">
            <el-select v-model="switchingLibraryId" size="small" style="width: 180px" @change="onSwitchLibrary">
              <el-option label="📚 当前作品库" value="" disabled />
              <el-option v-for="lib in accessibleLibs" :key="lib.id" :label="lib.name" :value="lib.id" />
            </el-select>
            <span class="toolbar-sep">|</span>
            <el-select v-model="sortBy" size="small" style="width: 140px" @change="loadArtworks">
              <el-option label="上传时间" value="created_at" />
              <el-option label="画家" value="artist" />
              <el-option label="年代" value="year" />
            </el-select>
            <el-button size="small" @click="toggleOrder">
              {{ order === 'desc' ? '↓ 降序' : '↑ 升序' }}
            </el-button>
          </div>
          <div class="toolbar-center">
            <span class="artwork-count">共 {{ totalArtworks }} 件</span>
          </div>
          <div class="toolbar-right">
            <el-button size="small" @click="showUploadArea = !showUploadArea" :disabled="!canEdit" :class="{ 'is-active': showUploadArea }">
              <el-icon><Upload /></el-icon>{{ showUploadArea ? '收起上传' : '上传作品' }}
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="showAiAnalyzeDialog = true" :loading="aiAnalyzing" title="从图片中检测题跋区域、OCR提取文字">
              <el-icon><MagicStick /></el-icon>AI识图
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="showAnalyzeModeDialog = true" :loading="analyzing" title="对题跋文字进行主题分类与情感分析">
              <el-icon><Refresh /></el-icon>文字分析
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="showTranslateModeDialog = true" :loading="batchTranslating" title="翻译题跋文字">
              <el-icon><Bottom /></el-icon>翻译
            </el-button>
          </div>
        </div>

        <div v-if="artworkLoading" class="loading-wrap">
          <el-skeleton :rows="3" animated />
        </div>

        <el-empty v-else-if="artworks.length === 0" description="库内还没有作品">
          <el-button type="primary" @click="showUploadArea = true" :disabled="!canEdit">上传作品</el-button>
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
                <el-button size="small" circle @click.stop="openSuggestEdit(artwork)" title="我的意见">
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
              <div class="artwork-status-tags">
                <el-tooltip :content="artwork.inscription_modern ? '翻译已完成' : '待翻译'" placement="top">
                  <span class="status-dot" :class="artwork.inscription_modern ? 'done' : 'pending'">译</span>
                </el-tooltip>
                <el-tooltip :content="artwork.content_analysis ? '文字分析已完成' : '待文字分析'" placement="top">
                  <span class="status-dot" :class="artwork.content_analysis ? 'done' : 'pending'">析</span>
                </el-tooltip>
                <el-tooltip :content="artwork.inscription_verified ? '题跋已校对' : '题跋待校对'" placement="top">
                  <span class="status-dot" :class="artwork.inscription_verified ? 'done' : 'pending'">校</span>
                </el-tooltip>
                <el-tooltip :content="artwork.is_manual_annotated ? '标注已完成' : '标注待定'" placement="top">
                  <span class="status-dot" :class="artwork.is_manual_annotated ? 'done' : 'pending'">注</span>
                </el-tooltip>
                <el-tooltip :content="artwork.status === 'analyzed' ? 'AI识图已完成' : 'AI识图待定'" placement="top">
                  <span class="status-dot" :class="artwork.status === 'analyzed' ? 'done' : 'pending'">识</span>
                </el-tooltip>
              </div>
            </div>
            <div class="artwork-card-footer" v-if="canEdit">
              <el-button link size="small" @click.stop="openProofread(artwork)">
                <el-icon><EditPen /></el-icon> 校对
              </el-button>
              <el-button link size="small" @click.stop="openAnnotate(artwork)">
                <el-icon><Crop /></el-icon> 标注
              </el-button>
              <el-button link size="small" @click.stop="handleTriggerAnalyze(artwork)">
                <el-icon><VideoPlay /></el-icon> AI分析
              </el-button>
              <el-button link size="small" type="danger" @click.stop="handleDeleteArtwork(artwork)">
                <el-icon><Delete /></el-icon> 删除
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
          <el-button type="primary" @click="showDetailDrawer = false; openSuggestEdit(selectedArtwork)">我的意见</el-button>
          <el-button @click="$router.push(`/tubi/${selectedArtwork.image_id}`)">打开完整详情</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 我的意见对话框 -->
    <el-dialog v-model="showSuggestDialog" title="我的意见" width="560px" destroy-on-close>
      <template v-if="suggestArtwork">
        <p style="margin-bottom:16px;color:var(--stone-gray)">
          您正在对 <strong>{{ suggestArtwork.title || '未命名' }}</strong> 提出修改意见，提交后由库主审核。
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
            <div class="old-value-display">{{ suggestForm.old_value }}</div>
          </el-form-item>
          <el-form-item label="新值" required>
            <el-input v-model="suggestForm.new_value" type="textarea" :autosize="{ minRows: 2, maxRows: 8 }" placeholder="在原值基础上修改，或输入新内容" />
          </el-form-item>
          <el-form-item label="修改说明">
            <el-input v-model="suggestForm.change_summary" type="textarea" :rows="3" placeholder="请说明修改依据，如文献出处、专家意见等" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showSuggestDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitChange" :loading="submitting">提交意见</el-button>
      </template>
    </el-dialog>

    <!-- 批量翻译选项弹窗 -->
    <el-dialog v-model="showTranslateModeDialog" title="批量翻译选项" width="420px">
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchTranslate('untranslated')">
          <div class="mode-icon"><el-icon><Bottom /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">仅翻译未翻译的</div>
            <div class="mode-desc">跳过已有翻译的记录</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchTranslate('all')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">重新翻译全部</div>
            <div class="mode-desc">覆盖已有翻译</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 批量重跑选项弹窗 -->
    <el-dialog v-model="showAnalyzeModeDialog" title="解析文字" width="420px">
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchAnalyze('incremental')">
          <div class="mode-icon"><el-icon><Refresh /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">增量重跑</div>
            <div class="mode-desc">仅处理未分析/已过期的作品</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchAnalyze('full')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">全部重跑</div>
            <div class="mode-desc">重新分析所有作品（覆盖已有结果）</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 翻译进度弹窗 -->
    <el-dialog v-model="showTranslateProgress" title="批量翻译进度" width="420px" :close-on-click-modal="false" :show-close="false">
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">正在翻译：</span>
          <span class="progress-value">{{ translateProgress.current }} / {{ translateProgress.total }}</span>
        </div>
        <el-progress :percentage="translateProgress.percent" :stroke-width="8" />
        <div class="progress-status">
          <span v-if="translateProgress.status === 'translating'" class="status-text">翻译中，请稍候...</span>
          <span v-else-if="translateProgress.status === 'done'" class="status-text done">翻译完成！</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchTranslate" :disabled="translateProgress.status === 'done'">取消</el-button>
        <el-button plain @click="showTranslateProgress = false" :disabled="translateProgress.status !== 'done'">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 批量分析进度弹窗 -->
    <el-dialog v-model="showAnalyzeProgress" title="批量重新分析进度" width="420px" :close-on-click-modal="false" :show-close="false">
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">正在分析：</span>
          <span class="progress-value">{{ analyzeProgress.current }} / {{ analyzeProgress.total }}</span>
        </div>
        <el-progress :percentage="analyzeProgress.percent" :stroke-width="8" />
        <div class="progress-status">
          <span v-if="analyzeProgress.status === 'analyzing'" class="status-text">分析中，请稍候...</span>
          <span v-else-if="analyzeProgress.status === 'done'" class="status-text done">分析完成！</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchAnalyze" :disabled="analyzeProgress.status === 'done'">取消</el-button>
        <el-button plain @click="showAnalyzeProgress = false" :disabled="analyzeProgress.status !== 'done'">关闭</el-button>
      </template>
    </el-dialog>

    <!-- AI识图弹窗 -->
    <el-dialog v-model="showAiAnalyzeDialog" title="批量AI识图" width="400px">
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchAiAnalyze('analyze_text_only')">
          <div class="mode-icon"><el-icon><MagicStick /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">开始识图</div>
            <div class="mode-desc">OCR提取题跋文字 + 识别画材标签（未分析的作品）</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option warn" @click="startBatchAiAnalyze('analyze')">
          <div class="mode-icon warning"><el-icon><Refresh /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">全部重新识图</div>
            <div class="mode-desc">覆盖已有结果，对库内所有作品重新分析</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- AI识图进度弹窗 -->
    <el-dialog v-model="showAiAnalyzeProgress" title="AI识图进度" width="420px" :close-on-click-modal="false" :show-close="false">
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">正在分析：</span>
          <span class="progress-value">{{ aiAnalyzeProgress.current }} / {{ aiAnalyzeProgress.total }}</span>
        </div>
        <el-progress :percentage="aiAnalyzeProgress.percent" :stroke-width="8" />
        <div class="progress-status">
          <span v-if="aiAnalyzeProgress.status === 'analyzing'" class="status-text">识图中，请稍候...</span>
          <span v-else-if="aiAnalyzeProgress.status === 'done'" class="status-text done">识图完成！</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchAiAnalyze" :disabled="aiAnalyzeProgress.status === 'done'">取消</el-button>
        <el-button plain @click="showAiAnalyzeProgress = false" :disabled="aiAnalyzeProgress.status !== 'done'">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Picture, Loading, Plus, View, ArrowRight, Collection, Edit, VideoPlay, Delete, Close, Bottom, Right, Refresh, RefreshRight, EditPen, Crop, MagicStick } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import { libraryApi, artworkApi, tubiApi } from '../api'
import TubiUploadInline from '@/components/tubi/TubiUploadInline.vue'
import { useSSEStream } from '@/composables/useSSEStream'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const props = defineProps({
  libraryId: { type: [Number, String], default: null },
  embedded: { type: Boolean, default: false }
})

const libraryId = computed(() => {
  if (props.libraryId) return parseInt(props.libraryId)
  return parseInt(route.params.id)
})

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
const showUploadArea = ref(false)

// ── Batch operations ──
const switchingLibraryId = ref(null)
const accessibleLibs = ref([])
const showTranslateModeDialog = ref(false)
const showTranslateProgress = ref(false)
const batchTranslating = ref(false)
const translateProgress = ref({ current: 0, total: 0, status: '', percent: 0 })
const showAnalyzeModeDialog = ref(false)
const showAnalyzeProgress = ref(false)
const analyzing = ref(false)
const analyzeProgress = ref({ current: 0, total: 0, status: '', percent: 0 })
const showAiAnalyzeDialog = ref(false)
const showAiAnalyzeProgress = ref(false)
const aiAnalyzing = ref(false)
const aiAnalyzeProgress = ref({ current: 0, total: 0, status: '', percent: 0 })

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
let translateCancelFn = null
let analyzeCancelFn = null
let aiAnalyzeCancelFn = null

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
    if (!props.embedded) router.push('/libraries')
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

// ── Upload callbacks ──
function onUploadRefresh() {
  loadArtworks()
  loadLibrary()
}

// ── Proofread / Annotate links ──
function openProofread(artwork) {
  const imageId = artwork.image_id || artwork.id
  if (imageId) {
    router.push({ name: 'Admin', query: { tab: 'verify', image_id: imageId } })
  }
}

function openAnnotate(artwork) {
  const imageId = artwork.image_id || artwork.id
  if (imageId) {
    const resolved = router.resolve({ name: 'InscriptionAnnotator', params: { id: imageId } })
    window.open(resolved.href, '_blank')
  }
}

// ── Library switcher ──
async function fetchAccessibleLibs() {
  try {
    const res = await fetch(`${API_BASE}/libraries/accessible-libraries`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}` }
    })
    const data = await res.json()
    accessibleLibs.value = data.libraries || []
    if (!switchingLibraryId.value && libraryId.value) {
      switchingLibraryId.value = libraryId.value
    }
  } catch (e) {
    console.error('获取作品库列表失败', e)
  }
}

function onSwitchLibrary(newLibId) {
  if (newLibId && newLibId !== libraryId.value) {
    if (props.embedded) {
      router.replace({ query: { ...route.query, detail_id: String(newLibId) } })
    } else {
      router.push(`/libraries/${newLibId}`)
    }
  }
}

// ── Batch translate ──
async function startBatchTranslate(mode) {
  const forceRetranslate = mode === 'all'
  showTranslateModeDialog.value = false
  batchTranslating.value = true
  showTranslateProgress.value = true
  translateProgress.value = { current: 0, total: 0, status: '', percent: 0 }
  try {
    const params = new URLSearchParams()
    params.set('library_id', String(libraryId.value))
    params.set('force_retranslate', String(forceRetranslate))
    const response = await fetch(`${API_BASE}/content-analysis/translate/batch/stream?${params.toString()}`, { method: 'POST' })
    const { streamSSE, cancel } = useSSEStream()
    translateCancelFn = cancel
    await streamSSE(response, {
      onEvent: (event) => {
        if (event.type === 'start') {
          translateProgress.value = { current: 0, total: event.total, status: 'translating', percent: 0 }
        } else if (event.type === 'progress' || event.type === 'record_done') {
          const pct = Math.round((event.current / event.total) * 100)
          translateProgress.value = { current: event.current, total: event.total, status: 'translating', percent: pct }
        } else if (event.type === 'done') {
          translateProgress.value = { current: event.total, total: event.total, status: 'done', percent: 100 }
          ElMessage.success(`批量翻译完成：成功 ${event.translated} 条，失败 ${event.failed} 条`)
          loadArtworks()
        }
      },
      onError: (err) => { ElMessage.error('批量翻译失败: ' + err.message) },
      onComplete: () => { batchTranslating.value = false },
    })
  } catch (e) {
    ElMessage.error('批量翻译失败')
    batchTranslating.value = false
  }
}

function cancelBatchTranslate() {
  if (translateCancelFn) { translateCancelFn(); translateCancelFn = null }
  batchTranslating.value = false
  showTranslateProgress.value = false
}

// ── Batch analyze ──
async function startBatchAnalyze(mode) {
  const incremental = mode === 'incremental'
  showAnalyzeModeDialog.value = false
  analyzing.value = true
  showAnalyzeProgress.value = true
  analyzeProgress.value = { current: 0, total: 0, status: 'analyzing', percent: 0 }
  try {
    const params = new URLSearchParams()
    params.set('library_id', String(libraryId.value))
    params.set('incremental', String(incremental))
    const response = await fetch(`${API_BASE}/content-analysis/batch-reanalyze/stream?${params.toString()}`, { method: 'POST' })
    const { streamSSE, cancel } = useSSEStream()
    analyzeCancelFn = cancel
    await streamSSE(response, {
      onEvent: (event) => {
        if (event.type === 'total') {
          analyzeProgress.value = { current: 0, total: event.total, status: 'analyzing', percent: 0 }
        } else if (event.type === 'progress') {
          const pct = Math.round((event.current / event.total) * 100)
          analyzeProgress.value = { current: event.current, total: event.total, status: 'analyzing', percent: pct }
        } else if (event.type === 'complete') {
          analyzeProgress.value = { current: event.total, total: event.total, status: 'done', percent: 100 }
          ElMessage.success(`分析完成：更新 ${event.updated} 条，错误 ${event.errors} 条`)
          loadArtworks()
        }
      },
      onError: (err) => { ElMessage.error('批量重跑失败: ' + err.message) },
      onComplete: () => { analyzing.value = false },
    })
  } catch (e) {
    ElMessage.error('批量重跑失败')
    analyzing.value = false
  }
}

function cancelBatchAnalyze() {
  if (analyzeCancelFn) { analyzeCancelFn(); analyzeCancelFn = null }
  analyzing.value = false
  showAnalyzeProgress.value = false
}

// ── Batch AI analyze ──
async function startBatchAiAnalyze(mode) {
  showAiAnalyzeDialog.value = false
  aiAnalyzing.value = true
  showAiAnalyzeProgress.value = true
  aiAnalyzeProgress.value = { current: 0, total: 0, status: 'analyzing', percent: 0 }
  try {
    const imageIds = artworks.value
      .filter(a => a.image_id)
      .map(a => a.image_id)
    if (imageIds.length === 0) {
      ElMessage.warning('库内没有可分析的作品')
      aiAnalyzing.value = false
      showAiAnalyzeProgress.value = false
      return
    }
    aiAnalyzeProgress.value.total = imageIds.length
    const r = await tubiApi.batchAutoAnalyze(imageIds, mode)
    if (!r.success) {
      ElMessage.error(r.detail || '触发分析失败')
      aiAnalyzing.value = false
      showAiAnalyzeProgress.value = false
      return
    }
    aiAnalyzeCancelFn = startAiPolling(imageIds)
  } catch (e) {
    ElMessage.error('触发分析失败')
    aiAnalyzing.value = false
    showAiAnalyzeProgress.value = false
  }
}

function startAiPolling(imageIds) {
  const timer = setInterval(async () => {
    try {
      const r = await tubiApi.batchGetStatus(imageIds)
      if (!r.success) return
      const done = r.data.filter(x => x.status === 'analyzed').length
      const errored = r.data.filter(x => x.status === 'error').length
      const total = r.data.length
      const pct = total > 0 ? Math.round((done / total) * 100) : 0
      aiAnalyzeProgress.value = { current: done, total, status: 'analyzing', percent: pct }
      if (done + errored >= total) {
        clearInterval(timer)
        aiAnalyzeCancelFn = null
        aiAnalyzeProgress.value = { current: done, total, status: 'done', percent: 100 }
        aiAnalyzing.value = false
        ElMessage.success(`AI识图完成：成功 ${done} 幅${errored > 0 ? `，失败 ${errored} 幅` : ''}`)
        loadArtworks()
      }
    } catch { /* ignore poll errors */ }
  }, 5000)
  return () => { clearInterval(timer); aiAnalyzeCancelFn = null }
}

function cancelBatchAiAnalyze() {
  if (aiAnalyzeCancelFn) { aiAnalyzeCancelFn(); aiAnalyzeCancelFn = null }
  aiAnalyzing.value = false
  showAiAnalyzeProgress.value = false
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
    if (!props.embedded) router.push('/libraries')
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
  suggestForm.change_summary = ''
  updateSuggestOldValue()
  showSuggestDialog.value = true
}

function updateSuggestOldValue() {
  if (!suggestArtwork.value) return
  const val = suggestArtwork.value[suggestForm.field_name]
  suggestForm.old_value = val !== null && val !== undefined ? String(val) : ''
  suggestForm.new_value = suggestForm.old_value
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

async function handleDeleteArtwork(artwork) {
  try {
    await ElMessageBox.confirm(`确定从作品库中删除「${artwork.title || artwork.filename || '未命名'}」？`, '确认删除', { type: 'warning' })
    await artworkApi.delete(artwork.id)
    ElMessage.success('已删除')
    await loadArtworks()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── Watch tab change to load data ──
watch(libraryId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    loadLibrary()
    loadArtworks()
    fetchAccessibleLibs()
    switchingLibraryId.value = newId
    activeTab.value = 'artworks'
  }
})

watch(manageTab, (tab) => {
  if (tab === 'collaborators') loadCollaborators()
  if (tab === 'pending') loadPendingRequests()
})

onMounted(async () => {
  await loadLibrary()
  await loadArtworks()
  fetchAccessibleLibs()
})

onUnmounted(() => {
  if (aiAnalyzeCancelFn) { aiAnalyzeCancelFn(); aiAnalyzeCancelFn = null }
  if (translateCancelFn) { translateCancelFn(); translateCancelFn = null }
  if (analyzeCancelFn) { analyzeCancelFn(); analyzeCancelFn = null }
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

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-lg);
  flex-wrap: wrap;
  gap: var(--space-sm);
}

.unified-toolbar {
  padding: 10px 14px;
  background: #fafaf7;
  border: 1px solid #e8e3da;
  border-radius: 10px;
  min-height: 38px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.toolbar-center {
  flex: 1;
  text-align: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.flow-arrow {
  color: #c8a45c;
  font-size: 16px;
  font-weight: 300;
  user-select: none;
  margin: 0 2px;
}

.artwork-count {
  font-size: 13px;
  color: var(--stone-gray);
  white-space: nowrap;
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

/* ── 新增样式 ── */
.filename-tip { margin-bottom: 16px; }
.filename-tip code { background: #fdf6f0; color: #c45a3c; padding: 1px 6px; border-radius: 3px; font-size: 12px; }
.toolbar-sep { color: #ccc; user-select: none; margin: 0 2px; }
.inline-upload-area { background: #fff; border: 1px solid #e8e3da; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
.upload-area-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.upload-area-header h3 { margin: 0; font-size: 16px; font-weight: 600; }

/* 状态标记点 */
.artwork-status-tags { display: flex; gap: 4px; margin-top: 4px; }
.status-dot {
  width: 18px; height: 18px; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 600; color: #fff;
  flex-shrink: 0; cursor: default;
}
.status-dot.done { background: #5a8c7a; }
.status-dot.pending { background: #d0ccc0; }

/* 模式选择弹窗样式 */
.translate-mode-options { display: flex; flex-direction: column; gap: 8px; }
.mode-option {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border: 1px solid #e8e3da; border-radius: 8px;
  cursor: pointer; transition: all 0.15s;
}
.mode-option:hover { border-color: #c45a3c; background: #fdf6f0; }
.mode-icon {
  width: 36px; height: 36px; border-radius: 8px;
  background: #f0ebe0; display: flex; align-items: center; justify-content: center;
  color: #5c5040; font-size: 16px; flex-shrink: 0;
}
.mode-icon.warning { background: #fef0e8; color: #c45a3c; }
.mode-info { flex: 1; min-width: 0; }
.mode-title { font-size: 14px; font-weight: 600; color: #2c2416; }
.mode-desc { font-size: 12px; color: #8a8578; margin-top: 2px; }
.mode-arrow { color: #c0b8a8; flex-shrink: 0; }

.progress-body { padding: 8px 0; }
.progress-info { display: flex; gap: 8px; margin-bottom: 12px; }
.progress-label { color: #8a8578; font-size: 13px; }
.progress-value { font-weight: 600; color: #2c2416; font-size: 13px; }
.progress-status { margin-top: 12px; }
.status-text { font-size: 13px; color: #8a8578; }
.status-text.done { color: #5a8c7a; font-weight: 500; }

.manage-badge {
  margin-left: 6px;
}

.unified-toolbar .el-button.is-active {
  background: #fdf6f0;
  border-color: #c45a3c;
  color: #c45a3c;
}

/* 我的意见对话框 */
.old-value-display {
  width: 100%;
  padding: 10px 12px;
  background: #f5f5f5;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 13px;
  color: #888;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
  user-select: text;
  cursor: text;
}
</style>
