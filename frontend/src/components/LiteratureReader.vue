<template>
  <div class="alr-overlay" @keydown.esc="$emit('close')" tabindex="0" ref="overlayRef">
    <!-- 顶部栏 -->
    <div class="alr-topbar">
      <div class="alr-topbar-left">
        <el-button text @click="$emit('close')" size="small">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <span class="alr-topbar-title">{{ book.title }}</span>
        <span class="alr-topbar-author" v-if="artistName">{{ artistName }}</span>
      </div>
      <div class="alr-topbar-right">
        <el-button-group size="small">
          <el-button :type="mode === 'text' ? 'primary' : 'default'" @click="mode = 'text'">正文</el-button>
          <el-button :type="mode === 'pdf' ? 'primary' : 'default'" @click="loadPdf">原 PDF</el-button>
        </el-button-group>
      </div>
    </div>

    <div class="alr-body">
      <!-- 左侧目录 -->
      <aside class="alr-sidebar" v-if="mode === 'text' && outline.length > 0">
        <div class="alr-outline-title">目录</div>
        <div
          v-for="(item, idx) in outline"
          :key="idx"
          class="alr-outline-item"
          :class="{ active: activeChunkIdx === idx }"
          @click="scrollToChunk(idx)"
        >
          {{ item.title || item.chapter_title || `第 ${idx + 1} 节` }}
        </div>
      </aside>

      <!-- 正文区 -->
      <main class="alr-main" ref="mainRef" v-show="mode === 'text'">
        <div v-if="loadingChunks" class="alr-loading">加载中...</div>
        <div v-else-if="chunks.length === 0" class="alr-empty">暂无章节内容</div>
        <div v-else class="alr-content">
          <div
            v-for="(chunk, idx) in chunks"
            :key="chunk.id"
            :ref="el => { chunkRefs[idx] = el }"
            class="alr-chunk"
          >
            <div v-if="chunk.chapter_title" class="alr-chapter-title">{{ chunk.chapter_title }}</div>
            <div class="alr-chapter-pages" v-if="chunk.page_start">
              第 {{ chunk.page_start }}-{{ chunk.page_end || chunk.page_start }} 页
            </div>
            <div class="alr-chapter-body" v-html="renderMarkdown(chunk.content)"></div>
          </div>
        </div>
      </main>

      <!-- PDF iframe -->
      <main class="alr-main alr-pdf-main" v-show="mode === 'pdf'">
        <div v-if="pdfLoading" class="alr-loading">加载 PDF 中...</div>
        <iframe
          v-if="pdfUrl"
          :src="pdfUrl"
          class="alr-pdf-frame"
          referrerpolicy="no-referrer"
        ></iframe>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'

const props = defineProps({
  book: { type: Object, required: true },
  artistName: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const overlayRef = ref(null)
const mainRef = ref(null)
const mode = ref('text')
const chunks = ref([])
const loadingChunks = ref(true)
const pdfLoading = ref(false)
const pdfUrl = ref('')
const activeChunkIdx = ref(0)
const chunkRefs = reactive({})

const outline = ref([])
try {
  outline.value = typeof props.book.outline === 'string' ? JSON.parse(props.book.outline) : (props.book.outline || [])
} catch { outline.value = [] }

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

function scrollToChunk(idx) {
  activeChunkIdx.value = idx
  const el = chunkRefs[idx]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function loadPdf() {
  mode.value = 'pdf'
  if (!pdfUrl.value) {
    pdfLoading.value = true
    pdfUrl.value = `${API_BASE}/knowledge/artists/${props.book.artist_id}/literature/${props.book.id}/pdf`
  }
}

async function loadChunks() {
  loadingChunks.value = true
  try {
    const res = await fetch(`${API_BASE}/knowledge/artists/${props.book.artist_id}/literature/${props.book.id}/chunks`)
    if (res.ok) {
      const data = await res.json()
      chunks.value = data.chunks || []
      // 如果没有 outline 数据，用 chunk 的 chapter_title 构建目录
      if (outline.value.length === 0 && chunks.value.length > 0) {
        outline.value = chunks.value.map(c => ({ title: c.chapter_title || `第 ${c.chunk_index + 1} 节` }))
      }
    }
  } catch (e) { console.error(e) }
  finally { loadingChunks.value = false }
}

function onScroll() {
  if (!mainRef.value || mode.value !== 'text') return
  const scrollTop = mainRef.value.scrollTop
  let closest = 0
  for (let i = 0; i < chunks.value.length; i++) {
    const el = chunkRefs[i]
    if (el && el.offsetTop <= scrollTop + 120) closest = i
  }
  activeChunkIdx.value = closest
}

onMounted(async () => {
  overlayRef.value?.focus()
  mainRef.value?.addEventListener('scroll', onScroll, { passive: true })
  // 先获取详情（含 outline），再加载 chunks
  try {
    const detRes = await fetch(`${API_BASE}/knowledge/artists/${props.book.artist_id}/literature/${props.book.id}`)
    if (detRes.ok) {
      const det = await detRes.json()
      if (det.outline && det.outline.length > 0) {
        outline.value = typeof det.outline === 'string' ? JSON.parse(det.outline) : det.outline
      }
    }
  } catch {}
  loadChunks()
})

onBeforeUnmount(() => {
  mainRef.value?.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.alr-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  z-index: 2000; background: #faf8f5;
  display: flex; flex-direction: column;
  outline: none;
}

.alr-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: #fff; border-bottom: 1px solid #e8e3da;
  flex-shrink: 0; z-index: 1;
}
.alr-topbar-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.alr-topbar-title { font-size: 15px; font-weight: 600; color: #2c2416; font-family: 'Noto Serif SC', serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alr-topbar-author { font-size: 13px; color: #8a8578; white-space: nowrap; }
.alr-topbar-right { flex-shrink: 0; }

.alr-body { display: flex; flex: 1; min-height: 0; }

/* 侧边目录 */
.alr-sidebar {
  width: 220px; flex-shrink: 0; overflow-y: auto;
  border-right: 1px solid #e8e3da; background: #f6f4ef; padding: 16px 0;
}
.alr-outline-title { font-size: 13px; font-weight: 600; color: #8a8578; padding: 0 16px 12px; }
.alr-outline-item {
  padding: 8px 16px; font-size: 13px; color: #8c7a5c;
  cursor: pointer; transition: all 0.12s; border-left: 3px solid transparent;
}
.alr-outline-item:hover { background: #edeae1; color: #3a3222; }
.alr-outline-item.active { background: #fdf6f0; color: #c45a3c; border-left-color: #c45a3c; font-weight: 500; }

/* 正文区 */
.alr-main { flex: 1; overflow-y: auto; }
.alr-loading, .alr-empty { text-align: center; padding: 80px 0; color: #8a8578; font-size: 15px; }
.alr-content { max-width: 720px; margin: 0 auto; padding: 32px 24px 80px; }
.alr-chunk { margin-bottom: 40px; }
.alr-chapter-title { font-size: 18px; font-weight: 600; color: #2c2416; font-family: 'Noto Serif SC', serif; margin-bottom: 6px; }
.alr-chapter-pages { font-size: 12px; color: #b0a890; margin-bottom: 16px; }
.alr-chapter-body { font-size: 15px; line-height: 1.8; color: #3a3222; }

/* PDF 模式 */
.alr-pdf-main { display: flex; flex-direction: column; }
.alr-pdf-frame { flex: 1; width: 100%; border: none; min-height: 0; }

@media (max-width: 768px) {
  .alr-sidebar { display: none; }
  .alr-content { padding: 20px 16px 60px; }
}
</style>
