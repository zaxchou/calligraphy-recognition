<template>
  <el-dialog
    v-model="localVisible"
    :show-close="false"
    width="95vw"
    top="2vh"
    :close-on-click-modal="true"
    class="dzi-preview-dialog"
    destroy-on-close
  >
    <div class="dzi-container">
      <div ref="viewerRef" class="dzi-viewer" />
      <div class="dzi-toolbar">
        <el-button size="small" circle @click="zoomIn" title="放大">
          <el-icon><ZoomIn /></el-icon>
        </el-button>
        <el-button size="small" circle @click="zoomOut" title="缩小">
          <el-icon><ZoomOut /></el-icon>
        </el-button>
        <el-button size="small" circle @click="resetZoom" title="重置">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button size="small" circle @click="toggleFullscreen" title="全屏">
          <el-icon><FullScreen /></el-icon>
        </el-button>
        <el-button size="small" circle @click="toggleRotate" title="旋转">
          <el-icon><RefreshRight /></el-icon>
        </el-button>
        <el-button size="small" circle @click="closeDialog" title="关闭">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import OpenSeadragon from 'openseadragon'
import { ZoomIn, ZoomOut, Refresh, FullScreen, RefreshRight, Close } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  imageUrl: { type: String, default: '' },
  dziUrl: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const localVisible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const viewerRef = ref(null)
let viewer = null
let rotation = 0

function initViewer() {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
  nextTick(() => {
    if (!viewerRef.value) return
    const tileSources = props.dziUrl ? props.dziUrl : props.imageUrl
    viewer = OpenSeadragon({
      element: viewerRef.value,
      tileSources: tileSources,
      prefixUrl: '/openseadragon-images/',
      showNavigator: true,
      navigatorPosition: 'BOTTOM_RIGHT',
      navigatorSizeRatio: 0.15,
      showZoomControl: false,
      showHomeControl: false,
      showFullPageControl: false,
      showSequenceControl: false,
      gestureSettingsTouch: {
        pinch: true,
        flick: true,
      },
      minZoomImageRatio: 0.5,
      maxZoomPixelRatio: 10,
      visibilityRatio: 0.1,
      constrainDuringPan: true,
      defaultZoomLevel: 0,
      animationTime: 0.3,
    })
  })
}

watch(localVisible, (v) => {
  if (v) {
    nextTick(() => initViewer())
  } else {
    if (viewer) {
      viewer.destroy()
      viewer = null
    }
  }
})

function zoomIn() {
  viewer?.viewport?.zoomBy(1.5)
}
function zoomOut() {
  viewer?.viewport?.zoomBy(0.667)
}
function resetZoom() {
  if (viewer) {
    viewer.viewport.goHome(true)
    rotation = 0
    viewer.viewport.setRotation(0)
  }
}
function toggleFullscreen() {
  if (viewer) {
    if (viewer.isFullPage()) {
      viewer.setFullPage(false)
    } else {
      viewer.setFullPage(true)
    }
  }
}
function toggleRotate() {
  rotation = (rotation + 90) % 360
  viewer?.viewport?.setRotation(rotation)
}
function closeDialog() {
  localVisible.value = false
}

onBeforeUnmount(() => {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
})
</script>

<style scoped>
.dzi-preview-dialog {
  --el-dialog-padding-primary: 0;
}
.dzi-container {
  position: relative;
  width: 100%;
  height: 88vh;
  background: #1a1a1a;
  overflow: hidden;
}
.dzi-viewer {
  width: 100%;
  height: 100%;
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
.dzi-toolbar .el-button {
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #fff;
}
.dzi-toolbar .el-button:hover {
  background: rgba(0, 0, 0, 0.8);
  border-color: rgba(255, 255, 255, 0.4);
}
</style>
