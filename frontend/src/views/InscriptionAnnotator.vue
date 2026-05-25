<template>
  <div class="annotator-page">
    <!-- 意见提交模式提示 -->
    <div v-if="isSuggestMode" class="suggest-banner">
      <el-icon style="margin-right:8px;"><EditPen /></el-icon>
      意见提交模式
      <span v-if="!isSuggestAdmin" style="margin-left:8px;color:#856404;">— 保存草稿到本地，完成后点「提交审阅」</span>
      <span v-else style="margin-left:8px;color:#856404;">— 管理员直接保存将写入数据库</span>
      <el-button v-if="hasDraft && !isSuggestAdmin" size="small" text style="margin-left:12px;color:#856404;" @click="restoreDraft">
        恢复上次草稿
      </el-button>
    </div>
    <div v-if="isReviewMode" class="review-banner">
      <el-icon style="margin-right:8px;"><View /></el-icon>
      审核预览模式 — 此标注图为变更请求中的新值，仅供查看
    </div>
    <!-- 主工作区 -->
    <div class="annotator-workspace">
      <!-- 左侧图片标注区 -->
      <div
        class="canvas-area"
        ref="canvasContainer"
        @wheel.prevent="onWheel"
        @mousedown="onCanvasMouseDown"
        @mousemove="onCanvasMouseMove"
        @mouseup="onCanvasMouseUp"
        @mouseleave="onCanvasMouseLeave"
      >
        <!-- 核心：SVG 内嵌图片，共享坐标系 -->
        <svg
          ref="svgRef"
          class="annotator-svg"
          :viewBox="viewBoxString"
          preserveAspectRatio="xMidYMid meet"
          @click="onSvgClick"
          @mousedown="onSvgMouseDown"
          @mousemove="onSvgMouseMove"
          @mouseup="onSvgMouseUp"
          @dblclick="closeCurrentPolygon"
          @contextmenu.prevent="onRightClick"
        >
          <!-- 图片作为 SVG 内部元素 -->
          <image
            :href="imageUrl"
            :width="imgNaturalW"
            :height="imgNaturalH"
            @load="onSvgImageLoad"
          />

          <!-- 已完成的多边形 -->
          <polygon
            v-for="(poly, idx) in polygons"
            :key="'p-' + idx"
            :points="polyPointsStr(poly)"
            class="poly-done"
            :class="{
              'poly-selected': selectedPolyIdx === idx,
              'poly-inscription': poly.type === 'inscription' || !poly.type,
              'poly-painting': poly.type === 'painting',
              'poly-margin': poly.type === 'margin'
            }"
            @click.stop="selectPolygon(idx)"
          />

          <!-- 当前绘制中的多边形 -->
          <polygon
            v-if="currentPoly.length > 1"
            :points="currentPolyPointsStr"
            class="poly-drawing"
            :class="{
              'drawing-inscription': currentRegionType === 'inscription',
              'drawing-painting': currentRegionType === 'painting',
              'drawing-margin': currentRegionType === 'margin'
            }"
          />

          <!-- 矩形模式拖拽预览 -->
          <rect
            v-if="drawMode === 'rect' && rectStart"
            :x="Math.min(rectStart.x, rectCurrent.x)"
            :y="Math.min(rectStart.y, rectCurrent.y)"
            :width="Math.abs(rectCurrent.x - rectStart.x)"
            :height="Math.abs(rectCurrent.y - rectStart.y)"
            class="rect-preview"
            :class="{
              'drawing-inscription': currentRegionType === 'inscription',
              'drawing-painting': currentRegionType === 'painting',
              'drawing-margin': currentRegionType === 'margin'
            }"
          />

          <!-- 已完成多边形的顶点控制点 -->
          <g v-for="(poly, pidx) in polygons" :key="'g-' + pidx">
            <circle
              v-for="(pt, vidx) in (poly.points || poly)"
              :key="vidx"
              :cx="pt.x"
              :cy="pt.y"
              :r="vertexRadius"
              class="vertex"
              :class="{
                'vertex-selected': selectedPolyIdx === pidx,
                'vertex-inscription': poly.type === 'inscription' || !poly.type,
                'vertex-painting': poly.type === 'painting',
                'vertex-margin': poly.type === 'margin'
              }"
              @mousedown.prevent.stop="startDragVertex(pidx, vidx, $event)"
            />
          </g>

          <!-- 当前多边形的顶点 -->
          <g v-if="currentPoly.length > 0">
            <circle
              v-for="(pt, vidx) in currentPoly"
              :key="'cp-' + vidx"
              :cx="pt.x"
              :cy="pt.y"
              :r="vertexRadius"
              class="vertex-drawing"
              :class="{
                'drawing-inscription': currentRegionType === 'inscription',
                'drawing-painting': currentRegionType === 'painting',
                'drawing-margin': currentRegionType === 'margin'
              }"
              @mousedown.prevent.stop="startDragVertex(-1, vidx, $event)"
            />
          </g>
        </svg>

        <!-- 放大镜 -->
        <div
          v-if="magnifierEnabled && magnifierVisible"
          class="magnifier"
          :style="magnifierStyle"
        >
          <canvas ref="magnifierCanvas" :width="magnifierSize" :height="magnifierSize"></canvas>
          <div class="magnifier-crosshair"></div>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="annotator-panel">
        <!-- 工具栏 -->
        <div class="panel-section toolbar-section">
          <div class="info-title">操作</div>
          <div class="toolbar-group">
            <el-button size="small" @click="goBack">
              <el-icon><ArrowLeft /></el-icon>
              返回
            </el-button>
            <span class="panel-title">手动标注区域</span>
          </div>
          <div class="toolbar-group">
            <span class="tip-text">{{ drawMode === 'rect' ? (currentRegionType === 'margin' ? '框选内容区，自动反算出四边余边' : '按住拖拽绘制矩形；拖拽顶点调整位置') : '点击添加顶点，双击封闭多边形；拖拽顶点调整位置' }}</span>
          </div>
          <div class="toolbar-controls">
            <div class="zoom-controls">
              <el-button size="small" @click="zoomOut" title="缩小">
                <el-icon><ZoomOut /></el-icon>
              </el-button>
              <span class="zoom-ratio">{{ displayScale }}%</span>
              <el-button size="small" @click="zoomIn" title="放大">
                <el-icon><ZoomIn /></el-icon>
              </el-button>
              <el-button size="small" @click="resetView" title="重置视图">
                <el-icon><FullScreen /></el-icon>
              </el-button>
            </div>
            <el-radio-group v-model="drawMode" size="small" class="draw-mode-selector">
              <el-radio-button value="poly">多边形</el-radio-button>
              <el-radio-button value="rect">矩形</el-radio-button>
            </el-radio-group>
            <el-radio-group v-model="currentRegionType" size="small" class="region-type-selector">
              <el-radio-button value="inscription">
                <span class="type-dot inscription"></span>题跋
              </el-radio-button>
              <el-radio-button value="painting">
                <span class="type-dot painting"></span>绘画
              </el-radio-button>
              <el-radio-button value="margin">
                <span class="type-dot margin"></span>余边
              </el-radio-button>
            </el-radio-group>
            <el-button
              v-show="false"
              :type="magnifierEnabled ? 'primary' : 'default'"
              @click="magnifierEnabled = !magnifierEnabled"
              size="small"
            >
              <el-icon><Search /></el-icon>
              放大镜 {{ magnifierEnabled ? '开' : '关' }}
            </el-button>
          </div>
          <div class="action-buttons">
            <template v-if="isReviewMode">
              <el-button size="small" @click="goBack">返回</el-button>
              <el-tag type="info" effect="plain">只读预览</el-tag>
            </template>
            <template v-else>
              <el-button size="small" @click="undoLast" :disabled="history.length === 0">撤销</el-button>
              <el-button size="small" @click="clearAll" :disabled="polygons.length === 0">清空</el-button>
              <el-button type="primary" size="small" @click="saveRegions" :loading="saving">
                {{ isSuggestMode && !isSuggestAdmin ? '保存草稿' : '保存标注' }}
              </el-button>
              <el-button v-if="isSuggestMode" type="warning" size="small" @click="submitForReview" :loading="submittingReview">
                提交审阅
              </el-button>
            </template>
          </div>
        </div>
        <!-- 图片信息 -->
        <div class="panel-section info-section">
          <div class="info-title">图片信息</div>
          <div class="info-row">
            <span class="info-label">ID</span>
            <span class="info-value">{{ recordData?.id }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">标题</span>
            <span class="info-value">{{ recordData?.title || '未命名' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">作者</span>
            <span class="info-value">{{ recordData?.artist || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">尺寸</span>
            <span class="info-value">{{ imgNaturalW }} × {{ imgNaturalH }}</span>
          </div>
        </div>

        <!-- 标注统计 -->
        <div class="panel-section stats-section">
          <div class="stats-title">标注统计</div>
          <div class="stat-big">
            <span class="stat-number">{{ polygons.length }}</span>
            <span class="stat-label">个区域</span>
          </div>
          <div class="stat-row" v-if="totalArea > 0">
            <span class="stat-row-label">已标面积</span>
            <span class="stat-row-value">{{ totalArea.toFixed(2) }}%</span>
          </div>
        </div>

        <!-- 多边形列表 -->
        <div class="panel-section list-section">
          <div class="list-title">
            区域列表
            <span class="list-count">{{ polygons.length }}</span>
          </div>
          <div class="poly-list" v-if="polygons.length > 0">
            <div
              v-for="(poly, idx) in polygons"
              :key="idx"
              class="poly-item"
              :class="{ 'poly-item-active': selectedPolyIdx === idx }"
              @click="selectPolygon(idx)"
            >
              <span class="poly-index">{{ idx + 1 }}</span>
              <span
                class="poly-type-dot"
                :class="poly.type === 'painting' ? 'type-painting' : poly.type === 'margin' ? 'type-margin' : 'type-inscription'"
                :title="poly.type === 'painting' ? '绘画区域，点击切换为余边' : poly.type === 'margin' ? '余边区域，点击切换为题跋' : '题跋区域，点击切换为绘画'"
                @click.stop="togglePolyType(idx)"
              ></span>
              <span class="poly-info">{{ polygonArea(idx).toFixed(2) }}%</span>
              <el-button
                size="small"
                text
                class="poly-delete"
                @click.stop="deletePolygon(idx)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <div class="poly-empty" v-else>
            尚未标注任何区域
          </div>
        </div>

        <!-- 操作提示 -->
        <div class="panel-section hint-section">
          <div class="hint-title" style="font-size:13px;font-weight:600;margin-bottom:8px;color:#4d4c48;">操作提示</div>
          <div class="hint-item">
            <span class="hint-key">多边形</span>
            <span class="hint-val">单击加点 / 双击封闭</span>
          </div>
          <div class="hint-item">
            <span class="hint-key">矩形</span>
            <span class="hint-val">按住拖拽框选</span>
          </div>
          <div class="hint-item">
            <span class="hint-key">拖拽顶点</span>
            <span class="hint-val">调整位置</span>
          </div>
          <div class="hint-item">
            <span class="hint-key">右键</span>
            <span class="hint-val">删除当前区域</span>
          </div>
          <div class="hint-item">
            <span class="hint-key">M</span>
            <span class="hint-val">切换放大镜</span>
          </div>
          <div class="hint-item">
            <span class="hint-key">Enter</span>
            <span class="hint-val">封闭多边形</span>
          </div>
          <div class="hint-item">
            <span class="hint-key">Esc</span>
            <span class="hint-val">取消绘制</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Delete, Search, ZoomIn, ZoomOut, FullScreen, EditPen, View } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

// === 状态 ===
const isSuggestMode = computed(() => route.query.mode === 'suggest')
const isReviewMode = computed(() => route.query.mode === 'review')
const isSuggestAdmin = computed(() => route.query.role === 'admin' || route.query.role === 'super_admin' || route.query.role === 'editor')
const submittingReview = ref(false)
const initialRegionsSnapshot = ref('[]')
const DRAFT_KEY = computed(() => `annotator_draft_${route.params.id}`)
const hasDraft = ref(false)

const imageUrl = ref('')
const imgNaturalW = ref(800)
const imgNaturalH = ref(600)
const svgRef = ref(null)
const canvasContainer = ref(null)

// === viewBox 缩放/平移状态 ===
const viewBoxX = ref(0)
const viewBoxY = ref(0)
const viewBoxW = ref(800)
const viewBoxH = ref(600)
const MIN_SCALE = 0.1 // 最小缩放10%
const MAX_SCALE = 10  // 最大缩放1000%
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, vx: 0, vy: 0 })
const isSpaceDown = ref(false)

// 当前缩放比例
const currentScale = computed(() => {
  const wRatio = viewBoxW.value / imgNaturalW.value
  const hRatio = viewBoxH.value / imgNaturalH.value
  return Math.max(wRatio, hRatio)
})

// 显示的缩放百分比
const displayScale = computed(() => Math.round(100 / currentScale.value))

// 完整 viewBox 字符串
const viewBoxString = computed(() => {
  return `${viewBoxX.value} ${viewBoxY.value} ${viewBoxW.value} ${viewBoxH.value}`
})

// 重置为原始视图
function resetView() {
  viewBoxX.value = 0
  viewBoxY.value = 0
  viewBoxW.value = imgNaturalW.value
  viewBoxH.value = imgNaturalH.value
}

// 图片加载时初始化 viewBox
watch(imgNaturalW, () => {
  resetView()
})

// 按钮缩放
function zoomIn() {
  const scale = currentScale.value / 1.25
  applyScale(scale, imgNaturalW.value / 2, imgNaturalH.value / 2)
}

function zoomOut() {
  const scale = currentScale.value * 1.25
  applyScale(scale, imgNaturalW.value / 2, imgNaturalH.value / 2)
}

// 应用缩放（以 viewBox 坐标为中心）
function applyScale(targetScale, centerX, centerY) {
  targetScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, targetScale))
  
  const oldVW = viewBoxW.value
  const oldVH = viewBoxH.value
  const newVW = imgNaturalW.value * targetScale
  const newVH = imgNaturalH.value * targetScale
  
  // 保持中心点不变
  viewBoxX.value = centerX - (centerX - viewBoxX.value) * newVW / oldVW
  viewBoxY.value = centerY - (centerY - viewBoxY.value) * newVH / oldVH
  viewBoxW.value = newVW
  viewBoxH.value = newVH
}

// 滚轮缩放（以鼠标在 SVG 上的点为中心）
function onWheel(e) {
  const svg = svgRef.value
  if (!svg) return
  
  const svgPt = screenToSvg(e.clientX, e.clientY)
  if (!svgPt) return
  
  const delta = e.deltaY < 0 ? -0.2 : 0.2 // 1/1.25 ≈ 0.8, 1.25
  const targetScale = currentScale.value * (1 + delta)
  applyScale(targetScale, svgPt.x, svgPt.y)
}

// 拖拽平移（以 canvas-area 鼠标移动量）
function onCanvasMouseDown(e) {
  // 中键始终平移，或者空格按下时左键也平移
  if (e.button === 1 || (e.button === 0 && isSpaceDown.value)) {
    isPanning.value = true
    panStart.value = {
      x: e.clientX,
      y: e.clientY,
      vx: viewBoxX.value,
      vy: viewBoxY.value
    }
    e.preventDefault()
    e.stopPropagation()
  }
}

function onCanvasMouseMove(e) {
  if (isPanning.value) {
    const dx = e.clientX - panStart.value.x
    const dy = e.clientY - panStart.value.y
    // 屏幕像素 → SVG 像素，5倍幅度
    const scale = currentScale.value
    viewBoxX.value = panStart.value.vx - dx * scale * 5
    viewBoxY.value = panStart.value.vy - dy * scale * 5
  }
  if (magnifierEnabled.value) {
    updateMagnifier(e)
  }
}

function onCanvasMouseUp() {
  isPanning.value = false
}

function onCanvasMouseLeave() {
  isPanning.value = false
  magnifierVisible.value = false
}

const polygons = ref([]) // [{type: 'inscription'|'painting'|'margin', points: [{x,y},...]}, ...]
const currentPoly = ref([]) // 当前正在绘制的多边形顶点
const currentRegionType = ref('inscription') // 当前绘制区域类型
const drawMode = ref('poly') // 'poly' | 'rect'
const rectStart = ref(null) // 矩形起点 {x,y}
const rectCurrent = ref(null) // 矩形当前鼠标位置 {x,y}
const selectedPolyIdx = ref(-1)
const history = ref([]) // 操作历史（用于撤销）

const saving = ref(false)
const recordData = ref(null)

// 选"余边"时自动切换为矩形工具
watch(currentRegionType, (t) => {
  if (t === 'margin') drawMode.value = 'rect'
})

// 顶点半径（SVG坐标，需根据图片大小缩放）
const vertexRadius = computed(() => {
  const minDim = Math.min(imgNaturalW.value, imgNaturalH.value)
  return Math.max(4, Math.round(minDim / 150))
})

// 放大镜
const magnifierEnabled = ref(false)
const magnifierVisible = ref(false)
const magnifierSize = 180
const magnifierZoom = 3
const magnifierX = ref(0)
const magnifierY = ref(0)
const magnifierCanvas = ref(null)

// 隐藏的 Image 对象，用于放大镜 canvas 绘制
const hiddenImg = ref(null)

// === 核心：屏幕坐标 → SVG 坐标转换 ===
function screenToSvg(clientX, clientY) {
  const svg = svgRef.value
  if (!svg) return null
  const pt = svg.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const ctm = svg.getScreenCTM()
  if (!ctm) return null
  const svgPt = pt.matrixTransform(ctm.inverse())
  return { x: Math.round(svgPt.x), y: Math.round(svgPt.y) }
}

// === 计算属性 ===
const currentPolyPointsStr = computed(() => {
  return currentPoly.value.map(p => `${p.x},${p.y}`).join(' ')
})

function polyPointsStr(poly) {
  // poly 现在是 {type, points} 结构
  const points = poly.points || poly
  return points.map(p => `${p.x},${p.y}`).join(' ')
}

const totalArea = computed(() => {
  return polygons.value.reduce((sum, poly, idx) => sum + polygonArea(idx), 0)
})

const magnifierStyle = computed(() => ({
  left: magnifierX.value + 'px',
  top: magnifierY.value + 'px',
  width: magnifierSize + 'px',
  height: magnifierSize + 'px'
}))

function polygonArea(idx) {
  const poly = polygons.value[idx]
  if (!poly) return 0
  const points = poly.points || poly
  if (!points || points.length < 3) return 0
  let area = 0
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length
    area += points[i].x * points[j].y
    area -= points[j].x * points[i].y
  }
  const absArea = Math.abs(area) / 2
  return (absArea / (imgNaturalW.value * imgNaturalH.value)) * 100
}

// === SVG 事件处理 ===
function onSvgClick(e) {
  // 审核预览模式：禁止修改
  if (isReviewMode.value) return
  // 矩形模式不通过点击添加点
  if (drawMode.value === 'rect') return
  // 如果正在拖拽，不处理
  if (isDragging) return
  // 如果点击的是已完成多边形或顶点，不添加新点
  if (e.target.tagName === 'polygon' && e.target.classList.contains('poly-done')) return
  if (e.target.tagName === 'circle') return

  const pt = screenToSvg(e.clientX, e.clientY)
  if (!pt) return

  // 边界检查
  if (pt.x < 0 || pt.x > imgNaturalW.value || pt.y < 0 || pt.y > imgNaturalH.value) return

  currentPoly.value.push(pt)
}

function onSvgMouseDown(e) {
  // 仅左键 + 矩形模式才处理（中键留给画布平移）
  if (e.button !== 0 || drawMode.value !== 'rect') {
    // 不阻止事件冒泡，让 canvas-area 的中键/空格平移正常工作
    return
  }
  if (isReviewMode.value) return
  const pt = screenToSvg(e.clientX, e.clientY)
  if (!pt) return
  if (pt.x < 0 || pt.x > imgNaturalW.value || pt.y < 0 || pt.y > imgNaturalH.value) return
  rectStart.value = { x: pt.x, y: pt.y }
  rectCurrent.value = { x: pt.x, y: pt.y }
  e.preventDefault()
  e.stopPropagation()
}

function onSvgMouseMove(e) {
  if (!rectStart.value || drawMode.value !== 'rect') return
  const pt = screenToSvg(e.clientX, e.clientY)
  if (!pt) return
  rectCurrent.value = { x: Math.max(0, Math.min(pt.x, imgNaturalW.value)), y: Math.max(0, Math.min(pt.y, imgNaturalH.value)) }
}

function onSvgMouseUp(e) {
  if (!rectStart.value || drawMode.value !== 'rect') return
  const pt = screenToSvg(e.clientX, e.clientY)
  if (!pt) { rectStart.value = null; rectCurrent.value = null; return }

  const x1 = rectStart.value.x
  const y1 = rectStart.value.y
  const x2 = Math.max(0, Math.min(pt.x, imgNaturalW.value))
  const y2 = Math.max(0, Math.min(pt.y, imgNaturalH.value))

  // 至少 5px 的矩形才保存
  if (Math.abs(x2 - x1) >= 5 && Math.abs(y2 - y1) >= 5) {
    const snap = JSON.parse(JSON.stringify(polygons.value))
    history.value.push({ type: 'add', polys: snap, current: JSON.parse(JSON.stringify(currentPoly.value)) })

    if (currentRegionType.value === 'margin') {
      // 余边模式：框选的是内容区，反算四边余边
      const cx1 = Math.min(x1, x2), cy1 = Math.min(y1, y2)
      const cx2 = Math.max(x1, x2), cy2 = Math.max(y1, y2)
      const W = imgNaturalW.value, H = imgNaturalH.value

      const marginRects = []
      // 上余边
      if (cy1 > 0) marginRects.push({ x: 0, y: 0, w: W, h: cy1 })
      // 下余边
      if (cy2 < H) marginRects.push({ x: 0, y: cy2, w: W, h: H - cy2 })
      // 左余边（避开上下已覆盖的区域）
      if (cx1 > 0) marginRects.push({ x: 0, y: cy1, w: cx1, h: cy2 - cy1 })
      // 右余边
      if (cx2 < W) marginRects.push({ x: cx2, y: cy1, w: W - cx2, h: cy2 - cy1 })

      for (const r of marginRects) {
        if (r.w > 0 && r.h > 0) {
          polygons.value.push({
            type: 'margin',
            points: [
              { x: r.x, y: r.y },
              { x: r.x + r.w, y: r.y },
              { x: r.x + r.w, y: r.y + r.h },
              { x: r.x, y: r.y + r.h }
            ]
          })
        }
      }
    } else {
      // 题跋/绘画模式：直接保存矩形
      polygons.value.push({
        type: currentRegionType.value,
        points: [
          { x: Math.min(x1, x2), y: Math.min(y1, y2) },
          { x: Math.max(x1, x2), y: Math.min(y1, y2) },
          { x: Math.max(x1, x2), y: Math.max(y1, y2) },
          { x: Math.min(x1, x2), y: Math.max(y1, y2) }
        ]
      })
    }
    selectedPolyIdx.value = polygons.value.length - 1
  }

  rectStart.value = null
  rectCurrent.value = null
}

function onSvgImageLoad() {
  // SVG <image> 加载完成，获取自然尺寸
  const svg = svgRef.value
  if (!svg) return
  const imgEl = svg.querySelector('image')
  if (imgEl) {
    // 使用 imgNaturalW/H 已经在 loadRecord 中设置
    console.log(`[Annotator] SVG image loaded, viewBox: ${imgNaturalW.value}x${imgNaturalH.value}`)
  }
}

function onRightClick(e) {
  // 右键删除当前绘制中的多边形
  if (currentPoly.value.length > 0) {
    currentPoly.value = []
  } else if (selectedPolyIdx.value >= 0) {
    deletePolygon(selectedPolyIdx.value)
  }
}

// === 放大镜 ===

function updateMagnifier(e) {
  const container = canvasContainer.value
  if (!container) return

  const containerRect = container.getBoundingClientRect()
  const mouseX = e.clientX - containerRect.left
  const mouseY = e.clientY - containerRect.top

  // 放大镜位置（偏移右下角）
  magnifierX.value = mouseX + 20
  magnifierY.value = mouseY + 20

  // 防止放大镜超出容器
  if (magnifierX.value + magnifierSize > containerRect.width) {
    magnifierX.value = mouseX - magnifierSize - 20
  }
  if (magnifierY.value + magnifierSize > containerRect.height) {
    magnifierY.value = mouseY - magnifierSize - 20
  }

  magnifierVisible.value = true
  renderMagnifier(e)
}

function renderMagnifier(e) {
  const canvas = magnifierCanvas.value
  const img = hiddenImg.value
  if (!canvas || !img || !img.complete) return

  const ctx = canvas.getContext('2d')
  const svgPt = screenToSvg(e.clientX, e.clientY)
  if (!svgPt) return

  // svgPt 现在是图片自然坐标
  const srcSize = magnifierSize / magnifierZoom

  ctx.clearRect(0, 0, magnifierSize, magnifierSize)
  ctx.imageSmoothingEnabled = false

  ctx.drawImage(
    img,
    svgPt.x - srcSize / 2,
    svgPt.y - srcSize / 2,
    srcSize,
    srcSize,
    0,
    0,
    magnifierSize,
    magnifierSize
  )

  // 画十字准线
  ctx.strokeStyle = 'rgba(201, 100, 66, 0.8)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(magnifierSize / 2, 0)
  ctx.lineTo(magnifierSize / 2, magnifierSize)
  ctx.moveTo(0, magnifierSize / 2)
  ctx.lineTo(magnifierSize, magnifierSize / 2)
  ctx.stroke()

  // 中心点标记
  ctx.fillStyle = '#c96442'
  ctx.beginPath()
  ctx.arc(magnifierSize / 2, magnifierSize / 2, 3, 0, Math.PI * 2)
  ctx.fill()
}

function closeCurrentPolygon() {
  // 矩形模式不封闭多边形
  if (drawMode.value === 'rect') return
  if (currentPoly.value.length >= 3) {
    const snap = JSON.parse(JSON.stringify(polygons.value))
    history.value.push({ type: 'add', polys: snap, current: JSON.parse(JSON.stringify(currentPoly.value)) })
    polygons.value.push({
      type: currentRegionType.value,
      points: [...currentPoly.value]
    })
    currentPoly.value = []
    selectedPolyIdx.value = polygons.value.length - 1
    // 完成题跋后提示切换绘画
    if (currentRegionType.value === 'inscription') {
      ElMessage.info('题跋区域已保存，可切换到「绘画」继续标注')
    }
  }
}

// 选择多边形
function selectPolygon(idx) {
  selectedPolyIdx.value = idx
}

// 切换多边形类型
function togglePolyType(idx) {
  const poly = polygons.value[idx]
  if (!poly) return
  history.value.push({ type: 'toggle', polys: JSON.parse(JSON.stringify(polygons.value)) })
  // 轮换: inscription → painting → margin → inscription
  if (poly.type === 'inscription' || !poly.type) poly.type = 'painting'
  else if (poly.type === 'painting') poly.type = 'margin'
  else poly.type = 'inscription'
}

// 删除多边形
function deletePolygon(idx) {
  history.value.push({ type: 'delete', polys: JSON.parse(JSON.stringify(polygons.value)), deletedIdx: idx })
  polygons.value.splice(idx, 1)
  if (selectedPolyIdx.value === idx) selectedPolyIdx.value = -1
  else if (selectedPolyIdx.value > idx) selectedPolyIdx.value--
}

// 顶点拖拽
let isDragging = false
let dragState = null // { polyIdx, vertexIdx }

function startDragVertex(polyIdx, vertexIdx, e) {
  e.preventDefault()
  e.stopPropagation()
  isDragging = false
  dragState = { polyIdx, vertexIdx }
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e) {
  if (!dragState) return
  isDragging = true
  const pt = screenToSvg(e.clientX, e.clientY)
  if (!pt) return

  if (dragState.polyIdx === -1) {
    if (currentPoly.value[dragState.vertexIdx]) {
      currentPoly.value[dragState.vertexIdx] = pt
    }
  } else {
    const poly = polygons.value[dragState.polyIdx]
    if (poly) {
      const points = poly.points || poly
      if (points[dragState.vertexIdx]) {
        points[dragState.vertexIdx] = pt
      }
    }
  }
}

function onDragEnd() {
  // 延迟重置 isDragging，防止 mouseup 触发 click
  setTimeout(() => { isDragging = false }, 50)
  dragState = null
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
}

// 键盘事件
function onKeyDown(e) {
  if (e.key === ' ' || e.code === 'Space') {
    isSpaceDown.value = true
    e.preventDefault()
  } else if (e.key === 'ArrowLeft') {
    const move = 100 * currentScale.value
    viewBoxX.value += move
    e.preventDefault()
  } else if (e.key === 'ArrowRight') {
    const move = 100 * currentScale.value
    viewBoxX.value -= move
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    const move = 100 * currentScale.value
    viewBoxY.value += move
    e.preventDefault()
  } else if (e.key === 'ArrowDown') {
    const move = 100 * currentScale.value
    viewBoxY.value -= move
    e.preventDefault()
  } else if (e.key === 'Escape') {
    if (rectStart.value) {
      // 取消矩形拖拽
      rectStart.value = null
      rectCurrent.value = null
    } else if (currentPoly.value.length > 0) {
      currentPoly.value = []
    } else {
      selectedPolyIdx.value = -1
    }
  } else if (e.key === 'Enter') {
    closeCurrentPolygon()
  } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
    undoLast()
  } else if (e.key === 'm' || e.key === 'M') {
    magnifierEnabled.value = !magnifierEnabled.value
  }
}

// 键盘释放
function onKeyUp(e) {
  if (e.key === ' ' || e.code === 'Space') {
    isSpaceDown.value = false
  }
}

// 撤销
function undoLast() {
  if (history.value.length === 0) return
  const last = history.value.pop()
  if (last.type === 'add') {
    polygons.value = last.polys
    currentPoly.value = last.current || []
  } else if (last.type === 'delete') {
    polygons.value = last.polys
  } else if (last.type === 'toggle') {
    polygons.value = last.polys
  } else if (last.type === 'clear') {
    polygons.value = last.polys
  }
}

// 清空
function clearAll() {
  if (polygons.value.length === 0) return
  history.value.push({ type: 'clear', polys: JSON.parse(JSON.stringify(polygons.value)) })
  polygons.value = []
  currentPoly.value = []
  selectedPolyIdx.value = -1
}

// 保存
async function saveRegions() {
  if (polygons.value.length === 0) {
    ElMessage.warning('请至少标注一个区域')
    return
  }

  const regions = polygons.value.map(poly => {
    const points = poly.points || poly
    return {
      type: poly.type || 'inscription',
      points: points.map(p => ({ x: p.x, y: p.y }))
    }
  })

  // suggest模式 + 普通用户 → 保存为本地草稿
  if (isSuggestMode.value && !isSuggestAdmin.value) {
    try {
      localStorage.setItem(DRAFT_KEY.value, JSON.stringify(regions))
      hasDraft.value = true
      ElMessage.success('草稿已保存到本地')
    } catch (e) {
      ElMessage.error('草稿保存失败: ' + e.message)
    }
    return
  }

  // 管理员/非suggest模式 → 直接写入数据库
  saving.value = true
  try {
    const res = await fetch(`/api/v1/tubi/${route.params.id}/regions`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}` },
      body: JSON.stringify({ regions })
    })

    if (!res.ok) throw new Error(await res.text())

    // 清除本地草稿
    localStorage.removeItem(DRAFT_KEY.value)
    hasDraft.value = false

    ElMessage.success('标注已保存')
    const targetId = recordData.value?.image_id || recordData.value?.id
    if (targetId) {
      router.push(`/tubi/${targetId}`)
    }
  } catch (err) {
    ElMessage.error('保存失败：' + err.message)
  } finally {
    saving.value = false
  }
}

// 恢复本地草稿
function restoreDraft() {
  try {
    const draft = localStorage.getItem(DRAFT_KEY.value)
    if (!draft) {
      ElMessage.info('没有找到本地草稿')
      return
    }
    const regions = JSON.parse(draft)
    polygons.value = regions
    history.value = []
    selectedPolyIdx.value = -1
    currentPoly.value = []
    ElMessage.success('已恢复上次保存的草稿')
  } catch (e) {
    ElMessage.error('草稿恢复失败: ' + e.message)
  }
}

// 意见提交模式：提交标注修改为 change_request
async function submitForReview() {
  if (polygons.value.length === 0) {
    ElMessage.warning('请至少标注一个区域')
    return
  }
  submittingReview.value = true
  try {
    const regions = polygons.value.map(poly => {
      const points = poly.points || poly
      return {
        type: poly.type || 'inscription',
        points: points.map(p => ({ x: p.x, y: p.y }))
      }
    })
    const newValue = JSON.stringify(regions)
    const oldValue = initialRegionsSnapshot.value || '[]'

    // 从 URL 参数或 sessionStorage 读取信息
    let libId = route.query.lib
    let artworkId = route.query.artwork
    if (!libId) libId = sessionStorage.getItem('suggest_library_id')
    if (!artworkId) artworkId = sessionStorage.getItem('suggest_artwork_id') || route.params.id
    if (!libId) {
      ElMessage.error('缺少作品库信息，请从作品详情页进入')
      return
    }

    const res = await fetch(`/api/v1/libraries/${libId}/requests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}` },
      body: JSON.stringify({
        artwork_id: artworkId,
        request_type: 'adjust_region',
        field_name: 'annotation_regions',
        old_value: oldValue,
        new_value: newValue,
        change_summary: '标注区域意见'
      })
    })

    if (!res.ok) {
      const errData = await res.json()
      throw new Error(errData.detail || '提交失败')
    }

    // 设置标志，供 TubiDetail 检测
    const imageId = route.params.id
    localStorage.setItem('suggest_annotation_done_' + imageId, '1')
    // 清除本地草稿
    localStorage.removeItem(DRAFT_KEY.value)

    ElMessage.success('标注意见已提交审阅！')
    // 提示后关闭窗口
    setTimeout(() => window.close(), 2000)
  } catch (err) {
    ElMessage.error('提交失败：' + err.message)
  } finally {
    submittingReview.value = false
  }
}

// 返回
function goBack() {
  router.back()
}

// 加载数据
async function loadRecord() {
  try {
    const res = await fetch(`/api/v1/tubi/${route.params.id}`)
    if (!res.ok) throw new Error('记录不存在')
    const data = await res.json()

    recordData.value = data.data

    // 设置图片尺寸 - 支持 image_width/image_height 或 width/height
    const w = data.data.image_width || data.data.width
    const h = data.data.image_height || data.data.height
    if (w && h) {
      imgNaturalW.value = w
      imgNaturalH.value = h
    }

    // 选择图片源：卷轴(宽高比>=5)用原图，普通图用缩略图
    const aspectRatio = (w && h) ? Math.max(w, h) / Math.max(Math.min(w, h), 1) : 0
    if (aspectRatio >= 5) {
      // 卷轴——直接用原图，缩略图拉伸太模糊
      let fullUrl = data.data.url || data.data.filepath || ''
      if (fullUrl && !fullUrl.startsWith('http')) {
        fullUrl = `${fullUrl.startsWith('/') ? '' : '/'}${fullUrl}`
      }
      imageUrl.value = fullUrl
    } else {
      // 普通图——用缩略图，大图也流畅
      let url = data.data.thumbnail_url || data.data.thumbnail_path || ''
      if (!url) {
        url = data.data.url || data.data.filepath || ''
      }
      if (url && !url.startsWith('http')) {
        if (!url.startsWith('/static/') && !url.startsWith('/')) url = '/' + url
      }
      imageUrl.value = url
    }

    // 预加载原图（用于放大镜高精度显示）
    const fullUrl = data.data.url || data.data.filepath || ''
    const magnifierSrc = (fullUrl && !fullUrl.startsWith('http'))
      ? `${fullUrl.startsWith('/') ? '' : '/'}${fullUrl}`
      : fullUrl
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      hiddenImg.value = img
      // 如果数据库没有尺寸，从图片获取
      if (!data.data.image_width || !data.data.image_height) {
        imgNaturalW.value = img.naturalWidth
        imgNaturalH.value = img.naturalHeight
      }
      console.log(`[Annotator] Image loaded: ${img.naturalWidth}x${img.naturalHeight}`)
    }
    img.src = magnifierSrc

    // 如果已有 regions，回显
    const allRegions = []
    if (data.data.regions?.margin_regions?.length) {
      data.data.regions.margin_regions.forEach(r => {
        if (r.x1 !== undefined) {
          allRegions.push({
            type: 'margin',
            points: [
              { x: r.x1, y: r.y1 },
              { x: r.x2, y: r.y1 },
              { x: r.x2, y: r.y2 },
              { x: r.x1, y: r.y2 }
            ]
          })
        } else if (r.points) {
          allRegions.push({ type: 'margin', points: r.points })
        }
      })
    }
    if (data.data.regions?.inscription_regions?.length) {
      data.data.regions.inscription_regions.forEach(r => {
        if (r.x1 !== undefined) {
          allRegions.push({
            type: 'inscription',
            points: [
              { x: r.x1, y: r.y1 },
              { x: r.x2, y: r.y1 },
              { x: r.x2, y: r.y2 },
              { x: r.x1, y: r.y2 }
            ]
          })
        } else if (r.points) {
          allRegions.push({ type: 'inscription', points: r.points })
        }
      })
    }
    if (data.data.regions?.painting_regions?.length) {
      data.data.regions.painting_regions.forEach(r => {
        if (r.x1 !== undefined) {
          allRegions.push({
            type: 'painting',
            points: [
              { x: r.x1, y: r.y1 },
              { x: r.x2, y: r.y1 },
              { x: r.x2, y: r.y2 },
              { x: r.x1, y: r.y2 }
            ]
          })
        } else if (r.points) {
          allRegions.push({ type: 'painting', points: r.points })
        }
      })
    }
    polygons.value = allRegions
    // 防御性处理：如果 regions 是数组格式（数据异常），尝试直接提取区域
    if (Array.isArray(data.data.regions)) {
      const extracted = data.data.regions
        .filter(function (r) { return r && r.type && r.points })
        .map(function (r) { return { type: r.type, points: r.points } })
      if (extracted.length > 0) {
        polygons.value = extracted
      }
    }
    // 审核预览模式：从 URL 参数读取新标注区域覆盖
    if (isReviewMode.value) {
      const encodedRegions = route.query.regions
      if (encodedRegions) {
        try {
          const parsedRegions = JSON.parse(decodeURIComponent(encodedRegions))
          if (Array.isArray(parsedRegions) && parsedRegions.length > 0) {
            polygons.value = parsedRegions
          }
        } catch (_) {}
      }
    }
    // 意见提交模式：记录初始状态用于 old_value
    if (isSuggestMode.value) {
      initialRegionsSnapshot.value = JSON.stringify(allRegions)
    }
    // 恢复本地草稿提示
    if (isSuggestMode.value && !isSuggestAdmin.value) {
      const draft = localStorage.getItem(DRAFT_KEY.value)
      if (draft) {
        hasDraft.value = true
      }
    }
  } catch (err) {
    ElMessage.error('加载记录失败：' + err.message)
  }
}

onMounted(() => {
  loadRecord()
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
})
</script>

<style scoped>
.annotator-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--parchment, #f5f4ed);
  font-family: 'Noto Sans SC', sans-serif;
}

/* 工具栏 */
.annotator-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: var(--ivory, #faf9f5);
  border-bottom: 1px solid var(--border-warm, #e8e6dc);
  flex-shrink: 0;
  gap: 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--near-black, #141413);
}

.toolbar-center {
  flex: 1;
  text-align: center;
}

.tip-text {
  font-size: 13px;
  color: var(--stone-gray, #87867f);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 缩放控制 */
.zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-right: 8px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 6px;
  border: 1px solid var(--border-cream, #e8e6dc);
}

.zoom-ratio {
  min-width: 50px;
  text-align: center;
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  font-variant-numeric: tabular-nums;
}

/* 区域类型选择器 */
.region-type-selector {
  margin-right: 8px;
}

.type-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
}

.type-dot.inscription {
  background: #c96442;
}

.type-dot.painting {
  background: #4a7fc9;
}

.type-dot.margin {
  background: #333;
}

/* 按钮文字垂直居中 */
.annotator-toolbar :deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 工作区 */
.annotator-workspace {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* 左侧画布 */
.canvas-area {
  flex: 1;
  background: #303030;
  position: relative;
  overflow: hidden;
}

/* SVG 填满整个画布区域 */
.annotator-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
}

/* 多边形样式 - stroke-width 用 vector-effect 保证视觉一致 */
.poly-done {
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  cursor: pointer;
  transition: fill 0.15s;
}

/* 题跋区域 - 红色 */
.poly-done.poly-inscription {
  fill: rgba(201, 100, 66, 0.25);
  stroke: #c96442;
}

.poly-done.poly-inscription:hover,
.poly-done.poly-inscription.poly-selected {
  fill: rgba(201, 100, 66, 0.4);
  stroke-width: 3;
}

/* 余边区域 - 灰色 */
.poly-done.poly-margin {
  fill: rgba(51, 51, 51, 0.3);
  stroke: #333;
}

.poly-done.poly-margin:hover,
.poly-done.poly-margin.poly-selected {
  fill: rgba(51, 51, 51, 0.45);
  stroke-width: 3;
}

/* 绘画区域 - 蓝色 */
.poly-done.poly-painting {
  fill: rgba(74, 127, 201, 0.25);
  stroke: #4a7fc9;
}

.poly-done.poly-painting:hover,
.poly-done.poly-painting.poly-selected {
  fill: rgba(74, 127, 201, 0.4);
  stroke-width: 3;
}

.poly-drawing {
  stroke-width: 1.5;
  stroke-dasharray: 6 3;
  vector-effect: non-scaling-stroke;
}

.poly-drawing.drawing-inscription {
  fill: rgba(201, 100, 66, 0.15);
  stroke: #e07a5a;
}

.poly-drawing.drawing-painting {
  fill: rgba(74, 127, 201, 0.15);
  stroke: #6a9fd9;
}

.poly-drawing.drawing-margin {
  fill: rgba(51, 51, 51, 0.2);
  stroke: #555;
}

/* 矩形模式拖拽预览 */
.rect-preview {
  stroke-width: 1.5;
  stroke-dasharray: 6 3;
  vector-effect: non-scaling-stroke;
  fill: none;
  pointer-events: none;
}
.rect-preview.drawing-inscription { stroke: #e07a5a; fill: rgba(201, 100, 66, 0.1); }
.rect-preview.drawing-painting { stroke: #6a9fd9; fill: rgba(74, 127, 201, 0.1); }
.rect-preview.drawing-margin { stroke: #555; fill: rgba(51, 51, 51, 0.15); }

/* 顶点样式 */
.vertex {
  stroke: white;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  cursor: move;
}

/* 题跋顶点 - 红色 */
.vertex.vertex-inscription {
  fill: #c96442;
}

.vertex.vertex-inscription:hover {
  fill: #a8503a;
}

/* 绘画顶点 - 蓝色 */
.vertex.vertex-painting {
  fill: #4a7fc9;
}

.vertex.vertex-painting:hover {
  fill: #3a6fb9;
}

/* 余边顶点 - 灰色 */
.vertex.vertex-margin {
  fill: #333;
}

.vertex.vertex-margin:hover {
  fill: #555;
}

.vertex-selected {
  fill: #a8503a;
  stroke: #ffd700;
  stroke-width: 2.5;
}

.vertex-drawing {
  stroke: white;
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
  cursor: move;
}

.vertex-drawing.drawing-inscription {
  fill: #e07a5a;
}

.vertex-drawing.drawing-painting {
  fill: #6a9fd9;
}

.vertex-drawing.drawing-margin {
  fill: #555;
}

/* 右侧面板 */
.annotator-panel {
  width: 280px;
  background: var(--ivory, #faf9f5);
  border-left: 1px solid var(--border-warm, #e8e6dc);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex-shrink: 0;
}

.panel-section {
  padding: 16px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
}

/* 工具栏区域 */
.toolbar-section {
  padding: 16px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
}

.toolbar-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--near-black, #141413);
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}

.toolbar-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

/* 按钮文字垂直居中 */
.toolbar-section :deep(.el-button),
.action-buttons :deep(.el-button),
.annotator-panel :deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.info-title,
.stats-title,
.list-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--charcoal-warm, #4d4c48);
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  margin-bottom: 6px;
}

.info-label {
  color: var(--stone-gray, #87867f);
}

.info-value {
  color: var(--near-black, #141413);
  font-weight: 500;
}

/* 统计 */
.stat-big {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
}

.stat-number {
  font-size: 42px;
  font-weight: 700;
  color: var(--cinnabar, #c96442);
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: var(--stone-gray, #87867f);
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 4px 0;
}

.stat-row-label {
  color: var(--stone-gray, #87867f);
}

.stat-row-value {
  font-weight: 600;
  color: var(--near-black, #141413);
}

/* 列表 */
.list-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.list-count {
  background: var(--cinnabar, #c96442);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 10px;
}

.poly-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.poly-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--parchment, #f5f4ed);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.poly-item:hover {
  background: var(--warm-sand, #e8e6dc);
}

.poly-item-active {
  background: rgba(201, 100, 66, 0.15);
  border: 1px solid var(--cinnabar, #c96442);
}

.poly-index {
  width: 20px;
  height: 20px;
  background: var(--cinnabar, #c96442);
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.poly-type-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  cursor: pointer;
  transition: transform 0.15s;
  flex-shrink: 0;
}

.poly-type-dot:hover {
  transform: scale(1.3);
}

.poly-type-dot.type-inscription {
  background: #c96442;
}

.poly-type-dot.type-painting {
  background: #4a7fc9;
}

.poly-type-dot.type-margin {
  background: #333;
}

.poly-info {
  flex: 1;
  color: var(--charcoal-warm, #4d4c48);
}

.poly-delete {
  color: var(--stone-gray, #87867f);
  padding: 2px;
}

.poly-empty {
  text-align: center;
  color: var(--stone-gray, #87867f);
  font-size: 13px;
  padding: 20px 0;
}

/* 提示 */
.hint-section {
  margin-top: auto;
}

.hint-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  margin-bottom: 6px;
}

.hint-key {
  background: var(--warm-sand, #e8e6dc);
  color: var(--charcoal-warm, #4d4c48);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 11px;
  min-width: 60px;
  text-align: center;
}

.hint-val {
  color: var(--stone-gray, #87867f);
}

/* 放大镜 */
.magnifier {
  position: absolute;
  border: 2px solid var(--cinnabar, #c96442);
  border-radius: 50%;
  overflow: hidden;
  pointer-events: none;
  z-index: 100;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  background: #000;
}

.magnifier canvas {
  display: block;
  border-radius: 50%;
}

.magnifier-crosshair {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 12px;
  height: 12px;
  transform: translate(-50%, -50%);
  border: 1.5px solid rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  pointer-events: none;
}

.suggest-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  background: #fff3cd;
  color: #856404;
  font-size: 14px;
  font-weight: 500;
  border-bottom: 1px solid #ffc107;
}
.review-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  background: #d9edf7;
  color: #31708f;
  font-size: 14px;
  font-weight: 500;
  border-bottom: 1px solid #bce8f1;
}
</style>
