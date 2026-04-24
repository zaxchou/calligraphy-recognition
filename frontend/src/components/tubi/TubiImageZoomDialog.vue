<template>
  <el-dialog
    v-model="localVisible"
    :show-close="false"
    width="95vw"
    :close-on-click-modal="true"
    class="image-preview-dialog"
    destroy-on-close
    :style="{ '--el-dialog-padding-primary': '0' }"
  >
    <div class="image-preview-container">
      <div
        class="image-preview-wrapper"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseLeave"
      >
        <img
          :src="imageUrl"
          alt="原图预览"
          class="preview-image-zoom"
          :style="{
            transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`,
            cursor: scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default'
          }"
          @wheel.prevent="handleWheel"
          draggable="false"
        />
        <!-- 工具栏覆盖在图片上 -->
        <div class="image-overlay-toolbar">
          <el-button
            type="primary"
            size="small"
            circle
            @click="zoomIn"
            :disabled="scale >= 10"
          >
            <el-icon><ZoomIn /></el-icon>
          </el-button>
          <el-button
            type="primary"
            size="small"
            circle
            @click="zoomOut"
            :disabled="scale <= 0.5"
          >
            <el-icon><ZoomOut /></el-icon>
          </el-button>
          <el-button
            type="default"
            size="small"
            circle
            @click="resetZoom"
          >
            <el-icon><RefreshRight /></el-icon>
          </el-button>
          <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
          <el-button
            type="default"
            size="small"
            circle
            class="close-btn"
            @click="localVisible = false"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ZoomIn, ZoomOut, RefreshRight, Close } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  imageUrl: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const localVisible = ref(props.modelValue)
const scale = ref(1)
const position = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })

watch(() => props.modelValue, (val) => {
  localVisible.value = val
  if (val) {
    resetZoom()
  }
})

watch(localVisible, (val) => {
  emit('update:modelValue', val)
})

function zoomIn() {
  if (scale.value < 10) {
    scale.value += 0.25
  }
}

function zoomOut() {
  if (scale.value > 0.5) {
    scale.value -= 0.25
  }
}

function resetZoom() {
  scale.value = 1
  position.value = { x: 0, y: 0 }
}

function handleWheel(e) {
  if (e.deltaY < 0) {
    zoomIn()
  } else {
    zoomOut()
  }
}

function handleMouseDown(e) {
  if (scale.value <= 1) return
  isDragging.value = true
  dragStart.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
}

function handleMouseMove(e) {
  if (!isDragging.value) return
  e.preventDefault()
  position.value = {
    x: e.clientX - dragStart.value.x,
    y: e.clientY - dragStart.value.y
  }
}

function handleMouseUp() {
  isDragging.value = false
}

function handleMouseLeave() {
  isDragging.value = false
}
</script>

<style scoped>
.image-preview-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 90vh;
}

.image-preview-wrapper {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.preview-image-zoom {
  max-width: 100%;
  max-height: 100%;
  transition: transform 0.1s ease-out;
  user-select: none;
}

.image-overlay-toolbar {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 20px;
  backdrop-filter: blur(4px);
}

.image-overlay-toolbar .el-button {
  --el-button-bg-color: rgba(255, 255, 255, 0.2);
  --el-button-border-color: rgba(255, 255, 255, 0.3);
  --el-button-text-color: #fff;
  --el-button-hover-bg-color: rgba(255, 255, 255, 0.3);
  --el-button-hover-border-color: rgba(255, 255, 255, 0.4);
  --el-button-hover-text-color: #fff;
}

.image-overlay-toolbar .close-btn {
  margin-left: 8px;
}

.zoom-level {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
  min-width: 40px;
  text-align: center;
}
</style>
