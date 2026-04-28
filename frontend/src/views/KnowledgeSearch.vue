<template>
  <div class="knowledge-search">
    <!-- 主内容区 -->
    <div class="main-container">
      <!-- 左侧搜索区 -->
      <div class="search-area">
        <!-- Tab 切换 -->
        <div class="mode-tabs">
          <button 
            class="mode-tab" 
            :class="{ active: activeMode === 'search' }"
            @click="switchMode('search')"
          >
            <Search class="tab-icon" />
            名词搜索
          </button>
          <button 
            class="mode-tab" 
            :class="{ active: activeMode === 'chat' }"
            @click="switchMode('chat')"
          >
            <MessageCircle class="tab-icon" />
            专家模式
          </button>
        </div>

        <!-- ===== 名词搜索模式 ===== -->
        <div v-if="activeMode === 'search'" class="mode-panel mode-search-enter">
        <!-- 欢迎标题 -->
        <div class="welcome-section" v-if="!hasSearched">
          <h1 class="welcome-title">写意知识库</h1>
          <p class="welcome-subtitle">搜索潘天寿构图法则、写意花鸟画技法等专业知识</p>
          
          <!-- 热门标签 -->
          <div class="hot-tags">
            <span class="tags-label">热门搜索：</span>
            <button 
              v-for="tag in hotTags" 
              :key="tag"
              class="tag-btn"
              @click="searchByTag(tag)"
            >
              {{ tag }}
            </button>
          </div>
        </div>

        <!-- 搜索框 -->
        <div class="search-box">
          <Search class="search-icon" />
          <input
            v-model="searchInput"
            type="text"
            class="search-input"
            placeholder="输入关键词搜索..."
            @keyup.enter="performSearch"
            :disabled="store.searchLoading"
          />
          <button class="search-btn" @click="performSearch" :disabled="store.searchLoading">
            <Loader2 v-if="store.searchLoading" class="icon spin" />
            <span v-else>搜索</span>
          </button>
        </div>

        <!-- 搜索进度条 -->
        <div v-if="store.searchLoading" class="search-progress-container">
          <div class="search-progress-bar">
            <div 
              class="search-progress-fill"
              :style="{ width: `${store.searchProgress}%` }"
            />
          </div>
          <span class="search-progress-text">搜索中...</span>
        </div>

        <!-- 搜索结果 -->
        <div class="search-results" v-if="hasSearched && !store.searchLoading">
          <div class="results-header">
            <span class="results-count">找到 {{ store.searchResults.length }} 个结果</span>
            <button class="clear-btn" @click="clearSearch">清除搜索</button>
          </div>
          
          <!-- AI 摘要卡片 -->
          <div v-if="store.aiSummary" class="ai-summary-card">
            <div class="ai-summary-header">
              <Sparkles class="ai-icon" />
              <span class="ai-summary-title">AI 概述</span>
              <span class="ai-confidence-badge" :class="getConfidenceClass(store.aiSummary.confidence)">
                {{ getConfidenceLabel(store.aiSummary.confidence) }}
              </span>
            </div>
            <p class="ai-summary-content">{{ cleanLatexSymbols(store.aiSummary.answer) }}</p>
            
            <!-- 要点列表 -->
            <div v-if="store.aiSummary.key_points && store.aiSummary.key_points.length > 0" class="ai-key-points">
              <div class="key-points-label">核心要点</div>
              <ul class="key-points-list">
                <li v-for="(point, idx) in store.aiSummary.key_points" :key="idx" class="key-point-item">
                  <span class="key-point-bullet">●</span>
                  <span class="key-point-text">{{ cleanLatexSymbols(point) }}</span>
                </li>
              </ul>
            </div>
            
            <!-- 相关概念 -->
            <div v-if="store.aiSummary.related_concepts && store.aiSummary.related_concepts.length > 0" class="ai-concepts">
              <span class="concepts-label">相关概念：</span>
              <button 
                v-for="(concept, idx) in store.aiSummary.related_concepts" 
                :key="idx"
                class="concept-tag"
                @click="searchByTag(concept)"
              >
                {{ concept }}
              </button>
            </div>

            <!-- 相关配图 -->
            <div v-if="store.relatedImages && store.relatedImages.length > 0" class="ai-related-images">
              <div class="related-images-label">相关配图</div>
              <div class="related-images-gallery">
                <div 
                  v-for="(img, idx) in store.relatedImages.slice(0, 4)" 
                  :key="idx" 
                  class="related-image-card"
                  @click="openImageDetail(img)"
                >
                  <img :src="getImageUrl(img.url)" :alt="cleanLatexSymbols(img.display_label) || img.figure_id || '配图'" class="related-image-thumb" />
                  <div class="related-image-info">
                    <span class="related-image-label">{{ cleanLatexSymbols(img.display_label) || img.figure_id || '配图' }}</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 来源引用 -->
            <div v-if="store.aiSummary.sources && store.aiSummary.sources.length > 0" class="ai-sources">
              <span class="sources-label">参考来源：</span>
              <button 
                v-for="(src, idx) in store.aiSummary.sources" 
                :key="idx" 
                class="source-tag"
                @click="scrollToSource(src)"
              >
                《{{ (src.book || '未知').replace(/[《》]/g, '') }}》第{{ src.page || 0 }}页
              </button>
            </div>
            
            <!-- 改写查询 -->
            <div v-if="store.queryRewrite && store.queryRewrite.rewrites && store.queryRewrite.rewrites.length > 0" class="ai-rewrites">
              <span class="rewrites-label">搜索扩展：</span>
              <button 
                v-for="(rq, idx) in store.queryRewrite.rewrites" 
                :key="idx"
                class="rewrite-tag"
                @click="searchByTag(rq)"
              >
                {{ rq }}
              </button>
            </div>
          </div>
          
          <div class="results-list" v-if="store.searchResults.length > 0">
            <div 
              v-for="(result, index) in store.searchResults" 
              :key="result.chunk_id || result.vector_id"
              :id="'search-result-' + index"
              :class="['result-item', { 'result-highlight': highlightedIndex === index, 'result-image-card': result.result_type === 'image' }]"
              @click="openDetail(result, index)"
            >
              <!-- 图像结果卡片 -->
              <template v-if="result.result_type === 'image'">
                <div class="result-image-layout">
                  <div class="result-image-preview">
                    <img :src="getImageUrl(result.image?.url || result.associated_images?.[0]?.url)" :alt="cleanLatexSymbols(result.image?.artwork_title) || '配图'" />
                  </div>
                  <div class="result-body">
                    <div class="result-header">
                      <div class="header-left">
                        <span class="result-type-badge image-badge">
                          <ImageIcon class="badge-icon" />配图
                        </span>
                        <span v-if="result.image?.artist" class="result-chapter">{{ result.image?.era ? result.image.era + '·' : '' }}{{ cleanLatexSymbols(result.image.artist) }}</span>
                      </div>
                      <span class="result-score-badge" :class="getScoreClass(result.score)">
                        {{ formatScore(result.score) }}% 匹配
                      </span>
                    </div>
                    
                    <p v-if="result.image?.artwork_title" class="image-title">《{{ cleanLatexSymbols(result.image.artwork_title) }}》</p>
                    <p v-if="result.image?.description" class="result-content image-desc">{{ cleanLatexSymbols(result.image.description) }}</p>
                    
                    <div class="result-footer">
                      <div class="footer-left">
                        <span class="result-book">
                          <Library class="book-icon" />
                          {{ result.book_title }}
                        </span>
                      </div>
                      <div class="result-meta">
                        <span class="view-detail">
                          查看大图 <ChevronRight class="view-icon" />
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
              
              <!-- 表格结果卡片 -->
              <template v-else-if="result.result_type === 'table'">
                <TableResultCard 
                  :result="result"
                  @click="openDetail(result, index)"
                />
              </template>
              
              <!-- 文本结果卡片 -->
              <template v-else>
                <div class="result-body">
                  <div class="result-header">
                    <div class="header-left">
                      <span class="result-chapter">{{ getChapterTitle(result) }}</span>
                      <span class="result-page">
                        <BookOpen class="page-icon" />
                        第 {{ result.page_start }}-{{ result.page_end }} 页
                      </span>
                    </div>
                    <span class="result-score-badge" :class="getScoreClass(result.score)">
                      {{ formatScore(result.score) }}% 匹配
                    </span>
                  </div>
                  
                  <p class="result-content">
                    <span v-if="result.context_before" class="context-ellipsis">...{{ cleanLatexSymbols(result.context_before.slice(-30)) }}</span>
                    <span class="highlight-text">{{ cleanLatexSymbols(truncateAtSentence(result.content, 150)) }}</span>
                    <span v-if="result.content.length > 150" class="fade-out">...</span>
                    <span v-if="result.context_after" class="context-ellipsis">{{ cleanLatexSymbols(result.context_after.slice(0, 30)) }}...</span>
                  </p>
                  
                  <div class="result-footer">
                    <div class="footer-left">
                      <span class="result-book">
                        <Library class="book-icon" />
                        {{ result.book_title }}
                      </span>
                    </div>
                    <div class="result-meta">
                      <span class="chunk-index">#{{ result.chunk_index + 1 }}</span>
                      <span class="view-detail">
                        阅读更多 <ChevronRight class="view-icon" />
                      </span>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
          
          <div class="no-results" v-else>
            <FileSearch class="no-results-icon" />
            <p>未找到相关结果，请尝试其他关键词</p>
          </div>
        </div>

        <!-- 下方工具面板 -->
        <div class="below-panel">
          <div class="panel-cards-grid">
            <!-- 上传 + 统计 -->
            <div class="panel-card">
              <button class="upload-btn" @click="showUploadModal = true">
                <span class="upload-icon">+</span>
                <span>上传PDF</span>
              </button>
              <div class="stats-row" v-if="store.stats">
                <div class="stat-chip">
                  <span class="stat-value-sm">{{ store.stats.books?.total || 0 }}</span>
                  <span class="stat-label-sm">书籍</span>
                </div>
                <div class="stat-chip">
                  <span class="stat-value-sm">{{ store.stats.contents?.chunks || 0 }}</span>
                  <span class="stat-label-sm">文本块</span>
                </div>
                <div class="stat-chip">
                  <span class="stat-value-sm">{{ store.stats.contents?.images || 0 }}</span>
                  <span class="stat-label-sm">图像</span>
                </div>
              </div>
            </div>

            <!-- 书库 -->
            <div class="panel-card">
              <div class="panel-header-with-actions">
                <h3 class="panel-title"><BookOpen class="panel-icon" />书库</h3>
                <div class="panel-actions" v-if="store.completedBooks.length > 0">
                  <button class="action-btn select-all-btn" @click="selectAllBooks" v-if="selectedBooks.length === 0" title="全选">全选</button>
                  <button class="action-btn clear-selection-btn" @click="clearSelection" v-else title="取消选择">取消选择</button>
                </div>
              </div>
              <div class="book-list">
                <div v-for="book in store.books" :key="book.id" class="book-item-wrapper">
                  <label class="book-item" :class="{ 'book-item-processing': book.status === 'processing' }">
                    <input type="checkbox" v-model="selectedBooks" :value="book.id" :disabled="book.status === 'processing'" />
                    <span class="book-name">
                      <span class="book-name-text">{{ book.title || book.file_name }}</span>
                      <span v-if="book.status === 'processing'" class="book-status-tag processing">处理中</span>
                      <span v-else-if="book.status === 'failed'" class="book-status-tag failed">失败</span>
                      <span v-else class="book-status-tag completed">已入库</span>
                    </span>
                  </label>
                  <div class="book-actions">
                    <button class="action-icon-btn reingest-btn" @click="reingestBook(book.id)" :disabled="reingestingBookId === book.id || book.status === 'processing'" title="重新入库">
                      <RefreshCw v-if="reingestingBookId !== book.id && book.status !== 'processing'" class="icon-small" />
                      <Loader2 v-else class="icon-small spin" />
                    </button>
                    <button class="action-icon-btn delete-btn" @click="deleteBook(book.id)" title="删除书籍">
                      <Trash2 class="icon-small" />
                    </button>
                  </div>
                  <div v-if="reingestingBookId === book.id" class="reingest-progress">
                    <div class="progress-bar-track">
                      <div class="progress-bar-fill" :style="{ width: store.processingProgress + '%' }"></div>
                    </div>
                    <span class="progress-text">{{ store.processingProgress || 0 }}% · {{ store.processingStage || '准备中...' }}</span>
                  </div>
                </div>
                <p v-if="store.books.length === 0" class="empty-text">暂无已入库的书籍</p>
              </div>
              <div class="book-list-hint">
                <Info class="hint-icon" />
                <span>全选可搜索所有书籍，不选则默认搜索全部</span>
              </div>
            </div>

            <!-- 搜索历史 -->
            <div class="panel-card">
              <div class="panel-header-with-actions">
                <h3 class="panel-title"><History class="panel-icon" />搜索历史</h3>
                <div class="panel-actions" v-if="store.searchHistory.length > 0">
                  <button class="action-btn clear-all-btn" @click="confirmClearHistory" title="清空历史">
                    <Trash2 class="icon-tiny" />清空
                  </button>
                </div>
              </div>
              <div class="history-list">
                <div v-for="item in store.searchHistory.slice(0, 6)" :key="item.id" class="history-item-wrapper">
                  <button class="history-item" @click="searchByTag(item.query)">
                    <Clock class="history-icon" />
                    <span class="history-query">{{ item.query }}</span>
                  </button>
                  <button class="delete-history-btn" @click="deleteHistoryItem(item.id)" title="删除">
                    <X class="icon-tiny" />
                  </button>
                </div>
                <p v-if="store.searchHistory.length === 0" class="empty-text">暂无搜索记录</p>
              </div>
            </div>
          </div>
        </div>
        </div>

        <!-- ===== 专家模式（聊天） ===== -->
        <div v-if="activeMode === 'chat'" class="mode-panel mode-chat-enter">
          <div class="chat-container">
            <!-- 聊天消息区 -->
            <div class="chat-messages" ref="chatMessagesRef">
              <!-- 欢迎消息 -->
              <div v-if="chatMessages.length === 0" class="chat-welcome">
                <div class="chat-welcome-icon">
                  <Sparkles class="welcome-sparkle" />
                </div>
                <h2 class="chat-welcome-title">写意画专家助手</h2>
                <p class="chat-welcome-desc">基于专业知识库，深度解答写意花鸟画、构图法则、笔墨技法等问题</p>
                <div class="chat-suggestions">
                  <button 
                    v-for="s in chatSuggestions" 
                    :key="s"
                    class="suggestion-btn"
                    @click="sendChatMessage(s)"
                  >
                    {{ s }}
                  </button>
                </div>
              </div>

              <!-- 消息列表 -->
              <div 
                v-for="(msg, idx) in chatMessages" 
                :key="idx"
                :class="['chat-message', msg.role]"
              >
                <div class="message-avatar">
                  <Bot v-if="msg.role === 'assistant'" class="avatar-icon" />
                  <User v-else class="avatar-icon" />
                </div>
                <div class="message-content">
                  <div class="message-role">{{ msg.role === 'user' ? '你' : '专家助手' }}</div>
                  <div v-if="msg.thinking" class="message-text thinking-indicator">
                    <span class="thinking-icon"><Sparkles class="icon-tiny" /></span>
                    <span>正在思考...</span>
                  </div>
                  <div v-else :class="['message-text', { 'has-loading': msg.role === 'assistant' && msg.loading }]" v-html="renderMarkdown(msg.content, msg.role === 'assistant' && msg.loading)"></div>
                </div>
              </div>
            </div>

            <!-- 输入区 -->
            <div class="chat-input-area">
              <div class="chat-input-box">
                <textarea
                  ref="chatInputRef"
                  v-model="chatInput"
                  class="chat-textarea"
                  placeholder="输入你的问题..."
                  @keydown.enter.exact="handleChatEnter"
                  @input="autoResizeTextarea"
                  rows="2"
                  :disabled="chatLoading"
                ></textarea>
                <button 
                  class="chat-send-btn" 
                  @click="sendChatMessage()"
                  :disabled="!chatInput.trim() || chatLoading"
                >
                  <Send class="send-icon" />
                </button>
              </div>
              <div class="chat-input-hint">
                <span class="hint-text">按 Enter 发送，Shift+Enter 换行</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- DEPRECATED: 面板已移至搜索区下方 below-panel -->
      <aside v-if="false" class="side-panel">
        <!-- 上传按钮 -->
        <div class="panel-section upload-section">
          <button class="upload-btn" @click="showUploadModal = true">
            <span class="upload-icon">+</span>
            <span>上传PDF</span>
          </button>
        </div>

        <!-- 书库选择 -->
        <div class="panel-section">
          <div class="panel-header-with-actions">
            <h3 class="panel-title">
              <BookOpen class="panel-icon" />
              书库
            </h3>
            <div class="panel-actions" v-if="store.completedBooks.length > 0">
              <button 
                class="action-btn select-all-btn" 
                @click="selectAllBooks"
                v-if="selectedBooks.length === 0"
                title="全选"
              >
                全选
              </button>
              <button 
                class="action-btn clear-selection-btn" 
                @click="clearSelection"
                v-else
                title="取消选择"
              >
                取消选择
              </button>
            </div>
          </div>
          <div class="book-list">
            <div 
              v-for="book in store.books" 
              :key="book.id"
              class="book-item-wrapper"
            >
              <label class="book-item" :class="{ 'book-item-processing': book.status === 'processing' }">
                <input 
                  type="checkbox" 
                  v-model="selectedBooks"
                  :value="book.id"
                  :disabled="book.status === 'processing'"
                />
                <span class="book-name">
                  <span class="book-name-text">{{ book.title || book.file_name }}</span>
                  <span v-if="book.status === 'processing'" class="book-status-tag processing">处理中</span>
                  <span v-else-if="book.status === 'failed'" class="book-status-tag failed">失败</span>
                  <span v-else class="book-status-tag completed">已入库</span>
                </span>
              </label>
              <div class="book-actions">
                <button 
                  class="action-icon-btn reingest-btn"
                  @click="reingestBook(book.id)"
                  :disabled="reingestingBookId === book.id || book.status === 'processing'"
                  title="重新入库"
                >
                  <RefreshCw v-if="reingestingBookId !== book.id && book.status !== 'processing'" class="icon-small" />
                  <Loader2 v-else class="icon-small spin" />
                </button>
                <button 
                  class="action-icon-btn delete-btn"
                  @click="deleteBook(book.id)"
                  title="删除书籍"
                >
                  <Trash2 class="icon-small" />
                </button>
              </div>
              <!-- 入库进度条 -->
              <div v-if="reingestingBookId === book.id" class="reingest-progress">
                <div class="progress-bar-track">
                  <div class="progress-bar-fill" :style="{ width: store.processingProgress + '%' }"></div>
                </div>
                <span class="progress-text">{{ store.processingProgress || 0 }}% · {{ store.processingStage || '准备中...' }}</span>
              </div>
            </div>
            <p v-if="store.books.length === 0" class="empty-text">
              暂无已入库的书籍
            </p>
          </div>
          <div class="book-list-hint">
            <Info class="hint-icon" />
            <span>全选可搜索所有书籍，不选则默认搜索全部</span>
          </div>
        </div>

        <!-- 搜索历史 -->
        <div class="panel-section">
          <div class="panel-header-with-actions">
            <h3 class="panel-title">
              <History class="panel-icon" />
              搜索历史
            </h3>
            <div class="panel-actions" v-if="store.searchHistory.length > 0">
              <button 
                class="action-btn clear-all-btn" 
                @click="confirmClearHistory"
                title="清空历史"
              >
                <Trash2 class="icon-tiny" />
                清空
              </button>
            </div>
          </div>
          <div class="history-list">
            <div 
              v-for="item in store.searchHistory" 
              :key="item.id"
              class="history-item-wrapper"
            >
              <button 
                class="history-item"
                @click="searchByTag(item.query)"
              >
                <Clock class="history-icon" />
                <span class="history-query">{{ item.query }}</span>
              </button>
              <button 
                class="delete-history-btn"
                @click="deleteHistoryItem(item.id)"
                title="删除"
              >
                <X class="icon-tiny" />
              </button>
            </div>
            <p v-if="store.searchHistory.length === 0" class="empty-text">
              暂无搜索记录
            </p>
          </div>
        </div>

        <!-- 统计信息 -->
        <div class="panel-section" v-if="store.stats">
          <h3 class="panel-title">
            <BarChart3 class="panel-icon" />
            知识库统计
          </h3>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ store.stats.books?.total || 0 }}</span>
              <span class="stat-label">书籍</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ store.stats.contents?.chunks || 0 }}</span>
              <span class="stat-label">文本块</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ store.stats.contents?.images || 0 }}</span>
              <span class="stat-label">图像</span>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 上传模态框 -->
    <UploadModal 
      v-model:visible="showUploadModal"
      @upload-success="handleUploadSuccess"
    />

    <!-- 详情弹窗 - 图书阅读器 -->
    <BookReaderModal
      v-model:visible="showReaderModal"
      :result="selectedResult"
      :search-query="searchInput"
      :all-results="store.searchResults"
      :current-index="selectedIndex"
      @navigate="navigateToResult"
      @navigate-chunk="handleNavigateChunk"
    />

    <!-- 相关配图预览浮层 -->
    <div v-if="relatedImagePreviewVisible" class="image-preview-overlay" @click="relatedImagePreviewVisible = false">
      <img :src="relatedImagePreviewUrl" class="preview-image" @click.stop />
      <button class="preview-close" @click="relatedImagePreviewVisible = false">
        <X class="icon" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { 
  Search, 
  Loader2, 
  BookOpen, 
  History, 
  Clock,
  BarChart3,
  FileSearch,
  ChevronRight,
  Library,
  RefreshCw,
  Info,
  Trash2,
  X,
  Sparkles,
  Image as ImageIcon,
  MessageCircle,
  Bot,
  User,
  Send
} from 'lucide-vue-next'
import { useKnowledgeStore } from '@/stores/knowledgeStore'
import { ElMessage, ElMessageBox } from 'element-plus'
import UploadModal from '@/components/UploadModal.vue'
import BookReaderModal from '@/components/BookReaderModal.vue'
import TableResultCard from '@/components/TableResultCard.vue'

const store = useKnowledgeStore()

// 状态
const searchInput = ref('')
const hasSearched = ref(false)
const selectedBooks = ref([])
const showUploadModal = ref(false)
const showReaderModal = ref(false)
const selectedResult = ref({})
const selectedIndex = ref(0)
const highlightedIndex = ref(-1)
const reingestingBookId = ref(null)

// 模式切换
const activeMode = ref('search') // 'search' | 'chat'

// 聊天状态
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatSessionId = ref(null)
const chatMessagesRef = ref(null)
const chatInputRef = ref(null)

// 聊天建议
const chatSuggestions = [
  '写意画中的"气韵生动"如何理解？',
  '潘天寿的构图有哪些核心法则？',
  '花鸟画中墨分五色的具体运用',
  '写意与工笔的根本区别是什么？',
]

// 热门标签
const hotTags = ['墨法', '构图', '笔法', '写意', '花鸟', '山水', '题跋', '印章']

// 方法
async function performSearch() {
  if (!searchInput.value.trim()) return
  
  hasSearched.value = true
  await store.search(searchInput.value, {
    bookIds: selectedBooks.value,
    limit: 20
  })
}

function searchByTag(tag) {
  searchInput.value = tag
  performSearch()
}

function clearSearch() {
  searchInput.value = ''
  hasSearched.value = false
  store.clearSearchResults()
}

function openDetail(result, index) {
  selectedResult.value = result
  selectedIndex.value = index
  showReaderModal.value = true
}

// 点击 AI 摘要的来源标签，滚动到对应的搜索结果
function scrollToSource(src) {
  const results = store.searchResults
  if (!results.length) return
  
  // 1. 精确匹配 book + page_start
  let matchIdx = results.findIndex(
    r => r.book_title === src.book && r.page_start === src.page
  )
  
  // 2. 模糊匹配 book + page 范围包含
  if (matchIdx === -1 && src.book) {
    matchIdx = results.findIndex(
      r => r.book_title === src.book && 
           src.page >= r.page_start && src.page <= (r.page_end || r.page_start)
    )
  }
  
  // 3. 只匹配 page（不同书名的同页也可能相关）
  if (matchIdx === -1 && src.page) {
    matchIdx = results.findIndex(r => r.page_start === src.page)
  }
  
  // 4. 包含匹配 book（LLM 输出的书名可能略有差异）
  if (matchIdx === -1 && src.book && src.book.length > 1) {
    const shortBook = src.book.replace(/[《》]/g, '')
    matchIdx = results.findIndex(r => {
      const rTitle = r.book_title.replace(/[《》]/g, '')
      return rTitle.includes(shortBook) || shortBook.includes(rTitle)
    })
  }
  
  if (matchIdx >= 0) {
    const el = document.getElementById('search-result-' + matchIdx)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      highlightedIndex.value = matchIdx
      setTimeout(() => { highlightedIndex.value = -1 }, 2000)
    }
  }
}

function navigateToResult(index) {
  if (index >= 0 && index < store.searchResults.length) {
    selectedIndex.value = index
    selectedResult.value = store.searchResults[index]
  }
}

// 处理书中翻页（来自 BookReaderModal 的 navigate-chunk 事件）
function handleNavigateChunk(chunkData) {
  // 将翻页后的文本块更新为当前选中的结果
  selectedResult.value = chunkData
}

// 清理 LaTeX 数学符号，转换为 Unicode 字符
function cleanLatexSymbols(text) {
  if (!text) return text
  // 将 $\textcircled{1}$ 格式转换为 ①②③ 等 Unicode 带圈数字
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

// 在句子边界截断文本（避免在句子中间截断）
function truncateAtSentence(text, maxLen) {
  if (!text || text.length <= maxLen) return text || ''
  // 在 maxLen 附近找到最近的句子结束符
  const truncated = text.substring(0, maxLen)
  // 优先在中文句号、英文句号+空格、换行符处截断
  const lastSentenceEnd = Math.max(
    truncated.lastIndexOf('。'),
    truncated.lastIndexOf('！'),
    truncated.lastIndexOf('？'),
    truncated.lastIndexOf('. '),
    truncated.lastIndexOf('\n')
  )
  if (lastSentenceEnd > maxLen * 0.5) {
    // 如果句子结束符在合理范围内，在此处截断
    return text.substring(0, lastSentenceEnd + 1)
  }
  // 否则在最后一个逗号、分号处截断
  const lastPunct = Math.max(
    truncated.lastIndexOf('，'),
    truncated.lastIndexOf('；'),
    truncated.lastIndexOf(','),
    truncated.lastIndexOf('、')
  )
  if (lastPunct > maxLen * 0.5) {
    return text.substring(0, lastPunct + 1)
  }
  // 兜底：直接截断
  return truncated
}

function handleUploadSuccess() {
  // 刷新书籍列表
  store.fetchBooks()
  store.fetchStats()
}

async function reingestBook(bookId) {
  if (reingestingBookId.value) return
  
  // 询问使用哪个解析器
  const parserChoice = await ElMessageBox.confirm(
    '选择 PDF 解析器：',
    '重新入库',
    {
      confirmButtonText: 'MinerU（AI解析，支持表格/大纲）',
      cancelButtonText: 'PyMuPDF（快速，基础解析）',
      distinguishCancelAndClose: true,
      type: 'info'
    }
  ).then(() => 'mineru').catch((action) => {
    if (action === 'cancel') return 'pymupdf'
    return null // close
  })
  
  if (!parserChoice) return // 用户关闭了对话框
  
  reingestingBookId.value = bookId
  try {
    const result = await store.reingestBook(bookId, {
      chunkStrategy: 'semantic',
      chunkSize: 500,
      parserBackend: parserChoice
    })
    
    // 轮询等待完成（store.startPollingTask 已启动）
    const taskResult = await waitForReingestComplete()
    
    if (taskResult === 'completed') {
      ElMessage.success('重新入库成功！')
    } else if (taskResult === 'failed') {
      ElMessage.error('重新入库失败: ' + (store.uploadError || '未知错误'))
    }
    
    // 刷新书籍列表和统计
    await store.fetchBooks()
    await store.fetchStats()
  } catch (e) {
    ElMessage.error('重新入库失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    reingestingBookId.value = null
  }
}

// 等待重新入库完成
function waitForReingestComplete() {
  return new Promise((resolve) => {
    const check = setInterval(() => {
      if (store.uploadStatus === 'completed') {
        clearInterval(check)
        resolve('completed')
      } else if (store.uploadStatus === 'error') {
        clearInterval(check)
        resolve('failed')
      }
    }, 500)
  })
}

async function deleteBook(bookId) {
  if (!confirm('确定要删除这本书吗？此操作不可恢复。')) return
  
  try {
    await store.deleteBook(bookId)
    ElMessage.success('书籍已删除')
    // 从选中列表中移除
    selectedBooks.value = selectedBooks.value.filter(id => id !== bookId)
    // 刷新统计
    store.fetchStats()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

function selectAllBooks() {
  selectedBooks.value = store.completedBooks.map(b => b.id)
}

function clearSelection() {
  selectedBooks.value = []
}

async function deleteHistoryItem(historyId) {
  try {
    await store.deleteSearchHistoryItem(historyId)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.message || '未知错误'))
  }
}

async function confirmClearHistory() {
  if (!confirm('确定要清空所有搜索历史吗？')) return
  
  try {
    await store.clearSearchHistory()
    ElMessage.success('搜索历史已清空')
  } catch (e) {
    ElMessage.error('清空失败: ' + (e.message || '未知错误'))
  }
}

// 获取智能章节标题
function getChapterTitle(result) {
  if (!result) return '正文'
  // 过滤掉"正文"标签
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
  // RRF融合后的分数范围通常在 0.01-0.05 之间
  // 跨模态搜索余弦分数在 0.19-0.23 之间
  // 需要映射到 1-100% 的显示范围
  if (score < 0.1) {
    // 假设 0.05 对应 100%，线性映射
    const normalized = Math.min(score / 0.05, 1)
    return Math.round(normalized * 100)
  }
  // 跨模态分数 (0.1-0.3) → 映射到合理百分比
  if (score < 0.3) {
    // 0.1 → 30%, 0.2 → 60%, 0.3 → 90%
    const normalized = Math.min((score - 0.05) / 0.25, 1)
    return Math.max(20, Math.round(normalized * 100))
  }
  // 如果已经是百分比（>1），直接返回
  if (score > 1) {
    return Math.min(Math.round(score), 100)
  }
  // 0.3-1 之间的分数，直接乘以100
  return Math.round(score * 100)
}

// 根据分数获取样式类
function getScoreClass(score) {
  const s = formatScore(score)
  if (s >= 80) return 'high'
  if (s >= 50) return 'medium'
  return 'low'
}

// AI 摘要置信度样式
function getConfidenceClass(confidence) {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.5) return 'medium'
  return 'low'
}

// AI 摘要置信度标签
function getConfidenceLabel(confidence) {
  if (confidence >= 0.8) return '高置信'
  if (confidence >= 0.5) return '中置信'
  return '参考'
}

// 获取图像 URL（兼容相对路径和绝对路径）
function getImageUrl(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  // /static/ 开头的路径直接走 FastAPI 静态文件服务，不需要代理前缀
  if (url.startsWith('/static/')) return url
  // /api/ 开头的路径已经是完整路径（后端拼好了），不需要再加前缀
  if (url.startsWith('/api/')) return url
  // 其他相对路径走后端代理
  return `/api/v1/knowledge/${url}`
}

// 相关配图预览
const relatedImagePreviewVisible = ref(false)
const relatedImagePreviewUrl = ref('')

// 打开相关配图预览
function openImageDetail(img) {
  // 直接打开图片预览，无需匹配搜索结果
  relatedImagePreviewUrl.value = getImageUrl(img.url)
  relatedImagePreviewVisible.value = true
}

// 初始化
onMounted(() => {
  store.fetchBooks()
  store.fetchSearchHistory()
  store.fetchStats()
})

// ============ 模式切换 ============
function switchMode(mode) {
  activeMode.value = mode
  // 专家模式隐藏浏览器滚动条
  const root = document.querySelector('.knowledge-search')
  if (root) {
    if (mode === 'chat') {
      root.classList.add('chat-mode')
    } else {
      root.classList.remove('chat-mode')
    }
  }
  if (mode === 'chat') {
    nextTick(() => {
      if (chatInputRef.value) chatInputRef.value.focus()
    })
  }
}

// ============ 聊天功能 ============

// 发送聊天消息
async function sendChatMessage(preset) {
  const text = preset || chatInput.value.trim()
  if (!text || chatLoading.value) return

  // 添加用户消息
  chatMessages.value.push({
    role: 'user',
    content: text,
  })

  chatInput.value = ''
  if (chatInputRef.value) {
    chatInputRef.value.style.height = 'auto'
  }

  // 添加助手占位消息
  const assistantIdx = chatMessages.value.length
  chatMessages.value.push({
    role: 'assistant',
    content: '',
    loading: true,
    thinking: true,  // 等待首个chunk的"思考中"状态
  })

  chatLoading.value = true
  scrollToBottom()

  try {
    const response = await fetch('/api/v1/knowledge/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: text,
        session_id: chatSessionId.value || undefined,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const dataStr = line.slice(6)
          try {
            const data = JSON.parse(dataStr)
            if (currentEvent === 'text' && data.content !== undefined) {
              chatMessages.value[assistantIdx].content += data.content
              chatMessages.value[assistantIdx].thinking = false  // 收到首个chunk，关闭思考状态
              // 注意：流式期间保持 loading=true，避免 renderMarkdown 做图片渲染导致截断乱码
              scrollToBottom()
            } else if (currentEvent === 'done') {
              if (data.session_id) chatSessionId.value = data.session_id
              chatMessages.value[assistantIdx].loading = false
              chatMessages.value[assistantIdx].thinking = false
            } else if (currentEvent === 'error') {
              chatMessages.value[assistantIdx].content = `抱歉，出错了：${data.message || '未知错误'}`
              chatMessages.value[assistantIdx].loading = false
              chatMessages.value[assistantIdx].thinking = false
            }
          } catch (e) {
            // 忽略 JSON 解析错误
          }
          currentEvent = ''
        }
      }
    }

    // 确保加载状态关闭
    chatMessages.value[assistantIdx].loading = false
    chatMessages.value[assistantIdx].thinking = false
  } catch (e) {
    chatMessages.value[assistantIdx].content = `网络错误：${e.message}`
    chatMessages.value[assistantIdx].loading = false
    chatMessages.value[assistantIdx].thinking = false
  } finally {
    chatLoading.value = false
    scrollToBottom()
  }
}

// 聊天 Enter 键处理
function handleChatEnter(e) {
  if (e.shiftKey) return // Shift+Enter 换行
  e.preventDefault()
  sendChatMessage()
}

// 自动调整 textarea 高度
function autoResizeTextarea() {
  const el = chatInputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    const container = chatMessagesRef.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

// 简单的 Markdown 渲染（加粗、换行、图片、代码块）
// 使用占位符策略避免图片 URL 被重复处理
// 注意：流式输出时不做图片渲染，避免标签被截断导致乱码
function renderMarkdown(text, showLoading = false) {
  if (!text && !showLoading) return ''
  if (!text) text = ''

  // 流式输出中（showLoading=true），只做最基础的文本渲染，避免标签截断
  if (showLoading) {
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>')
    html += '<span class="message-loading"><span class="loading-dot"></span><span class="loading-dot"></span><span class="loading-dot"></span></span>'
    return html
  }

  // ===== 完整渲染（消息已完成） =====

  // 第1步：提取 Markdown 图片语法 ![alt](url)，替换为占位符
  const imagePlaceholders = []
  let html = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    const idx = imagePlaceholders.length
    imagePlaceholders.push({ alt, url })
    return `\x00IMG${idx}\x00`
  })

  // 第2步：提取裸图片 URL
  // 匹配：1) 标准图片后缀结尾  2) 阿里云OSS域名（含.oss-cn-）上的URL
  html = html.replace(/(\/api\/v1\/[^\s]+\.(?:jpg|jpeg|png|gif|webp|svg)(?:\?[^\s]*)?|https?:\/\/[^\s]*?\.oss-cn-[^\s]+|https?:\/\/[^\s]+\.(?:jpg|jpeg|png|gif|webp|svg)(?:\?[^\s]*)?)/gi, (match, url) => {
    const idx = imagePlaceholders.length
    imagePlaceholders.push({ alt: '', url })
    return `\x00IMG${idx}\x00`
  })

  // 第3步：按行处理（标题、列表、分隔线需要在行首识别）
  const lines = html.split('\n')
  const processedLines = lines.map(line => {
    let l = line
    // 分隔线 ---（3个以上连字符，行首）
    if (/^---+$/.test(l.trim())) {
      return '<hr class="chat-hr">'
    }
    // 标题 ### / ## / #（行首）
    if (l.startsWith('### ')) {
      l = '<h4 class="chat-heading">' + l.slice(4) + '</h4>'
      return l
    }
    if (l.startsWith('## ')) {
      l = '<h3 class="chat-heading">' + l.slice(3) + '</h3>'
      return l
    }
    if (l.startsWith('# ')) {
      l = '<h2 class="chat-heading">' + l.slice(2) + '</h2>'
      return l
    }
    // 无序列表 - item（行首）
    if (l.startsWith('- ')) {
      l = '<div class="chat-list-item"><span class="chat-list-bullet">&bull;</span><span>' + l.slice(2) + '</span></div>'
      return l
    }
    return l
  })
  html = processedLines.join('\n')

  // 第4步：转义剩余文本的 HTML（但不碰已生成的标签和占位符）
  // 先保护已有 HTML 标签和占位符（开标签+闭标签都要保护）
  const protectedTokens = []
  html = html.replace(/<\/?(hr|h[2-4])[^>]*>|<\/div>|<div[^>]*>.*?<\/div>|\x00IMG\d+\x00/g, (match) => {
    const idx = protectedTokens.length
    protectedTokens.push(match)
    return `\x00PROT${idx}\x00`
  })
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // 还原保护的标签
  html = html.replace(/\x00PROT(\d+)\x00/g, (match, idxStr) => {
    return protectedTokens[parseInt(idxStr)]
  })

  // 第5步：还原图片占位符为 <img> 标签
  html = html.replace(/\x00IMG(\d+)\x00/g, (match, idxStr) => {
    const { alt, url } = imagePlaceholders[parseInt(idxStr)]
    return `<img src="${url}" alt="${alt}" class="chat-inline-image" onclick="window.__previewChatImage('${url}')" />`
  })

  // 第6步：加粗 **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  // 第7步：行内代码 `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // 第8步：换行（但不在块级元素后加 <br>）
  html = html.replace(/\n/g, '<br>')
  // 清理块级元素后多余的 <br>
  html = html.replace(/<\/(h[2-4]|hr|div)><br>/g, '</$1>')

  return html
}

// 挂载图片预览到 window（供 onclick 调用）
if (typeof window !== 'undefined') {
  window.__previewChatImage = (url) => {
    relatedImagePreviewUrl.value = url
    relatedImagePreviewVisible.value = true
  }
}
</script>

<style scoped>
.knowledge-search {
  min-height: 100vh;
  background: #f8f6f1;
  padding-top: 24px;
}

/* 主内容区 */
.main-container {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.search-area {
  width: 100%;
}

/* 欢迎区 */
.welcome-section {
  text-align: center;
  padding: 60px 0 40px;
}

.welcome-title {
  font-size: 36px;
  font-weight: 700;
  color: #3d3d3d;
  margin-bottom: 12px;
}

.welcome-subtitle {
  font-size: 16px;
  color: #8b7355;
  margin-bottom: 24px;
}

.hot-tags {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tags-label {
  color: #8b7355;
  font-size: 14px;
}

.tag-btn {
  padding: 6px 14px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 20px;
  font-size: 14px;
  color: #5a5a5a;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-btn:hover {
  background: #fff;
  border-color: #c45c48;
  color: #c45c48;
}

/* 搜索框 */
.search-box {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 700px;
  margin: 0 auto 40px;
  padding: 8px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.search-icon {
  width: 20px;
  height: 20px;
  color: #94a3b8;
  margin-left: 12px;
}

.search-input {
  flex: 1;
  padding: 12px 8px;
  border: none;
  font-size: 16px;
  color: #3d3d3d;
  background: transparent;
  outline: none;
}

.search-input::placeholder {
  color: #8b7355;
}

.search-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 24px;
  background: #c45c48;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.search-btn:hover:not(:disabled) {
  background: #a84838;
}

.search-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 搜索进度条 */
.search-progress-container {
  max-width: 700px;
  margin: -30px auto 30px;
  padding: 0 8px;
}

.search-progress-bar {
  height: 4px;
  background: #e8e4dc;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.search-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #c45c48, #e07a65);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.search-progress-text {
  font-size: 13px;
  color: #8b7355;
  text-align: center;
  display: block;
}

/* 搜索结果 */
.search-results {
  max-width: 800px;
  margin: 0 auto;
}

/* AI 摘要卡片 */
.ai-summary-card {
  background: linear-gradient(135deg, #fffbeb, #fef3c7, #fff7ed);
  border: 1px solid #fcd34d;
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 24px;
  animation: fadeInUp 0.4s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.ai-summary-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.ai-icon {
  width: 20px;
  height: 20px;
  color: #d97706;
  flex-shrink: 0;
}

.ai-summary-title {
  font-size: 15px;
  font-weight: 700;
  color: #92400e;
}

.ai-confidence-badge {
  margin-left: auto;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.ai-confidence-badge.high {
  background: #dcfce7;
  color: #166534;
}

.ai-confidence-badge.medium {
  background: #fef9c3;
  color: #854d0e;
}

.ai-confidence-badge.low {
  background: #f3f4f6;
  color: #6b7280;
}

.ai-summary-content {
  font-size: 14px;
  line-height: 1.9;
  color: #44403c;
  margin-bottom: 14px;
  text-align: justify;
  white-space: pre-wrap;
}

/* 要点列表 */
.ai-key-points {
  margin-bottom: 14px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 8px;
  border: 1px solid rgba(252, 211, 77, 0.3);
}

.key-points-label {
  font-size: 12px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 8px;
}

.key-points-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.key-point-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #44403c;
}

.key-point-bullet {
  color: #d97706;
  font-size: 8px;
  margin-top: 6px;
  flex-shrink: 0;
}

.key-point-text {
  flex: 1;
}

/* 相关概念 */
.ai-concepts {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.concepts-label {
  font-size: 12px;
  color: #92400e;
  font-weight: 500;
}

.concept-tag {
  padding: 2px 10px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid #fbbf24;
  border-radius: 12px;
  font-size: 12px;
  color: #92400e;
  cursor: pointer;
  transition: all 0.2s;
}

.concept-tag:hover {
  background: #fbbf24;
  color: #451a03;
  border-color: #f59e0b;
}

/* 相关配图 */
.ai-related-images {
  margin-bottom: 14px;
}

.related-images-label {
  font-size: 12px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 10px;
}

.related-images-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}

.related-image-card {
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(252, 211, 77, 0.3);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.related-image-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: #f59e0b;
}

.related-image-thumb {
  width: 100%;
  height: 100px;
  object-fit: cover;
  display: block;
}

.related-image-info {
  padding: 6px 8px;
}

.related-image-label {
  font-size: 11px;
  color: #78350f;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.ai-sources {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 10px;
  border-top: 1px dashed #fbbf24;
}

.sources-label {
  font-size: 12px;
  color: #92400e;
  font-weight: 500;
}

.source-tag {
  padding: 3px 10px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid #fcd34d;
  border-radius: 6px;
  font-size: 12px;
  color: #78350f;
  cursor: pointer;
  transition: all 0.2s;
}

.source-tag:hover {
  background: #fcd34d;
  color: #451a03;
  border-color: #f59e0b;
}

/* 搜索结果高亮动画 */
.result-highlight {
  animation: highlightPulse 2s ease-out;
  border-color: #f59e0b !important;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.3);
}

@keyframes highlightPulse {
  0% { box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.5); }
  30% { box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.3); }
  100% { box-shadow: none; }
}

.ai-rewrites {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.rewrites-label {
  font-size: 12px;
  color: #92400e;
  font-weight: 500;
}

.rewrite-tag {
  padding: 2px 10px;
  background: transparent;
  border: 1px dashed #d97706;
  border-radius: 12px;
  font-size: 12px;
  color: #b45309;
  cursor: pointer;
  transition: all 0.2s;
}

.rewrite-tag:hover {
  background: #fbbf24;
  border-style: solid;
  color: #78350f;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.results-count {
  font-size: 14px;
  color: #8b7355;
}

.clear-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 13px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: #f8f6f1;
  color: #3d3d3d;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  padding: 16px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  transition: all 0.2s;
  cursor: pointer;
}

.result-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #c45c48;
}

/* 图像结果卡片特殊样式 */
.result-item.result-image-card {
  padding: 12px;
}

.result-image-layout {
  display: flex;
  gap: 14px;
}

.result-image-preview {
  width: 120px;
  height: 90px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  background: #f8f6f1;
}

.result-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-image-card .result-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.image-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.badge-icon {
  width: 12px;
  height: 12px;
}

.image-title {
  font-size: 15px;
  font-weight: 600;
  color: #3d3d3d;
  margin: 6px 0;
}

.image-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  flex: 1;
}

/* 类型标记 */
.result-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

/* 内容区 */
.result-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-chapter {
  font-size: 14px;
  font-weight: 600;
  color: #c45c48;
  padding: 4px 10px;
  background: #fef2f2;
  border-radius: 4px;
}

.result-page {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8b7355;
}

.page-icon {
  width: 14px;
  height: 14px;
}

.result-score-badge {
  padding: 4px 10px;
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  color: #166534;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.result-score-badge.high {
  background: linear-gradient(135deg, #dcfce7, #86efac);
  color: #166534;
}

.result-score-badge.medium {
  background: linear-gradient(135deg, #fef9c3, #fde047);
  color: #854d0e;
}

.result-score-badge.low {
  background: linear-gradient(135deg, #fee2e2, #fca5a5);
  color: #991b1b;
}

.result-content {
  font-size: 14px;
  line-height: 1.8;
  color: #3d3d3d;
  margin-bottom: 12px;
  flex: 1;
  text-align: justify;
}

.context-ellipsis {
  color: #94a3b8;
  font-style: italic;
}

.highlight-text {
  color: #1e293b;
}

.fade-out {
  color: #cbd5e1;
}

.result-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  padding-top: 10px;
  border-top: 1px dashed #e8e4dc;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.result-book {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #64748b;
}

.book-icon {
  width: 14px;
  height: 14px;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chunk-index {
  padding: 2px 8px;
  background: #f1f5f9;
  color: #64748b;
  border-radius: 4px;
  font-size: 11px;
}

.view-detail {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #c45c48;
  font-weight: 500;
  transition: all 0.2s;
  padding: 4px 8px;
  border-radius: 4px;
}

.result-item:hover .view-detail {
  background: #fef2f2;
}

.view-icon {
  width: 16px;
  height: 16px;
}

.no-results {
  text-align: center;
  padding: 60px 20px;
  color: #8b7355;
}

.no-results-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  opacity: 0.5;
}

/* 右侧面板（已废弃，内容移至 below-panel） */
.side-panel {
  display: none;
}

/* 下方工具面板 */
.below-panel {
  width: 100%;
  margin: 32px auto 0;
}

.panel-cards-grid {
  display: grid;
  grid-template-columns: 30% 30% 40%;
  gap: 16px;
}

.panel-card {
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  padding: 16px;
}

.panel-card .upload-btn {
  padding: 10px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 12px;
}

.stats-row {
  display: flex;
  gap: 8px;
}

.stat-chip {
  flex: 1;
  text-align: center;
  padding: 8px 4px;
  background: #f8f6f1;
  border-radius: 8px;
}

.stat-value-sm {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #c45c48;
}

.stat-label-sm {
  font-size: 11px;
  color: #8b7355;
}

.panel-section {
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.upload-section {
  padding: 0;
  border: none;
  background: transparent;
}

.upload-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  background: #c45c48;
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-btn:hover {
  background: #a84838;
}

.upload-icon {
  font-size: 18px;
  font-weight: 300;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #3d3d3d;
  margin-bottom: 0;
}

.panel-header-with-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 12px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #f8f6f1;
  color: #3d3d3d;
}

.clear-all-btn:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #991b1b;
}

.icon-tiny {
  width: 12px;
  height: 12px;
}

.panel-icon {
  width: 18px;
  height: 18px;
  color: #8b7355;
}

.book-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.book-item-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 8px;
  transition: all 0.2s;
}

.book-item-wrapper:hover {
  background: #f8fafc;
}

.book-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  cursor: pointer;
}

.book-item input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #c45c48;
}

.book-name {
  font-size: 14px;
  color: #5a5a5a;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}

.book-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.book-status-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  flex-shrink: 0;
}

.book-status-tag.completed {
  background: #f0fdf4;
  color: #16a34a;
}

.book-status-tag.processing {
  background: #fef3c7;
  color: #d97706;
}

.book-status-tag.failed {
  background: #fef2f2;
  color: #dc2626;
}

.reingest-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 4px 2px 36px;
}

.progress-bar-track {
  flex: 1;
  height: 6px;
  background: #e8e4df;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #c45c48, #d4956a);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.progress-text {
  font-size: 11px;
  color: #8b7355;
  white-space: nowrap;
  min-width: 80px;
}

.book-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.action-icon-btn:hover:not(:disabled) {
  background: #f1f5f9;
}

.reingest-btn:hover:not(:disabled) {
  background: #fef3c7;
  color: #d97706;
}

.delete-btn:hover:not(:disabled) {
  background: #fee2e2;
  color: #ef4444;
}

.action-icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.icon-small {
  width: 14px;
  height: 14px;
}

.book-list-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 6px;
  font-size: 12px;
  color: #0369a1;
}

.hint-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-item-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 8px;
  transition: all 0.2s;
}

.history-item-wrapper:hover {
  background: #f8f6f1;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  padding: 8px;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  color: #5a5a5a;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.history-item:hover {
  color: #c45c48;
}

.history-icon {
  width: 14px;
  height: 14px;
  color: #8b7355;
  flex-shrink: 0;
}

.history-query {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-history-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #94a3b8;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
}

.history-item-wrapper:hover .delete-history-btn {
  opacity: 1;
}

.delete-history-btn:hover {
  background: #fee2e2;
  color: #ef4444;
}

.empty-text {
  font-size: 13px;
  color: #8b7355;
  text-align: center;
  padding: 16px 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8f6f1;
  border-radius: 8px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #c45c48;
}

.stat-label {
  font-size: 12px;
  color: #8b7355;
}

/* 响应式 */
@media (max-width: 768px) {
  .panel-cards-grid {
    grid-template-columns: 1fr;
  }
}

/* 相关配图预览浮层 */
.image-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: pointer;
}

.image-preview-overlay .preview-image {
  max-width: 85vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.image-preview-overlay .preview-close {
  position: absolute;
  top: 20px;
  right: 20px;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: white;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.image-preview-overlay .preview-close:hover {
  background: rgba(255, 255, 255, 0.3);
}

.image-preview-overlay .preview-close .icon {
  width: 20px;
  height: 20px;
}

/* ============ Tab 切换 ============ */
.mode-tabs {
  display: flex;
  gap: 4px;
  max-width: 700px;
  margin: 0 auto 24px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  padding: 4px;
  position: relative;
}

.mode-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #8b7355;
  background: transparent;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;
}

.mode-tab:hover {
  color: #5a5a5a;
  background: #f8f6f1;
}

.mode-tab.active {
  background: #c45c48;
  color: #fff;
  box-shadow: 0 2px 8px rgba(196, 92, 72, 0.3);
  transform: scale(1.02);
}

.tab-icon {
  width: 16px;
  height: 16px;
  transition: transform 0.3s;
}

.mode-tab.active .tab-icon {
  transform: rotate(10deg) scale(1.1);
}

/* Tab 切换过渡动效（CSS animation 方式） */
.mode-panel {
  animation: modeFadeIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes modeFadeIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ============ 聊天界面（专家模式隐藏浏览器滚动条） ============ */
.knowledge-search.chat-mode {
  overflow: hidden;
  height: 100vh;
}

.chat-container {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 180px);
  min-height: 500px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px 20px 0;
  scroll-behavior: smooth;
}

/* 聊天区自定义滚动条 */
.chat-messages::-webkit-scrollbar {
  width: 5px;
}
.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}
.chat-messages::-webkit-scrollbar-thumb {
  background: #d4cfc5;
  border-radius: 3px;
}
.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #b0aea5;
}

/* 聊天欢迎区 */
.chat-welcome {
  text-align: center;
  padding: 60px 20px 40px;
  animation: fadeInUp 0.5s ease-out;
}

.chat-welcome-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, #fef3c7, #fbbf24);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: floatIcon 3s ease-in-out infinite;
}

@keyframes floatIcon {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

.welcome-sparkle {
  width: 28px;
  height: 28px;
  color: #92400e;
}

.chat-welcome-title {
  font-size: 24px;
  font-weight: 700;
  color: #3d3d3d;
  margin-bottom: 8px;
}

.chat-welcome-desc {
  font-size: 14px;
  color: #8b7355;
  margin-bottom: 24px;
}

.chat-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 480px;
  margin: 0 auto;
}

.suggestion-btn {
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 10px;
  font-size: 14px;
  color: #5a5a5a;
  cursor: pointer;
  text-align: left;
  transition: all 0.25s;
  line-height: 1.5;
}

.suggestion-btn:hover {
  border-color: #c45c48;
  color: #c45c48;
  background: #fef2f2;
  transform: translateX(4px);
}

/* 消息气泡 */
.chat-message {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  animation: fadeInUp 0.3s ease-out;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.chat-message.user .message-avatar {
  background: #c45c48;
}

.chat-message.assistant .message-avatar {
  background: linear-gradient(135deg, #fef3c7, #fbbf24);
}

.avatar-icon {
  width: 16px;
  height: 16px;
}

.chat-message.user .avatar-icon {
  color: #fff;
}

.chat-message.assistant .avatar-icon {
  color: #92400e;
}

.message-content {
  max-width: 78%;
  min-width: 0;
}

.chat-message.user .message-content {
  text-align: right;
}

.message-role {
  font-size: 11px;
  color: #8b7355;
  margin-bottom: 4px;
  font-weight: 500;
}

.message-text {
  font-size: 14px;
  line-height: 1.8;
  color: #3d3d3d;
  text-align: left;
  word-break: break-word;
}

.chat-message.user .message-text {
  background: #c45c48;
  color: #fff;
  padding: 10px 16px;
  border-radius: 16px 16px 4px 16px;
  display: inline-block;
  text-align: left;
}

.chat-message.assistant .message-text {
  background: #fff;
  border: 1px solid #e8e4dc;
  padding: 12px 16px;
  border-radius: 16px 16px 16px 4px;
  min-height: 20px;
  overflow: hidden;
}

.chat-message.assistant .message-text code {
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* 聊天中图片 */
.chat-inline-image {
  max-width: 100%;
  width: auto;
  max-height: 280px;
  border-radius: 8px;
  margin: 8px 0;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: block;
  object-fit: contain;
}

.chat-inline-image:hover {
  transform: scale(1.02);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

/* 聊天 Markdown 标题 */
.message-text .chat-heading {
  font-size: 15px;
  font-weight: 700;
  color: #3d3d3d;
  margin: 12px 0 6px;
  padding: 0;
  line-height: 1.5;
}

.message-text h2.chat-heading {
  font-size: 17px;
  margin-top: 14px;
}

.message-text h3.chat-heading {
  font-size: 16px;
  margin-top: 12px;
}

/* 聊天列表项 */
.message-text .chat-list-item {
  display: flex;
  gap: 8px;
  padding: 2px 0;
  line-height: 1.7;
}

.message-text .chat-list-bullet {
  color: #c45c48;
  font-size: 12px;
  flex-shrink: 0;
  margin-top: 2px;
}

/* 聊天分隔线 */
.message-text .chat-hr {
  border: none;
  border-top: 1px solid #e8e4dc;
  margin: 12px 0;
}

/* 思考中提示 */
.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8b7355;
  font-size: 14px;
  animation: thinkingPulse 1.5s ease-in-out infinite;
}

.thinking-icon {
  display: flex;
  align-items: center;
  color: #d97706;
  animation: thinkingSpin 2s linear infinite;
}

@keyframes thinkingPulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

@keyframes thinkingSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 加载动画（在气泡内） */
.message-text .message-loading {
  display: inline-flex;
  gap: 5px;
  padding: 4px 0;
  vertical-align: middle;
  margin-left: 2px;
}

.message-text .loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #c45c48;
  display: inline-block;
  animation: loadingBounce 1.4s infinite ease-in-out both;
}

.message-text .loading-dot:nth-child(1) { animation-delay: 0s; }
.message-text .loading-dot:nth-child(2) { animation-delay: 0.16s; }
.message-text .loading-dot:nth-child(3) { animation-delay: 0.32s; }

@keyframes loadingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 输入区 */
.chat-input-area {
  padding: 12px 0 4px;
  border-top: 1px solid #e8e4dc;
}

.chat-input-box {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: #fff;
  border: 2px solid #e8e4dc;
  border-radius: 14px;
  padding: 10px 10px 10px 16px;
  transition: border-color 0.25s, box-shadow 0.25s;
}

.chat-input-box:focus-within {
  border-color: #c45c48;
  box-shadow: 0 0 0 3px rgba(196, 92, 72, 0.12);
}

.chat-textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  color: #3d3d3d;
  background: transparent;
  max-height: 150px;
  min-height: 44px;
  font-family: inherit;
}

.chat-textarea::placeholder {
  color: #b0aea5;
}

.chat-send-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: #c45c48;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.chat-send-btn:hover:not(:disabled) {
  background: #a84838;
  transform: scale(1.05);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-icon {
  width: 18px;
  height: 18px;
}

.chat-input-hint {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 6px 4px;
}

.hint-text {
  font-size: 11px;
  color: #b0aea5;
}
</style>
