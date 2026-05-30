<template>
  <div class="dzi-wrap">
    <div class="dzi-toolbar">
      <button class="dzi-btn" @click="$emit('close')" title="关闭">
        <el-icon><Close /></el-icon>
      </button>
      <button class="dzi-btn" @click="zoomIn" title="放大">
        <el-icon><ZoomIn /></el-icon>
      </button>
      <button class="dzi-btn" @click="zoomOut" title="缩小">
        <el-icon><ZoomOut /></el-icon>
      </button>
      <button class="dzi-btn" @click="resetZoom" title="重置">
        <el-icon><Refresh /></el-icon>
      </button>
      <button class="dzi-btn" @click="toggleFullscreen" title="系统全屏">
        <el-icon><FullScreen /></el-icon>
      </button>
      <button class="dzi-btn" @click="toggleRotate" title="旋转">
        <el-icon><RefreshRight /></el-icon>
      </button>
    </div>
    <div ref="viewerRef" class="dzi-viewer" />
    <div v-if="!viewerReady" class="dzi-loading">加载中...</div>
    <div class="dzi-hint">点击右上角 ✕ 或按 Esc 关闭</div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted } from 'vue'
import { ZoomIn, ZoomOut, Refresh, FullScreen, RefreshRight, Close } from '@element-plus/icons-vue'

const props = defineProps({
  imageUrl: String,
  dziUrl: String,
})
const emit = defineEmits(['close'])

const viewerRef = ref(null)
const viewerReady = ref(false)
let viewer = null
let rotation = 0
let _initRetry = 0

function initViewer() {
  _initRetry++
  const el = viewerRef.value
  if (!el || el.offsetWidth === 0) {
    if (_initRetry < 30) setTimeout(() => initViewer(), 200)
    return
  }
  const OSD = window.OpenSeadragon
  if (!OSD) {
    if (_initRetry < 30) setTimeout(() => initViewer(), 200)
    return
  }
  if (viewer) { viewer.destroy(); viewer = null }
  viewer = OSD({
    element: el,
    tileSources: props.dziUrl || { type: 'image', url: props.imageUrl },
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
  viewer.addHandler('open-failed', (e) => { console.error('[OSD] open-failed', e.message) })
}

function handleKeydown(e) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  setTimeout(initViewer, 150)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  if (viewer) { viewer.destroy(); viewer = null }
})

function zoomIn() { viewer?.viewport?.zoomBy(1.5) }
function zoomOut() { viewer?.viewport?.zoomBy(0.667) }
function resetZoom() {
  if (viewer) { viewer.viewport.goHome(true); rotation = 0; viewer.viewport.setRotation(0) }
}
function toggleFullscreen() {
  const el = viewerRef.value
  if (!el) return
  if (document.fullscreenElement) document.exitFullscreen()
  else if (el.requestFullscreen) el.requestFullscreen()
}
function toggleRotate() {
  rotation = (rotation + 90) % 360
  viewer?.viewport?.setRotation(rotation)
}
</script>

<style scoped>
.dzi-wrap {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  background: #1a1a1a;
}
.dzi-viewer {
  width: 100%;
  height: 100%;
}
.dzi-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #ff0;
  font-size: 18px;
  z-index: 5;
}
.dzi-hint {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255,255,255,0.35);
  font-size: 13px;
  z-index: 5;
  pointer-events: none;
}
.dzi-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}
.dzi-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 16px;
  line-height: 1;
}
.dzi-btn:hover {
  background: rgba(0, 0, 0, 0.8);
  border-color: rgba(255, 255, 255, 0.4);
}
</style>
