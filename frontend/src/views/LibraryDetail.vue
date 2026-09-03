<template>
  <div class="library-detail-page">
    <!-- 面包屑 + 标题 -->
    <div class="page-header" v-if="!embedded">
      <div>
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/libraries' }">{{ $t('gallery.title') }}</el-breadcrumb-item>
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
        {{ $t('librarydetail.t1') }}<code>清_李鱓_兰竹图_1750.jpg</code>
        {{ $t('librarydetail.t2') }}
      </template>
    </el-alert>

    <!-- 批量上传区域 -->
    <div v-if="showUploadArea" class="inline-upload-area">
      <div class="upload-area-header">
        <h3>{{ $t('librarydetail.t3') }}</h3>
        <el-button size="small" text @click="showUploadArea = false">
          <el-icon><Close /></el-icon> {{ $t('librarydetail.t4') }}
        </el-button>
      </div>
      <TibaUploadInline
        ref="uploadInlineRef"
        :library-id="libraryId"
        @refresh="onUploadRefresh"
      />
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane :label="$t('librarydetail.a1')" name="artworks">
        <!-- 统一工具栏 -->
        <div class="toolbar unified-toolbar">
          <div class="toolbar-left">
            <el-select v-model="switchingLibraryId" size="small" style="width: 180px" @change="onSwitchLibrary">
              <el-option :label="$t('librarydetail.a2')" value="" disabled />
              <el-option v-for="lib in accessibleLibs" :key="lib.id" :label="lib.name" :value="lib.id" />
            </el-select>
            <span class="toolbar-sep">|</span>
            <el-select v-model="sortBy" size="small" style="width: 140px" @change="loadArtworks">
              <el-option :label="$t('librarydetail.a3')" value="created_at" />
              <el-option :label="$t('suggest.field_artist')" value="artist" />
              <el-option :label="$t('suggest.field_year')" value="year" />
            </el-select>
            <el-button size="small" @click="toggleOrder">
              {{ order === 'desc' ? '↓ 降序' : '↑ 升序' }}
            </el-button>
          </div>
          <div class="toolbar-center">
            <span class="artwork-count">共 {{ totalArtworks }} 件</span>
          </div>
          <div class="toolbar-right">
            <el-button size="small" @click="handleUploadClick" :disabled="!canEdit" :class="{ 'is-active': showUploadArea }">
              <el-icon><Upload /></el-icon>{{ showUploadArea ? '收起上传' : '上传作品' }}
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="showAiAnalyzeDialog = true" :loading="aiAnalyzing" :title="$t('librarydetail.a4')">
              <el-icon><MagicStick /></el-icon>{{ $t('librarydetail.t5') }}
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="goVerifyPage" :title="$t('librarydetail.a5')">
              <el-icon><EditPen /></el-icon>{{ $t('librarydetail.t6') }}
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="showAnalyzeModeDialog = true" :loading="analyzing" :title="$t('librarydetail.a6')">
              <el-icon><Refresh /></el-icon>{{ $t('analysis.text') }}
            </el-button>
            <span class="flow-arrow">→</span>
            <el-button plain size="small" @click="showTranslateModeDialog = true" :loading="batchTranslating" :title="$t('librarydetail.a7')">
              <el-icon><Bottom /></el-icon>{{ $t('librarydetail.t7') }}
            </el-button>
          </div>
        </div>

        <div v-if="artworkLoading" class="loading-wrap">
          <el-skeleton :rows="3" animated />
        </div>

        <el-empty v-else-if="artworks.length === 0" :description="$t('librarydetail.a8')">
          <el-button type="primary" @click="handleUploadClick" :disabled="!canEdit">{{ $t('librarydetail.t8') }}</el-button>
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
              <el-icon v-else :size="40"><Picture /></el-icon>
              <div class="artwork-status-badge" v-if="artwork.status === 'analyzing'">
                <el-icon class="is-loading"><Loading /></el-icon>
              </div>
              <div class="artwork-status-dots">
                <el-tooltip :content="artwork.inscription_modern ? '翻译已完成' : '待翻译'" placement="top">
                  <span class="status-dot" :class="artwork.inscription_modern ? 'done' : 'pending'">{{ $t('librarydetail.t9') }}</span>
                </el-tooltip>
                <el-tooltip :content="artwork.content_analysis ? '文字分析已完成' : '待文字分析'" placement="top">
                  <span class="status-dot" :class="artwork.content_analysis ? 'done' : 'pending'">{{ $t('librarydetail.t10') }}</span>
                </el-tooltip>
                <el-tooltip :content="artwork.inscription_verified ? '题跋已校对' : '题跋待校对'" placement="top">
                  <span class="status-dot" :class="artwork.inscription_verified ? 'done' : 'pending'">{{ $t('librarydetail.t11') }}</span>
                </el-tooltip>
                <el-tooltip :content="artwork.is_manual_annotated ? '标注已完成' : '标注待定'" placement="top">
                  <span class="status-dot" :class="artwork.is_manual_annotated ? 'done' : 'pending'">{{ $t('librarydetail.t12') }}</span>
                </el-tooltip>
                <el-tooltip :content="(artwork.status === 'analyzed' && (artwork.inscription_content || artwork.content_analysis || artwork.analysis_note)) ? 'AI识图已完成' : 'AI识图待定'" placement="top">
                  <span class="status-dot" :class="(artwork.status === 'analyzed' && (artwork.inscription_content || artwork.content_analysis || artwork.analysis_note)) ? 'done' : 'pending'">{{ $t('librarydetail.t13') }}</span>
                </el-tooltip>
              </div>
            </div>
            <div class="artwork-info" @click="openArtworkDetail(artwork)">
              <h4 class="artwork-title">{{ artwork.title || artwork.filename || '未命名' }}</h4>
              <p class="artwork-meta">
                <span v-if="artwork.artist">{{ artwork.artist }}</span>
                <span v-if="artwork.year">({{ artwork.year }})</span>
              </p>
            </div>
            <div class="artwork-card-footer" v-if="canEdit">
              <button class="card-btn" @click.stop="openProofread(artwork)" :title="$t('librarydetail.a9')"><el-icon><EditPen /></el-icon></button>
              <button class="card-btn" @click.stop="openEdit(artwork)" :title="$t('librarydetail.a10')"><el-icon><Edit /></el-icon></button>
              <button class="card-btn" @click.stop="handleTriggerAnalyze(artwork)" :title="$t('librarydetail.a11')"><el-icon><VideoPlay /></el-icon></button>
              <button class="card-btn card-btn-danger" @click.stop="handleDeleteArtwork(artwork)" :title="$t('common.delete')"><el-icon><Delete /></el-icon></button>
              <button class="card-btn card-btn-suggest" v-if="!canEdit" @click.stop="openSuggestEdit(artwork)" :title="$t('btn.suggest')"><el-icon><Edit /></el-icon></button>
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
          {{ $t('librarydetail.t14') }}
          <el-badge v-if="pendingRequestCount > 0" :value="pendingRequestCount" class="manage-badge" />
        </template>

        <el-tabs v-model="manageTab" type="card">
          <el-tab-pane :label="$t('librarydetail.a12')" name="info">
            <el-form :model="editForm" label-width="100px" class="manage-form">
              <el-form-item :label="$t('librarydetail.a13')">
                <el-input v-model="editForm.name" maxlength="100" />
              </el-form-item>
              <el-form-item :label="$t('suggest.field_artist')">
                <el-input v-model="editForm.artist_name" maxlength="100" />
              </el-form-item>
              <el-form-item :label="$t('libraries.a3')">
                <el-input v-model="editForm.description" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item :label="$t('libraries.a4')">
                <el-radio-group v-model="editForm.visibility">
                  <el-radio value="private">{{ $t('librarydetail.t15') }}</el-radio>
                  <el-radio value="public">{{ $t('librarydetail.t16') }}</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleUpdateLibrary" :loading="saving">{{ $t('librarydetail.t17') }}</el-button>
                <el-button type="danger" plain @click="handleDeleteLibrary" :disabled="library.artwork_count > 0">
                  {{ $t('librarydetail.t18') }}
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane :label="$t('librarydetail.a14')" name="collaborators">
            <div class="manage-section">
              <h3>{{ $t('librarydetail.t19') }}</h3>
              <div class="add-collab-row">
                <el-input v-model="newCollabOpenid" :placeholder="$t('librarydetail.a15')" size="small" style="width: 300px" />
                <el-select v-model="newCollabRole" size="small" style="width: 120px">
                  <el-option :label="$t('librarydetail.t21')" value="viewer" />
                  <el-option :label="$t('librarydetail.t22')" value="editor" />
                  <el-option :label="$t('librarydetail.t23')" value="maintainer" />
                </el-select>
                <el-button type="primary" size="small" @click="handleAddCollaborator">{{ $t('albummanager.t17') }}</el-button>
              </div>

              <h3 style="margin-top: 24px">{{ $t('librarydetail.t20') }}</h3>
              <el-table :data="collaborators" style="width: 100%" v-if="collaborators.length > 0">
                <el-table-column prop="nickname" :label="$t('librarydetail.a16')" />
                <el-table-column prop="role" :label="$t('librarydetail.a17')">
                  <template #default="{ row }">
                    <el-tag v-if="row.role === 'viewer'" size="small">{{ $t('librarydetail.t21') }}</el-tag>
                    <el-tag v-else-if="row.role === 'editor'" type="warning" size="small">{{ $t('librarydetail.t22') }}</el-tag>
                    <el-tag v-else-if="row.role === 'maintainer'" type="danger" size="small">{{ $t('librarydetail.t23') }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="$t('engine.actions')" width="100">
                  <template #default="{ row }">
                    <el-button type="danger" link size="small" @click="handleRemoveCollaborator(row.user_id)">{{ $t('librarydetail.t24') }}</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else :description="$t('librarydetail.a18')" :image-size="60" />
            </div>
          </el-tab-pane>

          <el-tab-pane :label="$t('c-notificationbell.s3')" name="pending">
            <div class="manage-section">
              <div v-if="pendingRequests.length === 0">
                <el-empty :description="$t('contentverify.a21')" :image-size="80" />
              </div>
              <div v-else class="request-list">
                <div v-for="req in pendingRequests" :key="req.id" class="request-card">
                  <div class="request-header">
                    <span class="request-type">
                      <el-tag v-if="req.request_type === 'edit_field'" size="small">{{ $t('librarydetail.t25') }}</el-tag>
                      <el-tag v-else-if="req.request_type === 'edit_inscription'" type="warning" size="small">{{ $t('librarydetail.t26') }}</el-tag>
                      <el-tag v-else-if="req.request_type === 'adjust_region'" type="danger" size="small">{{ $t('librarydetail.t27') }}</el-tag>
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
                    <el-button type="success" size="small" @click="handleReview(req.id, 'approve')">{{ $t('c-notificationbell.s1') }}</el-button>
                    <el-button type="danger" size="small" @click="handleReview(req.id, 'reject')">{{ $t('contentverify.t7') }}</el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
    </el-tabs>

    <!-- 作品详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" :title="$t('librarydetail.a19')" size="600px">
      <template v-if="selectedArtwork">
        <div class="drawer-thumb">
          <el-image
            v-if="selectedArtwork.url || selectedArtwork.thumbnail_url"
            :src="selectedArtwork.url || selectedArtwork.thumbnail_url"
            :preview-src-list="[selectedArtwork.url || selectedArtwork.thumbnail_url]"
            :initial-index="0"
            fit="contain"
            style="max-width:100%;max-height:400px"
          >
            <template #error>
              <img v-if="selectedArtwork.thumbnail_url" :src="selectedArtwork.thumbnail_url" style="max-width:100%;max-height:400px;object-fit:contain" />
            </template>
          </el-image>
        </div>
        <el-descriptions :column="2" border style="margin-top:16px">
          <el-descriptions-item :label="$t('suggest.field_title')">{{ selectedArtwork.title || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('suggest.field_artist')">{{ selectedArtwork.artist || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('suggest.field_year')">{{ selectedArtwork.year || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('factor.period')">{{ selectedArtwork.period || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('factor.painting')">{{ selectedArtwork.material || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('librarydetail.a20')">{{ selectedArtwork.mounting_format || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('librarydetail.a21')">{{ selectedArtwork.current_location || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('contentverify.a22')">
            <el-tag v-if="selectedArtwork.status === 'analyzed'" type="success" size="small">{{ $t('analysis.complete') }}</el-tag>
            <el-tag v-else-if="selectedArtwork.status === 'analyzing'" type="warning" size="small">{{ $t('librarydetail.t28') }}</el-tag>
            <el-tag v-else type="info" size="small">{{ $t('librarydetail.t29') }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('suggest.field_notes')" :span="2">{{ selectedArtwork.notes || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('librarydetail.a22')" :span="2">{{ selectedArtwork.provenance || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions" style="margin-top:16px">
          <el-button type="primary" @click="showDetailDrawer = false; openSuggestEdit(selectedArtwork)">{{ $t('btn.suggest') }}</el-button>
          <el-button @click="openTibaDetail">{{ $t('librarydetail.t30') }}</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 我的意见对话框 -->
    <el-dialog v-model="showSuggestDialog" :title="$t('btn.suggest')" width="560px" destroy-on-close>
      <template v-if="suggestArtwork">
        <p style="margin-bottom:16px;color:var(--stone-gray)">
          {{ $t('librarydetail.t31') }}<strong>{{ suggestArtwork.title || '未命名' }}</strong> {{ $t('librarydetail.t32') }}
        </p>
        <el-form :model="suggestForm" label-position="top">
          <el-form-item :label="$t('suggest.field')">
            <el-select v-model="suggestForm.field_name" style="width:100%">
              <el-option :label="$t('suggest.field_title')" value="title" />
              <el-option :label="$t('suggest.field_artist')" value="artist" />
              <el-option :label="$t('suggest.field_year')" value="year" />
              <el-option :label="$t('factor.period')" value="period" />
              <el-option :label="$t('factor.painting')" value="material" />
              <el-option :label="$t('librarydetail.a23')" value="mounting_format" />
              <el-option :label="$t('librarydetail.a21')" value="current_location" />
              <el-option :label="$t('librarydetail.a24')" value="provenance" />
              <el-option :label="$t('librarydetail.a25')" value="style_tags" />
              <el-option :label="$t('librarydetail.a26')" value="subject_tags" />
              <el-option :label="$t('librarydetail.a27')" value="technique_tags" />
              <el-option :label="$t('librarydetail.a28')" value="inscription_author" />
              <el-option :label="$t('librarydetail.a29')" value="inscription_date" />
              <el-option :label="$t('suggest.field_notes')" value="notes" />
              <el-option :label="$t('suggest.field_inscription')" value="inscription_content" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('suggest.old_value')">
            <div class="old-value-display">{{ suggestForm.old_value }}</div>
          </el-form-item>
          <el-form-item :label="$t('suggest.new_value')" required>
            <el-input v-model="suggestForm.new_value" type="textarea" :autosize="{ minRows: 2, maxRows: 8 }" :placeholder="$t('suggest.new_value_ph')" />
          </el-form-item>
          <el-form-item :label="$t('suggest.change_desc')">
            <el-input v-model="suggestForm.change_summary" type="textarea" :rows="3" :placeholder="$t('suggest.change_desc_ph')" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showSuggestDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSubmitChange" :loading="submitting">{{ $t('suggest.submit') }}</el-button>
      </template>
    </el-dialog>

    <!-- 批量翻译选项弹窗 -->
    <el-dialog v-model="showTranslateModeDialog" :title="$t('librarydetail.a30')" width="420px">
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchTranslate('untranslated')">
          <div class="mode-icon"><el-icon><Bottom /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t33') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t34') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchTranslate('all')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t35') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t36') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchTranslate('en_untranslated')">
          <div class="mode-icon" style="background:#e8f0f8;"><el-icon><Bottom /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t37') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t38') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchTranslate('en_all')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t39') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t40') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 批量重跑选项弹窗 -->
    <el-dialog v-model="showAnalyzeModeDialog" :title="$t('librarydetail.a31')" width="420px">
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchAnalyze('incremental')">
          <div class="mode-icon"><el-icon><Refresh /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t41') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t42') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option" @click="startBatchAnalyze('full')">
          <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('analysis.all') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t43') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 翻译进度弹窗 -->
    <el-dialog v-model="showTranslateProgress" :title="$t('librarydetail.a32')" width="420px" :close-on-click-modal="false" :show-close="false">
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">{{ $t('librarydetail.t44') }}</span>
          <span class="progress-value">{{ translateProgress.current }} / {{ translateProgress.total }}</span>
        </div>
        <el-progress :percentage="translateProgress.percent" :stroke-width="8" />
        <div class="progress-status">
          <span v-if="translateProgress.status === 'translating'" class="status-text">{{ $t('librarydetail.t45') }}</span>
          <span v-else-if="translateProgress.status === 'done'" class="status-text done">{{ $t('librarydetail.t46') }}</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchTranslate" :disabled="translateProgress.status === 'done'">{{ $t('common.cancel') }}</el-button>
        <el-button plain @click="showTranslateProgress = false" :disabled="translateProgress.status !== 'done'">{{ $t('common.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- 批量分析进度弹窗 -->
    <el-dialog v-model="showAnalyzeProgress" :title="$t('librarydetail.a33')" width="420px" :close-on-click-modal="false" :show-close="false">
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">{{ $t('librarydetail.t47') }}</span>
          <span class="progress-value">{{ analyzeProgress.current }} / {{ analyzeProgress.total }}</span>
        </div>
        <el-progress :percentage="analyzeProgress.percent" :stroke-width="8" />
        <div class="progress-status">
          <span v-if="analyzeProgress.status === 'analyzing'" class="status-text">{{ $t('librarydetail.t48') }}</span>
          <span v-else-if="analyzeProgress.status === 'done'" class="status-text done">{{ $t('contentverify.s11') }}</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchAnalyze" :disabled="analyzeProgress.status === 'done'">{{ $t('common.cancel') }}</el-button>
        <el-button plain @click="showAnalyzeProgress = false" :disabled="analyzeProgress.status !== 'done'">{{ $t('common.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- AI识图弹窗 -->
    <el-dialog v-model="showAiAnalyzeDialog" :title="$t('librarydetail.a34')" width="400px">
      <div class="translate-mode-options">
        <div class="mode-option" @click="startBatchAiAnalyze('incremental')">
          <div class="mode-icon"><el-icon><MagicStick /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t49') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t50') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
        <div class="mode-option warn" @click="startBatchAiAnalyze('analyze')">
          <div class="mode-icon warning"><el-icon><Refresh /></el-icon></div>
          <div class="mode-info">
            <div class="mode-title">{{ $t('librarydetail.t51') }}</div>
            <div class="mode-desc">{{ $t('librarydetail.t52') }}</div>
          </div>
          <el-icon class="mode-arrow"><Right /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- AI识图进度弹窗 -->
    <el-dialog v-model="showAiAnalyzeProgress" :title="$t('librarydetail.a35')" width="420px" :close-on-click-modal="false" :show-close="false">
      <div class="progress-body">
        <div class="progress-info">
          <span class="progress-label">{{ $t('librarydetail.t47') }}</span>
          <span class="progress-value">{{ aiAnalyzeProgress.current }} / {{ aiAnalyzeProgress.total }}</span>
        </div>
        <el-progress :percentage="aiAnalyzeProgress.percent" :stroke-width="8" />
        <div class="progress-status">
          <span v-if="aiAnalyzeProgress.status === 'analyzing'" class="status-text">{{ $t('librarydetail.t53') }}</span>
          <span v-else-if="aiAnalyzeProgress.status === 'done'" class="status-text done">{{ $t('librarydetail.t54') }}</span>
        </div>
      </div>
      <template #footer>
        <el-button plain @click="cancelBatchAiAnalyze" :disabled="aiAnalyzeProgress.status === 'done'">{{ $t('common.cancel') }}</el-button>
        <el-button plain @click="showAiAnalyzeProgress = false" :disabled="aiAnalyzeProgress.status !== 'done'">{{ $t('common.close') }}</el-button>
      </template>
    </el-dialog>

    <TibaEditDialog ref="editDialogRef" @saved="loadArtworks" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Picture, Loading, Plus, View, ArrowRight, Collection, Edit, VideoPlay, Delete, Close, Bottom, Right, Refresh, RefreshRight, EditPen, Crop, MagicStick } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import { libraryApi, artworkApi, tibaApi } from '../api'
import TibaUploadInline from '@/components/tiba/TibaUploadInline.vue'
import TibaEditDialog from '@/components/tiba/TibaEditDialog.vue'
import { useSSEStream } from '@/composables/useSSEStream'
import { translate as t } from '@/locales'

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
const uploadInlineRef = ref(null)

function handleUploadClick() {
  if (showUploadArea.value) {
    showUploadArea.value = false
  } else {
    showUploadArea.value = true
    // UploadPhaseIdle 是异步组件，需要等它渲染完成
    let retries = 0
    const tryOpen = () => {
      if (uploadInlineRef.value?.triggerFilePicker()) {
        // 成功触发
      } else if (retries++ < 10) {
        setTimeout(tryOpen, 150)
      }
    }
    nextTick(() => setTimeout(tryOpen, 100))
  }
}

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
const editDialogRef = ref(null)

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
let translateCancelFn = null
let analyzeCancelFn = null
let aiAnalyzeCancelFn = null
const aiAnalyzeImageIds = ref([])  // 保存当前批次的 image_ids，用于取消

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
    ElMessage.error(t('libraries.s1'))
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
    ElMessage.error(t('librarydetail.s1'))
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

function openTibaDetail() {
  if (!selectedArtwork.value?.image_id) return
  window.open(window.location.origin + '/#/tiba/' + selectedArtwork.value.image_id, '_blank')
}

function openAnnotate(artwork) {
  const imageId = artwork.image_id || artwork.id
  if (imageId) {
    const resolved = router.resolve({ name: 'InscriptionAnnotator', params: { id: imageId } })
    window.open(resolved.href, '_blank')
  }
}

function openEdit(artwork) {
  editDialogRef.value?.open(artwork)
}

function goVerifyPage() {
  router.push({ name: 'Admin', query: { tab: 'verify' } })
}

// ── Library switcher ──
async function fetchAccessibleLibs() {
  try {
    const data = await api.get('/libraries/accessible-libraries')
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
  const isEnglish = mode === 'en_untranslated' || mode === 'en_all'
  const forceRetranslate = mode === 'all' || mode === 'en_all'
  showTranslateModeDialog.value = false
  batchTranslating.value = true
  showTranslateProgress.value = true
  translateProgress.value = { current: 0, total: 0, status: '', percent: 0 }
  try {
    const params = new URLSearchParams()
    params.set('library_id', String(libraryId.value))
    params.set('force_retranslate', String(forceRetranslate))
    if (isEnglish) params.set('target', 'english')
    const response = await fetch(`${API_BASE}/content-analysis/translate/batch/stream?${params.toString()}`, { method: 'POST', signal: AbortSignal.timeout(300000) })
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
    ElMessage.error(t('librarydetail.s2'))
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
    const response = await fetch(`${API_BASE}/content-analysis/batch-reanalyze/stream?${params.toString()}`, { method: 'POST', signal: AbortSignal.timeout(300000) })
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
    ElMessage.error(t('librarydetail.s3'))
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
    // 从后端获取所有作品（不限分页），避免只发当前页
    const resp = await tibaApi.getAllResults(0, 2000, null, libraryId.value)
    const allItems = resp?.results || resp?.data || []
    // 增量模式：只包含未分析的作品
    const imageIds = mode === 'incremental'
      ? allItems.filter(a => a.status !== 'analyzed').map(a => a.image_id || a.id).filter(Boolean)
      : allItems.map(a => a.image_id || a.id).filter(Boolean)
    if (imageIds.length === 0) {
      ElMessage.warning(mode === 'incremental' ? '没有未分析的作品' : '库内没有可分析的作品')
      aiAnalyzing.value = false
      showAiAnalyzeProgress.value = false
      return
    }
    aiAnalyzeImageIds.value = imageIds
    aiAnalyzeProgress.value.total = imageIds.length
    const r = await tibaApi.batchAutoAnalyze(imageIds, mode)
    if (!r.success) {
      ElMessage.error(r.detail || '触发分析失败')
      aiAnalyzing.value = false
      showAiAnalyzeProgress.value = false
      return
    }
    aiAnalyzeCancelFn = startAiPolling(imageIds)
  } catch (e) {
    ElMessage.error(t('librarydetail.s4'))
    aiAnalyzing.value = false
    showAiAnalyzeProgress.value = false
  }
}

function startAiPolling(imageIds) {
  const timer = setInterval(async () => {
    try {
      const r = await tibaApi.batchGetStatus(imageIds)
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

async function cancelBatchAiAnalyze() {
  if (aiAnalyzeCancelFn) { aiAnalyzeCancelFn(); aiAnalyzeCancelFn = null }
  aiAnalyzing.value = false
  showAiAnalyzeProgress.value = false
  // 调用后端真正取消队列中的任务
  if (aiAnalyzeImageIds.value.length > 0) {
    try { await tibaApi.batchCancel(aiAnalyzeImageIds.value) } catch {}
    aiAnalyzeImageIds.value = []
  }
}

async function handleUpdateLibrary() {
  saving.value = true
  try {
    await libraryApi.update(libraryId.value, editForm)
    ElMessage.success(t('librarydetail.s5'))
    await loadLibrary()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteLibrary() {
  try {
    await ElMessageBox.confirm(t('librarydetail.s12'), '确认删除', { type: 'warning' })
    await libraryApi.delete(libraryId.value, true)
    ElMessage.success(t('knowledgesearch.s2'))
    if (!props.embedded) router.push('/libraries')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(t('engine.delete_error'))
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
    ElMessage.warning(t('librarydetail.s6'))
    return
  }
  try {
    await libraryApi.addCollaborator(libraryId.value, {
      openid: newCollabOpenid.value.trim(),
      role: newCollabRole.value,
    })
    ElMessage.success(t('librarydetail.s7'))
    newCollabOpenid.value = ''
    await loadCollaborators()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  }
}

async function handleRemoveCollaborator(userId) {
  try {
    await ElMessageBox.confirm(t('librarydetail.s13'), '确认', { type: 'warning' })
    await libraryApi.removeCollaborator(libraryId.value, userId)
    ElMessage.success(t('librarydetail.s8'))
    await loadCollaborators()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(t('common.failure'))
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
    ElMessage.warning(t('suggest.enter_new_value'))
    return
  }
  if (suggestForm.new_value === suggestForm.old_value) {
    ElMessage.warning(t('librarydetail.s9'))
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
    ElMessage.success(t('librarydetail.s10'))
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
    ElMessage.success(t('librarydetail.s11'))
    await loadArtworks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '触发分析失败')
  }
}

async function handleDeleteArtwork(artwork) {
  try {
    await ElMessageBox.confirm(`确定从作品库中删除「${artwork.title || artwork.filename || '未命名'}」？`, '确认删除', { type: 'warning' })
    await artworkApi.delete(artwork.id)
    ElMessage.success(t('knowledgesearch.s2'))
    await loadArtworks()
  } catch (e) { if (e !== 'cancel') ElMessage.error(t('engine.delete_error')) }
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
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.artwork-card {
  background: var(--pure-white);
  border: 1px solid var(--border-cream);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.artwork-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.07);
}

.artwork-thumb {
  height: 160px;
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
  top: 6px;
  left: 6px;
  background: rgba(0,0,0,0.55);
  color: white;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

/* 状态点叠加在缩略图右上角 */
.artwork-status-dots {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 3px;
}

.artwork-status-dots .status-dot {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
  cursor: default;
  transition: background 0.2s;
}

.artwork-status-dots .status-dot.done {
  background: #4caf50;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}

.artwork-status-dots .status-dot.pending {
  background: rgba(255,255,255,0.12);
  color: rgba(255,255,255,0.25);
}

.artwork-card:hover .artwork-status-dots .status-dot.pending {
  background: rgba(0,0,0,0.3);
  color: rgba(255,255,255,0.6);
}

.artwork-info {
  padding: 8px 10px 6px;
}

.artwork-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--near-black);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.artwork-meta {
  font-size: 11px;
  color: var(--stone-gray);
}

/* 卡片底部操作按钮 */
.artwork-card-footer {
  display: flex;
  border-top: 1px solid #f0ede6;
  padding: 2px;
}

.card-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  border: none;
  background: transparent;
  color: #7a7568;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.12s;
}

.card-btn:hover { background: #f5f2eb; color: #5c5040; }
.card-btn-danger:hover { background: #fef0e8; color: #c45a3c; }
.card-btn-suggest { color: #b0a898; }

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
