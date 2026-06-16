<template>
  <Teleport to="body">
    <div v-if="visible" class="sl-overlay" @keydown.escape="close" tabindex="-1">
      <div class="sl-toolbar">
        <button class="sl-btn sl-btn-close" @click="close" title="关闭"><el-icon><Close /></el-icon></button>
        <button class="sl-btn" @click="zoomIn" title="放大"><el-icon><ZoomIn /></el-icon></button>
        <button class="sl-btn" @click="zoomOut" title="缩小"><el-icon><ZoomOut /></el-icon></button>
        <button class="sl-btn" @click="resetZoom" title="重置"><el-icon><Refresh /></el-icon></button>
        <button class="sl-btn" @click="toggleRotate" title="旋转"><el-icon><RefreshRight /></el-icon></button>
        <button class="sl-btn" @click="download" title="下载原图"><el-icon><Download /></el-icon></button>
      </div>

      <button v-if="images.length > 1" class="sl-arrow sl-left" @click.stop="prev" :disabled="index === 0">
        <span>‹</span>
      </button>

      <div class="sl-body">
        <div ref="viewerRef" class="sl-viewer" />
        <div v-if="!viewerReady" class="sl-loading">加载中...</div>
        <div v-if="currentDesc" class="sl-desc">{{ currentDesc }}</div>
        <div v-if="images.length > 1" class="sl-nav-dots">
          <span v-for="(img, i) in images" :key="i" class="sl-dot" :class="{ active: i === index }" @click="goTo(i)" />
        </div>
      </div>

      <button v-if="images.length > 1" class="sl-arrow sl-right" @click.stop="next" :disabled="index >= images.length - 1">
        <span>›</span>
      </button>

      <div class="sl-footer">
        <span class="sl-footer-name">{{ seal.name }}</span>
        <span v-if="seal.seal_type" class="sl-footer-sep">·</span>
        <span v-if="seal.seal_type" class="sl-footer-type">{{ seal.seal_type }}</span>
        <span v-if="images.length > 1" class="sl-footer-count">{{ index + 1 }} / {{ images.length }}</span>
        <span v-if="seal.source" class="sl-footer-source">{{ seal.source }}</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, onMounted, nextTick } from 'vue'
import { ZoomIn, ZoomOut, Refresh, RefreshRight, Close, Download } from '@element-plus/icons-vue'
import { ensureOpenSeadragon } from '../../utils/openseadragon'

const props = defineProps({
  visible: { type: Boolean, default: false },
  seal: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['close'])

const index = ref(0)
const viewerRef = ref(null)
const viewerReady = ref(false)
let viewer = null
let rotation = 0
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const images = computed(() => {
  return (props.seal.images || []).map(img => (
    typeof img === 'string' ? { path: img, description: '' } : img
  ))
})

function getFullUrl(path) {
  if (!path || typeof path !== 'string') return ''
  if (path.startsWith('http')) return path
  return `${API_BASE.replace('/api/v1', '')}${path}`
}

const currentImageUrl = computed(() => {
  const img = images.value[index.value]
  return img ? getFullUrl(img.path || img) : ''
})

const currentDesc = computed(() => {
  const img = images.value[index.value]
  return img ? (img.description || '') : ''
})

let _initRetry = 0

function initViewer() {
  _initRetry++
  const el = viewerRef.value
  if (!el || el.offsetWidth === 0) {
    if (_initRetry < 30) setTimeout(initViewer, 200)
    return
  }
  const OSD = window.OpenSeadragon
  if (OSD) {
    _startViewer(el, OSD)
  } else {
    ensureOpenSeadragon().then(OSD => {
      if (OSD) _startViewer(el, OSD)
    })
  }
}

function _startViewer(el, OSD) {
  if (viewer) { viewer.destroy(); viewer = null }
  viewerReady.value = false
  viewer = OSD({
    element: el,
    tileSources: {
      type: 'image',
      url: currentImageUrl.value,
    },
    prefixUrl: '/openseadragon-images/',
    showNavigator: true,
    navigatorPosition: 'BOTTOM_RIGHT',
    navigatorSizeRatio: 0.15,
    showZoomControl: false,
    showHomeControl: false,
    showFullPageControl: false,
    showSequenceControl: false,
    gestureSettingsTouch: { pinch: true, flick: true },
    minZoomImageRatio: 0.5,
    maxZoomPixelRatio: 10,
    visibilityRatio: 0.1,
    constrainDuringPan: true,
    defaultZoomLevel: 0,
    animationTime: 0.3,
    preserveViewport: true,
    preserveImageSizeOnResize: true,
  })
  viewer.addHandler('open', () => { viewerReady.value = true })
  viewer.addHandler('open-failed', () => { viewerReady.value = true })
}

function destroyViewer() {
  if (viewer) { viewer.destroy(); viewer = null }
  rotation = 0
}

function prev() {
  if (index.value > 0) { index.value--; scheduleReinit() }
}
function next() {
  if (index.value < images.value.length - 1) { index.value++; scheduleReinit() }
}
function goTo(i) {
  index.value = i; scheduleReinit()
}
function close() {
  emit('close')
}

let _reinitTimer = null
function scheduleReinit() {
  if (_reinitTimer) clearTimeout(_reinitTimer)
  _reinitTimer = setTimeout(() => { initViewer(); _reinitTimer = null }, 100)
}

function zoomIn() { viewer?.viewport?.zoomBy(1.5) }
function zoomOut() { viewer?.viewport?.zoomBy(0.667) }
function resetZoom() {
  if (viewer) { viewer.viewport.goHome(true); rotation = 0; viewer.viewport.setRotation(0) }
}
function toggleRotate() {
  rotation = (rotation + 90) % 360
  viewer?.viewport?.setRotation(rotation)
}

async function download() {
  const url = currentImageUrl.value
  if (!url) return
  try {
    const resp = await fetch(url)
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    const parts = url.split('/')
    const filename = parts[parts.length - 1] || 'seal.jpg'
    a.download = filename.includes('.') ? filename : filename + '.jpg'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } catch (e) {
    console.error('[SealLightbox] download failed:', e)
  }
}

function onKeydown(e) {
  if (!props.visible) return
  if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
  else if (e.key === 'ArrowRight') { e.preventDefault(); next() }
  else if (e.key === 'Escape') close()
}

watch(() => props.visible, (v) => {
  if (v) {
    index.value = 0
    _initRetry = 0
    nextTick(() => setTimeout(initViewer, 200))
  } else {
    destroyViewer()
  }
}, { immediate: true })

watch(() => props.seal, () => {
  if (props.visible) {
    index.value = 0
    nextTick(() => setTimeout(initViewer, 200))
  }
})

onBeforeUnmount(() => {
  destroyViewer()
  document.removeEventListener('keydown', onKeydown)
})

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.sl-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: #1a1a1a;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  outline: none;
}

.sl-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}

.sl-btn {
  width: 36px; height: 36px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(0,0,0,0.55);
  color: #fff;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  padding: 0; font-size: 16px; line-height: 1;
}
.sl-btn:hover { background: rgba(0,0,0,0.8); border-color: rgba(255,255,255,0.4); }

.sl-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  position: relative;
}

.sl-viewer {
  width: 100%;
  height: 100%;
}

.sl-loading {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  color: #ff0; font-size: 16px; z-index: 5;
}

.sl-desc {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  color: #d4cfc0;
  font-size: 15px;
  text-align: center;
  font-family: 'Noto Serif SC', serif;
  letter-spacing: 1px;
  z-index: 5;
  pointer-events: none;
  background: rgba(0,0,0,0.4);
  padding: 6px 16px;
  border-radius: 6px;
}

.sl-nav-dots {
  position: absolute;
  bottom: 64px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 10px;
  z-index: 5;
}

.sl-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.35);
  cursor: pointer;
  transition: background 0.2s;
}
.sl-dot.active { background: #fff; }

.sl-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #fff;
  font-size: 52px;
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 0.2s;
  padding: 12px 8px;
  line-height: 1;
  z-index: 10;
}
.sl-arrow:hover:not(:disabled) { opacity: 0.9; }
.sl-arrow:disabled { opacity: 0.1; cursor: default; }
.sl-left { left: 12px; }
.sl-right { right: 12px; }

.sl-footer {
  position: absolute;
  bottom: 16px;
  left: 0; right: 0;
  text-align: center;
  color: rgba(255,255,255,0.5);
  font-size: 13px;
  z-index: 5;
  pointer-events: none;
}
.sl-footer-name { font-weight: 600; color: #d4cfc0; }
.sl-footer-sep { margin: 0 8px; color: #666; }
.sl-footer-count { margin-left: 8px; color: #888; }
.sl-footer-source { display: block; margin-top: 4px; font-size: 12px; color: #8a8068; }
</style>
