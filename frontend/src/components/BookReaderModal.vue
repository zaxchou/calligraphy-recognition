<template>
  <Teleport to="body">
    <div v-if="visible" class="reader-overlay" @click="closeModal">
      <div class="reader-container" @click.stop>
        <!-- 顶部工具栏 -->
        <div class="reader-toolbar">
          <div class="toolbar-left">
            <button class="toolbar-btn" @click="closeModal">
              <ArrowLeft class="icon" />
              <span>返回搜索结果</span>
            </button>
            <span class="toolbar-divider">|</span>
            <span class="book-title">{{ result.result_type === 'image' ? (cleanLatexSymbols(result.image?.artwork_title) || '配图详情') : result.book_title }}</span>
            <span class="chapter-tag">{{ result.result_type === 'image' ? (result.image?.era ? result.image.era + '·' + (result.image.artist || '') : (result.image?.artist || '配图')) : getChapterTitle(result) }}</span>
          </div>
          <div class="toolbar-right">
            <span class="page-indicator">
              {{ result.result_type === 'image' ? '图像结果' : `第 ${result.page_start}-${result.page_end} 页` }}
            </span>
            <span class="score-badge" :class="getScoreClass(result.score)">
              相关度 {{ formatScore(result.score) }}%
            </span>
            <button class="close-btn" @click="closeModal">
              <X class="icon" />
            </button>
          </div>
        </div>

        <!-- 主阅读区 - 单栏布局，图片内联显示 -->
        <div class="reader-content">
          <div class="reader-main">
            <!-- 图像结果模式 -->
            <template v-if="result.result_type === 'image'">
              <div class="image-detail-page">
                <div class="image-detail-header">
                  <span class="page-chapter">{{ result.image?.era ? result.image.era + '·' : '' }}{{ result.image?.artist || '未知作者' }}</span>
                  <span class="page-number">配图</span>
                </div>
                
                <div class="image-detail-body">
                  <div class="image-detail-main">
                    <img 
                      :src="getFullImageUrl(result.image?.url || result.associated_images?.[0]?.url)" 
                      :alt="cleanLatexSymbols(result.image?.artwork_title) || '配图'" 
                      class="image-detail-img"
                      @click="openImagePreviewDirect(getFullImageUrl(result.image?.url || result.associated_images?.[0]?.url))"
                    />
                  </div>
                  <div class="image-detail-info">
                    <h2 v-if="result.image?.artwork_title" class="artwork-title">《{{ cleanLatexSymbols(result.image.artwork_title) }}》</h2>
                    <div v-if="result.image?.artist" class="artwork-meta">
                      <span class="meta-label">作者</span>
                      <span class="meta-value">{{ result.image?.era ? result.image.era + '·' : '' }}{{ cleanLatexSymbols(result.image.artist) }}</span>
                    </div>
                    <div v-if="result.image?.chapter" class="artwork-meta">
                      <span class="meta-label">章节</span>
                      <span class="meta-value">{{ cleanLatexSymbols(result.image.chapter) }}</span>
                    </div>
                    <div v-if="result.image?.description" class="artwork-desc">
                      <p>{{ cleanLatexSymbols(result.image.description) }}</p>
                    </div>
                  </div>
                </div>
                
                <!-- 关联文本块 -->
                <div v-if="relatedChunks.length > 0" class="related-chunks-section">
                  <ImageRelatedChunks 
                    :chunks="relatedChunks"
                    :loading="loadingRelatedChunks"
                    @chunk-click="onRelatedChunkClick"
                  />
                </div>
              </div>
            </template>
            
            <!-- 文本结果模式 -->
            <template v-else>
            <div class="book-page">
              <!-- 页面头部 -->
              <div class="page-header">
                <span class="page-chapter">{{ getChapterTitle(result) }}</span>
                <span class="page-number">第 {{ result.page_start }} 页</span>
                <div class="header-actions">
                  <button class="view-pdf-btn" @click="openPdfSource">
                    <FileDown class="icon" />
                    <span>查看 PDF</span>
                  </button>
                </div>
              </div>

              <!-- 标签页切换 -->
              <div class="reader-tabs">
                <button 
                  class="tab-btn"
                  :class="{ active: activeTab === 'content' }"
                  @click="activeTab = 'content'"
                >
                  <FileText class="icon" />
                  <span>文本内容</span>
                </button>
                <button 
                  v-if="documentOutline.length > 0"
                  class="tab-btn"
                  :class="{ active: activeTab === 'outline' }"
                  @click="activeTab = 'outline'"
                >
                  <ListTree class="icon" />
                  <span>文档大纲</span>
                  <span class="tab-count">{{ documentOutline.length }}</span>
                </button>
                <button 
                  v-if="markdownContent"
                  class="tab-btn"
                  :class="{ active: activeTab === 'markdown' }"
                  @click="activeTab = 'markdown'"
                >
                  <FileCode class="icon" />
                  <span>Markdown</span>
                </button>
              </div>

              <!-- 标签页内容 -->
              <div class="tab-content">
                <!-- 文本内容标签页 -->
                <div v-show="activeTab === 'content'" class="tab-pane">
                  <div class="page-content" ref="pageContent">
                    <!-- 上文 -->
                    <div v-if="result.context_before" class="context-section before">
                      <p class="context-text">{{ cleanLatexSymbols(result.context_before) }}</p>
                      <div class="context-marker">⋯ 上文 ⋯</div>
                    </div>

                    <!-- 当前内容（高亮） -->
                    <div class="current-content">
                      <p class="content-text" v-html="highlightedContent"></p>
                    </div>

                    <!-- 关联图片 - 内联显示在文本下方 -->
                    <div v-if="result.associated_images?.length > 0" class="inline-images">
                      <div class="images-header">
                        <ImageIcon class="icon" />
                        <span>关联插图 ({{ result.associated_images.length }}张)</span>
                      </div>
                      <div class="images-grid">
                        <div 
                          v-for="(img, idx) in result.associated_images" 
                          :key="img.id || idx"
                          class="inline-image-item"
                          @click="openImagePreviewByIndex(idx)"
                        >
                          <img 
                            :src="getImageUrl(img)" 
                            :alt="img.caption || img.figure_id || '插图'"
                            class="inline-image"
                            @error="handleImageError"
                          />
                          <div v-if="img.caption || img.figure_id" class="inline-image-caption">
                            {{ img.caption || img.figure_id }}
                          </div>
                          <div class="image-overlay">
                            <span class="zoom-hint">点击放大</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- 下文 -->
                    <div v-if="result.context_after" class="context-section after">
                      <div class="context-marker">⋯ 下文 ⋯</div>
                      <p class="context-text">{{ cleanLatexSymbols(result.context_after) }}</p>
                    </div>
                  </div>
                </div>

                <!-- 文档大纲标签页 -->
                <div v-show="activeTab === 'outline'" class="tab-pane">
                  <DocumentOutline 
                    :outline="documentOutline"
                    :loading="loadingOutline"
                    @item-click="onOutlineItemClick"
                  />
                </div>

                <!-- Markdown 标签页 -->
                <div v-show="activeTab === 'markdown'" class="tab-pane">
                  <MarkdownViewer 
                    :markdown="markdownContent"
                    :loading="loadingMarkdown"
                  />
                </div>
              </div>

              <!-- 页面底部 -->
              <div class="page-footer">
                <span class="source-info">
                  <BookOpen class="source-icon" />
                  {{ result.book_title }}
                </span>
                <div class="page-nav">
                  <button 
                    class="nav-btn" 
                    :disabled="loading"
                    @click="loadPrevChunk"
                  >
                    <Loader2 v-if="loading" class="icon spin" />
                    <ChevronLeft v-else class="icon" />
                    上一页
                  </button>
                  <span class="nav-divider">|</span>
                  <button 
                    class="nav-btn" 
                    :disabled="loading"
                    @click="loadNextChunk"
                  >
                    下一页
                    <Loader2 v-if="loading" class="icon spin" />
                    <ChevronRight v-else class="icon" />
                  </button>
                </div>
              </div>
            </div>
            </template>
          </div>
        </div>

        <!-- 底部信息栏 -->
        <div class="reader-footer">
          <div class="footer-info">
            <span v-if="result.result_type !== 'image'" class="info-item">
              <Hash class="info-icon" />
              块ID: {{ result.chunk_id?.slice(0, 8) }}...
            </span>
            <span v-if="result.result_type !== 'image'" class="info-item">
              <Layers class="info-icon" />
              索引: {{ result.chunk_index }}
            </span>
            <span class="info-item" v-if="result.associated_images?.length || result.image?.url">
              <ImageIcon class="info-icon" />
              {{ result.result_type === 'image' ? '图像' : `关联图片: ${result.associated_images.length} 张` }}
            </span>
          </div>
          <div class="footer-actions">
            <button v-if="result.result_type !== 'image'" class="action-btn" @click="copyContent">
              <Copy class="icon" />
              复制文本
            </button>
            <button v-if="result.book_id && result.result_type !== 'image'" class="action-btn primary" @click="openPdfSource">
              <FileText class="icon" />
              查看PDF原文
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 图片预览 -->
    <div v-if="previewVisible" class="image-preview-overlay" @click="previewVisible = false">
      <img :src="previewImageUrl" class="preview-image" />
      <button class="preview-close" @click.stop="previewVisible = false">
        <X class="icon" />
      </button>
    </div>
    
    <!-- PDF 查看器 -->
    <div v-if="showPdfViewer" class="pdf-viewer-overlay" @click="closePdfViewer">
      <div class="pdf-viewer-container" @click.stop>
        <div class="pdf-viewer-header">
          <div class="pdf-viewer-title">
            <FileDown class="icon" />
            <span>PDF 原文查看</span>
            <span class="pdf-book-name">{{ result.book_title }}</span>
          </div>
          <button class="pdf-viewer-close" @click="closePdfViewer">
            <X class="icon" />
          </button>
        </div>
        <div class="pdf-viewer-body">
          <PdfViewer 
            v-if="pdfUrl"
            ref="pdfViewerRef"
            :pdf-url="pdfUrl"
            :initial-page="result.page_start || 1"
            :bboxes="pdfBboxes"
            :auto-scroll-to-bbox="true"
            @page-change="onPdfPageChange"
            @bbox-click="onPdfBboxClick"
            @pdf-loaded="onPdfLoaded"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { 
  X, ArrowLeft, ChevronLeft, ChevronRight, 
  ImageIcon, BookOpen, Hash, Layers, Copy, FileText, 
  Loader2, FileDown, ListTree, FileCode
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledgeStore'
import PdfViewer from './PdfViewer.vue'
import DocumentOutline from './DocumentOutline.vue'
import MarkdownViewer from './MarkdownViewer.vue'
import ImageRelatedChunks from './ImageRelatedChunks.vue'

const store = useKnowledgeStore()

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  result: {
    type: Object,
    default: () => ({})
  },
  searchQuery: {
    type: String,
    default: ''
  },
  allResults: {
    type: Array,
    default: () => []
  },
  currentIndex: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update:visible', 'navigate', 'navigate-chunk'])

// 状态
const currentImageIndex = ref(0)
const previewVisible = ref(false)
const previewImageUrl = ref('')
const pageContent = ref(null)
const loading = ref(false)
const totalChunks = ref(0)
const activeTab = ref('content')

// PDF 查看器状态
const showPdfViewer = ref(false)
const pdfUrl = ref('')
const pdfBboxes = ref([])
const pdfViewerRef = ref(null)

// 文档大纲状态
const documentOutline = ref([])
const loadingOutline = ref(false)

// Markdown 内容状态
const markdownContent = ref('')
const loadingMarkdown = ref(false)

// 关联文本块状态
const relatedChunks = ref([])
const loadingRelatedChunks = ref(false)

// 当前阅读的文本块（可独立于搜索结果翻页）
const readerResult = computed(() => ({
  ...props.result,
  content: props.result.content_full || props.result.content || ''
}))

// 计算属性
const currentImage = computed(() => {
  if (!props.result.associated_images?.length) return null
  return props.result.associated_images[currentImageIndex.value]
})

const highlightedContent = computed(() => {
  let content = readerResult.value.content
  // 先清理 LaTeX 符号
  content = cleanLatexSymbols(content)
  if (props.searchQuery) {
    const regex = new RegExp(`(${escapeRegExp(props.searchQuery)})`, 'gi')
    content = content.replace(regex, '<mark class="highlight">$1</mark>')
  }
  return content
})

// 基于搜索结果的翻页
const hasPrevResult = computed(() => props.currentIndex > 0)
const hasNextResult = computed(() => props.currentIndex < props.allResults.length - 1)

// 方法
function closeModal() {
  emit('update:visible', false)
}

function getImageUrl(img) {
  if (!img || !img.stored_url) return ''
  // 如果已经是完整 URL，直接返回
  if (img.stored_url.startsWith('http')) {
    return img.stored_url
  }
  // 将 /api/knowledge 替换为 /api/v1/knowledge
  const url = img.stored_url.replace('/api/knowledge', '/api/v1/knowledge')
  // 使用相对路径，让 Vite proxy 处理
  return url
}

// 获取图像结果的 URL（兼容 image.url 和 associated_images[].url）
function getFullImageUrl(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  // /static/ 开头的路径直接走 FastAPI 静态文件服务
  if (url.startsWith('/static/')) return url
  // /api/ 开头的路径已经是完整路径，不需要再加前缀
  if (url.startsWith('/api/')) return url
  return `/api/v1/knowledge/${url}`
}

// 直接用 URL 打开图片预览
function openImagePreviewDirect(url) {
  if (!url) return
  previewImageUrl.value = url
  previewVisible.value = true
}

// 获取智能章节标题
function getChapterTitle(result) {
  if (!result) return '正文'
  if (result.chapter_title && result.chapter_title.trim() && result.chapter_title.trim() !== '正文') {
    return result.chapter_title.trim()
  }
  // 尝试从内容推断章节
  const content = result.content || ''
  const chapterMatch = content.match(/第[一二三四五六七八九十百千万\d]+章[\s]*([^\n]{2,20})/)
  if (chapterMatch) {
    return chapterMatch[0].trim()
  }
  // 返回页码范围作为标识
  return `第${result.page_start || 1}页`
}

// 格式化匹配分数
function formatScore(score) {
  if (!score || score <= 0) return 0
  if (score < 0.1) {
    const normalized = Math.min(score / 0.05, 1)
    return Math.round(normalized * 100)
  }
  // 跨模态分数 (0.1-0.3) → 映射到合理百分比
  if (score < 0.3) {
    const normalized = Math.min((score - 0.05) / 0.25, 1)
    return Math.max(20, Math.round(normalized * 100))
  }
  if (score > 1) {
    return Math.min(Math.round(score), 100)
  }
  return Math.round(score * 100)
}

// 根据分数获取样式类
function getScoreClass(score) {
  const s = formatScore(score)
  if (s >= 80) return 'high'
  if (s >= 50) return 'medium'
  return 'low'
}

function openImagePreview() {
  if (!currentImage.value) return
  previewImageUrl.value = getImageUrl(currentImage.value)
  previewVisible.value = true
}

function openImagePreviewByIndex(index) {
  if (!props.result.associated_images?.length) return
  const img = props.result.associated_images[index]
  if (img) {
    previewImageUrl.value = getImageUrl(img)
    previewVisible.value = true
  }
}

function handleImageError(event) {
  event.target.style.display = 'none'
  // 显示占位符
  const parent = event.target.parentElement
  if (parent) {
    const placeholder = document.createElement('div')
    placeholder.className = 'no-image-fallback'
    placeholder.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>'
    parent.appendChild(placeholder)
  }
}

// 翻页：在搜索结果间切换
function loadPrevResult() {
  if (hasPrevResult.value) {
    emit('navigate', props.currentIndex - 1)
  }
}

function loadNextResult() {
  if (hasNextResult.value) {
    emit('navigate', props.currentIndex + 1)
  }
}

// 翻页：在书中翻页（同书同章节的文本块）
async function loadPrevChunk() {
  if (loading.value) return
  const bookId = props.result.book_id
  const chunkIdx = props.result.chunk_index
  if (!bookId || chunkIdx == null || chunkIdx <= 0) {
    // 如果没有前一个块，尝试跳转到上一个搜索结果
    loadPrevResult()
    return
  }
  loading.value = true
  try {
    const chunk = await store.fetchChunkDetail(bookId, chunkIdx - 1)
    if (chunk) {
      // 获取关联图片
      let images = []
      if (chunk.associated_images?.length) {
        const imgResponse = await store.fetchBookImages(bookId)
        images = (imgResponse || []).filter(img => 
          chunk.associated_images.includes(img.id)
        )
      }
      emit('navigate-chunk', {
        ...chunk,
        book_id: bookId,
        book_title: props.result.book_title,
        associated_images: images,
        score: props.result.score,
      })
    } else {
      loadPrevResult()
    }
  } catch (e) {
    console.error('加载上一页失败:', e)
  } finally {
    loading.value = false
  }
}

async function loadNextChunk() {
  if (loading.value) return
  const bookId = props.result.book_id
  const chunkIdx = props.result.chunk_index
  if (!bookId || chunkIdx == null) {
    loadNextResult()
    return
  }
  loading.value = true
  try {
    const chunk = await store.fetchChunkDetail(bookId, chunkIdx + 1)
    if (chunk) {
      let images = []
      if (chunk.associated_images?.length) {
        const imgResponse = await store.fetchBookImages(bookId)
        images = (imgResponse || []).filter(img => 
          chunk.associated_images.includes(img.id)
        )
      }
      emit('navigate-chunk', {
        ...chunk,
        book_id: bookId,
        book_title: props.result.book_title,
        associated_images: images,
        score: props.result.score,
      })
    } else {
      loadNextResult()
    }
  } catch (e) {
    console.error('加载下一页失败:', e)
  } finally {
    loading.value = false
  }
}

function copyContent() {
  const text = readerResult.value.content
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('文本已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function openPdfSource() {
  const bookId = props.result.book_id
  if (bookId) {
    // 设置 PDF URL
    pdfUrl.value = `/api/v1/knowledge/books/${bookId}/pdf`
    
    // 构建 bbox 数据
    const bboxes = []
    if (props.result.bbox) {
      bboxes.push({
        page: props.result.page_start || 1,
        x: props.result.bbox.x || 0,
        y: props.result.bbox.y || 0,
        width: props.result.bbox.width || 100,
        height: props.result.bbox.height || 50,
        label: '当前内容',
        active: true
      })
    }
    pdfBboxes.value = bboxes
    
    // 显示 PDF 查看器
    showPdfViewer.value = true
  }
}

function closePdfViewer() {
  showPdfViewer.value = false
  pdfUrl.value = ''
  pdfBboxes.value = []
}

// 加载文档大纲
async function loadDocumentOutline(bookId) {
  if (!bookId) return
  loadingOutline.value = true
  try {
    const response = await fetch(`/api/v1/knowledge/books/${bookId}/outline`)
    if (response.ok) {
      const data = await response.json()
      documentOutline.value = data.outline || []
    }
  } catch (e) {
    console.error('加载大纲失败:', e)
  } finally {
    loadingOutline.value = false
  }
}

// 加载 Markdown 内容
async function loadMarkdownContent(bookId) {
  if (!bookId) return
  loadingMarkdown.value = true
  try {
    const response = await fetch(`/api/v1/knowledge/books/${bookId}/markdown`)
    if (response.ok) {
      const data = await response.json()
      markdownContent.value = data.markdown || ''
    }
  } catch (e) {
    console.error('加载 Markdown 失败:', e)
  } finally {
    loadingMarkdown.value = false
  }
}

// 加载关联文本块
async function loadRelatedChunks(imageId) {
  if (!imageId) return
  loadingRelatedChunks.value = true
  try {
    const response = await fetch(`/api/v1/knowledge/images/${imageId}/related-chunks`)
    if (response.ok) {
      const data = await response.json()
      relatedChunks.value = data.chunks || []
    }
  } catch (e) {
    console.error('加载关联文本块失败:', e)
  } finally {
    loadingRelatedChunks.value = false
  }
}

// 待跳转的页面（用于 PDF 加载完成后自动跳转）
const pendingPageNavigation = ref(null)

// 大纲项点击 - 跳转到 PDF 对应页面
function onOutlineItemClick(item) {
  if (item.page) {
    const bookId = props.result.book_id
    if (!bookId) return
    
    // 如果 PDF 查看器未打开，先打开它
    if (!showPdfViewer.value) {
      pendingPageNavigation.value = item.page
      pdfUrl.value = `/api/v1/knowledge/books/${bookId}/pdf`
      pdfBboxes.value = []
      showPdfViewer.value = true
    } else {
      // PDF 查看器已打开，直接跳转
      if (pdfViewerRef.value) {
        pdfViewerRef.value.goToPage(item.page)
      }
    }
  }
}

// PDF 加载完成事件处理
function onPdfLoaded(info) {
  console.log('PDF 加载完成:', info)
  // 如果有待跳转的页面，现在跳转
  if (pendingPageNavigation.value && pdfViewerRef.value) {
    const targetPage = pendingPageNavigation.value
    pendingPageNavigation.value = null
    nextTick(() => {
      pdfViewerRef.value.goToPage(targetPage)
    })
  }
}

// 关联文本块点击 - 导航到该文本块
function onRelatedChunkClick(chunk) {
  if (chunk && chunk.chunk_id) {
    // 发送导航事件，让父组件处理搜索结果切换
    emit('navigate-chunk', chunk)
  }
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// PDF 查看器事件处理
function onPdfPageChange(page) {
  console.log('PDF 页面切换:', page)
}

function onPdfBboxClick(bbox) {
  console.log('点击 bbox:', bbox)
}

// 清理 LaTeX 数学符号，转换为 Unicode 字符
function cleanLatexSymbols(text) {
  if (!text) return text
  // 将 $\textcircled{N}$ 格式转换为 ①②③ 等 Unicode 带圈数字
  const circledMap = {
    '0': '⓪', '1': '①', '2': '②', '3': '③', '4': '④',
    '5': '⑤', '6': '⑥', '7': '⑦', '8': '⑧', '9': '⑨',
    '10': '⑩', '11': '⑪', '12': '⑫', '13': '⑬', '14': '⑭',
    '15': '⑮', '16': '⑯', '17': '⑰', '18': '⑱', '19': '⑲',
    '20': '⑳'
  }
  // 匹配 $\textcircled{N}$ 或 $\textcircled{NN}$
  return text.replace(/\$\\textcircled\{(\d+)\}\$/g, (match, num) => {
    return circledMap[num] || `(${num})`
  })
}

// 监听结果变化，重置图片索引，加载相关数据
watch(() => props.result, (newResult) => {
  currentImageIndex.value = 0
  nextTick(() => {
    if (pageContent.value) {
      pageContent.value.scrollTop = 0
    }
  })
  
  // 清空之前的数据
  documentOutline.value = []
  markdownContent.value = ''
  relatedChunks.value = []
  
  if (newResult) {
    const bookId = newResult.book_id
    
    // 文本结果：加载大纲和 Markdown
    if (newResult.result_type !== 'image' && bookId) {
      loadDocumentOutline(bookId)
      loadMarkdownContent(bookId)
    }
    
    // 图像结果：加载关联文本块
    if (newResult.result_type === 'image' && newResult.image?.id) {
      loadRelatedChunks(newResult.image.id)
    }
  }
}, { immediate: true })

// 键盘导航
watch(() => props.visible, (visible) => {
  if (visible) {
    document.addEventListener('keydown', handleKeydown)
  } else {
    document.removeEventListener('keydown', handleKeydown)
  }
})

function handleKeydown(e) {
  if (e.key === 'Escape') {
    closeModal()
  } else if (e.key === 'ArrowLeft') {
    loadPrevChunk()
  } else if (e.key === 'ArrowRight') {
    loadNextChunk()
  }
}
</script>

<style scoped>
/* 阅读器遮罩 */
.reader-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.reader-container {
  background: #f5f0e8;
  border-radius: 8px;
  width: 100%;
  max-width: 1400px;
  height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

/* 工具栏 */
.reader-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e4dc;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  color: #5a5a5a;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: #f8f6f1;
  color: #c45c48;
}

.toolbar-divider {
  color: #d4cfc5;
}

.book-title {
  font-size: 14px;
  font-weight: 600;
  color: #3d3d3d;
}

.chapter-tag {
  padding: 4px 10px;
  background: #c45c48;
  color: #fff;
  border-radius: 4px;
  font-size: 12px;
}

.page-indicator {
  font-size: 13px;
  color: #8b7355;
}

.score-badge {
  padding: 4px 10px;
  background: #dcfce7;
  color: #16a34a;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.score-badge.high {
  background: #dcfce7;
  color: #166534;
}

.score-badge.medium {
  background: #fef9c3;
  color: #854d0e;
}

.score-badge.low {
  background: #fee2e2;
  color: #991b1b;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #f8f6f1;
  border: none;
  border-radius: 6px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #fee2e2;
  color: #ef4444;
}

.icon {
  width: 18px;
  height: 18px;
}

/* 主内容区 */
.reader-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 阅读器滚动容器 - 替代 flex overflow 的中间层 */
.reader-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

/* 左侧图片区 */
.reader-left {
  width: 45%;
  background: #2a2a2a;
  padding: 24px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.image-gallery {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.gallery-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #1a1a1a;
  border-radius: 8px;
  padding: 20px;
  min-height: 300px;
}

.main-image {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
  cursor: zoom-in;
  transition: transform 0.3s;
}

.main-image:hover {
  transform: scale(1.02);
}

.image-caption {
  margin-top: 12px;
  padding: 6px 16px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border-radius: 4px;
  font-size: 13px;
}

.gallery-thumbs {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.thumb-btn {
  width: 60px;
  height: 60px;
  padding: 4px;
  background: #1a1a1a;
  border: 2px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}

.thumb-btn.active {
  border-color: #c45c48;
}

.thumb-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-image-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
}

.placeholder-icon {
  width: 64px;
  height: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

/* 右侧文本区 */
.reader-right {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  background: linear-gradient(to right, #e8e4dc 0%, #f5f0e8 5%);
}

.book-page {
  background: #fffef8;
  padding: 40px;
  box-shadow: 
    0 0 20px rgba(0, 0, 0, 0.1),
    inset 30px 0 40px -30px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #e8e4dc;
  margin-bottom: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.view-pdf-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f5f0e8;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 13px;
  color: #5a5a5a;
  cursor: pointer;
  transition: all 0.2s;
}

.view-pdf-btn:hover {
  background: #c45c48;
  border-color: #c45c48;
  color: #fff;
}

/* 标签页 */
.reader-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #e8e4dc;
  background: #faf9f7;
  margin: 0 -40px;
  padding: 0 40px;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: 13px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: -1px;
}

.tab-btn:hover {
  color: #5a5a5a;
  background: rgba(196, 92, 72, 0.05);
}

.tab-btn.active {
  color: #c45c48;
  border-bottom-color: #c45c48;
  font-weight: 600;
}

.tab-count {
  padding: 1px 6px;
  background: #e8e4dc;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  color: #8b7355;
}

.tab-btn.active .tab-count {
  background: rgba(196, 92, 72, 0.15);
  color: #c45c48;
}

/* 标签页内容 */
.tab-content {
  flex: 1;
  overflow: hidden;
}

.tab-pane {
  height: 100%;
  overflow-y: auto;
}

.page-chapter {
  font-size: 14px;
  font-weight: 600;
  color: #c45c48;
}

.page-number {
  font-size: 13px;
  color: #8b7355;
}

.page-content {
  font-size: 16px;
  line-height: 2;
  color: #3d3d3d;
}

.context-section {
  opacity: 0.6;
}

.context-section.before {
  margin-bottom: 24px;
}

.context-section.after {
  margin-top: 24px;
}

.context-text {
  font-style: italic;
  text-align: justify;
}

.context-marker {
  text-align: center;
  color: #8b7355;
  font-size: 12px;
  margin: 16px 0;
  letter-spacing: 4px;
}

.current-content {
  padding: 20px 0;
}

.content-text {
  text-align: justify;
  text-indent: 2em;
}

/* 内联图片区域 */
.inline-images {
  margin: 24px 0;
  padding: 16px;
  background: #f8f6f1;
  border-radius: 8px;
  border: 1px dashed #d4cfc5;
}

.images-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #8b7355;
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.inline-image-item {
  position: relative;
  cursor: pointer;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.2s;
}

.inline-image-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.inline-image {
  width: 100%;
  height: 100px;
  object-fit: cover;
  display: block;
}

.inline-image-caption {
  padding: 6px 8px;
  font-size: 11px;
  color: #5a5a5a;
  background: #fff;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.inline-image-item:hover .image-overlay {
  opacity: 1;
}

.zoom-hint {
  color: #fff;
  font-size: 12px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 4px;
}

:deep(.highlight) {
  background: #fef3c7;
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: 500;
}

.page-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 24px;
  border-top: 1px solid #e8e4dc;
  margin-top: 24px;
}

.source-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #8b7355;
}

.source-icon {
  width: 16px;
  height: 16px;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  background: #f8f6f1;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 13px;
  color: #5a5a5a;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background: #c45c48;
  border-color: #c45c48;
  color: #fff;
}

.nav-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.nav-divider {
  color: #d4cfc5;
}

/* 底部信息栏 */
.reader-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-top: 1px solid #e8e4dc;
}

.footer-info {
  display: flex;
  gap: 20px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8b7355;
}

.info-icon {
  width: 14px;
  height: 14px;
}

.footer-actions {
  display: flex;
  gap: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #f8f6f1;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 13px;
  color: #5a5a5a;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #e8e4dc;
}

.action-btn.primary {
  background: #c45c48;
  border-color: #c45c48;
  color: #fff;
}

.action-btn.primary:hover {
  background: #a84838;
}

/* 图片预览 */
.image-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.preview-image {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
}

.preview-close {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 50%;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.preview-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.no-image-fallback {
  width: 100%;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f0e8;
}

/* 图像详情页 */
.image-detail-page {
  background: #fffef8;
  padding: 40px;
  box-shadow: 
    0 0 20px rgba(0, 0, 0, 0.1),
    inset 30px 0 40px -30px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

.image-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 20px;
  border-bottom: 1px solid #e8e4dc;
  margin-bottom: 24px;
}

.image-detail-body {
  display: flex;
  gap: 30px;
  align-items: flex-start;
}

.image-detail-main {
  flex: 1;
  min-width: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f8f6f1;
  border-radius: 8px;
  padding: 20px;
  max-height: 500px;
  overflow: hidden;
}

.image-detail-img {
  max-width: 100%;
  max-height: 460px;
  object-fit: contain;
  cursor: zoom-in;
  transition: transform 0.3s;
}

.image-detail-img:hover {
  transform: scale(1.02);
}

.image-detail-info {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.artwork-title {
  font-size: 20px;
  font-weight: 700;
  color: #3d3d3d;
  margin: 0;
}

.artwork-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 12px;
  color: #8b7355;
  font-weight: 500;
}

.meta-value {
  font-size: 14px;
  color: #3d3d3d;
}

.artwork-desc {
  padding: 12px 16px;
  background: #f8f6f1;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.8;
  color: #44403c;
  text-align: justify;
}

@media (max-width: 1024px) {
  .image-detail-body {
    flex-direction: column;
  }
  
  .image-detail-info {
    width: 100%;
  }
}

/* PDF 查看器弹窗 */
.pdf-viewer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1500;
  padding: 20px;
}

.pdf-viewer-container {
  background: #f5f0e8;
  border-radius: 12px;
  width: 100%;
  max-width: 1200px;
  height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.pdf-viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e4dc;
}

.pdf-viewer-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #3d3d3d;
}

.pdf-book-name {
  font-weight: 400;
  color: #8b7355;
  font-size: 14px;
  margin-left: 8px;
}

.pdf-viewer-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: #f8f6f1;
  border: none;
  border-radius: 8px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.pdf-viewer-close:hover {
  background: #fee2e2;
  color: #ef4444;
}

.pdf-viewer-body {
  flex: 1;
  overflow: hidden;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 响应式 */
@media (max-width: 1024px) {
  .reader-content {
    flex-direction: column;
  }
  
  .reader-left {
    width: 100%;
    height: 40%;
  }
  
  .reader-right {
    height: 60%;
  }
}

/* 文档大纲区域 */
.outline-section {
  margin-top: 24px;
}

/* Markdown 视图区域 */
.markdown-section {
  margin-top: 24px;
}

/* 关联文本块区域 */
.related-chunks-section {
  margin-top: 24px;
}
</style>
