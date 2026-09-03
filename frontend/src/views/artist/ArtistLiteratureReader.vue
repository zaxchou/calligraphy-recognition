<template>
  <div class="alr-page">
    <!-- 合并顶部栏：标题 + 搜索，fixed -->
    <div class="alr-topbar">
      <div class="alr-toprow">
        <div class="alr-toprow-left">
          <el-button text size="small" @click="goBack">
            <el-icon><ArrowLeft /></el-icon> {{ $t('common.back') }}
          </el-button>
          <span class="alr-topbar-title">{{ book?.title }}</span>
          <span class="alr-topbar-meta" v-if="book">
            <template v-if="book.author">{{ book.author }}</template>
            <template v-if="book.source_type"> · {{ book.source_type }}</template>
            <template v-if="book.journal"> · {{ book.journal }}</template>
            <template v-if="book.publish_year"> · {{ book.publish_year }}</template>
          </span>
        </div>
        <div class="alr-toprow-right">
          <el-button text size="small" @click="toggleSearch" :title="showSearch ? $t('artist.artistliteraturereader.a1') : $t('common.search')">
            <el-icon><Search /></el-icon>
          </el-button>
          <el-button text size="small" @click="sidebarCollapsed = !sidebarCollapsed" :title="sidebarCollapsed ? $t('artist.artistliteraturereader.a2') : $t('artist.artistliteraturereader.a3')">
            <el-icon><Fold /></el-icon>
          </el-button>
          <el-button text size="small" @click="downloadPdf">
            <el-icon><Download /></el-icon> PDF
          </el-button>
        </div>
      </div>
      <div class="alr-searchrow" v-if="showSearch">
        <el-input v-model="searchQuery" size="small" :placeholder="$t('c-literaturereader.a1')" clearable
          @keyup.enter="doSearch" @clear="clearSearch" class="alr-search-input">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <template v-if="searchResults.length">
          <span class="alr-search-count">{{ searchIdx + 1 }} / {{ searchResults.length }} 条匹配</span>
          <el-button text size="small" @click="prevMatch">{{ $t('c-literaturereader.t3') }}</el-button>
          <el-button text size="small" @click="nextMatch">{{ $t('c-literaturereader.t4') }}</el-button>
        </template>
        <span v-else-if="searchQuery && searchResults.length === 0" class="alr-search-count">{{ $t('c-literaturereader.t5') }}</span>
      </div>
    </div>

    <div class="alr-body">
      <!-- 左侧目录 -->
      <aside class="alr-sidebar" :class="{ collapsed: sidebarCollapsed }" v-if="outline.length > 0">
        <div class="alr-sidebar-content" v-show="!sidebarCollapsed">
          <div class="alr-outline-title">{{ $t('c-literaturereader.t6') }}</div>
          <div
            v-for="(item, idx) in outline"
            :key="idx"
            class="alr-outline-item"
            :class="{ active: activeChunkIdx === idx }"
            @click="scrollToChunk(item.chunkIdx ?? idx)"
          >
            {{ item.title || item.chapter_title || `第 ${idx + 1} 节` }}
          </div>
        </div>
      </aside>

      <!-- 正文区 -->
      <main class="alr-main" ref="mainRef">
        <div v-if="loadingChunks" class="alr-loading">{{ $t('common.loading') }}</div>
        <div v-else-if="chunks.length === 0" class="alr-empty">{{ $t('c-literaturereader.t7') }}</div>
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
            <div class="alr-chapter-body" v-html="$sanitize(renderMarkdown(chunk.content))"></div>
            <div v-if="imagesByChunkId[chunk.id] && imagesByChunkId[chunk.id].length" class="alr-images">
              <div v-for="img in imagesByChunkId[chunk.id]" :key="img.id" class="alr-image-item">
                <img :src="img.stored_url" :alt="img.caption || `第${img.page}页插图`" class="alr-image" loading="lazy" />
                <div v-if="img.caption" class="alr-image-caption">{{ img.caption }}</div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Search, Fold, Download } from '@element-plus/icons-vue'
import api from '../../api'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = computed(() => route.params.name)
const bookId = computed(() => route.params.bookId)

const book = ref(null)
const mainRef = ref(null)
const chunks = ref([])
const images = ref([])
const loadingChunks = ref(true)
const activeChunkIdx = ref(0)
const chunkRefs = reactive({})
const loadingDetail = ref(true)

// 侧边目录折叠
const sidebarCollapsed = ref(false)
const showSearch = ref(false)

function toggleSearch() {
  showSearch.value = !showSearch.value
  if (!showSearch.value) clearSearch()
}

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

function downloadPdf() {
  window.open(`${API_BASE}/knowledge/artists/${book.value.artist_id}/literature/${bookId.value}/pdf`, '_blank')
}

async function loadChunks() {
  loadingChunks.value = true
  try {
    const data = await api.get(`/knowledge/artists/${book.value.artist_id}/literature/${bookId.value}/chunks`)
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
  } catch (e) { console.error(e) }
  finally { loadingChunks.value = false }
}

async function loadImages() {
  try {
    const data = await api.get(`/knowledge/artists/${book.value.artist_id}/literature/${bookId.value}/images`)
    images.value = data.images || []
  } catch {}
}

function imagesForPage(page) {
  return images.value.filter(img => img.page === page)
}

// 全局去重：每张图只分配给第一个覆盖其页码的 chunk
const imagesByChunkId = computed(() => {
  const map = {}
  if (!chunks.value.length || !images.value.length) return map
  const assigned = new Set()
  for (const chunk of chunks.value) {
    if (!chunk.page_start) continue
    const pageEnd = chunk.page_end || chunk.page_start
    const matched = []
    for (const img of images.value) {
      if (assigned.has(img.id)) continue
      if (img.page >= chunk.page_start && img.page <= pageEnd) {
        matched.push(img)
        assigned.add(img.id)
      }
    }
    if (matched.length) map[chunk.id] = matched
  }
  return map
})

function onScroll() {
  if (!mainRef.value) return
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
    const data = await api.get(`/artists/by-name/${encodeURIComponent(artistName.value)}`)
    const aid = data.artist?.id
    if (!aid) return

    const det = await api.get(`/knowledge/artists/${aid}/literature/${bookId.value}`)
    book.value = { ...det, artist_id: aid }
    if (det.outline && det.outline.length > 0) {
      outline.value = typeof det.outline === 'string' ? JSON.parse(det.outline) : det.outline
    }
  } catch (e) { console.error(e) }
  finally { loadingDetail.value = false }
}

function loadAll() {
  chunks.value = []
  images.value = []
  outline.value = []
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

/* 合并顶部栏：fixed */
.alr-topbar {
  position: sticky; top: 0; z-index: 100;
  background: #fff;
  border-bottom: 1px solid #e8e3da;
  flex-shrink: 0;
}
.alr-toprow {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px;
}
.alr-toprow-left { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; }
.alr-topbar-title { font-size: 15px; font-weight: 600; color: #2c2416; font-family: 'Noto Serif SC', serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alr-topbar-meta { font-size: 12px; color: #8a8578; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.alr-toprow-right { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }

/* 搜索行：居右 */
.alr-searchrow {
  display: flex; align-items: center; gap: 12px;
  padding: 0 16px 8px;
  justify-content: flex-end;
}
.alr-search-input { width: 260px; }
.alr-search-count { font-size: 13px; color: #8a8578; white-space: nowrap; }
:deep(.alr-highlight) { background: #fff3cd; color: #2c2416; padding: 1px 2px; border-radius: 2px; }

.alr-body { display: flex; flex: 1; min-height: 0; }

/* 侧边目录 - 折叠时右侧留32px给toggle按钮 */
.alr-sidebar {
  width: 220px; flex-shrink: 0; overflow-y: auto;
  border-right: 1px solid #e8e3da; background: #f6f4ef;
  transition: width 0.2s ease;
}
.alr-sidebar.collapsed { width: 0; overflow: hidden; border-right: none; }
.alr-sidebar-content { padding: 16px 0; min-width: 220px; }
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

@media (max-width: 768px) {
  .alr-sidebar { display: none; }
  .alr-content { padding: 20px 16px 60px; }
}
</style>
