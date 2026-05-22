<template>
  <div class="analysis-container">
    <!-- 左侧：原作图 + 作品信息（sticky） -->
    <div class="left-panel">
      <!-- 原作卡片 -->
      <el-card shadow="always" class="original-image-card" v-if="analyzeStatus === 'analyzed' && currentImage?.url">
        <template #header>
          <div class="card-header navigation-header">
            <el-button
              size="small"
              :disabled="!prevImage"
              @click="$emit('navigate', prevImage)"
              :icon="ArrowLeft"
            >
              上一幅
            </el-button>
            <span class="nav-title">{{ currentImage.title || '未命名' }}</span>
            <el-button
              size="small"
              :disabled="!nextImage"
              @click="$emit('navigate', nextImage)"
              :icon="ArrowRight"
            >
              下一幅
            </el-button>
          </div>
        </template>
        <div class="original-image-wrapper">
          <img :src="currentImage.thumbnailUrl || currentImage.url" class="original-image" @click="openImagePreview(currentImage.url, currentImage.dzi_url)" title="点击放大查看" />
          <el-icon class="zoom-icon" @click="openImagePreview(currentImage.url, currentImage.dzi_url)" title="放大查看"><ZoomIn /></el-icon>
        </div>

        <!-- 册页导航 -->
        <div v-if="albumNavigation.is_in_album" class="album-navigation">
          <div class="album-nav-header">
            <span class="album-nav-title">「{{ albumNavigation.album_name }}」</span>
            <span class="album-nav-count">第{{ albumNavigation.current_index + 1 }}幅 / 共{{ albumNavigation.total_count }}幅</span>
          </div>
          <div class="album-nav-scroll">
            <button class="album-nav-arrow left" @click="scrollAlbumThumbs(-1)" title="向左滚动">
              <el-icon><ArrowLeft /></el-icon>
            </button>
            <div class="album-nav-thumbnails" ref="albumThumbsRef" @wheel.prevent="onAlbumThumbnailsWheel">
              <div
                v-for="(item, idx) in albumNavigation.items"
                :key="item.id"
                :class="['album-nav-thumbnail', { active: item.is_current }]"
                @click="$emit('navigate-album', item)"
              >
                <img
                  v-if="item.thumbnail_url"
                  :src="item.thumbnail_url"
                  @error="e => e.target.style.display='none'"
                />
                <div v-else class="thumb-placeholder">{{ item.album_index || idx + 1 }}</div>
              </div>
            </div>
            <button class="album-nav-arrow right" @click="scrollAlbumThumbs(1)" title="向右滚动">
              <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </el-card>

      <!-- 画作信息卡片（作者/年份/尺寸合并） -->
      <div class="artwork-info-card" v-if="currentImage.artist || currentImage.year || (currentImage.artwork_width_cm && currentImage.artwork_height_cm)">
        <div class="info-card-row" v-if="currentImage.artist">
          <span class="info-card-label">作者</span>
          <span class="info-card-value">{{ currentImage.artist }}</span>
        </div>
        <div class="info-card-row" v-if="currentImage.year">
          <span class="info-card-label">年份</span>
          <span class="info-card-value">{{ currentImage.year }}年 {{ getDisplayAge(currentImage) !== null ? `(${getDisplayAge(currentImage)}岁)` : '' }}</span>
        </div>
        <div class="info-card-row" v-if="currentImage.artwork_width_cm && currentImage.artwork_height_cm">
          <span class="info-card-label">尺寸</span>
          <span class="info-card-value">{{ currentImage.artwork_height_cm }}cm × {{ currentImage.artwork_width_cm }}cm</span>
        </div>
        <div class="info-card-actions">
          <el-button v-if="authStore.isAdmin || (authStore.isEditor && currentImage.owner_id === authStore.userId)" plain size="small" class="btn-action" @click="$emit('edit-current')">
            <el-icon><Edit /></el-icon><span class="btn-label">编辑</span>
          </el-button>
          <el-button v-if="authStore.isLoggedIn" plain size="small" class="btn-action" @click="openSuggestEdit">
            <el-icon><EditPen /></el-icon><span class="btn-label">我的意见</span>
          </el-button>
          <el-button plain size="small" class="btn-action" @click="openRevisions">
            <el-icon><Clock /></el-icon><span class="btn-label">版本历史</span>
          </el-button>
          <el-button plain size="small" class="btn-action" @click="$emit('back')">
            <el-icon><HomeFilled /></el-icon><span class="btn-label">返回</span>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 右侧：分析结果 -->
    <div class="right-panel">
      <el-card shadow="hover" class="upload-card" :body-style="{ padding: '0' }">
        <div class="image-display">
          <!-- 面积占比智能示意图 + 标签/款识/钤印 并排布局 -->
          <div v-if="analyzeStatus === 'analyzed'" class="analysis-result-layout">
            <div class="analysis-left-col">
              <div class="annotated-image-section">
                <h4 class="section-title">
                  <el-icon><DataAnalysis /></el-icon> 面积占比智能示意图
                  <el-button
                    v-if="authStore.isAdmin || (authStore.isEditor && currentImage.owner_id === authStore.userId)"
                    size="small" text
                    class="btn-annotate"
                    @click="$emit('open-annotator')"
                  >手动标注</el-button>
                </h4>
                <div class="annotated-image-wrapper" @mouseenter="showDiagramOverlay = true" @mouseleave="showDiagramOverlay = false">
                  <img :src="currentImage.annotatedImageUrl" class="annotated-image" />
                  <div v-if="currentImage.isManualAnnotated" class="manual-annotated-badge" title="已手动标注">
                    <el-icon><Check /></el-icon>
                  </div>
                  <!-- 悬浮布局示意图 -->
                  <transition name="fade">
                    <div v-if="showDiagramOverlay && diagramRegions.inscription_regions?.length" class="diagram-hover-overlay">
                      <svg
                        class="diagram-svg"
                        :viewBox="`0 0 100 ${(100 * (currentImage?.height || 1) / (currentImage?.width || 1)).toFixed(1)}`"
                        preserveAspectRatio="xMidYMid meet"
                      >
                        <polygon
                          v-for="(reg, idx) in diagramRegions.painting_regions"
                          :key="'p'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-painting-poly"
                        />
                        <polygon
                          v-for="(reg, idx) in diagramRegions.inscription_regions"
                          :key="'i'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-inscription-poly"
                        />
                        <polygon
                          v-for="(reg, idx) in diagramRegions.blank_regions"
                          :key="'b'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-blank-poly"
                        />
                      </svg>
                      <div class="diagram-legend-overlay">
                        <span class="legend-item"><span class="legend-dot inscription"></span>题跋</span>
                        <span class="legend-item"><span class="legend-dot painting"></span>绘画</span>
                        <span class="legend-item"><span class="legend-dot blank"></span>留白</span>
                      </div>
                    </div>
                  </transition>
                </div>
              </div>
              <!-- 题跋布局类型（精简版） -->
              <div class="spatial-analysis-card" v-if="analyzeStatus === 'analyzed' && positionAnalysis">
                <h4 class="section-title">
                  <el-icon><DataAnalysis /></el-icon> 题跋布局类型
                  <div class="form-types-inline" v-if="positionAnalysis?.form_types?.length">
                    <el-tooltip
                      v-for="ft in positionAnalysis.form_types.filter(f => f.matched)"
                      :key="ft.code"
                      :content="ft.description"
                      placement="bottom"
                      effect="dark"
                    >
                      <span class="form-type-tag" :class="`tag-code-${ft.code}`">
                        {{ ft.name }}
                      </span>
                    </el-tooltip>
                    <span v-if="positionAnalysis.vl_overall_status === 'partial_timeout'" class="vl-timeout-badge">VL超时</span>
                  </div>
                </h4>
                <div class="spatial-description" v-if="positionAnalysis?.form_types?.length">
                  <div
                    v-for="ft in positionAnalysis.form_types.filter(f => f.matched)"
                    :key="ft.code"
                    class="form-type-desc-row"
                  >
                    <span class="desc-tag" :class="`desc-tag-${ft.code}`">{{ ft.code }}</span>
                    <span class="desc-text">{{ ft.description }}</span>
                  </div>
                  <div v-if="!positionAnalysis.form_types.filter(f => f.matched).length" class="desc-none">
                    {{ positionAnalysis.layout_description || '暂无形式分析结果' }}
                  </div>
                </div>
                <div class="spatial-description" v-else>
                  {{ positionAnalysis.layout_description }}
                </div>
              </div>
              <!-- 主题与情感分析卡片 -->
              <div class="theme-sentiment-card" v-if="currentImage?.contentAnalysis">
                <h4 class="section-title">
                  <el-icon><DataAnalysis /></el-icon> 主题与情感分析
                  <el-tag size="small" type="info" v-if="currentImage.contentAnalysis?.period_phase">
                    {{ currentImage.contentAnalysis.period_phase }}
                  </el-tag>
                </h4>
                <div class="theme-sentiment-content">
                  <div class="ts-section" v-if="currentImage.contentAnalysis?.themes?.length">
                    <div class="ts-label">主题</div>
                    <div class="theme-tags">
                      <el-tag
                        v-for="theme in currentImage.contentAnalysis.themes"
                        :key="theme.code"
                        size="small"
                        class="theme-tag"
                      >
                        {{ theme.name }}
                        <span class="theme-confidence">({{ Math.round(theme.confidence * 100) }}%)</span>
                      </el-tag>
                    </div>
                  </div>

                  <div class="ts-section" v-if="currentImage.contentAnalysis?.sentiment">
                    <div class="ts-label">情感极性</div>
                    <div class="sentiment-card">
                      <div class="sentiment-header">
                        <span
                          class="sentiment-dot"
                          :style="{ background: currentImage.contentAnalysis.sentiment.polarity === 'positive'  ? '#4e8cff' : currentImage.contentAnalysis.sentiment.polarity === 'negative'  ? '#ff6b35' : '#b8a47e' }"
                        ></span>
                        <span class="sentiment-polarity-text" :style="{
                          color: currentImage.contentAnalysis.sentiment.polarity === 'positive' ? '#67c23a' :
                                 currentImage.contentAnalysis.sentiment.polarity === 'negative' ? '#f56c6c' : '#909399'
                        }">{{
                          currentImage.contentAnalysis.sentiment.polarity === 'positive'  ? '积极' :
                          currentImage.contentAnalysis.sentiment.polarity === 'negative'  ? '消极' : '中性'
                        }}</span>
                        <span class="sentiment-sep">·</span>
                        <span class="sentiment-score-text">强度 {{
                          Math.round(getSentimentIntensity(currentImage.contentAnalysis.sentiment) * 100)
                        }}%</span>
                        <template v-if="currentImage.contentAnalysis.sentiment.emotion_score != null">
                          <span class="sentiment-sep">·</span>
                          <span class="sentiment-score-text">分值 {{ currentImage.contentAnalysis.sentiment.emotion_score > 0 ? '+' : '' }}{{ currentImage.contentAnalysis.sentiment.emotion_score }}</span>
                        </template>
                        <template v-if="currentImage.contentAnalysis.v4_confidence != null">
                          <span class="sentiment-sep">·</span>
                          <span
                            class="sentiment-score-text confidence-tag"
                            :class="currentImage.contentAnalysis.v4_confidence >= 0.7 ? 'conf-high' : currentImage.contentAnalysis.v4_confidence >= 0.4 ? 'conf-mid' : 'conf-low'"
                          >
                            可信度 {{ Math.round(currentImage.contentAnalysis.v4_confidence * 100) }}%
                          </span>
                        </template>
                      </div>
                      <div class="sentiment-bar-track">
                        <div
                          class="sentiment-bar-fill"
                          :style="{
                            width: Math.round(getSentimentIntensity(currentImage.contentAnalysis.sentiment) * 100) + '%',
                            background: currentImage.contentAnalysis.sentiment.polarity === 'positive'  ? '#4e8cff' : currentImage.contentAnalysis.sentiment.polarity === 'negative'  ? '#ff6b35' : '#b8a47e'
                          }"
                        ></div>
                      </div>
                    </div>
                    <!-- 结构化推导步骤（新版） -->
                    <div class="reasoning-steps" v-if="currentImage.contentAnalysis.sentiment.reasoning_steps?.length">
                      <div class="reasoning-label">推导过程</div>
                      <div class="steps-list">
                        <div
                          v-for="(step, idx) in currentImage.contentAnalysis.sentiment.reasoning_steps"
                          :key="idx"
                          class="step-item"
                          :class="{ 'step-final': step.offset === null }"
                        >
                          <span class="step-icon">{{ step.icon }}</span>
                          <div class="step-body">
                            <div class="step-header">
                              <span class="step-label">{{ step.label }}</span>
                              <span
                                v-if="step.offset !== null && step.offset !== 0"
                                class="step-offset"
                                :class="step.offset > 0 ? 'offset-pos' : 'offset-neg'"
                              >{{ step.offset > 0 ? '+' : '' }}{{ step.offset }}</span>
                              <span v-else-if="step.offset === 0" class="step-offset offset-zero">0</span>
                            </div>
                            <div class="step-detail" v-html="mapPolarityText(step.detail)"></div>
                          </div>
                        </div>
                      </div>
                    </div>
                    <!-- 兼容旧版纯文本推导 -->
                    <div class="sentiment-reasoning" v-else-if="currentImage.contentAnalysis.sentiment.reasoning">
                      <div class="reasoning-label">推导过程</div>
                      <div class="reasoning-text">{{ currentImage.contentAnalysis.sentiment.reasoning }}</div>
                    </div>
                  </div>

                <div class="ts-empty" v-if="!currentImage.contentAnalysis?.themes?.length && !currentImage.contentAnalysis?.sentiment">
                  暂无内容分析数据
                </div>
                </div>
              </div>
            </div>
            <div class="analysis-right-col">
              <div class="inscription-note-main">
                <h4><el-icon><Edit /></el-icon> 款识题跋</h4>
                <div v-if="currentImage.inscriptionContent" class="inscription-content">
                  {{ currentImage.inscriptionContent }}
                </div>
                <div v-else class="inscription-empty">
                  <p>暂无款识题跋内容</p>
                  <p class="empty-tip">可在编辑画作信息时添加</p>
                </div>
                <div v-if="currentImage.inscriptionModern && currentImage.inscriptionModern !== currentImage.inscriptionContent" class="inscription-translation">
                  <div class="translation-divider"></div>
                  <div class="translation-label">
                    <el-tag type="success" size="small">白话文</el-tag>
                  </div>
                  <div class="translation-content">{{ currentImage.inscriptionModern }}</div>
                </div>
              </div>
              <div class="seal-note-main">
                <h4><el-icon><Collection /></el-icon> 钤印</h4>
                <div v-if="currentImage.sealContent" class="seal-content">
                  <div class="seal-tags-display">
                    <span v-for="(seal, idx) in detailSealTags" :key="idx"
                      class="seal-display-tag"
                      :class="{ 'has-image': detailSealImageMap[seal.name] }"
                      @click="openSealLightbox(seal.name)">
                      {{ seal.name }}
                      <span v-if="seal.seal_type" class="seal-display-type">{{ seal.seal_type }}</span>
                    </span>
                  </div>
                </div>
                <div v-else class="seal-empty"><p>暂无钤印内容</p></div>
              </div>
              <div v-if="currentImage && getDetailAllTags().length > 0" class="detail-tags-section">
                <div class="detail-tags-list">
                  <span v-for="(tag, idx) in getDetailAllTags()" :key="idx" class="detail-tag" @click="$emit('filter-by-tag', tag)">{{ tag }}</span>
                </div>
              </div>
              <!-- 题跋占比分析 -->
              <div class="stats-section">
                <h4 class="section-title"><el-icon><PieChart /></el-icon> 题跋占比分析</h4>
                <div class="stats-content">
                  <div ref="pieChartRef" class="pie-chart-small"></div>
                </div>
                <div class="stats-list">
                  <div class="stat-item inscription">
                    <span class="stat-dot" style="background: #d4846a;"></span>
                    <span class="stat-name">题跋区域</span>
                    <span class="stat-percentile" v-if="areaPercentile !== null">高于{{ currentImage.artist || '该画家' }} {{ areaPercentile }}% 的作品</span>
                    <span class="stat-percent">{{ areaStats.inscriptionPercent }}%</span>
                  </div>
                  <div class="stat-item painting" v-if="areaStats.paintingPercent > 0">
                    <span class="stat-dot" style="background: #7ba3c4;"></span>
                    <span class="stat-name">绘画区域</span>
                    <span class="stat-percent">{{ areaStats.paintingPercent }}%</span>
                  </div>
                  <div class="stat-item blank" v-if="areaStats.blankPercent > 0">
                    <span class="stat-dot" style="background: #a8c97a;"></span>
                    <span class="stat-name">留白区域</span>
                    <span class="stat-percent">{{ areaStats.blankPercent }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 未分析时显示Canvas -->
          <div class="canvas-wrapper" v-else>
            <canvas ref="canvasRef" class="annotation-canvas"></canvas>
          </div>

          <!-- AI分析进度显示 -->
          <div v-if="analyzeStatus === 'analyzing'" class="analyzing-progress">
            <div class="glow-progress-container">
              <div class="glow-progress-bar">
                <div class="glow-progress-fill" :style="{ width: analyzeProgress + '%' }"></div>
              </div>
              <span class="glow-progress-text">{{ analyzeProgress }}%</span>
            </div>
            <p class="analyzing-text">{{ analyzingStep }}</p>
            <p class="analyzing-subtext">书画AI智能系统正在分析中...</p>
          </div>

          <div class="image-meta">
            <el-tag>{{ currentImage.name }}</el-tag>
            <el-tag type="info">{{ currentImage.width }} × {{ currentImage.height }}</el-tag>
            <el-tag v-if="analyzeStatus === 'analyzed'" type="success">分析完成</el-tag>
            <el-button
              v-if="analyzeStatus !== 'analyzing' && analyzeStatus !== 'analyzed'"
              type="primary"
              size="small"
              @click="$emit('auto-analyze')"
            >
              开始AI分析
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- 作品库 -->
      <el-card shadow="hover" class="history-card">
        <template #header>
          <div class="card-header">
            <span>作品库</span>
            <el-button type="primary" size="small" @click="openRanking" :icon="Clock">
              查看全部
            </el-button>
          </div>
        </template>
        <div class="history-grid" v-if="relatedWorks.length > 0">
          <div
            v-for="item in relatedWorks"
            :key="item.id"
            class="history-grid-item"
            :class="{ 'is-current': item.id === currentImage.id }"
            @click="$emit('history-item-click', item)"
          >
            <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="history-grid-thumb" loading="lazy" />
            <div v-else class="history-grid-thumb-placeholder">
              <el-icon size="16"><Picture /></el-icon>
            </div>
            <div v-if="item.id === currentImage.id" class="history-grid-thumb-overlay">
              <el-icon><Check /></el-icon>
            </div>
            <div class="history-grid-title">{{ item.title || '未命名' }}</div>
          </div>
        </div>
        <div class="history-summary empty" v-else>
          <p>暂无同作者作品</p>
        </div>
      </el-card>
    </div>

    <!-- 深度缩放查看器（覆盖整个浏览器窗口） -->
    <TubiDeepZoomDialog
      v-if="imagePreviewVisible"
      :image-url="currentPreviewImage"
      :dzi-url="currentPreviewDzi"
      @close="imagePreviewVisible = false"
    />

    <!-- 印章 Lightbox（OpenSeadragon 缩放/翻页） -->
    <SealLightbox
      v-if="sealLightboxVisible"
      :visible="sealLightboxVisible"
      :seal="selectedSealForLightbox"
      @close="sealLightboxVisible = false"
    />

    <!-- 我的意见对话框 -->
    <el-dialog v-model="showSuggestDialog" title="我的意见" width="560px" destroy-on-close @closed="suggestDialogClosed">
      <p style="margin-bottom:16px;color:var(--stone-gray)">
        您正在对 <strong>{{ currentImage.title || '未命名' }}</strong> 提出修改意见，提交后由管理员审核。
      </p>
      <el-form :model="suggestForm" label-position="top">
        <el-form-item label="修改字段">
          <el-select v-model="suggestForm.field_name" style="width:100%">
            <el-option label="标题" value="title" />
            <el-option label="画家" value="artist" />
            <el-option label="年代" value="year" />
            <el-option label="时期" value="period" />
            <el-option label="备注" value="notes" />
            <el-option label="题跋内容" value="inscription_content" />
            <el-option label="标注图" value="annotation_regions" />
          </el-select>
        </el-form-item>
        <el-form-item label="原值">
          <div class="old-value-display">{{ suggestForm.old_value }}</div>
        </el-form-item>
        <template v-if="suggestForm.field_name === 'annotation_regions'">
          <el-form-item label="修改标注">
            <div style="font-size:13px;color:#666;margin-bottom:12px;">
              点击下方按钮，在标注编辑器中修改题跋区域。修改完成后点击"提交审阅"即可。
            </div>
            <el-button type="primary" @click="openAnnotatorSuggest">
              <el-icon><EditPen /></el-icon> 打开标注编辑器
            </el-button>
            <div v-if="suggestAnnotationSaved" style="margin-top:10px;color:#67c23a;font-size:13px;">
              <el-icon><CircleCheckFilled /></el-icon> 标注意见已提交
            </div>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="新值" required>
            <el-input v-model="suggestForm.new_value" type="textarea" :autosize="{ minRows: 2, maxRows: 8 }" placeholder="在原值基础上修改，或输入新内容" />
          </el-form-item>
          <el-form-item label="修改说明" required>
            <el-input v-model="suggestForm.change_summary" type="textarea" :rows="3" placeholder="请说明修改依据，如文献出处、专家意见等" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showSuggestDialog = false">取消</el-button>
        <el-button v-if="suggestForm.field_name !== 'annotation_regions'" type="primary" @click="handleSubmitChange" :loading="submitting">提交意见</el-button>
      </template>
    </el-dialog>

    <!-- 版本历史对话框 -->
    <el-dialog v-model="showRevisionsDialog" title="版本历史" width="700px" destroy-on-close>
      <div v-if="revisionsLoading" style="text-align:center;padding:40px;">
        <el-icon class="is-loading" size="24"><Loading /></el-icon>
        <p style="margin-top:12px;color:#999;">加载中...</p>
      </div>
      <template v-else>
        <el-empty v-if="revisions.length === 0" description="暂无版本历史" />
        <el-timeline v-else>
          <el-timeline-item
            v-for="rev in revisions"
            :key="rev.id"
            :timestamp="rev.created_at"
            placement="top"
          >
            <div class="rev-header">
              <span class="rev-number">#{{ rev.revision_number }}</span>
              <el-tag :type="rev.operation_type === 'rollback' ? 'warning' : rev.operation_type === 'approve' ? 'success' : 'info'" size="small">
                {{ rev.operation_type === 'rollback' ? '回滚' : rev.operation_type === 'approve' ? '审核通过' : '直接编辑' }}
              </el-tag>
            </div>
            <div class="rev-summary">{{ rev.change_summary || '无摘要' }}</div>
            <el-button v-if="rev.revision_number > 1" text size="small" type="primary" @click="handleRollback(rev)">
              回滚到此版本
            </el-button>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Picture, Edit, EditPen, HomeFilled, Clock, ArrowLeft, ArrowRight, ArrowDown, Collection, Check, DataAnalysis, PieChart, ZoomIn, CircleCheckFilled
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDisplayAge } from '../tubi/utils'
import { sealsApi } from '../api'
import api from '../api'
import TubiDeepZoomDialog from '../components/tubi/TubiDeepZoomDialog.vue'
import SealLightbox from '../components/seal/SealLightbox.vue'
import { useAuthStore } from '../stores/authStore'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const authStore = useAuthStore()

function canEditItem(item) {
  return authStore.isAdmin || (authStore.isEditor && item.owner_id === authStore.userId)
}

// 我的意见
const showSuggestDialog = ref(false)
const suggestForm = reactive({
  field_name: 'title',
  old_value: '',
  new_value: '',
  change_summary: ''
})
const submitting = ref(false)
const suggestAnnotationSaved = ref(false)

function getSuggestFieldValue(fieldName) {
  if (!props.currentImage) return ''
  if (fieldName === 'inscription_content') {
    return props.currentImage.inscriptionContent || ''
  }
  if (fieldName === 'annotation_regions') {
    return '标注图（请在标注编辑器中查看）'
  }
  const val = props.currentImage[fieldName]
  return val !== null && val !== undefined ? String(val) : ''
}

function updateSuggestOldValue() {
  suggestForm.old_value = getSuggestFieldValue(suggestForm.field_name)
  suggestForm.new_value = suggestForm.old_value
}

watch(() => suggestForm.field_name, updateSuggestOldValue)

const ANNOTATE_SUGGEST_FLAG = 'suggest_annotation_done_'

function openSuggestEdit() {
  if (!props.currentImage) return
  if (!props.currentImage.library_id) {
    ElMessage.warning('该作品未关联作品库，无法提交意见')
    return
  }
  // 检查先前打开的标注审阅是否已保存
  const id = props.currentImage.id || props.currentImage.image_id
  suggestAnnotationSaved.value = !!localStorage.getItem(ANNOTATE_SUGGEST_FLAG + id)
  suggestForm.field_name = 'title'
  suggestForm.old_value = getSuggestFieldValue('title')
  suggestForm.new_value = suggestForm.old_value
  suggestForm.change_summary = ''
  showSuggestDialog.value = true
}

function openAnnotatorSuggest() {
  if (!props.currentImage) return
  const imageId = props.currentImage.image_id || props.currentImage.id
  if (!imageId) {
    ElMessage.warning('无法获取作品ID')
    return
  }
  const libId = props.currentImage.library_id
  const artworkDbId = props.currentImage.id || props.currentImage.db_id
  const role = authStore.userInfo?.role || 'guest'
  // 同时存入 sessionStorage 和 URL 参数（sessionStorage 在部分浏览器跨 window.open 不可靠）
  sessionStorage.setItem('suggest_library_id', String(libId))
  sessionStorage.setItem('suggest_artwork_id', String(artworkDbId))
  window.open(`/#/annotate/${imageId}?mode=suggest&role=${role}&lib=${libId}&artwork=${artworkDbId}`, '_blank')
}

function suggestDialogClosed() {
  // 关闭对话框时检查标注保存标志
  const id = props.currentImage?.id || props.currentImage?.image_id
  if (id && localStorage.getItem(ANNOTATE_SUGGEST_FLAG + id)) {
    suggestAnnotationSaved.value = true
    localStorage.removeItem(ANNOTATE_SUGGEST_FLAG + id)
  }
}

async function handleSubmitChange() {
  if (!suggestForm.new_value) {
    ElMessage.warning('请输入新值')
    return
  }
  if (!suggestForm.change_summary || !suggestForm.change_summary.trim()) {
    ElMessage.warning('请填写修改说明')
    return
  }
  const libId = props.currentImage.library_id
  if (!libId) {
    ElMessage.error('该作品未关联作品库，无法提交意见。请刷新页面后重试')
    return
  }
  submitting.value = true
  try {
    const data = {
      artwork_id: props.currentImage.id || props.currentImage.db_id,
      field_name: suggestForm.field_name,
      old_value: suggestForm.old_value,
      new_value: suggestForm.new_value,
      change_summary: suggestForm.change_summary,
      request_type: suggestForm.field_name === 'inscription_content' ? 'edit_inscription' : 'edit_field'
    }
    await api.post(`/libraries/${libId}/requests`, data)
    ElMessage.success('意见已提交')
    showSuggestDialog.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

// 版本历史
const showRevisionsDialog = ref(false)
const revisions = ref([])
const revisionsLoading = ref(false)

async function openRevisions() {
  if (!props.currentImage) return
  showRevisionsDialog.value = true
  revisionsLoading.value = true
  try {
    const resp = await api.get(`/artworks/${props.currentImage.id}/revisions`)
    revisions.value = resp.revisions || []
  } catch (e) {
    ElMessage.error('加载版本历史失败')
    revisions.value = []
  } finally {
    revisionsLoading.value = false
  }
}

async function handleRollback(rev) {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 #${rev.revision_number}？此操作不可撤销。`,
      '回滚确认',
      { confirmButtonText: '确认回滚', cancelButtonText: '取消', type: 'warning' }
    )
    await api.post(`/artworks/${props.currentImage.id}/rollback/${rev.id}`)
    ElMessage.success('回滚成功')
    showRevisionsDialog.value = false
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '回滚失败')
    }
  }
}

// 印章显示
const sealLibraryCache = ref([])
const detailSealImageMap = ref({})
const detailSealTypeMap = ref({})

const sealLightboxVisible = ref(false)
const selectedSealForLightbox = ref({ name: '', images: [] })

function openSealLightbox(name) {
  const found = sealLibraryCache.value.find(s => s.name === name)
  if (!found) return
  selectedSealForLightbox.value = found
  sealLightboxVisible.value = true
}

const detailSealTags = computed(() => {
  const content = props.currentImage?.sealContent || ''
  if (!content) return []
  const cleaned = content.replace(/^作者印[：:]\s*/, '')
  return cleaned.split(/[、，,]/).map(n => n.trim()).filter(n => n).map(n => ({
    name: n,
    seal_type: detailSealTypeMap.value[n] || null
  }))
})

async function loadSealLibraryForDetail() {
  if (!props.currentImage?.sealContent) return
  try {
    const res = await sealsApi.list({ limit: 200 })
    if (res.success) {
      sealLibraryCache.value = res.seals || []
      const imgMap = {}, typeMap = {}
      for (const s of sealLibraryCache.value) {
        imgMap[s.name] = !!(s.images && s.images.length > 0)
        if (s.seal_type) typeMap[s.name] = s.seal_type
      }
      detailSealImageMap.value = imgMap
      detailSealTypeMap.value = typeMap
    }
  } catch (e) { console.error('加载印章库失败', e) }
}

onMounted(() => { loadSealLibraryForDetail() })

watch(() => props.currentImage, (img) => {
  if (img && img.sealContent && !sealLibraryCache.value.length) {
    loadSealLibraryForDetail()
  }
})

const props = defineProps({
  currentImage: { type: Object, required: true },
  analysis: {
    type: Object,
    default: () => ({
      status: 'pending',
      progress: 0,
      step: '准备分析...',
      areaStats: { inscriptionPercent: 0, paintingPercent: 0, blankPercent: 0 },
      note: '',
      positionAnalysis: null
    })
  },
  prevImage: { type: Object, default: null },
  nextImage: { type: Object, default: null },
  albumNavigation: { type: Object, default: () => ({ is_in_album: false, items: [] }) },
  historyList: { type: Array, default: () => [] },
  getDetailAllTags: { type: Function, default: () => [] }
})

// 兼容旧的 prop 访问方式（向后兼容）
const analyzeStatus = computed(() => props.analysis?.status || 'pending')
const analyzeProgress = computed(() => props.analysis?.progress || 0)
const analyzingStep = computed(() => props.analysis?.step || '准备分析...')
const areaStats = computed(() => props.analysis?.areaStats || { inscriptionPercent: 0, paintingPercent: 0, blankPercent: 0 })
const analysisNote = computed(() => props.analysis?.note || '')
const positionAnalysis = computed(() => props.analysis?.positionAnalysis || null)

const areaPercentile = computed(() => {
  const myPct = areaStats.value.inscriptionPercent
  if (!myPct || !props.currentImage?.artist || !props.historyList?.length) return null
  const sameArtist = props.historyList.filter(i => i.artist === props.currentImage.artist && i.inscriptionPercent != null && i.inscriptionPercent > 0)
  if (sameArtist.length < 5) return null
  const below = sameArtist.filter(i => i.inscriptionPercent < myPct).length
  return Math.round(below / sameArtist.length * 100)
})

const emit = defineEmits([
  'back', 'edit-current', 'open-upload', 'auto-analyze',
  'navigate', 'navigate-album', 'open-annotator',
  'filter-by-tag', 'history-item-click'
])

// ── 相关作品（同作者，前3 + 当前 + 后8 = 12条）──
const relatedWorks = computed(() => {
  if (!props.currentImage || !props.historyList?.length) return []
  const currentId = props.currentImage.id
  const currentArtist = props.currentImage.artist
  if (!currentId || !currentArtist) return []
  const sameArtist = props.historyList.filter(item => item.artist === currentArtist)
  const idx = sameArtist.findIndex(item => item.id === currentId)
  if (idx < 0) return sameArtist.slice(0, 12)
  const start = Math.max(0, idx - 3)
  return sameArtist.slice(start, start + 12)
})

function openRanking() {
  window.open('/#/tubi/list', '_blank')
}

// ── 册页缩略图滚轮横向滚动 ──────────────────────
const albumThumbsRef = ref(null)

function onAlbumThumbnailsWheel(e) {
  const el = albumThumbsRef.value || e.currentTarget
  if (e.deltaY !== 0) {
    el.scrollLeft += e.deltaY
  }
}

function scrollAlbumThumbs(direction) {
  const el = albumThumbsRef.value
  if (!el) return
  el.scrollBy({ left: direction * 120, behavior: 'smooth' })
}

// ── 悬浮示意图 ────────────────────────────────
const showDiagramOverlay = ref(false)

// ── Canvas 相关 ────────────────────────────────
const canvasRef = ref(null)
let canvas = null
let ctx = null

// ── 饼图相关 ──────────────────────────────────
const pieChartRef = ref(null)
let pieChart = null
let pieChartUpdateRaf = 0

// ── 原图预览缩放 ──────────────────────────────
const imagePreviewVisible = ref(false)
const currentPreviewImage = ref('')
const currentPreviewDzi = ref('')

function openImagePreview(imageUrl, dziUrl) {
  currentPreviewImage.value = imageUrl
  currentPreviewDzi.value = dziUrl || ''
  imagePreviewVisible.value = true
}

// ── 解析 regions ──────────────────────────────
function parseRegions(regionsData) {
  if (!regionsData) return { inscription_regions: [], painting_regions: [], blank_regions: [] }
  let parsed = regionsData
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed) } catch { return { inscription_regions: [], painting_regions: [], blank_regions: [] } }
  }
  return {
    inscription_regions: parsed.inscription_regions || [],
    painting_regions: parsed.painting_regions || [],
    blank_regions: parsed.blank_regions || []
  }
}

// ── 图表 computed ──────────────────────────────
const diagramRegions = computed(() => {
  const currentRegions = parseRegions(props.currentImage?.regions)
  if (!currentRegions.inscription_regions?.length) {
    return { inscription_regions: [], painting_regions: [], blank_regions: [] }
  }
  return currentRegions
})

function toDiagramPoints(reg) {
  if (!reg?.points || reg.points.length < 2) return ''
  const w = props.currentImage?.width || 1000
  const h = props.currentImage?.height || 1000
  const viewBoxH = 100 * h / w
  const pts = reg.points
  if (pts.length === 2) {
    const [p1, p2] = pts
    const rect = [
      { x: Math.min(p1.x, p2.x), y: Math.min(p1.y, p2.y) },
      { x: Math.max(p1.x, p2.x), y: Math.min(p1.y, p2.y) },
      { x: Math.max(p1.x, p2.x), y: Math.max(p1.y, p2.y) },
      { x: Math.min(p1.x, p2.x), y: Math.max(p1.y, p2.y) },
    ]
    return rect.map((p) => `${(p.x / w * 100).toFixed(1)},${(p.y / h * viewBoxH).toFixed(1)}`).join(' ')
  }
  return pts.map((p) => `${(p.x / w * 100).toFixed(1)},${(p.y / h * viewBoxH).toFixed(1)}`).join(' ')
}

// ── 情感强度计算（兼容新旧数据）──
function getSentimentIntensity(sentiment) {
  if (!sentiment) return 0
  if (sentiment.intensity != null) return sentiment.intensity
  // 旧数据兜底：用 emotion_score 绝对值估算（假设最大范围是2）
  return Math.min(Math.abs(sentiment.emotion_score || 0) / 2, 1)
}

// ── 情感文本映射（将英文极性映射为带样式的中文标签）──
function mapPolarityText(text) {
  if (!text) return ''
  return text
    .replace(/\bpositive\b/g, '<span class="pol-label pol-positive">积极</span>')
    .replace(/\bnegative\b/g, '<span class="pol-label pol-negative">消极</span>')
    .replace(/\bneutral\b/g, '<span class="pol-label pol-neutral">中性</span>')
}

function getInscriptionAreaClass() {
  if (!positionAnalysis.value) return ''
  if (positionAnalysis.value.form_types?.length) {
    const matched = positionAnalysis.value.form_types.filter(f => f.matched)
    if (matched.length) return `area-code-${matched[0].code}`
  }
  const layoutType = positionAnalysis.value.layout_type
  if (layoutType === '边角式') return 'area-corner'
  if (layoutType === '拦边封角式') return 'area-frame'
  if (layoutType === '穿插式') return 'area-interleaved'
  if (layoutType === '满布式') return 'area-full'
  if (layoutType === '独立式') return 'area-independent'
  return ''
}

function getInscriptionAreaStyle() {
  if (!positionAnalysis.value) return {}
  const pos = positionAnalysis.value.position
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  const width = props.currentImage?.width || 1000
  const height = props.currentImage?.height || 1000

  const leftPct = (ml / width) * 100
  const rightPct = (mr / width) * 100
  const topPct = (mt / height) * 100
  const bottomPct = (mb / height) * 100
  const areaWidth = 100 - leftPct - rightPct
  const areaHeight = 100 - topPct - bottomPct

  if (areaWidth > 3 && areaHeight > 3 && areaWidth < 95 && areaHeight < 95) {
    return {
      left: leftPct.toFixed(1) + '%',
      top: topPct.toFixed(1) + '%',
      width: areaWidth.toFixed(1) + '%',
      height: areaHeight.toFixed(1) + '%'
    }
  }

  const fallbacks = {
    '左上': { left: '5%', top: '5%', width: '30%', height: '25%' },
    '右上': { right: '5%', top: '5%', width: '30%', height: '25%' },
    '左下': { left: '5%', bottom: '5%', width: '30%', height: '25%' },
    '右下': { right: '5%', bottom: '5%', width: '30%', height: '25%' },
    '左侧': { left: '5%', top: '20%', width: '25%', height: '60%' },
    '右侧': { right: '5%', top: '20%', width: '25%', height: '60%' },
    '上方': { left: '20%', top: '5%', width: '60%', height: '20%' },
    '底部': { left: '20%', bottom: '5%', width: '60%', height: '20%' },
  }
  return fallbacks[pos] || { left: '35%', top: '35%', width: '30%', height: '30%' }
}

function getEdgeDistanceShortText() {
  if (!positionAnalysis.value) return ''
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  const margins = [
    { name: '左', val: ml }, { name: '右', val: mr },
    { name: '上', val: mt }, { name: '下', val: mb }
  ]
  const minMargin = margins.reduce((min, cur) => cur.val < min.val ? cur : min)
  return `${minMargin.name}${Math.round(minMargin.val)}`
}

// ── Canvas 初始化和绘制 ───────────────────────
function initCanvas() {
  if (!canvasRef.value || !props.currentImage) return

  const imageUrl = props.currentImage.url || props.currentImage.annotatedImageUrl
  if (!imageUrl) return

  canvas = canvasRef.value
  ctx = canvas.getContext('2d')

  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    const containerWidth = canvas.parentElement.clientWidth - 40
    const scale = containerWidth / img.width
    const displayWidth = containerWidth
    const displayHeight = img.height * scale

    canvas.width = displayWidth
    canvas.height = displayHeight
    canvas.style.width = displayWidth + 'px'
    canvas.style.height = displayHeight + 'px'

    ctx.drawImage(img, 0, 0, displayWidth, displayHeight)

    if (analyzeStatus.value === 'analyzed') {
      drawRegions()
    }
  }
  img.onerror = () => console.error('Failed to load image:', imageUrl)
  img.src = imageUrl
}

function drawRegions() {
  if (!ctx || !canvas || !props.currentImage) return

  const imageUrl = props.currentImage.url || props.currentImage.annotatedImageUrl
  if (!imageUrl) return

  const regions = parseRegions(props.currentImage.regions)
  const scaleX = canvas.width / props.currentImage.width
  const scaleY = canvas.height / props.currentImage.height

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const colors = {
      inscription: 'rgba(220, 92, 92, 0.3)',
      painting: 'rgba(74, 144, 217, 0.28)',
      blank: 'rgba(90, 184, 112, 0.25)'
    }
    const borderColors = {
      inscription: '#dc5c5c',
      painting: '#4a90d9',
      blank: '#5ab870'
    }

    function drawPolygonRegion(reg, color, borderColor) {
      if (reg.points && Array.isArray(reg.points) && reg.points.length >= 3) {
        ctx.beginPath()
        reg.points.forEach((point, index) => {
          const x = point.x * scaleX
          const y = point.y * scaleY
          if (index === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        })
        ctx.closePath()
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.stroke()
      } else if (reg.x1 !== undefined && reg.y1 !== undefined && reg.x2 !== undefined && reg.y2 !== undefined) {
        ctx.fillStyle = color
        ctx.fillRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.strokeRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
      }
    }

    regions.inscription_regions?.forEach(reg => drawPolygonRegion(reg, colors.inscription, borderColors.inscription))
    regions.painting_regions?.forEach(reg => drawPolygonRegion(reg, colors.painting, borderColors.painting))
    regions.blank_regions?.forEach(reg => drawPolygonRegion(reg, colors.blank, borderColors.blank))
  }
  img.onerror = () => console.error('Failed to load image in drawRegions:', imageUrl)
  img.src = imageUrl
}

// ── 饼图更新 ─────────────────────────────────
function updatePieChart() {
  if (!pieChartRef.value) {
    if (pieChartUpdateRaf) cancelAnimationFrame(pieChartUpdateRaf)
    pieChartUpdateRaf = requestAnimationFrame(() => {
      pieChartUpdateRaf = 0
      updatePieChart()
    })
    return
  }

  const container = pieChartRef.value
  if (container.clientWidth === 0 || container.clientHeight === 0) {
    if (pieChartUpdateRaf) cancelAnimationFrame(pieChartUpdateRaf)
    pieChartUpdateRaf = requestAnimationFrame(() => {
      pieChartUpdateRaf = 0
      updatePieChart()
    })
    return
  }

  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value)
  }

  const insc = areaStats.value.inscriptionPercent || 0
  const paint = areaStats.value.paintingPercent || 0
  const blank = areaStats.value.blankPercent || 0

  const rawItems = [
    { name: '题跋', value: insc, color: '#d4846a' },
    { name: '绘画', value: paint, color: '#7ba3c4' },
    { name: '留白', value: blank, color: '#a8c97a' },
  ].filter(i => i.value > 0)

  rawItems.sort((a, b) => b.value - a.value)

  const rankConfigs = [
    { offset: 30, percentSize: 20, nameSize: 13 },
    { offset: 18, percentSize: 16, nameSize: 10 },
    { offset: 6,  percentSize: 12, nameSize: 9 },
  ]

  const data = rawItems.map((item, idx) => {
    const cfg = rankConfigs[idx] || rankConfigs[rankConfigs.length - 1]
    const percentText = `${item.value.toFixed(2).replace(/\.00$/, '')}%`
    // 文字小于9px 或 扇区小于12% 时外置黑字（14%以上内显）
    const isTooSmall = cfg.nameSize < 9 || item.value < 10

    return {
      value: item.value,
      name: item.name,
      selected: true,
      selectedOffset: cfg.offset,
      label: isTooSmall
        ? {
            position: 'outside',
            formatter: `{percentOut|${percentText}}\n{nameOut|${item.name}}`,
            color: '#333',
            rich: {
              percentOut: { fontSize: 10, fontWeight: 700, color: '#333', lineHeight: 12 },
              nameOut: { fontSize: 9, fontWeight: 500, color: '#555', lineHeight: 11 },
            }
          }
        : {
            position: 'inside',
            formatter: `{percent|${percentText}}\n{name|${item.name}}`,
            rich: {
              percent: { fontSize: cfg.percentSize, fontWeight: 700, color: '#fff', lineHeight: cfg.percentSize + 2 },
              name: { fontSize: cfg.nameSize, fontWeight: 500, color: 'rgba(255,255,255,0.92)', lineHeight: cfg.nameSize + 2 },
            }
          },
      labelLine: isTooSmall ? { show: true, length: 6, length2: 3, smooth: true } : { show: false },
      itemStyle: {
        color: item.color,
        borderRadius: 6,
        borderColor: item.color,
        borderWidth: 1
      }
    }
  })

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const orig = rawItems.find(i => i.name === p.name)
        return `${p.name}: ${orig ? orig.value.toFixed(2).replace(/\.00$/, '') : p.value}%`
      },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e4e7ed',
      borderWidth: 1,
      textStyle: { color: '#333' }
    },
    graphic: {
      type: 'circle',
      left: 'center',
      top: 'center',
      shape: { cx: 0, cy: 0, r: 20 },
      style: { fill: '#fff' },
      z: 10
    },
    series: [{
      type: 'pie',
      radius: '86%',
      center: ['50%', '50%'],
      selectedMode: false,
      avoidLabelOverlap: true,
      labelLayout: { hideOverlap: false },
      emphasis: {
        scale: false,
        itemStyle: { shadowBlur: 12, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.18)' }
      },
      data
    }]
  }

  pieChart.setOption(option, true)
}

// ── 监听 currentImage 变化 ─────────────────────
watch(() => props.currentImage, async (newVal) => {
  if (!newVal) return
  await nextTick()
  initCanvas()
  if (analyzeStatus.value === 'analyzed') {
    drawRegions()
    setTimeout(() => updatePieChart(), 300)
  }
}, { immediate: true })

// 监听 areaStats 变化更新饼图
watch(() => areaStats.value, () => {
  if (analyzeStatus.value === 'analyzed') {
    nextTick(() => updatePieChart())
  }
}, { deep: true })

function handleResize() {
  pieChart?.resize()
  if (props.currentImage) {
    initCanvas()
    if (analyzeStatus.value === 'analyzed') drawRegions()
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChart?.dispose()
  pieChart = null
})

defineExpose({
  updatePieChart,
  initCanvas
})
</script>

<style src="../tubi/TubiAnalysis.css" scoped></style>

<style scoped>
/* upload-card 去背景/边框/阴影，避免双层卡片感 */
:deep(.upload-card) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
:deep(.upload-card .el-card__body) {
  padding: 0 !important;
  overflow: visible;
}
:deep(.upload-card) {
  overflow: visible;
}
:deep(.upload-card .image-display) {
  padding: 0;
}
:deep(.upload-card .analysis-result-layout) {
  margin: 0;
}

/* 卡片背景调亮，与页面背景拉开层次 */
:deep(.annotated-image-section) {
  background: #faf9f7;
}
:deep(.analysis-right-col .inscription-note-main),
:deep(.analysis-right-col .seal-note-main),
:deep(.analysis-right-col .stats-section),
:deep(.analysis-right-col .detail-tags-section) {
  background: #fff;
}
.artwork-info-card,
.spatial-analysis-card {
  background: #fff;
}

/* 所有卡片统一默认阴影，hover 加深 */
:deep(.annotated-image-section),
:deep(.analysis-right-col .inscription-note-main),
:deep(.analysis-right-col .seal-note-main),
:deep(.analysis-right-col .stats-section),
:deep(.analysis-right-col .detail-tags-section),
.artwork-info-card,
.spatial-analysis-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease;
}
:deep(.annotated-image-section:hover),
:deep(.analysis-right-col .inscription-note-main:hover),
:deep(.analysis-right-col .seal-note-main:hover),
:deep(.analysis-right-col .stats-section:hover),
:deep(.analysis-right-col .detail-tags-section:hover),
.artwork-info-card:hover,
.spatial-analysis-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}
:deep(.theme-sentiment-card) {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}
:deep(.theme-sentiment-card:hover) {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

/* 现代文翻译样式 */
.inscription-translation {
  margin-top: 10px;
  padding-top: 10px;
}
.translation-divider {
  height: 1px;
  background: linear-gradient(to right, transparent, #e8e6dc 20%, #e8e6dc 80%, transparent);
  margin-bottom: 8px;
}
.translation-label {
  margin-bottom: 8px;
}
/* 画作信息卡片（合并作者/年份/尺寸 + 操作按钮） */
.artwork-info-card {
  padding: 10px 12px;
  background: #faf9f7;
  border-radius: 8px;
  border: 1px solid #e8e4da;
}
.info-card-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
}
.info-card-row + .info-card-row {
  border-top: 1px solid #ede9de;
}
.info-card-label {
  font-size: 11px;
  color: #8a7a5e;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 28px;
}
.info-card-value {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}
.info-card-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 8px;
  border-top: 1px solid #ede9de;
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

/* 版本历史对话框 */
.rev-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.rev-number {
  font-weight: 700;
  font-size: 15px;
  color: #333;
}
.rev-summary {
  font-size: 13px;
  color: #666;
  margin: 4px 0;
}

.btn-action {
  flex: 1 1 0;
  min-width: 0;
  width: 0;
  font-size: 12px !important;
  box-shadow: none !important;
}
:deep(.btn-action .el-button__content) {
  font-size: 12px;
  justify-content: center;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
:deep(.btn-action .el-button__content .el-icon) {
  flex-shrink: 0;
  font-size: 14px;
}
/* 作品信息表格 */
.image-info-header {
  justify-content: flex-start !important;
  display: flex !important;
}
.artwork-info-table { width: 100%; }
.info-row-horizontal {
  display: flex;
  gap: 8px;
  width: 100%;
}
.info-item {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 10px;
  background: #f8f9fa;
  border-radius: 6px;
  transition: all 0.2s ease;
}
.info-item:nth-child(1) { flex: 0 0 30%; }
.info-item:nth-child(2) { flex: 0 0 35%; }
.info-item:nth-child(3) { flex: 0 0 35%; }
.info-item:hover {
  background: #f1f3f5;
  transform: translateY(-1px);
}
.info-label {
  font-size: 10px;
  color: #6b7280;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.info-value {
  font-size: 11px;
  color: #111827;
  font-weight: 500;
  line-height: 1.3;
}
.translation-content {
  font-size: 13px;
  line-height: 1.8;
  color: #3d3d3a;
  font-style: italic;
  white-space: pre-wrap;
}

/* 导航按钮左右分布，标题居中 */
.navigation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.navigation-header :deep(.el-button) {
  flex: 0 0 auto;
  padding: 5px 8px;
  font-size: 12px;
}
.nav-title {
  flex: 1;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
  color: #333;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 6px;
  min-width: 0;
}

/* ── 响应式 ── */

/* 强制导航栏不换行（父级 card-header 有 flex-wrap: wrap） */
.navigation-header {
  flex-wrap: nowrap;
}

/* 手机：导航按钮更紧凑 */
@media (max-width: 768px) {
  .navigation-header :deep(.el-button) {
    padding: 5px 6px !important;
    font-size: 11px !important;
  }
  .nav-title {
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .navigation-header {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
  }
  .navigation-header :deep(.el-button) {
    flex: 0 1 auto !important;
    min-width: 0 !important;
    padding: 8px 10px !important;
    font-size: 0 !important;
  }
  .navigation-header :deep(.el-button .el-icon) {
    font-size: 16px !important;
  }
  .nav-title {
    font-size: 12px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }
}

/* 面积占比智能示意图标题与按钮同行 */
.annotated-image-section .section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: left;
}
.btn-annotate {
  font-size: 11px;
  padding: 3px 10px;
}
/* 面积示意图容器（用于定位打勾徽章） */
.annotated-image-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
  background: linear-gradient(180deg, #ede8dc 0%, #e2dcd0 100%);
  border-radius: 6px;
  padding: 4px;
}

/* 手动标注打勾徽章 */
.manual-annotated-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  background: rgba(76, 175, 80, 0.9);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

/* 册页导航样式 */
.album-navigation {
  margin-top: 8px;
  padding: 8px;
  background: #faf8f3;
  border-radius: 8px;
  border: 1px solid #ede9de;
}
.album-nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.album-nav-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}
.album-nav-count {
  font-size: 11px;
  color: #8a8a7a;
}
.album-nav-scroll {
  display: flex;
  align-items: center;
  gap: 4px;
}
.album-nav-arrow {
  flex-shrink: 0;
  width: 22px;
  height: 38px;
  border: 1px solid #d4cfc5;
  border-radius: 4px;
  background: #faf9f7;
  color: #8a8a7a;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  padding: 0;
}
.album-nav-arrow:hover {
  background: #f0ece3;
  color: #333;
  border-color: #b8a47e;
}
.album-nav-arrow:active {
  transform: scale(0.92);
}
.album-nav-thumbnails {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  padding: 3px 0;
  scroll-behavior: smooth;
  scroll-snap-type: x mandatory;
  scrollbar-width: none; /* Firefox */
}
.album-nav-thumbnails::-webkit-scrollbar { display: none; /* Chrome/Safari */ }
.album-nav-thumbnail {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 5px;
  border: 2px solid transparent;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0ece3;
  scroll-snap-align: start;
}
.album-nav-thumbnail:hover {
  border-color: #4A90D9;
  transform: translateY(-1px);
}
.album-nav-thumbnail.active {
  border-color: #4A90D9;
  box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.25);
}
.album-nav-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.album-nav-thumbnail .thumb-placeholder {
  font-size: 12px;
  color: #8a8a7a;
  font-weight: 500;
}

/* ── 悬浮布局示意图覆盖层 ── */
.diagram-hover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 253, 245, 0.88);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px;
  pointer-events: none;
  z-index: 5;
}
.diagram-hover-overlay .diagram-svg {
  width: 100%;
  max-height: 100%;
}
.diagram-legend-overlay {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  font-size: 11px;
  color: #666;
}
.diagram-legend-overlay .legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 3px;
  vertical-align: middle;
}
.diagram-legend-overlay .legend-dot.inscription { background: rgba(201, 100, 66, 0.7); }
.diagram-legend-overlay .legend-dot.painting { background: rgba(74, 144, 217, 0.7); }
.diagram-legend-overlay .legend-dot.blank { background: rgba(144, 164, 174, 0.5); }
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* ── 题跋布局类型（精简卡片） ── */
.spatial-analysis-card {
  margin-top: 10px;
  padding: 10px 12px;
  background: #faf9f7;
  border-radius: 8px;
  border: 1px solid #e8e4da;
}
.spatial-analysis-card .section-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #333;
  margin-bottom: 8px;
}
.form-types-inline {
  display: inline-flex;
  gap: 4px;
  margin-left: 6px;
}
.spatial-description {
  font-size: 12px;
  line-height: 1.7;
  color: #555;
}
.form-type-desc-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 8px;
  line-height: 1.7;
}
.desc-tag {
  flex-shrink: 0;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: #ede9de;
  color: #8a7a5e;
  font-weight: 600;
}
.desc-text {
  color: #555;
}
.desc-none {
  color: #999;
  font-style: italic;
}

/* 印章标签显示 */
.seal-tags-display {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.seal-display-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f5f3ee;
  border: 1px solid #e8e5de;
  font-size: 12px;
  color: #5a5a4e;
  cursor: default;
  transition: all 0.15s;
}

.seal-display-tag.has-image {
  cursor: pointer;
  border-color: #d0ccc2;
}

.seal-display-tag.has-image:hover {
  background: #ede9e0;
  border-color: #c96442;
  color: #c96442;
}

.seal-display-type {
  font-size: 10px;
  color: #aaa;
}

.stat-percentile {
  font-size: 11px;
  color: #c96442;
  margin-left: 6px;
  font-weight: 500;
}

/* ── 情感标签样式 ── */
:deep(.pol-label) {
  font-weight: 700;
}
:deep(.pol-positive) {
  color: #67c23a;
}
:deep(.pol-negative) {
  color: #f56c6c;
}
:deep(.pol-neutral) {
  color: #909399;
}
</style>
