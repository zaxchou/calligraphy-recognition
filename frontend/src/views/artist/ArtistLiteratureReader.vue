<template>
  <div class="alr-page">
    <!-- 顶部栏 -->
    <div class="alr-topbar">
      <div class="alr-topbar-left">
        <el-button text size="small" @click="goBack">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <span class="alr-topbar-title">{{ book?.title }}</span>
        <span class="alr-topbar-author" v-if="artistName">{{ artistName }}</span>
      </div>
      <div class="alr-topbar-right">
        <el-button-group size="small">
          <el-button :type="mode === 'text' ? 'primary' : 'default'" @click="mode = 'text'">正文</el-button>
          <el-button :type="mode === 'pdf' ? 'primary' : 'default'" @click="loadPdf">原 PDF</el-button>
        </el-button-group>
        <el-button text size="small" @click="goBack">关闭</el-button>
      </div>
    </div>

    <!-- 内文搜索条 -->
    <div class="alr-searchbar" v-if="mode === 'text'">
      <el-input v-model="searchQuery" size="small" placeholder="搜索内文..." clearable
        @keyup.enter="doSearch" @clear="clearSearch" class="alr-search-input">
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <template v-if="searchResults.length">
        <span class="alr-search-count">{{ searchIdx + 1 }} / {{ searchResults.length }} 条匹配</span>
        <el-button text size="small" @click="prevMatch">‹ 上一个</el-button>
        <el-button text size="small" @click="nextMatch">下一个 ›</el-button>
      </template>
      <span v-else-if="searchQuery && searchResults.length === 0" class="alr-search-count">无匹配</span>
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
          @click="scrollToChunk(item.chunkIdx ?? idx)"
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
            <div v-if="chunk.chapter_title && (idx === 0 || chunk.chapter_title !== chunks[idx-1].chapter_title)" class="alr-chapter-title">{{ chunk.chapter_title }}</div>
            <div class="alr-chapter-pages" v-if="chunk.page_start">
              第 {{ chunk.page_start }}-{{ chunk.page_end || chunk.page_start }} 页
            </div>
            <div class="alr-chapter-body" v-html="renderMarkdown(chunk.content)"></div>
            <div v-if="chunk.page_start && imagesForPage(chunk.page_start).length" class="alr-images">
              <div v-for="img in imagesForPage(chunk.page_start)" :key="img.id" class="alr-image-item">
                <img :src="img.stored_url" :alt="img.caption || `第${img.page}页插图`" class="alr-image" loading="lazy" />
                <div v-if="img.caption" class="alr-image-caption">{{ img.caption }}</div>
              </div>
            </div>
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
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Search } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = computed(() => route.params.name)
const bookId = computed(() => route.params.bookId)

const book = ref(null)
const mainRef = ref(null)
const mode = ref('text')
const chunks = ref([])
const images = ref([])
const loadingChunks = ref(true)
const pdfLoading = ref(false)
const pdfUrl = ref('')
const activeChunkIdx = ref(0)
const chunkRefs = reactive({})
const loadingDetail = ref(true)

// 内文搜索
const searchQuery = ref('')
const searchResults = ref([])
const searchIdx = ref(-1)

const outline = ref([])

function renderMarkdown(text) {
  if (!text) return ''
  let h = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  if (searchQuery.value && searchResults.value.length) {
    const q = searchQuery.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const re = new RegExp(`(${q})`, 'gi')
    h = h.replace(re, '<mark class="alr-highlight">$1</mark>')
  }
  return h
}

function doSearch() {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) { searchResults.value = []; searchIdx.value = -1; return }
  const results = []
  chunks.value.forEach((c, idx) => {
    if (!c.content) return
    const lower = c.content.toLowerCase()
    let pos = 0
    while ((pos = lower.indexOf(q, pos)) !== -1) {
      results.push({ chunkIdx: idx, start: pos, end: pos + q.length })
      pos += 1
    }
  })
  searchResults.value = results
  searchIdx.value = results.length > 0 ? 0 : -1
  if (results.length > 0) scrollToChunk(results[0].chunkIdx)
}

function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  searchIdx.value = -1
}

function nextMatch() {
  if (!searchResults.value.length) return
  searchIdx.value = (searchIdx.value + 1) % searchResults.value.length
  scrollToChunk(searchResults.value[searchIdx.value].chunkIdx)
}

function prevMatch() {
  if (!searchResults.value.length) return
  searchIdx.value = (searchIdx.value - 1 + searchResults.value.length) % searchResults.value.length
  scrollToChunk(searchResults.value[searchIdx.value].chunkIdx)
}

function scrollToChunk(idx) {
  activeChunkIdx.value = idx
  const el = chunkRefs[idx]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function goBack() {
  router.push({ name: 'ArtistLiterature', params: { name: artistName.value } })
}

function loadPdf() {
  mode.value = 'pdf'
  if (!pdfUrl.value) {
    pdfLoading.value = true
    pdfUrl.value = `${API_BASE}/knowledge/artists/${book.value.artist_id}/literature/${bookId.value}/pdf`
  }
}

async function loadChunks() {
  loadingChunks.value = true
  try {
    const res = await fetch(`${API_BASE}/knowledge/artists/${book.value.artist_id}/literature/${bookId.value}/chunks`)
    if (res.ok) {
      const data = await res.json()
      chunks.value = data.chunks || []
      if (outline.value.length === 0 && chunks.value.length > 0) {
        const seen = new Set()
        const deduped = []
        chunks.value.forEach(c => {
          const title = c.chapter_title || `第 ${c.chunk_index + 1} 节`
          if (!seen.has(title)) {
            seen.add(title)
            deduped.push({ title, chunkIdx: c.chunk_index })
          }
        })
        outline.value = deduped
      }
    }
  } catch (e) { console.error(e) }
  finally { loadingChunks.value = false }
}

async function loadImages() {
  try {
    const res = await fetch(`${API_BASE}/knowledge/artists/${book.value.artist_id}/literature/${bookId.value}/images`)
    if (res.ok) {
      const data = await res.json()
      images.value = data.images || []
    }
  } catch {}
}

function imagesForPage(page) {
  return images.value.filter(img => img.page === page)
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

async function fetchBook() {
  loadingDetail.value = true
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(artistName.value)}`)
    if (!res.ok) return
    const data = await res.json()
    const aid = data.artist?.id
    if (!aid) return

    const detRes = await fetch(`${API_BASE}/knowledge/artists/${aid}/literature/${bookId.value}`)
    if (detRes.ok) {
      const det = await detRes.json()
      book.value = { ...det, artist_id: aid }
      if (det.outline && det.outline.length > 0) {
        outline.value = typeof det.outline === 'string' ? JSON.parse(det.outline) : det.outline
      }
    }
  } catch (e) { console.error(e) }
  finally { loadingDetail.value = false }
}

function loadAll() {
  chunks.value = []
  images.value = []
  outline.value = []
  pdfUrl.value = ''
  mode.value = 'text'
  searchQuery.value = ''
  searchResults.value = []
  searchIdx.value = -1
  activeChunkIdx.value = 0
  fetchBook().then(() => {
    if (book.value) {
      loadChunks()
      loadImages()
    }
  })
}

watch(() => route.params.bookId, loadAll)

onMounted(() => {
  mainRef.value?.addEventListener('scroll', onScroll, { passive: true })
  loadAll()
})

onBeforeUnmount(() => {
  mainRef.value?.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.alr-page {
  background: #faf8f5;
  min-height: calc(100vh - 200px);
  display: flex; flex-direction: column;
}

/* 内文搜索条 */
.alr-searchbar {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 20px; background: #fff; border-bottom: 1px solid #e8e3da;
  flex-shrink: 0;
}
.alr-search-input { width: 260px; }
.alr-search-count { font-size: 13px; color: #8a8578; white-space: nowrap; }
:deep(.alr-highlight) { background: #fff3cd; color: #2c2416; padding: 1px 2px; border-radius: 2px; }

.alr-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: #fff; border-bottom: 1px solid #e8e3da;
  flex-shrink: 0; z-index: 1;
}
.alr-topbar-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.alr-topbar-title { font-size: 15px; font-weight: 600; color: #2c2416; font-family: 'Noto Serif SC', serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alr-topbar-author { font-size: 13px; color: #8a8578; white-space: nowrap; }
.alr-topbar-right { flex-shrink: 0; display: flex; align-items: center; gap: 10px; }

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
.alr-images { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; padding-top: 12px; border-top: 1px solid #edeae1; }
.alr-image-item { flex: 0 0 auto; max-width: 280px; }
.alr-image { max-width: 100%; max-height: 300px; border-radius: 6px; border: 1px solid #e8e3da; cursor: pointer; transition: transform 0.2s; }
.alr-image:hover { transform: scale(1.02); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
.alr-image-caption { font-size: 12px; color: #8a8578; margin-top: 4px; text-align: center; }

/* PDF 模式 */
.alr-pdf-main { display: flex; flex-direction: column; }
.alr-pdf-frame { flex: 1; width: 100%; border: none; min-height: 0; }

@media (max-width: 768px) {
  .alr-sidebar { display: none; }
  .alr-content { padding: 20px 16px 60px; }
}
</style>
