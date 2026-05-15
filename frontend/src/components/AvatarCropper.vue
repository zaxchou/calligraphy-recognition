<template>
  <el-dialog
    v-model="visible"
    title="裁剪头像"
    width="420px"
    align-center
    :close-on-click-modal="false"
    @closed="cleanup"
  >
    <div class="cropper-body">
      <div class="crop-frame" ref="frameRef" @mousedown="onMouseDown" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp">
        <img
          v-if="src"
          :src="src"
          ref="imgRef"
          class="crop-img"
          :style="imgStyle"
          @load="onImgLoad"
        />
        <div class="crop-circle" :style="circleStyle" />
      </div>
      <div class="crop-controls">
        <span class="crop-hint">拖拽图片调整位置</span>
        <el-slider
          v-model="scale"
          :min="0.5"
          :max="2"
          :step="0.01"
          :format-tooltip="(v) => Math.round(v * 100) + '%'"
        />
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="cropping" @click="doCrop">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['cropped'])
const visible = ref(false)
const src = ref('')
const cropping = ref(false)

const imgRef = ref(null)
const frameRef = ref(null)

const offsetX = ref(0)
const offsetY = ref(0)
const scale = ref(1)
const naturalW = ref(0)
const naturalH = ref(0)
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const origOffset = ref({ x: 0, y: 0 })

const CIRCLE_SIZE = 220

const circleStyle = computed(() => ({
  width: CIRCLE_SIZE + 'px',
  height: CIRCLE_SIZE + 'px',
}))

const imgStyle = computed(() => ({
  width: naturalW.value * scale.value + 'px',
  height: naturalH.value * scale.value + 'px',
  left: offsetX.value + 'px',
  top: offsetY.value + 'px',
}))

function open(file) {
  if (src.value) URL.revokeObjectURL(src.value)
  src.value = URL.createObjectURL(file)
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
  naturalW.value = 0
  naturalH.value = 0
  visible.value = true
}

function onImgLoad() {
  nextTick(() => {
    const frame = frameRef.value
    const img = imgRef.value
    if (!frame || !img) return
    naturalW.value = img.naturalWidth
    naturalH.value = img.naturalHeight
    const fw = frame.clientWidth
    const fh = frame.clientHeight
    const s = Math.max(CIRCLE_SIZE / naturalW.value, CIRCLE_SIZE / naturalH.value, 0.6)
    scale.value = Math.round(s * 100) / 100
    offsetX.value = (fw - naturalW.value * s) / 2
    offsetY.value = (fh - naturalH.value * s) / 2
  })
}

// ── 拖拽 ──
function onMouseDown(e) {
  if (e.target === imgRef.value) {
    dragging.value = true
    dragStart.value = { x: e.clientX, y: e.clientY }
    origOffset.value = { x: offsetX.value, y: offsetY.value }
    e.preventDefault()
  }
}
function onMouseMove(e) {
  if (!dragging.value) return
  offsetX.value = origOffset.value.x + (e.clientX - dragStart.value.x)
  offsetY.value = origOffset.value.y + (e.clientY - dragStart.value.y)
}
function onMouseUp() { dragging.value = false }

// ── 裁剪 ──
function doCrop() {
  const frame = frameRef.value
  if (!imgRef.value || !frame) return

  cropping.value = true
  const canvas = document.createElement('canvas')
  const size = CIRCLE_SIZE * 2 // 2x retina
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')

  // 圆形裁剪
  ctx.beginPath()
  ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2)
  ctx.clip()

  const fw = frame.clientWidth
  const fh = frame.clientHeight
  const s = scale.value

  // 圆在 frame 中居中 → 圆心 (fw/2, fh/2)
  // 图片在 frame 中的位置: (offsetX, offsetY)，尺寸: (naturalW*s, naturalH*s)
  // frame 坐标 → 源图坐标: srcCoord = (frameCoord - offset) / s
  const srcCenterX = (fw / 2 - offsetX.value) / s
  const srcCenterY = (fh / 2 - offsetY.value) / s
  const srcCropSize = CIRCLE_SIZE / s

  ctx.drawImage(
    imgRef.value,
    srcCenterX - srcCropSize / 2, srcCenterY - srcCropSize / 2, srcCropSize, srcCropSize,
    0, 0, size, size,
  )

  canvas.toBlob((blob) => {
    cropping.value = false
    if (blob) {
      emit('cropped', blob)
      visible.value = false
    } else {
      ElMessage.error('裁剪失败')
    }
  }, 'image/jpeg', 0.85)
}

function cleanup() {
  if (src.value) { URL.revokeObjectURL(src.value); src.value = '' }
}

defineExpose({ open })
</script>

<style scoped>
.cropper-body {
  display: flex; flex-direction: column; align-items: center;
}
.crop-frame {
  width: 100%; height: 320px;
  background: #1a1a1a;
  position: relative; overflow: hidden;
  cursor: grab; user-select: none;
  border-radius: 10px;
}
.crop-frame:active { cursor: grabbing; }
.crop-img {
  position: absolute;
  width: auto; height: auto; max-width: none;
}
.crop-circle {
  position: absolute; border-radius: 50%;
  top: 50%; left: 50%; transform: translate(-50%, -50%);
  box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);
  border: 2px solid rgba(255,255,255,0.8);
  pointer-events: none;
}
.crop-controls {
  width: 100%; padding: 16px 0 0;
}
.crop-hint {
  font-size: 12px; color: #8c7a5c; display: block; margin-bottom: 8px;
}
</style>
