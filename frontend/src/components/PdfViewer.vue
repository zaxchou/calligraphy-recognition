<template>
  <div class="pdf-native" ref="container">
    <div class="pdf-nav">
      <button class="nav-btn" :disabled="currentPage <= 1" @click="goTo(currentPage - 1)">
        <ChevronLeft class="icon" />
      </button>
      <span class="page-info">
        <input type="number" v-model.number="pageInput" :min="1" :max="totalPages" class="page-input" @keyup.enter="goTo(pageInput)" />
        <span class="page-total">/ {{ totalPages || '?' }}</span>
      </span>
      <button class="nav-btn" :disabled="currentPage >= totalPages" @click="goTo(currentPage + 1)">
        <ChevronRight class="icon" />
      </button>
      <button class="nav-btn" @click="zoomOut"><ZoomOut class="icon" /></button>
      <span class="zoom-level">{{ Math.round(zoom * 100) }}%</span>
      <button class="nav-btn" @click="zoomIn"><ZoomIn class="icon" /></button>
    </div>
    <div class="pdf-frame-wrap" :style="{ height: frameHeight + 'px' }">
      <div v-if="loading" class="pdf-loading"><Loader2 class="icon spin" /> 加载 PDF...</div>
      <div v-else-if="error" class="pdf-error">
        <AlertCircle class="icon" /> {{ error }}
        <button class="retry-btn" @click="loadPdf">重试</button>
      </div>
      <iframe v-else :key="iframeKey" :src="iframeUrl" class="pdf-ifr" @load="onIframeLoad"></iframe>
    </div>
    <div v-if="bboxes.length" class="pdf-bbox-info">
      <div v-for="(b, i) in currentBboxes" :key="i" class="bbox-chip" :class="{ active: b.active }">{{ b.label || '高亮区域' }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Loader2, AlertCircle } from 'lucide-vue-next'

const props = defineProps({
  pdfUrl: { type: String, required: true },
  initialPage: { type: Number, default: 1 },
  bboxes: { type: Array, default: () => [] },
  autoScrollToBbox: { type: Boolean, default: false },
})

const emit = defineEmits(['page-change', 'bbox-click', 'pdf-loaded'])

const container = ref(null)
const loading = ref(true)
const error = ref(null)
const currentPage = ref(props.initialPage)
const totalPages = ref(0)
const zoom = ref(1)
const pageInput = ref(props.initialPage)
const frameHeight = ref(500)
const iframeKey = ref(0)

// Uses backend URL directly with hash params for page/zoom navigation.
// Browser HTTP cache handles PDF caching — 20MB loaded once, subsequent loads instant.

const iframeUrl = computed(() =>
  `${props.pdfUrl}#page=${currentPage.value}&zoom=${Math.round(zoom.value * 100)}`
)

const currentBboxes = computed(() =>
  props.bboxes.filter(b => b.page === currentPage.value)
)

function goTo(p) {
  const page = Math.max(1, Math.min(p, totalPages.value || 9999))
  currentPage.value = page
  pageInput.value = page
  iframeKey.value++
  emit('page-change', page)
}

function zoomIn() { zoom.value = Math.min(3, +(zoom.value + 0.25).toFixed(2)); iframeKey.value++ }
function zoomOut() { zoom.value = Math.max(0.5, +(zoom.value - 0.25).toFixed(2)); iframeKey.value++ }

function onIframeLoad() {
  loading.value = false
  totalPages.value = totalPages.value || 0
  emit('pdf-loaded', { currentPage: currentPage.value })
}

function loadPdf() {
  loading.value = false
  error.value = null
  totalPages.value = 0
  iframeKey.value++
}

watch(() => props.pdfUrl, () => { loadPdf() })

onMounted(() => {
  if (container.value) {
    const parent = container.value.closest('.ks-panel-body, .right-panel-body, .ks-panel-pdf')
    if (parent) {
      frameHeight.value = parent.clientHeight - 44
      const ro = new ResizeObserver(() => { frameHeight.value = parent.clientHeight - 44 })
      ro.observe(parent)
    } else frameHeight.value = Math.max(400, window.innerHeight * 0.5)
  }
  loadPdf()
})
</script>

<style scoped>
.pdf-native { display: flex; flex-direction: column; height: 100%; }
.pdf-nav { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-bottom: 1px solid #f0eee6; flex-shrink: 0; }
.nav-btn { border: none; background: #f5f2eb; padding: 4px 8px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; transition: background 0.15s; color: #5e5d59; }
.nav-btn:hover:not(:disabled) { background: #e8e4da; }
.nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.page-info { display: flex; align-items: center; gap: 2px; font-size: 13px; color: #303133; min-width: 70px; }
.page-input { width: 40px; border: 1px solid #e0ddd3; border-radius: 4px; padding: 2px 6px; font-size: 13px; text-align: center; outline: none; }
.page-input:focus { border-color: #c96442; }
.page-total { color: #999; }
.zoom-level { font-size: 12px; color: #888; min-width: 40px; text-align: center; }
.pdf-frame-wrap { flex: 1; position: relative; overflow: hidden; }
.pdf-ifr { width: 100%; height: 100%; border: none; }
.pdf-loading, .pdf-error { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: #999; font-size: 14px; background: #fafaf8; }
.retry-btn { border: 1px solid #c96442; background: #fff; color: #c96442; padding: 6px 18px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.retry-btn:hover { background: #fdf8f5; }
.pdf-bbox-info { padding: 8px 12px; border-top: 1px solid #f0eee6; display: flex; flex-wrap: wrap; gap: 6px; }
.bbox-chip { font-size: 11px; padding: 3px 10px; border-radius: 4px; background: #fef0e8; color: #c96442; border: 1px solid #f0d4c8; }
.bbox-chip.active { background: #c96442; color: #fff; }
.icon { width: 16px; height: 16px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
