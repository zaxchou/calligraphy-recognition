<template>
  <el-dialog
    v-model="localVisible"
    :title="title"
    width="90%"
    :close-on-click-modal="true"
    class="image-preview-dialog"
    destroy-on-close
  >
    <div class="image-preview-container">
      <div class="image-preview-toolbar">
        <el-button
          type="primary"
          size="small"
          @click="zoomIn"
          :disabled="scale >= 10"
        >
          放大
        </el-button>
        <el-button
          type="primary"
          size="small"
          @click="zoomOut"
          :disabled="scale <= 0.5"
        >
          缩小
        </el-button>
        <el-button
          type="default"
          size="small"
          @click="resetZoom"
        >
          重置
        </el-button>
        <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
      </div>
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
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  imageUrl: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: '原图查看'
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
  gap: 12px;
}

.image-preview-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.zoom-level {
  margin-left: 12px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.image-preview-wrapper {
  width: 100%;
  height: 600px;
  overflow: hidden;
  background: #f5f5f5;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-image-zoom {
  max-width: 100%;
  max-height: 100%;
  transition: transform 0.1s ease-out;
  user-select: none;
}
</style>
