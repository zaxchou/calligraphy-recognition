<template>
  <Teleport to="body">
    <div v-if="visible" class="sl-overlay" @click.self="close">
      <button class="sl-close" @click="close" title="关闭">✕</button>
      <div class="sl-body">
        <button v-if="images.length > 1" class="sl-arrow sl-left" @click.stop="prev" :disabled="index === 0">
          <span>‹</span>
        </button>

        <div class="sl-main">
          <img :src="currentImage" :alt="seal.name" class="sl-image" />
          <div v-if="currentDesc" class="sl-desc">{{ currentDesc }}</div>
          <div class="sl-nav-dots" v-if="images.length > 1">
            <span
              v-for="(img, i) in images"
              :key="i"
              class="sl-dot"
              :class="{ active: i === index }"
              @click="index = i"
            />
          </div>
        </div>

        <button v-if="images.length > 1" class="sl-arrow sl-right" @click.stop="next" :disabled="index >= images.length - 1">
          <span>›</span>
        </button>
      </div>

      <div class="sl-footer">
        <span class="sl-footer-name">{{ seal.name }}</span>
        <span v-if="seal.seal_type" class="sl-footer-sep">·</span>
        <span v-if="seal.seal_type" class="sl-footer-type">{{ seal.seal_type }}</span>
        <span v-if="seal.source" class="sl-footer-source">{{ seal.source }}</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  seal: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['close'])

const index = ref(0)
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const images = computed(() => {
  return (props.seal.images || []).map(img => (
    typeof img === 'string' ? { path: img, description: '' } : img
  ))
})

const currentImage = computed(() => {
  const img = images.value[index.value]
  if (!img) return ''
  const path = img.path || img
  if (!path || typeof path !== 'string') return ''
  if (path.startsWith('http')) return path
  return `${API_BASE.replace('/api/v1', '')}${path}`
})

const currentDesc = computed(() => {
  const img = images.value[index.value]
  return img ? (img.description || '') : ''
})

function prev() {
  if (index.value > 0) index.value--
}

function next() {
  if (index.value < images.value.length - 1) index.value++
}

function close() {
  emit('close')
}

function onKeydown(e) {
  if (!props.visible) return
  if (e.key === 'ArrowLeft') prev()
  else if (e.key === 'ArrowRight') next()
  else if (e.key === 'Escape') close()
}

watch(() => props.visible, (v) => {
  if (v) index.value = 0
})

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.sl-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(28, 24, 14, 0.92);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.sl-close {
  position: absolute;
  top: 16px;
  right: 20px;
  background: none;
  border: none;
  color: #fff;
  font-size: 28px;
  cursor: pointer;
  opacity: 0.7;
  transition: opacity 0.2s;
  line-height: 1;
  padding: 8px;
}
.sl-close:hover { opacity: 1; }

.sl-body {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  max-width: 96vw;
  max-height: 78vh;
}

.sl-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 80vw;
  max-height: 78vh;
}

.sl-image {
  max-width: 80vw;
  max-height: 68vh;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 4px 32px rgba(0,0,0,0.3);
  user-select: none;
  -webkit-user-drag: none;
}

.sl-desc {
  color: #d4cfc0;
  font-size: 15px;
  margin-top: 16px;
  text-align: center;
  font-family: 'Noto Serif SC', serif;
  letter-spacing: 1px;
}

.sl-nav-dots {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.sl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.35);
  cursor: pointer;
  transition: background 0.2s;
}
.sl-dot.active { background: #fff; }

.sl-arrow {
  background: none;
  border: none;
  color: #fff;
  font-size: 48px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s;
  padding: 8px;
  line-height: 1;
}
.sl-arrow:hover:not(:disabled) { opacity: 1; }
.sl-arrow:disabled { opacity: 0.15; cursor: default; }

.sl-footer {
  position: absolute;
  bottom: 24px;
  left: 0;
  right: 0;
  text-align: center;
  color: #a09880;
  font-size: 13px;
}

.sl-footer-name {
  font-weight: 600;
  color: #d4cfc0;
}

.sl-footer-sep {
  margin: 0 8px;
  color: #666;
}

.sl-footer-type {
  color: #a09880;
}

.sl-footer-source {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #8a8068;
  max-width: 80vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-left: auto;
  margin-right: auto;
}
</style>
