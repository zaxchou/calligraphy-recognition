<template>
  <div class="analysis-container">
    <!-- 左侧：原作图 + 作品信息（sticky） -->
    <div class="left-panel">
      <!-- 原作卡片 -->
      <el-card shadow="hover" class="original-image-card" v-if="analyzeStatus === 'analyzed' && currentImage?.url">
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
            >
              下一幅
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </template>
        <div class="original-image-wrapper">
          <img :src="currentImage.thumbnailUrl || currentImage.url" class="original-image" @click="openImagePreview(currentImage.url)" title="点击放大查看" />
          <el-icon class="zoom-icon" @click="openImagePreview(currentImage.url)" title="放大查看"><ZoomIn /></el-icon>
        </div>

        <!-- 册页导航 -->
        <div v-if="albumNavigation.is_in_album" class="album-navigation">
          <div class="album-nav-header">
            <span class="album-nav-title">「{{ albumNavigation.album_name }}」</span>
            <span class="album-nav-count">第{{ albumNavigation.current_index + 1 }}幅 / 共{{ albumNavigation.total_count }}幅</span>
          </div>
          <div class="album-nav-thumbnails">
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
          <el-button plain size="small" class="btn-action" @click="$emit('edit-current')">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-button plain size="small" class="btn-action" @click="$emit('back')" :icon="HomeFilled">
            返回
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
                  <el-button size="small" text class="btn-annotate" @click="$emit('open-annotator')">手动标注</el-button>
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
                    <div class="sentiment-gauge-row">
                      <div class="sentiment-gauge">
                        <svg viewBox="0 0 120 120" class="gauge-svg">
                          <!-- 背景弧 -->
                          <circle cx="60" cy="60" r="50" fill="none" stroke="#e8e4da" stroke-width="8"
                            stroke-dasharray="235.6 78.5" stroke-dashoffset="-39.3" stroke-linecap="round" />
                          <!-- 强度弧 -->
                          <circle cx="60" cy="60" r="50" fill="none"
                            :stroke="currentImage.contentAnalysis.sentiment.polarity === 'positive' ? '#c96442' : currentImage.contentAnalysis.sentiment.polarity === 'negative' ? '#6b8cae' : '#b8a47e'"
                            stroke-width="8"
                            :stroke-dasharray="`${235.6 * currentImage.contentAnalysis.sentiment.intensity} ${235.6 * (1 - currentImage.contentAnalysis.sentiment.intensity) + 78.5}`"
                            stroke-dashoffset="-39.3" stroke-linecap="round"
                            class="gauge-arc" />
                        </svg>
                        <div class="gauge-center">
                          <span class="gauge-emoji">{{ currentImage.contentAnalysis.sentiment.polarity === 'positive' ? '&#x1F31F;' : currentImage.contentAnalysis.sentiment.polarity === 'negative' ? '&#x1F327;' : '&#x26C5;' }}</span>
                          <span class="gauge-percent">{{ Math.round(currentImage.contentAnalysis.sentiment.intensity * 100) }}%</span>
                        </div>
                      </div>
                      <div class="sentiment-info">
                        <el-tag
                          size="small"
                          :type="currentImage.contentAnalysis.sentiment.polarity === 'positive' ? 'success' : currentImage.contentAnalysis.sentiment.polarity === 'negative' ? 'danger' : 'info'"
                          class="sentiment-tag"
                        >
                          {{ currentImage.contentAnalysis.sentiment.polarity === 'positive' ? '积极' : currentImage.contentAnalysis.sentiment.polarity === 'negative' ? '消极' : '中性' }}
                        </el-tag>
                        <span class="sentiment-intensity-label">强度 {{ Math.round(currentImage.contentAnalysis.sentiment.intensity * 100) }}%</span>
                      </div>
                    </div>
                    <div class="sentiment-reasoning" v-if="currentImage.contentAnalysis.sentiment.channel2?.reasoning">
                      <div class="reasoning-label">推导过程</div>
                      <div class="reasoning-text">{{ currentImage.contentAnalysis.sentiment.channel2.reasoning }}</div>
                    </div>
                    <div class="sentiment-reasoning" v-else-if="currentImage.contentAnalysis.sentiment.channel1?.reasoning">
                      <div class="reasoning-label">推导过程</div>
                      <div class="reasoning-text">{{ currentImage.contentAnalysis.sentiment.channel1.reasoning }}</div>
                    </div>
                  </div>

                <div class="ts-empty" v-if="!currentImage.contentAnalysis?.themes?.length && !currentImage.contentAnalysis?.sentiment">
                  暂无内容分析数据
                </div>
                </div>
              </div>
            </div>
            <div class="analysis-right-col">
              <div v-if="currentImage && getDetailAllTags().length > 0" class="detail-tags-section">
                <div class="detail-tags-list">
                  <span v-for="(tag, idx) in getDetailAllTags()" :key="idx" class="detail-tag" @click="$emit('filter-by-tag', tag)">{{ tag }}</span>
                </div>
              </div>
              <div class="inscription-note-main">
                <h4><el-icon><Edit /></el-icon> 款识题跋</h4>
                <div v-if="currentImage.inscriptionContent" class="inscription-content">
                  {{ currentImage.inscriptionContent }}
                </div>
                <div v-else class="inscription-empty">
                  <p>暂无款识题跋内容</p>
                  <p class="empty-tip">可在编辑画作信息时添加</p>
                </div>
                <div v-if="currentImage.inscriptionModern" class="inscription-translation">
                  <div class="translation-divider"></div>
                  <div class="translation-label">
                    <div class="clickable-tag-wrapper" @click="translationExpanded = !translationExpanded">
                      <el-tag type="success" size="small" class="clickable-tag">白话文</el-tag>
                      <el-icon class="expand-icon" :class="{ 'rotated': translationExpanded }"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <div class="translation-content" v-show="translationExpanded">{{ currentImage.inscriptionModern }}</div>
                </div>
              </div>
              <div class="seal-note-main">
                <h4><el-icon><Collection /></el-icon> 钤印</h4>
                <div v-if="currentImage.sealContent" class="seal-content">
                  <div class="seal-tags-display">
                    <el-popover v-for="(seal, idx) in detailSealTags" :key="idx" :width="120" placement="top" :disabled="!detailSealImageMap[seal.name]" trigger="hover">
                      <template #reference>
                        <span class="seal-display-tag" :class="{ 'has-image': detailSealImageMap[seal.name] }">
                          {{ seal.name }}
                          <span v-if="seal.seal_type" class="seal-display-type">{{ seal.seal_type }}</span>
                        </span>
                      </template>
                      <img v-if="detailSealImageMap[seal.name]" :src="detailSealImageMap[seal.name]" style="width: 100px; height: 100px; object-fit: contain;" />
                    </el-popover>
                  </div>
                </div>
                <div v-else class="seal-empty"><p>暂无钤印内容</p></div>
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
            <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="history-grid-thumb" />
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

    <!-- 原图放大查看对话框 -->
    <TubiImageZoomDialog
      v-model="imagePreviewVisible"
      :image-url="currentPreviewImage"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  Picture, Edit, HomeFilled, Clock, ArrowLeft, ArrowRight, ArrowDown, Collection, Check, DataAnalysis, PieChart, ZoomIn
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDisplayAge } from '../tubi/utils'
import { sealsApi } from '../api'
import TubiImageZoomDialog from '../components/tubi/TubiImageZoomDialog.vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1'

// 印章显示
const sealLibraryCache = ref([])
const detailSealImageMap = ref({})
const detailSealTypeMap = ref({})

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
  try {
    const res = await sealsApi.list({ limit: 200 })
    if (res.success) {
      sealLibraryCache.value = res.seals || []
      const imgMap = {}, typeMap = {}
      for (const s of sealLibraryCache.value) {
        if (s.images && s.images.length > 0) {
          const img = s.images[0]
          imgMap[s.name] = img.startsWith('http') ? img : `${API_BASE.replace('/api/v1', '')}${img}`
        }
        if (s.seal_type) typeMap[s.name] = s.seal_type
      }
      detailSealImageMap.value = imgMap
      detailSealTypeMap.value = typeMap
    }
  } catch (e) { console.error('加载印章库失败', e) }
}

onMounted(() => { loadSealLibraryForDetail() })

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

const emit = defineEmits([
  'back', 'edit-current', 'open-upload', 'auto-analyze',
  'navigate', 'navigate-album', 'open-annotator',
  'filter-by-tag', 'history-item-click'
])

// ── 翻译折叠 ──────────────────────────────────
const translationExpanded = ref(false)

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
  window.open('/#/tubi/ranking', '_blank')
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

function openImagePreview(imageUrl) {
  currentPreviewImage.value = imageUrl
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
.clickable-tag-wrapper {
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
}
.clickable-tag-wrapper:hover {
  transform: translateY(-1px);
}
.clickable-tag-wrapper:hover .clickable-tag {
  box-shadow: 0 2px 8px rgba(90, 138, 74, 0.25);
}
.clickable-tag { white-space: nowrap; }
.expand-icon {
  transition: transform 0.2s ease;
  font-size: 12px;
  color: #5a8a4a;
  flex-shrink: 0;
}
.expand-icon.rotated { transform: rotate(180deg); }
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
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #ede9de;
}
.btn-action {
  flex: 1;
  font-size: 12px !important;
  box-shadow: none !important;
}
:deep(.btn-action .el-button__content) {
  font-size: 12px;
  justify-content: center;
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
  background: #fffef8;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #ede9de;
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
  font-weight: 500;
  color: #333;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 6px;
  min-width: 0;
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
.album-nav-thumbnails {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  padding: 3px 0;
  scroll-behavior: smooth;
}
.album-nav-thumbnails::-webkit-scrollbar { height: 4px; }
.album-nav-thumbnails::-webkit-scrollbar-thumb {
  background: #d4cfc5;
  border-radius: 2px;
}
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
}
.album-nav-thumbnail:hover {
  border-color: #c96442;
  transform: translateY(-1px);
}
.album-nav-thumbnail.active {
  border-color: #c96442;
  box-shadow: 0 0 0 2px rgba(201, 100, 66, 0.25);
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
  font-weight: 600;
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
</style>
