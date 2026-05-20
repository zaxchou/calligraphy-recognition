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

  <!-- 解析文字选项弹窗 -->
  <el-dialog
    v-model="showAnalyzeModeDialog"
    title="解析文字"
    width="420px"
    class="translate-mode-dialog claude-dialog"
  >
    <div class="translate-mode-options">
      <div class="mode-option" @click="startIncrementalSmartProcess()">
        <div class="mode-icon"><el-icon><Refresh /></el-icon></div>
        <div class="mode-info">
          <div class="mode-title">增量重跑</div>
          <div class="mode-desc">仅处理尚未分析或分析已过期的作品，保留已有结果</div>
        </div>
        <el-icon class="mode-arrow"><Right /></el-icon>
      </div>
      <div class="mode-option" @click="startBatchAnalyze('full')">
        <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
        <div class="mode-info">
          <div class="mode-title">全部重跑</div>
          <div class="mode-desc">重新分析所有作品的主题和情感（会覆盖已有分析结果）</div>
        </div>
        <el-icon class="mode-arrow"><Right /></el-icon>
      </div>
    </div>
    <div v-if="batchResultData" style="margin-top:12px; padding:10px; background:#f5f7fa; border-radius:6px; font-size:13px; color:#333;">
      <p style="margin:0 0 6px; font-weight:600;">📋 上次结果</p>
      <p style="margin:2px 0;">{{ batchResultData.message }}</p>
      <p v-if="batchResultData.report" style="margin:2px 0; color:#999;">
        可信度 {{ batchResultData.report.confidence_stats?.average || '?' }} | LLM修正 {{ batchResultData.report.llm_corrected || 0 }} 幅 | {{ batchResultData.report.updated_at || '' }}
      </p>
      <el-button text size="small" type="primary" @click="showAnalyzeModeDialog = false; showBatchResultDialog = true" style="margin-top:4px;">查看完整报告</el-button>
    </div>
    <template #footer>
      <el-button @click="showAnalyzeModeDialog = false">取消</el-button>
    </template>
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
        :color="analyzeProgressColor"
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

  <!-- 批量重跑结果弹窗 -->
  <el-dialog
    v-model="showBatchResultDialog"
    title="批量重跑结果"
    width="860px"
    class="claude-dialog batch-result-dialog"
    @close="closeBatchResultDialog"
  >
    <div v-if="batchResultData" class="batch-result-body">
      <!-- 概览 -->
      <div class="report-header">
        <div class="report-title">{{ batchResultData.message }}</div>
        <div class="report-summary">
          重跑完成: <span class="highlight">{{ batchResultData.updated }}</span> 幅更新,
          <span :class="batchResultData.errors > 0 ? 'error' : ''">{{ batchResultData.errors }}</span> 幅错误
        </div>
      </div>

      <!-- 一、主题覆盖率对比 -->
      <div class="report-section" v-if="batchResultData.report?.theme_coverage?.length">
        <div class="section-title">一、主题覆盖率对比（新 vs 旧，含1st/2nd/3rd）</div>
        <table class="report-table">
          <thead>
            <tr>
              <th>主题</th>
              <th>旧</th>
              <th>旧%</th>
              <th>新</th>
              <th>新%</th>
              <th>变化</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in batchResultData.report.theme_coverage" :key="item.name">
              <td>{{ item.name }}</td>
              <td>{{ item.old_count }}</td>
              <td>{{ item.old_percent }}%</td>
              <td>{{ item.new_count }}</td>
              <td>{{ item.new_percent }}%</td>
              <td :class="item.change > 0 ? 'up' : item.change < 0 ? 'down' : ''">
                {{ item.change > 0 ? '+' : '' }}{{ item.change }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 一.5、第一主题分布对比 -->
      <div class="report-section" v-if="batchResultData.report?.primary_theme_distribution?.length">
        <div class="section-title">一.5、第一主题分布对比（新 vs 旧）</div>
        <table class="report-table">
          <thead>
            <tr>
              <th>主题</th>
              <th>旧</th>
              <th>旧%</th>
              <th>新</th>
              <th>新%</th>
              <th>变化</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in batchResultData.report.primary_theme_distribution" :key="item.name">
              <td>{{ item.name }}</td>
              <td>{{ item.old_count }}</td>
              <td>{{ item.old_percent }}%</td>
              <td>{{ item.new_count }}</td>
              <td>{{ item.new_percent }}%</td>
              <td :class="item.change > 0 ? 'up' : item.change < 0 ? 'down' : ''">
                {{ item.change > 0 ? '+' : '' }}{{ item.change }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 二、情感分布对比 -->
      <div class="report-section" v-if="batchResultData.report?.sentiment_distribution?.length">
        <div class="section-title">二、情感分布对比（新 vs 旧）</div>
        <div class="sentiment-row" v-for="item in batchResultData.report.sentiment_distribution" :key="item.polarity">
          <span class="sentiment-label" :class="item.polarity">{{ item.polarity }}</span>
          <span>: 旧 {{ item.old_count }}({{ item.old_percent }}%) → 新 {{ item.new_count }}({{ item.new_percent }}%)</span>
          <span :class="item.change > 0 ? 'up' : item.change < 0 ? 'down' : ''">
            {{ item.change > 0 ? '+' : '' }}{{ item.change }}
          </span>
        </div>
      </div>

      <!-- 三、情感分数对比 -->
      <div class="report-section" v-if="batchResultData.report?.emotion_score_stats?.new_average !== undefined">
        <div class="section-title">三、情感分数对比</div>
        <div class="score-row">
          新均值: <span class="highlight">{{ batchResultData.report.emotion_score_stats.new_average > 0 ? '+' : '' }}{{ batchResultData.report.emotion_score_stats.new_average }}</span>
          <span v-if="batchResultData.report.emotion_score_stats.old_average !== null">
            (旧: {{ batchResultData.report.emotion_score_stats.old_average > 0 ? '+' : '' }}{{ batchResultData.report.emotion_score_stats.old_average }})
          </span>
        </div>
        <div class="score-row">
          新范围: {{ batchResultData.report.emotion_score_stats.new_min }} ~ {{ batchResultData.report.emotion_score_stats.new_max }}
        </div>
      </div>

      <!-- 四、主题变化路径 -->
      <div class="report-section" v-if="batchResultData.report?.theme_change_paths?.length">
        <div class="section-title">四、主题变化路径（Top 10）</div>
        <div class="change-path" v-for="(item, idx) in batchResultData.report.theme_change_paths" :key="idx">
          {{ item.from }} → {{ item.to }}: {{ item.count }} 幅
        </div>
        <div v-if="batchResultData.report.theme_change_paths.length === 0" class="no-change">无主题变化</div>
      </div>

      <!-- 四.五、可信度分布（v2.1） -->
      <div class="report-section" v-if="batchResultData.report?.confidence_stats">
        <div class="section-title">四.五、可信度分布</div>
        <div class="confidence-grid">
          <div class="conf-bar-row">
            <span class="conf-label">高 (≥0.7)</span>
            <div class="conf-bar-track"><div class="conf-bar high" :style="{ width: batchResultData.report.confidence_stats.high_percent + '%' }"></div></div>
            <span class="conf-count">{{ batchResultData.report.confidence_stats.high }} 幅 ({{ batchResultData.report.confidence_stats.high_percent }}%)</span>
          </div>
          <div class="conf-bar-row">
            <span class="conf-label">中 (0.4~0.7)</span>
            <div class="conf-bar-track"><div class="conf-bar mid" :style="{ width: batchResultData.report.confidence_stats.mid_percent + '%' }"></div></div>
            <span class="conf-count">{{ batchResultData.report.confidence_stats.mid }} 幅 ({{ batchResultData.report.confidence_stats.mid_percent }}%)</span>
          </div>
          <div class="conf-bar-row">
            <span class="conf-label">低 (&lt;0.4)</span>
            <div class="conf-bar-track"><div class="conf-bar low" :style="{ width: batchResultData.report.confidence_stats.low_percent + '%' }"></div></div>
            <span class="conf-count">{{ batchResultData.report.confidence_stats.low }} 幅 ({{ batchResultData.report.confidence_stats.low_percent }}%)</span>
          </div>
        </div>
        <div class="conf-avg">平均可信度：{{ batchResultData.report.confidence_stats.average }}</div>
        <div v-if="batchResultData.report.low_conf_count > 0" class="conf-hint">
          ⚠️ {{ batchResultData.report.low_conf_count }} 幅作品可信度 &lt; 0.6，建议运行分歧检测以校准规则
        </div>
        <div v-if="batchResultData.report.llm_corrected > 0" class="conf-hint" style="color:#67c23a">
          ✅ DeepSeek 自动修正了 {{ batchResultData.report.llm_corrected }} 幅低可信度作品
        </div>
      </div>

      <!-- 五、偏差检测与调整建议 -->
      <div class="report-section" v-if="batchResultData.report?.deviation_checks?.length">
        <div class="section-title">五、偏差检测与调整建议（基于第一主题）</div>
        <div class="deviation-item" v-for="(item, idx) in batchResultData.report.deviation_checks" :key="idx">
          <span :class="item.status === 'ok' ? 'status-ok' : 'status-warn'">
            [{{ item.status === 'ok' ? 'OK' : '!' }}]
          </span>
          <span class="deviation-theme">{{ item.theme }}:</span>
          <span>{{ item.suggestion }}</span>
        </div>
      </div>

      <div class="report-footer">
        重跑完成。请根据偏差检测结果调整规则，然后重新运行。
      </div>
    </div>
    <template #footer>
      <el-button plain size="small" @click="copyReportAsMarkdown" :disabled="!batchResultData">
        <el-icon><CopyDocument /></el-icon>复制报告(MD)
      </el-button>
      <el-button @click="closeBatchResultDialog">取消</el-button>
      <el-button type="primary" @click="rerunFromResult" :loading="analyzing">重新分析</el-button>
    </template>
  </el-dialog>
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
                    <el-link v-if="row.artwork_image_id" type="primary" :underline="false" @click="$router.push(`/tubi/${row.artwork_image_id}`)">
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
                    <el-link v-if="row.artwork_image_id" type="primary" :underline="false" @click="$router.push(`/tubi/${row.artwork_image_id}`)">
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
              <div class="diff-panel-content" v-html="renderDiffSegments(diffOldSegments)"></div>
            </div>
            <div class="diff-arrow"><el-icon size="20"><Right /></el-icon></div>
            <div class="diff-panel">
              <h4 class="diff-panel-title diff-panel-new">新值</h4>
              <div class="diff-panel-content" v-html="renderDiffSegments(diffNewSegments)"></div>
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
import { ref, onMounted, watch, computed, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { Bottom, Refresh, RefreshRight, Right, CopyDocument, WarningFilled } from '@element-plus/icons-vue'
import { useBatchOperations } from '../composables/useBatchOperations'
import { useSSEStream } from '../composables/useSSEStream'

import VerifyPanel from './VerifyPanel.vue'
import AlbumManager from './AlbumManager.vue'
import TagManager from './TagManager.vue'
import StripManager from './StripManager.vue'
import DimensionInput from './DimensionInput.vue'
import AnnotationVerify from './AnnotationVerify.vue'
import ArtistInfoManager from './ArtistInfoManager.vue'
import ArtistRulesManager from './ArtistRulesManager.vue'
import SealManager from './SealManager.vue'
import ImageSearchPanel from '../components/tubi/ImageSearchPanel.vue'
import AdminDashboard from './admin/Dashboard.vue'
import AdminUsers from './admin/Users.vue'
import AdminSettings from './admin/Settings.vue'
import { useAuthStore } from '../stores/authStore'
import { libraryApi } from '../api/index.js'
import { computeDiff } from '../utils/diff'
import LibraryManage from './admin/LibraryManage.vue'

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
const activeTab = ref(VALID_TABS.includes(route.query.tab) ? route.query.tab : 'artist-info')
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
const adminBatchState = inject('adminBatchState', null)

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

// 监听侧边栏批量操作触发（已迁移至作品库详情页）
// watch(adminBatchTrigger, ...) 已移除

// ── 状态 ──
const records = ref([])
const loading = ref(false)
const saving = ref(false)
const translating = ref(false)
const verifiedCount = ref(0)
const totalCount = ref(0)
const translatedCount = ref(0)
const analyzedCount = ref(0)
const annotatedCount = ref(0)
const incrementalProcessing = ref(false)
const selectedLibraryId = ref(null)
const selectedArtist = ref('all')
const artistList = ref([])

// URL → artist 同步（浏览器后退/前进时刷新）
watch(() => route.query.artist, (newArtist) => {
  const artist = Array.isArray(newArtist) ? newArtist[0] : newArtist
  if (artist && artist !== selectedArtist.value) {
    selectedArtist.value = artist
    fetchRecords()
  }
})

function onArtistChange() {
  router.replace({ query: { ...route.query, artist: selectedArtist.value } })
  fetchRecords()
}
async function fetchArtistList() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
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
  analyzeProgressColor,
  startBatchAnalyze,
  cancelBatchAnalyze,
  startBatchTranslate,
  cancelBatchTranslate,
  batchResultData,
  showBatchResultDialog,
  closeBatchResultDialog,
} = useBatchOperations({ apiBase: API_BASE, fetchRecords, getArtist: () => '', getLibraryId: () => selectedLibraryId.value })

// 同步批量操作的 loading 状态到侧边栏
watch([analyzing, batchTranslating], () => {
  if (adminBatchState) {
    adminBatchState.analyzing = analyzing.value
    adminBatchState.translating = batchTranslating.value
  }
})

// 始终弹出模式选择窗口（含上次结果链接）
function openBatchReanalyze() {
  showAnalyzeModeDialog.value = true
}

// 从结果弹窗重新分析
function rerunFromResult() {
  showBatchResultDialog.value = false
  startBatchAnalyze('full')
}

// 增量智能处理：SSE 流式版，带进度显示
async function startIncrementalSmartProcess() {
  showAnalyzeModeDialog.value = false
  incrementalProcessing.value = true
  showAnalyzeProgress.value = true
  analyzeProgress.value = { current: 0, total: 0, status: 'analyzing', percent: 0 }
  try {
    const params = new URLSearchParams()
    params.set('incremental', 'true')
    if (selectedLibraryId.value) params.set('library_id', String(selectedLibraryId.value))
    const response = await fetch(
      `${API_BASE}/content-analysis/batch-reanalyze/stream?${params.toString()}`,
      { method: 'POST' }
    )
    const { streamSSE } = useSSEStream()
    let report = null
    await streamSSE(response, {
      onEvent: (event) => {
        if (event.type === 'total') {
          analyzeProgress.value = { current: 0, total: event.total, status: 'analyzing', percent: 0 }
        } else if (event.type === 'progress') {
          const pct = Math.round((event.current / event.total) * 100)
          analyzeProgress.value = { current: event.current, total: event.total, status: 'analyzing', percent: pct }
        } else if (event.type === 'complete') {
          report = event
          batchResultData.value = {
            total: event.total,
            updated: event.updated,
            errors: event.errors,
            message: event.message,
            report: { ...event.report, updated_at: new Date().toLocaleString() },
          }
          try { localStorage.setItem(`batch-reanalyze-result_lib${selectedLibraryId.value}`, JSON.stringify(batchResultData.value)) } catch {}
          analyzeProgress.value = { current: event.total, total: event.total, status: 'done', percent: 100 }
          showBatchResultDialog.value = true
          if (event.report?.llm_corrected > 0) {
            ElMessage.success(`完成！DeepSeek 自动修正了 ${event.report.llm_corrected} 幅`)
          } else if (event.total > 0) {
            ElMessage.success(`完成！共处理 ${event.total} 幅作品`)
          } else {
            ElMessage.info('没有新作品需要处理')
          }
          fetchRecords()
        }
      },
      onError: (err) => {
        ElMessage.error('处理失败: ' + err.message)
      },
    })
  } catch (err) {
    ElMessage.error('处理失败: ' + (err.message || err))
  } finally {
    incrementalProcessing.value = false
    showAnalyzeProgress.value = false
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
    const params = new URLSearchParams({ limit: 500 })
    if (artistParam) params.set('artist', artistParam)
    if (selectedLibraryId.value) params.set('library_id', String(selectedLibraryId.value))
    const res = await fetch(`${API_BASE}/content-analysis/records?${params}`)
    const data = await res.json()
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

async function onReanalyze(recordId) {
  try {
    const resp = await fetch(`${API_BASE}/content-analysis/reanalyze-one/${recordId}`, { method: 'POST' })
    const data = await resp.json()
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
  const route = router.resolve({ name: 'TubiDetail', params: { id: recordId } })
  window.open(route.href, '_blank')
}

function copyReportAsMarkdown() {
  const r = batchResultData.value
  if (!r) return
  const report = r.report
  if (!report) return

  let md = `批量重跑报告 — 共 ${r.total} 幅，${r.updated} 幅更新，${r.errors} 幅错误\n\n`

  if (report.theme_coverage?.length) {
    md += `## 一、主题覆盖率对比\n`
    md += `| 主题 | 旧 | 旧% | 新 | 新% | 变化 |\n|------|-----|------|-----|------|------|\n`
    for (const t of report.theme_coverage) {
      md += `| ${t.name} | ${t.old_count} | ${t.old_percent}% | ${t.new_count} | ${t.new_percent}% | ${t.change >= 0 ? '+' : ''}${t.change} |\n`
    }
    md += `\n`
  }

  if (report.primary_theme_distribution?.length) {
    md += `## 一.五、第一主题分布对比\n`
    md += `| 主题 | 旧 | 旧% | 新 | 新% | 变化 |\n|------|-----|------|-----|------|------|\n`
    for (const t of report.primary_theme_distribution) {
      md += `| ${t.name} | ${t.old_count} | ${t.old_percent}% | ${t.new_count} | ${t.new_percent}% | ${t.change >= 0 ? '+' : ''}${t.change} |\n`
    }
    md += `\n`
  }

  if (report.sentiment_distribution?.length) {
    md += `## 二、情感分布对比\n`
    for (const s of report.sentiment_distribution) {
      md += `- **${s.polarity}**: 旧 ${s.old_count}(${s.old_percent}%) → 新 ${s.new_count}(${s.new_percent}%) (${s.change >= 0 ? '+' : ''}${s.change})\n`
    }
    md += `\n`
  }

  if (report.emotion_score_stats?.new_average !== undefined) {
    md += `## 三、情感分数对比\n`
    md += `| 指标 | 值 |\n|------|----|\n`
    md += `| 新均值 | ${report.emotion_score_stats.new_average} |\n`
    if (report.emotion_score_stats.old_average !== null && report.emotion_score_stats.old_average !== undefined) {
      md += `| 旧均值 | ${report.emotion_score_stats.old_average} |\n`
    }
    md += `| 新范围 | ${report.emotion_score_stats.new_min} ~ ${report.emotion_score_stats.new_max} |\n`
    md += `\n`
  }

  if (report.theme_change_paths?.length) {
    md += `## 四、主题变化路径（Top 10）\n`
    for (const p of report.theme_change_paths) {
      md += `- ${p.from} → ${p.to}: ${p.count} 幅\n`
    }
    md += `\n`
  }

  if (report.confidence_stats) {
    md += `## 四.五、可信度分布\n`
    md += `| 级别 | 数量 | 占比 |\n|------|------|------|\n`
    md += `| 高 (≥0.7) | ${report.confidence_stats.high} 幅 | ${report.confidence_stats.high_percent}% |\n`
    md += `| 中 (0.4~0.7) | ${report.confidence_stats.mid} 幅 | ${report.confidence_stats.mid_percent}% |\n`
    md += `| 低 (<0.4) | ${report.confidence_stats.low} 幅 | ${report.confidence_stats.low_percent}% |\n`
    md += `\n平均可信度：${report.confidence_stats.average}\n`
    if (r.report.low_conf_count > 0) {
      md += `\n⚠️ ${r.report.low_conf_count} 幅作品可信度 < 0.6\n`
    }
    if (r.report.llm_corrected > 0) {
      md += `\n✅ DeepSeek 修正 ${r.report.llm_corrected} 幅\n`
    }
    md += `\n`
  }

  if (report.deviation_checks?.length) {
    md += `## 五、偏差检测与调整建议\n`
    for (const d of report.deviation_checks) {
      md += `- [${d.status === 'ok' ? 'OK' : '!'}] **${d.theme}**: ${d.suggestion}\n`
    }
    md += `\n`
  }

  navigator.clipboard.writeText(md).then(
    () => ElMessage.success('报告已复制到剪贴板'),
    () => ElMessage.error('复制失败，请手动复制')
  )
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

/* 批量重跑结果报告样式 */
.batch-result-dialog :deep(.el-dialog__body) {
  max-height: 70vh;
  overflow-y: auto;
}

.batch-result-body {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.report-header {
  background: linear-gradient(135deg, #faf9f7 0%, #f5f4ed 100%);
  padding: 16px 20px;
  border-radius: 10px;
  margin-bottom: 20px;
  border: 1px solid #e8e4da;
}

.report-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  font-weight: 600;
  color: #141413;
  margin-bottom: 8px;
}

.report-summary {
  font-size: 14px;
  color: #5e5d59;
}

.report-summary .highlight {
  color: #c96442;
  font-weight: 600;
}

.report-summary .error {
  color: #d32f2f;
  font-weight: 600;
}

.report-section {
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e8e4da;
}

.section-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 14px;
  font-weight: 600;
  color: #141413;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0eee6;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.report-table th {
  background: #f5f4ed;
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #3d3d3a;
  border-bottom: 2px solid #e8e4da;
}

.report-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f0eee6;
}

.report-table tr:hover {
  background: #faf9f7;
}

.report-table .up {
  color: #c96442;
  font-weight: 600;
}

.report-table .down {
  color: #5a7d5a;
  font-weight: 600;
}

.sentiment-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0eee6;
}

.sentiment-row:last-child {
  border-bottom: none;
}

.sentiment-label {
  font-weight: 600;
  min-width: 80px;
}

.sentiment-label.positive {
  color: #4e8cff;
}

.sentiment-label.negative {
  color: #ff6b35;
}

.sentiment-label.neutral {
  color: #7f7f7f;
}

.sentiment-row .up {
  color: #c96442;
  font-weight: 600;
}

.sentiment-row .down {
  color: #5a7d5a;
  font-weight: 600;
}

.score-row {
  padding: 6px 0;
  color: #3d3d3a;
}

.score-row .highlight {
  color: #c96442;
  font-weight: 600;
}

.change-path {
  padding: 6px 0;
  color: #5e5d59;
}

.no-change {
  color: #87867f;
  font-style: italic;
}

.deviation-item {
  padding: 8px 0;
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.status-ok {
  color: #5a7d5a;
  font-weight: 600;
}

.status-warn {
  color: #c96442;
  font-weight: 600;
}

.deviation-theme {
  font-weight: 600;
  color: #141413;
}

.report-footer {
  margin-top: 20px;
  padding: 12px 16px;
  background: #fdf8f6;
  border-radius: 8px;
  border: 1px solid #f0d4c8;
  color: #c96442;
  font-size: 13px;
  text-align: center;
}

.confidence-grid { padding: 8px 0; }
.conf-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 12px; }
.conf-label { width: 70px; color: #666; }
.conf-bar-track { flex: 1; height: 8px; background: #eee; border-radius: 4px; overflow: hidden; }
.conf-bar { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.conf-bar.high { background: #67c23a; }
.conf-bar.mid { background: #e6a23c; }
.conf-bar.low { background: #f56c6c; }
.conf-count { width: 120px; text-align: right; color: #999; font-family: monospace; font-size: 11px; }
.conf-avg { font-size: 13px; color: #666; text-align: center; margin-top: 6px; font-family: monospace; }
.conf-hint { font-size: 12px; color: #e6a23c; text-align: center; margin-top: 6px; }

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
</style>
