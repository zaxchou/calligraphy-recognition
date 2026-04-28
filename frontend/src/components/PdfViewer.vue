<template>
  <div class="pdf-viewer" ref="viewerContainer">
    <!-- 加载状态 -->
    <div v-if="loading" class="pdf-loading">
      <Loader2 class="icon spin" />
      <span>加载 PDF 中...</span>
    </div>
    
    <!-- 错误状态 -->
    <div v-else-if="error" class="pdf-error">
      <AlertCircle class="icon" />
      <span>{{ error }}</span>
      <button class="retry-btn" @click="loadPdf">重试</button>
    </div>
    
    <!-- PDF 内容 -->
    <div v-else class="pdf-content">
      <!-- 页面导航栏 -->
      <div class="page-nav-bar">
        <button 
          class="nav-btn" 
          :disabled="currentPage <= 1"
          @click="goToPage(currentPage - 1)"
        >
          <ChevronLeft class="icon" />
        </button>
        <span class="page-info">
          <input 
            type="number" 
            v-model.number="pageInput" 
            :min="1" 
            :max="totalPages"
            class="page-input"
            @keyup.enter="goToPage(pageInput)"
            @blur="goToPage(pageInput)"
          />
          <span class="page-total">/ {{ totalPages }}</span>
        </span>
        <button 
          class="nav-btn" 
          :disabled="currentPage >= totalPages"
          @click="goToPage(currentPage + 1)"
        >
          <ChevronRight class="icon" />
        </button>
        
        <!-- 缩放控制 -->
        <div class="zoom-controls">
          <button class="nav-btn" @click="zoomOut">
            <ZoomOut class="icon" />
          </button>
          <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
          <button class="nav-btn" @click="zoomIn">
            <ZoomIn class="icon" />
          </button>
          <button class="nav-btn" @click="fitWidth">
            <Maximize2 class="icon" />
          </button>
        </div>
      </div>
      
      <!-- PDF 渲染区域 -->
      <div class="pdf-viewport" ref="viewport">
        <canvas ref="pdfCanvas"></canvas>
        
        <!-- bbox 高亮层 -->
        <div class="bbox-overlay" ref="bboxOverlay">
          <div 
            v-for="(bbox, index) in visibleBboxes" 
            :key="index"
            class="bbox-highlight"
            :class="{ 'bbox-active': bbox.active }"
            :style="getBboxStyle(bbox)"
            @click="onBboxClick(bbox)"
          >
            <span v-if="bbox.label" class="bbox-label">{{ bbox.label }}</span>
          </div>
        </div>
      </div>
      
      <!-- 缩略图导航（可选） -->
      <div v-if="showThumbnails" class="thumbnail-panel">
        <div 
          v-for="page in totalPages" 
          :key="page"
          class="thumbnail-item"
          :class="{ 'thumbnail-active': page === currentPage }"
          @click="goToPage(page)"
        >
          <canvas :ref="el => thumbnailRefs[page] = el"></canvas>
          <span class="thumbnail-page">{{ page }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { 
  Loader2, AlertCircle, ChevronLeft, ChevronRight, 
  ZoomIn, ZoomOut, Maximize2 
} from 'lucide-vue-next'

// PDF.js 动态导入
let pdfjsLib = null

const props = defineProps({
  // PDF 文件 URL
  pdfUrl: {
    type: String,
    required: true
  },
  // 初始页码
  initialPage: {
    type: Number,
    default: 1
  },
  // bbox 数据数组 [{ page, x, y, width, height, label, active }]
  bboxes: {
    type: Array,
    default: () => []
  },
  // 是否显示缩略图
  showThumbnails: {
    type: Boolean,
    default: false
  },
  // 自动滚动到第一个 bbox
  autoScrollToBbox: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['page-change', 'bbox-click', 'pdf-loaded'])

// 状态
const loading = ref(true)
const error = ref(null)
const pdfDoc = ref(null)
const currentPage = ref(props.initialPage)
const totalPages = ref(0)
const scale = ref(1.5)
const pageInput = ref(props.initialPage)

// DOM refs
const viewerContainer = ref(null)
const viewport = ref(null)
const pdfCanvas = ref(null)
const bboxOverlay = ref(null)
const thumbnailRefs = ref({})

// 渲染任务
let renderTask = null

// 计算当前页的 bbox
const visibleBboxes = computed(() => {
  return props.bboxes.filter(bbox => bbox.page === currentPage.value)
})

// 初始化 PDF.js
async function initPdfJs() {
  if (!pdfjsLib) {
    try {
      const pdfjsModule = await import('pdfjs-dist')
      pdfjsLib = pdfjsModule
      
      // 设置 worker - 使用 CDN 方式（兼容 pdfjs-dist 5.x）
      pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`
    } catch (e) {
      console.error('PDF.js 初始化失败:', e)
      error.value = 'PDF.js 加载失败，请刷新页面重试'
      loading.value = false
      return false
    }
  }
  return true
}

// 加载 PDF
async function loadPdf() {
  loading.value = true
  error.value = null
  
  const initialized = await initPdfJs()
  if (!initialized) return
  
  try {
    const loadingTask = pdfjsLib.getDocument({
      url: props.pdfUrl,
      cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
      cMapPacked: true,
      enableXfa: true
    })
    
    pdfDoc.value = await loadingTask.promise
    totalPages.value = pdfDoc.value.numPages
    currentPage.value = Math.min(props.initialPage, totalPages.value)
    pageInput.value = currentPage.value
    
    await renderPage(currentPage.value)
    
    emit('pdf-loaded', {
      totalPages: totalPages.value,
      currentPage: currentPage.value
    })
  } catch (e) {
    console.error('PDF 加载失败:', e)
    error.value = `PDF 加载失败: ${e.message || '未知错误'}`
  } finally {
    loading.value = false
  }
}

// 渲染指定页面
async function renderPage(pageNum) {
  if (!pdfDoc.value || !pdfCanvas.value) return
  
  // 取消之前的渲染任务
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  
  try {
    const page = await pdfDoc.value.getPage(pageNum)
    const viewportObj = page.getViewport({ scale: scale.value })
    
    const canvas = pdfCanvas.value
    const context = canvas.getContext('2d')
    
    // 设置 canvas 尺寸
    canvas.height = viewportObj.height
    canvas.width = viewportObj.width
    
    // 设置 viewport 容器尺寸
    if (viewport.value) {
      viewport.value.style.width = `${viewportObj.width}px`
      viewport.value.style.height = `${viewportObj.height}px`
    }
    
    // 渲染页面
    renderTask = page.render({
      canvasContext: context,
      viewport: viewportObj
    })
    
    await renderTask.promise
    renderTask = null
    
    // 渲染缩略图（如果启用）
    if (props.showThumbnails) {
      await renderThumbnail(pageNum, page)
    }
    
    // 自动滚动到第一个 bbox
    if (props.autoScrollToBbox && visibleBboxes.value.length > 0) {
      scrollToFirstBbox()
    }
  } catch (e) {
    if (e.name !== 'RenderingCancelledException') {
      console.error('页面渲染失败:', e)
      error.value = '页面渲染失败'
    }
  }
}

// 渲染缩略图
async function renderThumbnail(pageNum, page) {
  const thumbCanvas = thumbnailRefs.value[pageNum]
  if (!thumbCanvas) return
  
  const thumbViewport = page.getViewport({ scale: 0.2 })
  const context = thumbCanvas.getContext('2d')
  
  thumbCanvas.height = thumbViewport.height
  thumbCanvas.width = thumbViewport.width
  
  await page.render({
    canvasContext: context,
    viewport: thumbViewport
  }).promise
}

// 页面导航
function goToPage(page) {
  const pageNum = Math.max(1, Math.min(page, totalPages.value))
  if (pageNum !== currentPage.value) {
    currentPage.value = pageNum
    pageInput.value = pageNum
    renderPage(pageNum)
    emit('page-change', pageNum)
  }
}

// 缩放控制
function zoomIn() {
  scale.value = Math.min(scale.value + 0.25, 3)
  renderPage(currentPage.value)
}

function zoomOut() {
  scale.value = Math.max(scale.value - 0.25, 0.5)
  renderPage(currentPage.value)
}

function fitWidth() {
  if (viewport.value && pdfCanvas.value) {
    const containerWidth = viewport.value.parentElement.clientWidth - 40
    const canvasWidth = pdfCanvas.value.width / scale.value
    scale.value = containerWidth / canvasWidth
    renderPage(currentPage.value)
  }
}

// 获取 bbox 样式
function getBboxStyle(bbox) {
  // bbox 坐标需要根据 scale 转换
  const x = bbox.x * scale.value
  const y = bbox.y * scale.value
  const width = bbox.width * scale.value
  const height = bbox.height * scale.value
  
  return {
    left: `${x}px`,
    top: `${y}px`,
    width: `${width}px`,
    height: `${height}px`
  }
}

// 点击 bbox
function onBboxClick(bbox) {
  emit('bbox-click', bbox)
}

// 滚动到第一个 bbox
function scrollToFirstBbox() {
  if (visibleBboxes.value.length > 0 && bboxOverlay.value) {
    const firstBbox = visibleBboxes.value[0]
    const y = firstBbox.y * scale.value
    bboxOverlay.value.parentElement.scrollTo({
      top: Math.max(0, y - 100),
      behavior: 'smooth'
    })
  }
}

// 跳转到包含指定 bbox 的页面
function goToBbox(bbox) {
  if (bbox.page !== currentPage.value) {
    goToPage(bbox.page)
  }
  // 等待渲染完成后滚动
  nextTick(() => {
    scrollToFirstBbox()
  })
}

// 监听 props 变化
watch(() => props.pdfUrl, (newUrl) => {
  if (newUrl) {
    loadPdf()
  }
})

watch(() => props.initialPage, (newPage) => {
  if (newPage && newPage !== currentPage.value) {
    goToPage(newPage)
  }
})

watch(() => props.bboxes, () => {
  // bbox 变化时重新渲染高亮
  nextTick(() => {
    if (props.autoScrollToBbox && visibleBboxes.value.length > 0) {
      scrollToFirstBbox()
    }
  })
}, { deep: true })

// 生命周期
onMounted(() => {
  if (props.pdfUrl) {
    loadPdf()
  }
})

onUnmounted(() => {
  // 清理渲染任务
  if (renderTask) {
    renderTask.cancel()
  }
  // 清理 PDF 文档
  if (pdfDoc.value) {
    pdfDoc.value.destroy()
  }
})

// 暴露方法给父组件
defineExpose({
  goToPage,
  goToBbox,
  zoomIn,
  zoomOut,
  fitWidth,
  getCurrentPage: () => currentPage.value,
  getTotalPages: () => totalPages.value
})
</script>

<style scoped>
.pdf-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f0e8;
  border-radius: 8px;
  overflow: hidden;
}

/* 加载和错误状态 */
.pdf-loading,
.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: #8b7355;
}

.pdf-error {
  color: #ef4444;
}

.retry-btn {
  padding: 8px 16px;
  background: #c45c48;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.retry-btn:hover {
  background: #a84838;
}

/* 页面导航栏 */
.page-nav-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e8e4dc;
}

.nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: #f8f6f1;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background: #c45c48;
  border-color: #c45c48;
  color: #fff;
}

.nav-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-input {
  width: 50px;
  height: 32px;
  text-align: center;
  border: 1px solid #e8e4dc;
  border-radius: 4px;
  font-size: 14px;
}

.page-input:focus {
  outline: none;
  border-color: #c45c48;
}

.page-total {
  font-size: 14px;
  color: #8b7355;
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 24px;
  padding-left: 24px;
  border-left: 1px solid #e8e4dc;
}

.zoom-level {
  font-size: 13px;
  color: #8b7355;
  min-width: 45px;
  text-align: center;
}

/* PDF 渲染区域 */
.pdf-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pdf-viewport {
  flex: 1;
  overflow: auto;
  display: flex;
  justify-content: center;
  padding: 20px;
  position: relative;
}

.pdf-viewport canvas {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

/* bbox 高亮层 */
.bbox-overlay {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  pointer-events: none;
}

.bbox-highlight {
  position: absolute;
  border: 2px solid #c45c48;
  background: rgba(196, 92, 72, 0.15);
  cursor: pointer;
  pointer-events: auto;
  transition: all 0.2s;
}

.bbox-highlight:hover {
  background: rgba(196, 92, 72, 0.3);
  border-color: #a84838;
}

.bbox-highlight.bbox-active {
  border-color: #16a34a;
  background: rgba(22, 163, 74, 0.2);
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.3);
}

.bbox-label {
  position: absolute;
  top: -20px;
  left: 0;
  padding: 2px 6px;
  background: #c45c48;
  color: #fff;
  font-size: 11px;
  border-radius: 3px;
  white-space: nowrap;
}

.bbox-active .bbox-label {
  background: #16a34a;
}

/* 缩略图面板 */
.thumbnail-panel {
  width: 120px;
  background: #fff;
  border-left: 1px solid #e8e4dc;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thumbnail-item {
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 4px;
  overflow: hidden;
  transition: all 0.2s;
}

.thumbnail-item:hover {
  border-color: #c45c48;
}

.thumbnail-item.thumbnail-active {
  border-color: #c45c48;
  box-shadow: 0 2px 8px rgba(196, 92, 72, 0.3);
}

.thumbnail-item canvas {
  width: 100%;
  display: block;
}

.thumbnail-page {
  display: block;
  text-align: center;
  padding: 4px;
  font-size: 12px;
  color: #8b7355;
  background: #f8f6f1;
}

/* 图标 */
.icon {
  width: 18px;
  height: 18px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
