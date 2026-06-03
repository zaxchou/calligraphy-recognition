﻿﻿﻿﻿<template>
<div class="ks-root" data-chat-v="2">

  <transition name="view-switch" mode="out-in">
  <div v-if="centered" key="center" class="ks-center-wrap">
    <div class="ks-center-body">
      <h1 class="ks-center-title">写意知识库</h1>
      <p class="ks-center-sub">潘天寿构图法则 · 写意花鸟画技法</p>
      <div class="ks-center-search">
        <Search class="ks-search-icon" />
        <input v-model="searchInput" type="text" class="ks-center-input" placeholder="搜索写意花鸟画、潘天寿构图法则等专业知识..." @keyup.enter="performSearch" :disabled="store.searchLoading" ref="searchInputRef" @input="centered=true" />
        <button class="ks-search-btn" @click="performSearch" :disabled="store.searchLoading"><Loader2 v-if="store.searchLoading" class="icon spin" /><span v-else>搜索</span></button>
      </div>
      <div class="ks-mode-row">
        <button :class="['ks-mode-pill',{active:activeMode==='search'}]" @click="activeMode='search'"><Search class="icon-xs" /> 搜索模式</button>
        <button v-if="siteConfig.readonly !== 'true' || authStore.isLoggedIn" :class="['ks-mode-pill',{active:activeMode==='chat'}]" @click="switchMode('chat')"><MessageCircle class="icon-xs" /> 小墨</button>
        <button class="ks-mode-pill ks-mode-pill-icon" @click="switchMode('lib')" :class="{active:libOpen}" title="书库管理"><BookOpen class="icon-xs" /></button>
      </div>
      <div class="ks-tags"><span class="ks-tag-label">搜索历史：</span><button v-for="t in store.searchHistory.slice(0,8)" :key="t.id" class="ks-tag" @click="searchByTag(t.query)">{{ t.query }}</button></div>
    </div>
  </div>

  <div v-else-if="activeMode==='search'" key="search" class="ks-search-view" :class="{'with-panel':rightPanelOpen}">
    <header class="ks-bar"><h1 class="ks-bar-title">写意知识库</h1>
      <div class="ks-bar-search"><Search class="ks-search-icon" /><input v-model="searchInput" type="text" class="ks-bar-input" placeholder="搜索专业知识..." @keyup.enter="performSearch" :disabled="store.searchLoading" />
        <button v-if="searchInput" class="ks-bar-clear" @click="clearSearch"><X class="icon-sm" /></button>
        <button class="ks-search-btn" @click="performSearch" :disabled="store.searchLoading"><Loader2 v-if="store.searchLoading" class="icon spin" /><span v-else>搜索</span></button>
      </div>
      <button class="ks-barlib-btn" @click="toggleLib" :class="{active:libOpen}" title="书库管理"><BookOpen class="icon-sm" /></button>
    </header>
    <div class="ks-mode-row ks-mode-row-inline"><button :class="['ks-mode-pill',{active:true}]" @click="goCentered"><Search class="icon-xs" /> 搜索模式</button><button v-if="siteConfig.readonly !== 'true' || authStore.isLoggedIn" :class="['ks-mode-pill']" @click="switchMode('chat')"><MessageCircle class="icon-xs" /> 小墨</button></div>
    <div class="ks-body-wrap" :class="{'with-panel':rightPanelOpen}">
      <div class="ks-main">
        <div class="ks-search-panel">
          <div v-if="store.searchLoading" class="ks-progress"><div class="ks-progress-fill" :style="{width:store.searchProgress+'%'}"></div></div>
          <div v-if="store.aiSummary?.answer" class="ks-card"><div class="ks-card-hd"><Sparkles class="ks-summary-spark" /><span>AI概述</span><span class="ks-summary-conf" :class="'conf-'+getConfClass(store.aiSummary.confidence)">{{ getConfLabel(store.aiSummary.confidence) }}</span></div>
            <div class="ks-card-body" v-html="renderCitations(store.aiSummary.answer)" @click="onCitationClick($event)"></div>
            <div v-if="store.relatedImages?.length" class="ks-related-img-row"><div v-for="(ri,i) in store.relatedImages.slice(0,6)" :key="ri.url" class="ks-related-img-thumb" @click="openImagePreview(ri,store.relatedImages.slice(0,6),i)"><img :src="getImageUrl(ri.stored_url||ri.url)" /><span>{{ ri.display_label||ri.figure_id||'' }}</span></div></div>
            <div v-if="store.aiSummary.key_points?.length" class="ks-points"><div class="ks-points-label">核心要点</div><ul><li v-for="(p,i) in store.aiSummary.key_points" :key="i">{{ cleanLatex(p) }}</li></ul></div>
            <div v-if="store.aiSummary.sources?.length" class="ks-sources"><span class="ks-sources-label">参考来源：</span><button v-for="(s,i) in store.aiSummary.sources" :key="i" class="ks-src" @click="scrollToResult(s)">《{{ (s.book||'').replace(/[《》]/g,'') }}》p.{{ s.page||'?' }}</button></div>
          </div>
          <div v-if="hasSearched&&!store.searchLoading" class="ks-results">
            <div class="ks-rbar"><span>共{{ store.searchResults.length }}条结果</span><button class="ks-clear-btn" @click="clearSearch">清除</button></div>
            <div v-if="store.searchResults.length===0" class="ks-empty"><FileSearch class="ks-empty-icon" /><p>未找到相关结果</p></div>
            <div class="ks-rlist"><div v-for="(r,i) in store.searchResults" :key="r.chunk_id||r.vector_id||i" :class="['ks-rcard',{'active':highlightedIndex===i,'img':r.result_type==='image'}]" :style="{animationDelay:`${i*0.06}s`}" @click="openDetail(r,i)">
              <template v-if="r.result_type==='image'"><div class="ks-rimg"><img :src="getImageUrl(r.image?.stored_url||r.image?.url||r.associated_images?.[0]?.stored_url||r.associated_images?.[0]?.url)" /></div><div class="ks-rbody"><div class="ks-rhead"><span class="ks-badge"><ImageIcon class="icon-xs" />配图</span><span class="ks-rscore" :class="getScoreClass(r.score)">{{ formatScore(r.score) }}%</span></div><div class="ks-rfoot"><span>{{ r.book_title }}</span><span class="ks-raction">查看大图 <ChevronRight class="icon-xs" /></span></div></div>
    <!-- Citation Modal -->
    <div v-if="citationModal.show" class="citation-overlay" @click="closeCitation">
      <div class="citation-modal" @click.stop>
        <div class="citation-modal-header">
          <span class="citation-modal-title">????</span>
          <button class="citation-modal-close" @click="closeCitation">&times;</button>
        </div>
        <div class="citation-modal-body">
          <div class="citation-modal-row"><span class="citation-modal-label">??</span><span class="citation-modal-value">{{ citationModal.source.book }}</span></div>
          <div v-if="citationModal.source.page" class="citation-modal-row"><span class="citation-modal-label">??</span><span class="citation-modal-value">?{{ citationModal.source.page }}?</span></div>
          <div v-if="citationModal.source.chapter" class="citation-modal-row"><span class="citation-modal-label">??</span><span class="citation-modal-value">{{ citationModal.source.chapter }}</span></div>
          <div v-if="citationModal.source.snippet" class="citation-modal-row"><span class="citation-modal-label">??</span><span class="citation-modal-value citation-snippet">{{ citationModal.source.snippet }}</span></div>
          <div v-if="citationModal.source.url" class="citation-modal-row">
            <span class="citation-modal-label">??</span>
            <a :href="'#'+citationModal.source.url" class="citation-modal-link" @click="closeCitation">{{ citationModal.source.name || citationModal.source.book }} &rarr;</a>
          </div>
        </div>
      </div>
    </div>

</template>
              <template v-else-if="r.result_type==='table'"><TableResultCard :result="r" @click="openDetail(r,i)" /></template>
              <template v-else><div class="ks-rbody"><div class="ks-rhead"><span class="ks-rchap">{{ getChapter(r) }}</span><span v-if="r.source==='private'" class="ks-source-badge private" title="私人文档">📁</span><span v-else class="ks-source-badge public" title="公共知识库">📚</span><span class="ks-rscore" :class="getScoreClass(r.score)">{{ formatScore(r.score) }}%</span></div><p class="ks-rsnip" v-html="highlightSnippet(r)"></p><div class="ks-rfoot"><span><BookOpen class="icon-xs" />{{ r.book_title }}·p.{{ r.page_start||'?' }}</span><span class="ks-raction">查看原文 <ChevronRight class="icon-xs" /></span></div></div></template>
            </div></div>
          </div>
        </div>
      </div>
      <transition name="slide-right"><div v-if="rightPanelOpen" class="ks-panel">
        <div class="ks-phdr"><span class="ks-ptitle">{{ activeResult?.book_title||'文档查看' }}</span><div class="ks-phdr-acts"><button v-if="pdfUrl" class="ks-pdf-btn" @click="openPdf"><FileDown class="icon-sm" />PDF</button><button class="ks-pclose" @click="closePanel"><X class="icon" /></button></div></div>
        <div class="ks-pbody">
          <div v-if="activeResult?.result_type==='image'" class="ks-pimg"><img :src="getFullImageUrl(activeResult)" class="ks-pimg-main" @click="openImagePreview(activeResult.image||activeResult.associated_images?.[0],activeResult.associated_images,0)" /><ImageRelatedChunks v-if="activeResult.image?.id" :chunks="relatedChunks" :loading="loadingRelated" @chunk-click="onRelatedClick" /></div>
          <div v-if="activeResult?.result_type!=='image'" class="ks-detail"><div class="ks-dmeta"><span class="ks-dchap">{{ getChapter(activeResult) }}</span><span class="ks-dpage" v-if="activeResult.page_start"><BookOpen class="icon-xs" />第{{ activeResult.page_start }}{{ activeResult.page_end!==activeResult.page_start?'-'+activeResult.page_end:'' }}页</span></div>
            <div v-if="activeResult.context_before" class="ks-dctx"><p class="ks-dctx-txt">{{ cleanLatex(activeResult.context_before) }}</p><div class="ks-dctx-mrk">···上文···</div></div>
            <div class="ks-dcontent" v-html="highlightDetail(activeResult)"></div>
            <div v-if="activeResult.associated_images?.length" class="ks-dims"><div class="ks-dims-label"><ImageIcon class="icon-xs" />关联配图</div><div class="ks-dims-grid"><div v-for="(img,i) in activeResult.associated_images" :key="i" class="ks-dim" @click="openImagePreview(img,activeResult.associated_images,i)"><img :src="getImageUrl(img.stored_url||img.url||img.id)" @error="e=>{e.target.src='/placeholder.png'}" /><span v-if="img.figure_id">{{ img.figure_id }}</span></div></div></div>
            <div v-if="activeResult.context_after" class="ks-dctx"><div class="ks-dctx-mrk">···下文···</div><p class="ks-dctx-txt">{{ cleanLatex(activeResult.context_after) }}</p></div>
            <div class="ks-dnav"><button class="ks-dnav-btn" :disabled="loadingChunk||chunkIndex<=0" @click="loadPrevChunk"><ChevronLeft class="icon-xs" />上一段</button><span class="ks-dnav-info" v-if="chunkIndex>0">第{{ chunkIndex+1 }}段</span><button class="ks-dnav-btn" :disabled="loadingChunk" @click="loadNextChunk">下一段<ChevronRight class="icon-xs" /></button></div>
          </div>
          <div class="ks-ptabs"><button :class="{active:panelTab==='outline'}" @click="panelTab='outline'"><ListTree class="icon-xs" />大纲</button><button v-if="markdownContent" :class="{active:panelTab==='markdown'}" @click="panelTab='markdown'"><FileCode class="icon-xs" />原文</button><button v-if="activeResult?.associated_images?.length" :class="{active:panelTab==='images'}" @click="panelTab='images'"><ImageIcon class="icon-xs" />配图</button></div>
          <div v-show="panelTab==='outline'" class="ks-ptab"><input v-model="outlineFilter" class="ks-outline-filter" placeholder="筛选大纲标题..." /><DocumentOutline :outline="filteredOutline" :loading="loadingOutline" @item-click="onOutlineClick" /></div>
          <div v-show="panelTab==='markdown'" class="ks-ptab" ref="mdContentRef"><MarkdownViewer :markdown="markdownContent" :loading="loadingMarkdown" /></div>
          <div v-show="panelTab==='images'" class="ks-ptab"><div class="ks-pimg-grid"><div v-for="(img,i) in activeResult?.associated_images" :key="i" class="ks-pimg-item" @click="openImagePreview(img,activeResult?.associated_images,i)"><img :src="getImageUrl(img.stored_url||img.url||img.id)" /><span v-if="img.figure_id">{{ img.figure_id }}</span></div></div></div>
        </div>
      </div></transition>
    </div>
  </div>

  <div v-else key="chat" class="ks-chat-shell">
    <transition name="sidebar-slide">
      <ChatSidebar
        v-if="sidebarOpen"
        :sessions="chatStore.sessions"
        :activeId="chatStore.currentSessionId"
        @newChat="startNewChat"
        @select="selectSession"
        @delete="deleteSession"
      />
    </transition>
    <div class="ks-chat-main">
      <div class="ks-chat-topbar">
        <button class="ks-sidebar-toggle" @click="sidebarOpen=!sidebarOpen" :title="sidebarOpen?'收起侧栏':'展开侧栏'">
          <PanelLeft v-if="sidebarOpen" class="icon-sm" />
          <PanelLeftOpen v-else class="icon-sm" />
        </button>
        <span class="ks-chat-title">小墨</span>
        <div class="ks-chat-topbar-right">
          <button class="ks-back-btn" @click="goCentered"><ChevronLeft class="icon-xs" /> 返回搜索</button>
          <button :class="['ks-mode-pill-sm',{active:activeMode==='search'}]" @click="goCentered"><Search class="icon-xs" /> 搜索</button>
          <button class="ks-mode-pill-sm ks-mode-pill-icon-sm" @click="toggleLib" :class="{active:libOpen}" title="书库管理"><BookOpen class="icon-xs" /></button>
        </div>
      </div>
      <div class="ks-chat-body">
        <div class="ks-chat-msgs" ref="chatMsgsRef">
          <div v-if="chatMessages.length===0" class="ks-chat-welcome"><Sparkles class="ks-chat-welcome-icon" /><h3>小墨</h3><p>基于专业知识库，解答写意花鸟画、构图法则、笔墨技法等问题</p><div class="ks-chat-sugs"><button v-for="s in chatSuggestions" :key="s" class="ks-sug-btn" @click="sendChat(s)">{{ s }}</button></div></div>
          <div v-for="(m,i) in chatMessages" :key="m.id||i" :class="['ks-cmsg',m.role]">
            <div class="ks-ccontent">
              <div v-if="m.thinking" class="ks-cthinking"><Sparkles class="icon-xs" />思考中...</div>
              <div v-else class="ks-ctext" @click="onChatContentClick" v-html="renderCitations(renderMd(m.content,m.loading))"></div>
              <div v-if="m.role==='assistant'&&m.sources&&m.sources.length" class="ks-csources"><div class="ks-csrc-title">📖 引用来源</div><div v-for="s in m.sources" :key="s.index" class="ks-csrc-item" @click="citationSource=s" style="cursor:pointer"><span class="ks-csrc-idx">[{{ s.index }}]</span><template v-if="s._source==='database'||s.url"><a class="ks-csrc-link" :href="chatLink(s.url)" target="_blank" rel="noopener"><span v-if="s.name||s.book" class="ks-csrc-book">{{ s.name||s.book }}</span><ExternalLink class="icon-xs" style="width:12px;height:12px;vertical-align:middle;margin-left:2px" /></a></template><template v-else><span class="ks-csrc-book">{{ s.book }}</span><span v-if="s.page" class="ks-csrc-page">第{{ s.page }}页</span></template><span v-if="s.snippet" class="ks-csrc-snip">"{{ s.snippet }}"</span></div></div>
            </div>
          </div>
        </div>
        <div class="ks-chat-input-row">
          <div class="ks-chat-input-wrap">
            <textarea ref="chatInputRef" v-model="chatInput" class="ks-chat-ta" placeholder="向小墨提问..." @keydown.enter.exact.prevent="sendChat()" @input="autoResize" rows="1" :disabled="chatLoading"></textarea>
            <button class="ks-chat-send" @click="sendChat()" :disabled="!chatInput.trim()||chatLoading">
              <Send v-if="!chatLoading" class="icon-sm" />
              <Loader2 v-else class="icon-sm spin" />
            </button>
          </div>
          <p class="ks-chat-footnote">回答基于知识库内容，可能需要核实重要信息</p>
        </div>
      </div>
    </div>
  </div>
  </transition>

  <transition name="drop"><div v-if="libOpen" class="ks-lib-pop">
    <div class="ks-lib-inner"><div class="ks-lib-row"><button class="ks-upload-btn" @click="showUploadModal=true"><span class="ks-upload-icon">+</span>上传PDF</button><div class="ks-lib-stats" v-if="store.stats"><span>{{ store.stats.books?.total||0 }}书</span><span>{{ store.stats.contents?.chunks||0 }}块</span><span>{{ store.stats.contents?.images||0 }}图</span></div></div>
      <div class="ks-lib-books" v-if="store.books.length"><div v-for="b in store.books" :key="b.id" class="ks-lib-book"><label class="ks-lib-bl"><input type="checkbox" v-model="selectedBooks" :value="b.id" :disabled="b.status==='processing'" /><span class="ks-lib-bn">{{ b.title||b.file_name }}</span><span :class="['ks-lib-bs',b.status]">{{ statusLabel(b.status) }}</span></label><div class="ks-lib-bacts"><button v-if="isAdmin" class="ks-lib-act" @click="reingest(b.id)" :disabled="reingestingId===b.id"><RefreshCw v-if="reingestingId!==b.id" class="icon-xs" /><Loader2 v-else class="icon-xs spin" /></button><button v-if="isAdmin" class="ks-lib-act del" @click="delBook(b.id)"><Trash2 class="icon-xs" /></button></div></div></div>
      <p v-else class="ks-lib-empty">暂无已入库的书籍</p>
    </div>
  </div></transition>

  <UploadModal v-model:visible="showUploadModal" @upload-success="onUploaded" />
  <div v-if="previewVisible" class="ks-preview-overlay" @click="previewVisible=false"><button v-if="previewList.length>1" class="ks-preview-nav ks-preview-prev" @click.stop="prevPreview"><ChevronLeft class="icon" /></button><img :src="previewImageUrl" class="ks-preview-img" @click.stop /><button v-if="previewList.length>1" class="ks-preview-nav ks-preview-next" @click.stop="nextPreview"><ChevronRight class="icon" /></button><button class="ks-preview-close" @click="previewVisible=false"><X class="icon" /></button><span v-if="previewList.length>1" class="ks-preview-counter">{{previewIndex+1}}/{{previewList.length}}</span></div>

  <!-- 引用来源弹窗 -->
  <Teleport to="body">
    <div v-if="citationSource" class="ks-cite-overlay" @click="closeCitation">
      <div class="ks-cite-modal" @click.stop>
        <div class="ks-cite-modal-hd">
          <span class="ks-cite-modal-idx">[{{ citationSource.index }}]</span>
          <span class="ks-cite-modal-title">{{ citationSource.name || citationSource.book || '引用来源' }}</span>
          <button class="ks-cite-modal-close" @click="closeCitation"><X class="icon-sm" /></button>
        </div>
        <div class="ks-cite-modal-body">
          <div v-if="citationSource._source==='database'" class="ks-cite-db">
            <span class="ks-cite-type">{{ {artwork:'画作',artist:'艺术家',seal:'印章'}[citationSource.type]||'实体' }}</span>
            <a v-if="citationSource.url" :href="citationSource.url" target="_blank" rel="noopener" class="ks-cite-go">查看详情 →</a>
          </div>
          <div v-else class="ks-cite-book-info">
            <span v-if="citationSource.book">《{{ citationSource.book }}》</span>
            <span v-if="citationSource.page">第{{ citationSource.page }}页</span>
            <span v-if="citationSource.chapter">· {{ citationSource.chapter }}</span>
          </div>
          <p v-if="citationSource.snippet" class="ks-cite-snippet">"{{ citationSource.snippet }}"</p>
        </div>
      </div>
    </div>
  </Teleport>
</div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, Loader2, BookOpen, ChevronRight, ChevronLeft, Library, RefreshCw, Trash2, X, Sparkles, Image as ImageIcon, MessageCircle, Send, FileSearch, ListTree, FileCode, FileDown, PanelLeft, PanelLeftOpen, ExternalLink } from 'lucide-vue-next'
import { useKnowledgeStore } from '@/stores/knowledgeStore'
import { ElMessage, ElMessageBox } from 'element-plus'
import UploadModal from '@/components/UploadModal.vue'
import TableResultCard from '@/components/TableResultCard.vue'
import { useAuthStore } from '../stores/authStore'
import { siteConfig } from '../config'

const authStore = useAuthStore()
const chatStore = useChatStore()
const isAdmin = computed(() => authStore.isEditor)
const router = useRouter()
const route = useRoute()
import DocumentOutline from '@/components/DocumentOutline.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import ChatSidebar from '@/components/ChatSidebar.vue'
import ImageRelatedChunks from '@/components/ImageRelatedChunks.vue'
import { useChatStore } from '../stores/chatStore'

const store = useKnowledgeStore()
const searchInput = ref(''), hasSearched = ref(false), centered = ref(true), selectedBooks = ref([]), showUploadModal = ref(false), highlightedIndex = ref(-1), reingestingId = ref(null), searchInputRef = ref(null), activeMode = ref('search'), activeResult = ref(null), rightPanelOpen = ref(false), panelTab = ref('outline'), pdfUrl = ref('')
const documentOutline = ref([]), loadingOutline = ref(false), markdownContent = ref(''), loadingMarkdown = ref(false), relatedChunks = ref([]), loadingRelated = ref(false), libOpen = ref(false), previewVisible = ref(false), previewImageUrl = ref(''), previewList = ref([]), previewIndex = ref(0), mdContentRef = ref(null), chunkIndex = ref(0), loadingChunk = ref(false)
const outlineFilter = ref(''), filteredOutline = computed(()=>{var f=outlineFilter.value.trim();if(!f)return documentOutline.value;f=f.toLowerCase();return documentOutline.value.filter(o=>(o.title||'').toLowerCase().includes(f))})
const chatMessages = ref([]), chatInput = ref(''), chatLoading = ref(false), chatMsgsRef = ref(null), chatInputRef = ref(null), sidebarOpen = ref(true), citationSource = ref(null)
const chatSuggestions = ['写意画中的"气韵生动"如何理解？','潘天寿的构图有哪些核心法则？','花鸟画中墨分五色的具体运用','写意与工笔的根本区别是什么？']

function cleanLatex(s){return(s||'').replace(/\$[^$]*\$/g,'').replace(/\\[a-zA-Z]+/g,'').replace(/[\{\}]/g,'')}
function truncateAt(s,n){return s&&s.length>n?s.slice(0,n):(s||'')}
function formatScore(s){return s?Math.round(s*100):0}
function getScoreClass(s){const v=formatScore(s);return v>=95?'s-high':v>=80?'s-mid':'s-low'}
function getChapter(r){return r.chapter||r.section||r.book_title||''}
function getConfClass(c){return c>=0.7?'high':c>=0.4?'mid':'low'}
function getConfLabel(c){return c>=0.7?'高可信':c>=0.4?'中可信':'低可信'}
function statusLabel(s){return s==='completed'?'✓':s==='processing'?'处理中':s==='failed'?'失败':s}
function getImageUrl(u){if(!u)return'';if(u.startsWith('http'))return u;if(u.startsWith('/api/'))return u;if(/^[a-f0-9-]{36}$/.test(u))return'/api/v1/knowledge/images/'+u;return'/api/v1/knowledge/'+u.replace(/^\/+/,'')}
function getFullImageUrl(r){return getImageUrl(r.image?.stored_url||r.associated_images?.[0]?.stored_url)}
function openPdf(){if(pdfUrl.value)window.open(pdfUrl.value,'_blank')}
function onChatContentClick(e) {
  const cite = e.target.closest('.ks-cite')
  console.log('[CITE-DEBUG] click:', e.target.tagName, e.target.className, 'found cite:', !!cite)
  if (cite) {
    const idx = parseInt(cite.getAttribute('data-idx') || cite.textContent.replace(/[\[\]]/g, ''))
        if (idx) {
      const msgs = chatMessages.value
      for (let i = msgs.length - 1; i >= 0; i--) {
        const m = msgs[i]
        if (m.role === 'assistant' && m.sources) {
          const s = m.sources.find(x => x.index === idx)
                    if (s) { citationSource.value = s; console.log('[CITE-DEBUG] citationSource set!'); return }
        }
      }
          }
  }
}
function closeCitation(){citationSource.value=null}
function chatLink(url){if(!url)return'';const m=url.match(/\/tiba\/[a-f0-9-]+/);if(m)return'#'+m[0];const a=url.match(/\/artist\/[^)\s]+/);if(a)return'#'+a[0];return url.startsWith('/')?'#'+url:url}
function renderCitations(t){return(t||'').replace(/\[(\d+)\]/g,'<sup class="ks-cite" data-idx="$1">[$1]</sup>')}
function escapeHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function renderMd(t, l) {
  if (!t) return l ? '<span class="ks-loading-dots">...</span>' : ''
  let h = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  // 标题
  h = h.replace(/^### (.+)$/gm, '<h3 class="ks-md-h3">$1</h3>')
  h = h.replace(/^## (.+)$/gm, '<h2 class="ks-md-h2">$1</h2>')
  h = h.replace(/^# (.+)$/gm, '<h1 class="ks-md-h1">$1</h1>')
  // 分割线
  h = h.replace(/^---$/gm, '<hr class="ks-md-hr">')
  // 引用
  h = h.replace(/^> (.+)$/gm, '<blockquote class="ks-md-quote">$1</blockquote>')
  // Markdown 链接 [text](url) — /tiba/xxx 和 /artist/xxx 转为 Vue Router hash 格式
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
    // 提取路径：支持完整URL（http://xxx/tiba/yyy）和相对路径（/tiba/yyy）
    const tibaMatch = url.match(/\/tiba\/[a-f0-9-]+/)
    const artistMatch = url.match(/\/artist\/[^)\s]+/)
    let href = url
    if (tibaMatch) href = '#' + tibaMatch[0]
    else if (artistMatch) href = '#' + artistMatch[0]
    return `<a href="${href}" target="_blank" rel="noopener">${text}</a>`
  })
  // 行内格式
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/`([^`\n]+)`/g, '<code class="ks-md-inline-code">$1</code>')
  // 无序列表
  h = h.replace(/^- (.+)$/gm, '<li class="ks-md-li">$1</li>')
  h = h.replace(/((?:<li class="ks-md-li">.+<\/li>\n?)+)/g, '<ul class="ks-md-ul">$1</ul>')
  // 有序列表
  h = h.replace(/^(\d+)[.)] (.+)$/gm, '<li class="ks-md-li-ol">$2</li>')
  h = h.replace(/((?:<li class="ks-md-li-ol">.+<\/li>\n?)+)/g, '<ol class="ks-md-ol">$1</ol>')
  // 换行
  h = h.replace(/\n/g, '<br>')
  return h
}

function switchMode(m){
  if(m==='lib'){toggleLib();return}
  // 小墨：未登录时跳转登录页
  if(m==='chat'){
    if(!authStore.isLoggedIn){
      router.push('/login')
      return
    }
    chatStore.fetchSessions()
  }
  centered.value=false
  activeMode.value=m
  libOpen.value=false
}
function toggleLib(){libOpen.value=!libOpen.value}

function goCentered(){centered.value=true;activeMode.value='search';closePanel();searchInput.value='';hasSearched.value=false;store.clearSearchResults();nextTick(()=>searchInputRef.value?.focus());router.replace({name:'KnowledgeSearch'})}

function highlightSnippet(r){
  const b=r.context_before?`<span class="ks-snip-pre">...${escapeHtml(cleanLatex(r.context_before.slice(-30)))}</span>`:'', a=r.context_after?`<span class="ks-snip-post">${escapeHtml(cleanLatex(r.context_after.slice(0,30)))}...</span>`:''
  let c=escapeHtml(cleanLatex(truncateAt(r.content,150)))
  const q=(searchInput.value||store.searchQuery||'').trim()
  if(q)for(const w of q.split(/\s+/).filter(Boolean))c=c.replace(new RegExp(`(${escapeHtml(w).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`,'gi'),'<mark class="ks-hl">$1</mark>')
  return b+`<span class="ks-snip-hl">${c}</span>`+a
}
function highlightDetail(r){
  let c=escapeHtml(cleanLatex(r.content||''));const q=(searchInput.value||store.searchQuery||'').trim()
  if(q)for(const w of q.split(/\s+/).filter(Boolean))c=c.replace(new RegExp(`(${escapeHtml(w).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`,'gi'),'<mark class="ks-hl">$1</mark>')
  return c
}

async function performSearch(){if(!searchInput.value.trim())return;centered.value=false;hasSearched.value=true;highlightedIndex.value=-1;closePanel();activeMode.value='search';await store.search(searchInput.value,{bookIds:selectedBooks.value,limit:20,includePrivate:false});router.replace({name:'KnowledgeSearch',query:{q:searchInput.value.trim()}})}
function searchByTag(t){searchInput.value=t;performSearch()}
function clearSearch(){searchInput.value='';hasSearched.value=false;centered.value=true;store.clearSearchResults();closePanel();nextTick(()=>searchInputRef.value?.focus());router.replace({name:'KnowledgeSearch'})}
function onCitationClick(e){const c=e.target.closest('.ks-cite');if(!c)return;const m=c.textContent.match(/\d+/);if(!m)return;const s=(store.aiSummary?.sources||[])[parseInt(m[0])-1];if(s)scrollToResult(s)}
function scrollToResult(src){var bk=(src.book||'').replace(/[《》]/g,'').trim(),pg=parseInt(src.page)||0;var i=store.searchResults.findIndex(function(r){var rbk=(r.book_title||'').replace(/[《》]/g,'').trim();var rpg=parseInt(r.page_start)||0;return rbk.includes(bk)||bk.includes(rbk)||(rbk&&bk&&rbk.toLowerCase()===bk.toLowerCase())});if(i<0&&pg>0)i=store.searchResults.findIndex(function(r){var rpg=parseInt(r.page_start)||0;return Math.abs(rpg-pg)<=2});if(i>=0)openDetail(store.searchResults[i],i)}
function closePanel(){rightPanelOpen.value=false;activeResult.value=null;pdfUrl.value='';documentOutline.value=[];markdownContent.value='';relatedChunks.value=[];outlineFilter.value=''}
function openDetail(r,i){activeResult.value=r;highlightedIndex.value=i;rightPanelOpen.value=true;panelTab.value='outline';documentOutline.value=[];markdownContent.value='';relatedChunks.value=[];outlineFilter.value='';chunkIndex.value=r.chunk_index??0;const b=r.book_id;if(r.result_type!=='image'&&b){pdfUrl.value=`/api/v1/knowledge/books/${b}/pdf`;loadOutline(b);loadMarkdown(b)}else if(r.result_type==='image'){pdfUrl.value='';if(r.image?.id)loadRelated(r.image.id)}}
async function loadPrevChunk(){if(loadingChunk.value||chunkIndex.value<=0)return;const id=activeResult.value?.book_id;if(!id)return;loadingChunk.value=true;try{const i=chunkIndex.value-1;const r=await fetch(`/api/v1/knowledge/books/${id}/chunks?offset=${i}&limit=1`);if(r.ok){const d=await r.json();if(d.length>0){chunkIndex.value=i;activeResult.value={...activeResult.value,...d[0],chunk_index:i}}}}catch{}finally{loadingChunk.value=false}}
async function loadNextChunk(){if(loadingChunk.value)return;const id=activeResult.value?.book_id;if(!id)return;loadingChunk.value=true;try{const i=(chunkIndex.value??0)+1;const r=await fetch(`/api/v1/knowledge/books/${id}/chunks?offset=${i}&limit=1`);if(r.ok){const d=await r.json();if(d.length>0){chunkIndex.value=i;activeResult.value={...activeResult.value,...d[0],chunk_index:i}}}}catch{}finally{loadingChunk.value=false}}
async function loadOutline(id){loadingOutline.value=true;try{const r=await fetch(`/api/v1/knowledge/books/${id}/outline`);if(r.ok)documentOutline.value=(await r.json()).outline||[]}catch{}finally{loadingOutline.value=false}}
async function loadMarkdown(id){loadingMarkdown.value=true;try{const r=await fetch(`/api/v1/knowledge/books/${id}/markdown`);if(r.ok)markdownContent.value=(await r.json()).markdown||''}catch{}finally{loadingMarkdown.value=false}}
async function loadRelated(id){loadingRelated.value=true;try{const r=await fetch(`/api/v1/knowledge/images/${id}/related-chunks`);if(r.ok)relatedChunks.value=(await r.json()).chunks||[]}catch{}finally{loadingRelated.value=false}}
function onOutlineClick(item){var isCross=item.target_book_id&&item.page&&item.target_book_id!==activeResult.value?.book_id;if(!isCross&&item.title&&markdownContent.value){panelTab.value='markdown';nextTick(()=>{if(mdContentRef.value){const el=mdContentRef.value.querySelector(`[data-section-id="${item.id}"]`)||[...mdContentRef.value.querySelectorAll('h1,h2,h3,h4')].find(h=>h.textContent?.trim()===item.title?.trim());if(el)el.scrollIntoView({behavior:'smooth',block:'start'})}})};if(isCross){window.open(`/api/v1/knowledge/books/${item.target_book_id}/pdf#page=${item.page}`,'_blank')}else if(item.page&&pdfUrl.value&&!item.target_book_id){window.open(`${pdfUrl.value}#page=${item.page}`,'_blank')}}
async function sendChat(msg) {
  const t = (msg || chatInput.value).trim()
  if (!t || chatLoading.value) return
  if (!authStore.isLoggedIn) { ElMessage.warning('请先登录'); router.push('/login'); return }
  if (!msg) chatInput.value = ''

  // 添加用户消息和 assistant 占位
  chatMessages.value.push({ role: 'user', content: t })
  chatMessages.value.push({ role: 'assistant', content: '', thinking: true, loading: true })
  chatLoading.value = true
  nextTick(() => { if (chatMsgsRef.value) chatMsgsRef.value.scrollTop = chatMsgsRef.value.scrollHeight })

  try {
    const sid = chatStore.currentSessionId
    // 有 session_id 时由后端从 DB 加载历史，首轮时传前端 history
    const history = sid ? [] : chatMessages.value
      .filter(m => !m.thinking && !m.loading && m.role !== 'system')
      .slice(0, -1)
      .map(m => ({ role: m.role, content: m.content }))

    const r = await fetch('/api/v1/knowledge/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authStore.token}` },
      body: JSON.stringify({ prompt: t, history, session_id: sid || undefined }),
    })

    // SSE 流式读取
    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let textEvent = false

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          textEvent = line.slice(7).trim() === 'text'
          continue
        }
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6))
            const last = chatMessages.value[chatMessages.value.length - 1]
            if (!last || last.role !== 'assistant') continue
            if (last.thinking) { last.thinking = false; last.content = '' }
            if (textEvent) { last.content += d.content || '' }
            else if (d.sources) { last.sources = d.sources }
            if (d.session_id && !chatStore.currentSessionId) {
              chatStore.setCurrentSession(d.session_id)
            }
          } catch {}
        }
      }
    }

    const last = chatMessages.value[chatMessages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.thinking = false
      last.loading = false
      if (!last.content) last.content = '未找到相关信息'
    }
    chatStore.fetchSessions()
  } catch {
    const last = chatMessages.value[chatMessages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.thinking = false
      last.loading = false
      last.content = '查询失败，请重试'
    }
  } finally {
    chatLoading.value = false
    nextTick(() => { if (chatMsgsRef.value) chatMsgsRef.value.scrollTop = chatMsgsRef.value.scrollHeight })
  }
}
function autoResize(){if(chatInputRef.value){chatInputRef.value.style.height='auto';chatInputRef.value.style.height=Math.min(chatInputRef.value.scrollHeight,120)+'px'}}
// Chat sidebar actions
async function startNewChat(){chatMessages.value=[];chatStore.startNewSession()}
async function selectSession(id){chatMessages.value=[];chatStore.setCurrentSession(id);chatLoading.value=true;try{const msgs=await chatStore.fetchMessages(id);chatMessages.value=msgs.map(m=>({role:m.role,content:m.content,sources:m.sources||null}))}catch{}finally{chatLoading.value=false;nextTick(()=>{if(chatMsgsRef.value)chatMsgsRef.value.scrollTop=chatMsgsRef.value.scrollHeight})}}
async function deleteSession(id){try{await ElMessageBox.confirm('确定删除此对话？','确认删除',{type:'warning'});await chatStore.deleteSession(id);chatMessages.value=[]}catch{}}
function onUploaded(){store.fetchBooks();store.fetchStats()}
async function reingest(id){reingestingId.value=id;try{await store.reingestBook(id)}catch{}finally{reingestingId.value=null}}
async function delBook(id){try{await ElMessageBox.confirm('确定删除此书及其所有关联数据？','确认删除',{type:'warning'});await store.deleteBook(id)}catch{}}
function openImagePreview(img,list,n){previewList.value=list&&list.length>1?list:[];previewIndex.value=n>=0?n:0;previewImageUrl.value=getImageUrl(img.stored_url||img.url||img.id||img);previewVisible.value=true}
function nextPreview(){if(previewIndex.value<previewList.value.length-1){previewIndex.value++;var ni=previewList.value[previewIndex.value];previewImageUrl.value=getImageUrl(ni.stored_url||ni.url||ni.id||ni)}}
function prevPreview(){if(previewIndex.value>0){previewIndex.value--;var ni=previewList.value[previewIndex.value];previewImageUrl.value=getImageUrl(ni.stored_url||ni.url||ni.id||ni)}}
function onPreviewKey(e){if(e.key==='ArrowRight')nextPreview();else if(e.key==='ArrowLeft')prevPreview();else if(e.key==='Escape')previewVisible.value=false}
onMounted(async()=>{await Promise.all([store.fetchBooks(),store.fetchStats(),store.fetchSearchHistory()]);const urlQ=route.query.q;if(urlQ){searchInput.value=urlQ;await performSearch()}else{nextTick(()=>searchInputRef.value?.focus())};document.addEventListener('keydown',onPreviewKey)})
onBeforeUnmount(()=>{document.removeEventListener('keydown',onPreviewKey)})
</script>

<style scoped>
.ks-root{min-height:100vh;background:#fafaf8}
.ks-center-wrap{display:flex;justify-content:center;align-items:center;min-height:100vh;padding:24px}
.ks-center-body{text-align:center;max-width:640px;width:100%;margin-top:-80px}
.ks-center-title{font-family:'Noto Serif SC',serif;font-size:36px;font-weight:700;color:#141413;margin:0 0 6px}
.ks-center-sub{font-size:15px;color:#b0aca2;margin:0 0 32px}
.ks-center-search{display:flex;align-items:center;background:#fff;border:1.5px solid #e0ddd3;border-radius:12px;overflow:hidden;width:100%;margin-bottom:16px;transition:all 0.3s ease;position:relative}
.ks-center-search::before{content:'';position:absolute;inset:-4px;border-radius:16px;background:transparent;transition:all 0.5s cubic-bezier(0.25,0.1,0.25,1);pointer-events:none;z-index:-1}
.ks-center-search:focus-within{border-color:#c96442;box-shadow:0 0 0 4px rgba(201,100,66,0.06)}
.ks-center-search:focus-within::before{box-shadow:0 0 24px 6px rgba(201,100,66,0.08);animation:ks-glow-pulse 2s ease-in-out infinite}
@keyframes ks-glow-pulse{0%,100%{box-shadow:0 0 20px 4px rgba(201,100,66,0.06)}50%{box-shadow:0 0 32px 8px rgba(201,100,66,0.12)}}
.ks-search-icon{color:#b8b4aa;margin-left:14px;width:18px;height:18px;flex-shrink:0}
.ks-center-input{flex:1;border:none;outline:none;padding:12px 10px;font-size:15px;color:#141413;background:transparent}
.ks-center-input::placeholder{color:#c0bdb3}
.ks-search-btn{border:none;background:#c96442;color:#fff;padding:12px 24px;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.2s ease;white-space:nowrap;border-radius:0 12px 12px 0}
.ks-search-btn:hover{background:#a8513a;transform:scale(1.03);box-shadow:0 2px 8px rgba(201,100,66,0.25)}
.ks-search-btn:disabled{opacity:0.6;cursor:not-allowed}
.ks-mode-row{display:flex;justify-content:center;gap:8px;margin-bottom:16px}
.ks-mode-pill{border:1.5px solid #e0ddd3;background:#fff;padding:7px 18px;border-radius:22px;font-size:13px;font-weight:600;color:#5e5d59;cursor:pointer;display:flex;align-items:center;gap:5px;transition:all 0.25s cubic-bezier(0.25,0.1,0.25,1)}
.ks-mode-pill:hover{border-color:#c96442;color:#c96442;transform:translateY(-1px)}
.ks-mode-pill:active{transform:scale(0.96)}
.ks-mode-pill.active{background:#c96442;color:#fff;border-color:#c96442;box-shadow:0 2px 8px rgba(201,100,66,0.25);transform:none}
.ks-mode-pill-icon{padding:7px 12px}
.ks-tags{display:flex;justify-content:center;flex-wrap:wrap;gap:6px;margin-top:20px;padding-top:16px;border-top:1px solid #f0ede4}
.ks-tag-label{font-size:12px;color:#a8a59d;line-height:28px;margin-right:2px}
.ks-tag{border:none;background:#f5f2eb;padding:4px 14px;border-radius:14px;font-size:12px;color:#8a877e;cursor:pointer;transition:all 0.2s ease}
.ks-tag:hover{background:#fdf8f5;color:#c96442}

.ks-search-view{padding:16px 24px 32px}
.ks-bar{display:flex;align-items:center;gap:12px;margin-bottom:0}
.ks-search-view.with-panel .ks-bar{padding-right:60vw}
.ks-bar-title{font-family:'Noto Serif SC',serif;font-size:18px;font-weight:700;color:#141413;margin:0;white-space:nowrap}
.ks-bar-search{flex:1;max-width:520px;display:flex;align-items:center;background:#fff;border:1.5px solid #e0ddd3;border-radius:12px;transition:all 0.3s ease;position:relative}
.ks-bar-search::before{content:'';position:absolute;inset:-3px;border-radius:15px;background:transparent;transition:all 0.5s cubic-bezier(0.25,0.1,0.25,1);pointer-events:none;z-index:-1}
.ks-bar-search:focus-within{border-color:#c96442;box-shadow:0 0 0 3px rgba(201,100,66,0.06)}
.ks-bar-search:focus-within::before{box-shadow:0 0 18px 4px rgba(201,100,66,0.08);animation:ks-glow-pulse 2s ease-in-out infinite}
.ks-bar-input{flex:1;border:none;outline:none;padding:10px 8px;font-size:14px;color:#141413;background:transparent}
.ks-bar-input::placeholder{color:#c0bdb3}
.ks-bar-clear{border:none;background:none;padding:4px;cursor:pointer;color:#c0bdb3;display:flex}
.ks-bar-clear:hover{color:#c96442}
.ks-barlib-btn{border:none;background:#f5f2eb;width:36px;height:36px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#8a877e;transition:all 0.15s}
.ks-barlib-btn:hover,.ks-barlib-btn.active{background:#c96442;color:#fff}
.ks-mode-row-inline{margin:12px 0}
.ks-body-wrap{display:flex;gap:0;position:relative}
.ks-main{flex:1;min-width:0;transition:margin-right 0.3s}
.ks-body-wrap.with-panel .ks-main{margin-right:60vw}
.ks-search-panel{margin-bottom:16px}
.ks-progress{height:3px;background:#f0ede4;border-radius:2px;margin-bottom:16px;overflow:hidden;animation:ks-card-in 0.3s both}
.ks-progress-fill{height:100%;background:linear-gradient(90deg,#c96442,#e8a060,#c96442);background-size:200% 100%;border-radius:2px;transition:width 0.3s;animation:ks-shimmer 1.5s ease-in-out infinite}
@keyframes ks-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

.ks-card{background:#fff;border:1px solid #e8e4da;border-radius:14px;padding:16px 20px;margin-bottom:16px;animation:ks-banner-in 0.5s 0.05s cubic-bezier(0.25,0.1,0.25,1) both}
@keyframes ks-banner-in{from{opacity:0;transform:translateY(-20px)}to{opacity:1;transform:translateY(0)}}
.ks-card-hd{display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:14px;font-weight:600;color:#141413}
.ks-summary-spark{color:#c96442;width:18px;height:18px}
.ks-summary-conf{font-size:11px;padding:2px 8px;border-radius:10px;margin-left:auto}
.ks-summary-conf.conf-high{background:#eaf7ea;color:#5a7d5a}
.ks-summary-conf.conf-mid{background:#fef7e8;color:#b8860b}
.ks-summary-conf.conf-low{background:#fef0ed;color:#c96442}
.ks-card-body{font-size:14px;line-height:1.8;color:#3d3d3a}
.ks-card-body :deep(.ks-cite){color:#c96442;cursor:pointer;font-weight:600;text-decoration:underline;text-underline-offset:2px}
.ks-points{margin-top:12px;padding-top:10px;border-top:1px solid #f0eee6}
.ks-points-label{font-size:12px;font-weight:600;color:#6b6b66;margin-bottom:4px}
.ks-points ul{margin:0;padding:0 0 0 18px;font-size:13px;color:#5e5d59;line-height:1.7}
.ks-sources{margin-top:8px;padding-top:8px;border-top:1px solid #f0eee6;display:flex;flex-wrap:wrap;gap:4px}
.ks-sources-label{font-size:12px;color:#999}
.ks-src{border:none;background:#f5f2eb;padding:2px 8px;border-radius:4px;font-size:12px;color:#6b6b66;cursor:pointer}
.ks-src:hover{background:#fdf8f5;color:#c96442}

.ks-results{margin-bottom:16px}
.ks-rbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;font-size:13px;color:#888}
.ks-clear-btn{border:none;background:none;color:#c96442;font-size:13px;cursor:pointer}
.ks-empty{text-align:center;padding:40px 0;color:#c0bdb3}
.ks-empty-icon{width:36px;height:36px;margin-bottom:10px}
.ks-rlist{display:flex;flex-direction:column;gap:8px}
.ks-rcard{background:#fff;border:1px solid #e8e6dc;border-radius:12px;overflow:hidden;cursor:pointer;transition:all 0.2s ease;display:flex;opacity:0;animation:ks-result-in 0.45s cubic-bezier(0.25,0.1,0.25,1) forwards}
@keyframes ks-result-in{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes ks-card-in{from{opacity:0;transform:translateY(16px) scale(0.97)}to{opacity:1;transform:translateY(0) scale(1)}}
.ks-rcard:hover{border-color:#c96442;box-shadow:0 2px 8px rgba(201,100,66,0.08)}
.ks-rcard.active{border-color:#c96442;background:#fdf8f5}
.ks-rimg{width:120px;flex-shrink:0;min-height:120px;display:flex;align-items:center;justify-content:center;background:#f5f2eb;border-radius:8px 0 0 8px}
.ks-rimg img{width:100%;height:100%;object-fit:contain;aspect-ratio:1}
.ks-rbody{padding:12px 14px;flex:1;min-width:0}
.ks-rhead{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.ks-badge{display:inline-flex;align-items:center;gap:3px;background:#fef0e8;color:#c96442;font-size:10px;padding:2px 6px;border-radius:4px}
.ks-rchap{font-size:12px;font-weight:600;color:#303133;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ks-rscore{margin-left:auto;font-size:12px;font-weight:700}
.ks-rscore.s-high{color:#c96442}.ks-rscore.s-mid{color:#b8a47e}.ks-rscore.s-low{color:#aaa}
.ks-rsnip{font-size:13px;line-height:1.6;color:#5e5d59;margin:4px 0}
.ks-snip-pre{color:#c0bdb3;font-size:12px}.ks-snip-hl{color:#303133}.ks-snip-post{color:#c0bdb3;font-size:12px}.ks-hl{background:#fef0e0;color:#c96442;font-weight:600;border-radius:2px;padding:0 1px}
.ks-rfoot{display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#999}
.ks-raction{color:#c96442;display:flex;align-items:center;gap:2px}

/* ── ChatGPT-style: 全屏 fixed 布局 ── */
.ks-chat-shell{position:fixed;inset:0;z-index:9999;display:flex;background:#fafaf8;overflow:hidden}
.ks-chat-main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
.ks-chat-topbar{display:flex;align-items:center;gap:8px;padding:0 20px;height:48px;border-bottom:1px solid #e8e6dc;background:#fff;flex-shrink:0}
.ks-sidebar-toggle{border:none;background:transparent;color:#999;cursor:pointer;padding:6px;border-radius:6px;display:flex;align-items:center;transition:all 0.15s}
.ks-sidebar-toggle:hover{background:#f5f2eb;color:#3d3d3a}
.ks-chat-title{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600;color:#141413;flex:1}
.ks-chat-topbar-right{display:flex;align-items:center;gap:6px}
.ks-mode-pill-sm{border:1px solid #e0ddd3;background:#fff;padding:4px 10px;border-radius:16px;font-size:12px;color:#5e5d59;cursor:pointer;display:flex;align-items:center;gap:4px;transition:all 0.2s}
.ks-mode-pill-sm:hover{border-color:#c96442;color:#c96442}
.ks-mode-pill-sm.active{background:#c96442;color:#fff;border-color:#c96442}
.ks-mode-pill-icon-sm{padding:4px 8px}
.ks-sidebar-toggle .icon-sm,.ks-mode-pill-sm .icon-xs{width:16px;height:16px;flex-shrink:0}
.ks-back-btn{border:none;background:#f5f2eb;color:#5e5d59;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:5px;transition:all 0.15s}
.ks-back-btn:hover{background:#e8e4d8;color:#141413}

/* ── Chat body ── */
.ks-chat-body{flex:1;display:flex;flex-direction:column;overflow:hidden;max-width:860px;width:100%;margin:0 auto;padding:0 24px}
.ks-chat-msgs{flex:1;overflow-y:auto;padding:20px 0;scroll-behavior:smooth}
.ks-chat-msgs::-webkit-scrollbar{width:6px}
.ks-chat-msgs::-webkit-scrollbar-track{background:transparent}
.ks-chat-msgs::-webkit-scrollbar-thumb{background:#d8d4cc;border-radius:3px}
.ks-chat-msgs::-webkit-scrollbar-thumb:hover{background:#c0bbb3}

/* ── Welcome ── */
.ks-chat-welcome{text-align:center;padding:40px 16px;margin-top:10vh}
.ks-chat-welcome-icon{color:#c96442;width:40px;height:40px;margin-bottom:12px}
.ks-chat-welcome h3{font-size:24px;margin:0 0 6px;color:#141413;font-family:'Noto Serif SC',serif}
.ks-chat-welcome p{font-size:14px;margin:0 0 16px;color:#8a877e;max-width:480px;margin-left:auto;margin-right:auto}
.ks-chat-sugs{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}
.ks-sug-btn{border:1px solid #d8d4cc;background:#fff;padding:6px 14px;border-radius:20px;font-size:13px;color:#5e5d59;cursor:pointer;transition:all 0.2s}
.ks-sug-btn:hover{border-color:#c96442;color:#c96442;background:#fdf8f5}

/* ── Message bubbles — DeepSeek compact style ── */
.ks-cmsg{padding:8px 0;max-width:860px;margin:0 auto;animation:ks-msg-in 0.2s ease both}
@keyframes ks-msg-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.ks-cmsg.assistant{background:#fff;padding:14px 20px;border-radius:10px;margin-bottom:2px}
.ks-cmsg.user{display:flex;justify-content:flex-end;padding:6px 0}
.ks-cmsg.user .ks-ctext{background:#e8e4dc;border-radius:18px 18px 4px 18px;padding:9px 14px;display:inline-block;max-width:65%;font-size:14px;line-height:1.45;color:#1a1a1a}
.ks-cmsg.assistant .ks-ctext{font-size:14px;line-height:1.5;color:#1a1a1a;padding:0}
.ks-ccontent{min-width:0}
.ks-cmsg.user .ks-ccontent{display:flex;justify-content:flex-end}
.ks-ctext :deep(h1),.ks-ctext :deep(h2),.ks-ctext :deep(h3){margin:10px 0 2px;color:#141413;font-family:'Noto Serif SC',serif;font-weight:600}
.ks-ctext :deep(h1){font-size:17px}.ks-ctext :deep(h2){font-size:15px}.ks-ctext :deep(h3){font-size:14px}
.ks-ctext :deep(p){margin:0 0 4px}
.ks-ctext :deep(strong){color:#141413;font-weight:600}
.ks-ctext :deep(blockquote){margin:4px 0;padding:4px 10px;border-left:3px solid #c96442;background:#faf9f7;color:#5e5d59;font-style:italic;border-radius:0 6px 6px 0}
.ks-ctext :deep(ul),.ks-ctext :deep(ol){margin:2px 0;padding-left:18px}
.ks-ctext :deep(li){margin:1px 0;line-height:1.5}
.ks-ctext :deep(li)::marker{color:#c96442}
.ks-ctext :deep(code){background:#f0eee6;padding:1px 5px;border-radius:3px;font-size:13px;font-family:'JetBrains Mono',monospace;color:#c96442}
.ks-ctext :deep(hr){border:none;border-top:1px solid #e8e6dc;margin:8px 0}
.ks-ctext :deep(a){color:#c96442;text-decoration:underline}

/* ── Sources card ── */
.ks-csources{margin-top:12px;padding:10px 14px;background:#faf9f7;border-radius:8px;border:1px solid #ece9e0}
.ks-csrc-title{font-size:12px;font-weight:600;color:#6b6b66;margin-bottom:6px}
.ks-csrc-item{font-size:12px;color:#8a877e;line-height:1.8;display:flex;flex-wrap:wrap;gap:0 6px;padding:3px 4px;border-radius:4px;transition:background 0.15s}
.ks-csrc-item:hover{background:#f0ede5}
.ks-csrc-idx{color:#c96442;font-weight:600;flex-shrink:0}
.ks-csrc-book{color:#3d3d3a;font-weight:600}
.ks-csrc-page{color:#6b6b66}
.ks-csrc-snip{color:#a09d96;font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:280px}
.ks-csrc-link{color:#c96442;text-decoration:none;font-weight:600;display:inline-flex;align-items:center;gap:2px}
.ks-csrc-link:hover{text-decoration:underline}

/* 引用弹窗 */
.ks-cite-overlay{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center}
.ks-cite-modal{background:#fff;border-radius:12px;max-width:420px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.15);overflow:hidden}
.ks-cite-modal-hd{display:flex;align-items:center;gap:8px;padding:14px 16px;border-bottom:1px solid #ece9e0}
.ks-cite-modal-idx{color:#c96442;font-weight:700;font-size:14px;flex-shrink:0}
.ks-cite-modal-title{font-size:14px;font-weight:600;color:#141413;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ks-cite-modal-close{border:none;background:transparent;color:#999;cursor:pointer;padding:4px;border-radius:4px}
.ks-cite-modal-close:hover{background:#f5f2eb;color:#3d3d3a}
.ks-cite-modal-body{padding:16px}
.ks-cite-db{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.ks-cite-type{background:#fef0e8;color:#c96442;font-size:12px;padding:2px 8px;border-radius:4px;font-weight:600}
.ks-cite-go{color:#c96442;font-size:13px;text-decoration:none;font-weight:600}
.ks-cite-go:hover{text-decoration:underline}
.ks-cite-book-info{font-size:13px;color:#5e5d59;margin-bottom:10px}
.ks-cite-snippet{font-size:14px;line-height:1.7;color:#3d3d3a;background:#faf9f7;padding:12px;border-radius:8px;border-left:3px solid #c96442;margin:0}

.ks-cthinking{font-size:14px;color:#8a877e;padding:8px 0;display:flex;align-items:center;gap:6px;animation:ks-pulse 1.5s ease-in-out infinite}
@keyframes ks-pulse{0%,100%{opacity:1}50%{opacity:0.5}}

/* ── Input row ── */
.ks-chat-input-row{padding:8px 24px 12px;flex-shrink:0}
.ks-chat-input-wrap{display:flex;align-items:flex-end;gap:8px;background:#fff;border:1.5px solid #d8d4cc;border-radius:16px;padding:6px 6px 6px 16px;transition:border-color 0.2s;box-shadow:0 1px 3px rgba(0,0,0,0.04)}
.ks-chat-input-wrap:focus-within{border-color:#c96442;box-shadow:0 1px 8px rgba(201,100,66,0.08)}
.ks-chat-ta{flex:1;border:none;outline:none;padding:8px 0;font-size:15px;resize:none;line-height:1.5;background:transparent;color:#2c2c2c;font-family:inherit;max-height:160px}
.ks-chat-ta::placeholder{color:#b0aca2}
.ks-chat-send{border:none;background:#141413;color:#fff;width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;transition:all 0.2s}
.ks-chat-send:hover{background:#3d3d3a}
.ks-chat-send:disabled{opacity:0.35;cursor:not-allowed}
.ks-chat-send .icon-sm{width:16px;height:16px}
.spin{animation:ks-spin 1s linear infinite}
@keyframes ks-spin{to{transform:rotate(360deg)}}
.ks-chat-footnote{text-align:center;font-size:11px;color:#b0aca2;margin-top:6px}

/* ── Sidebar toggle transition ── */
.sidebar-slide-enter-active,.sidebar-slide-leave-active{transition:all 0.25s cubic-bezier(0.4,0,0.2,1)}
.sidebar-slide-enter-from,.sidebar-slide-leave-to{width:0;min-width:0;overflow:hidden;opacity:0}
.sidebar-slide-enter-to,.sidebar-slide-leave-from{width:260px;min-width:260px}

.ks-panel{position:fixed;top:64px;right:0;width:60vw;max-width:960px;min-width:480px;height:calc(100vh - 64px);background:#fff;border-left:1px solid #e8e6dc;display:flex;flex-direction:column;z-index:10000002;box-shadow:-4px 0 20px rgba(0,0,0,0.06)}
.ks-phdr{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #f0eee6;flex-shrink:0;animation:ks-panel-in 0.3s 0.05s ease both}
.ks-ptitle{font-size:14px;font-weight:600;color:#141413;overflow:hidden
;text-overflow:ellipsis;white-space:nowrap}
.ks-phdr-acts{display:flex;align-items:center;gap:6px}
.ks-panel .ks-pbody{animation:ks-panel-in 0.35s 0.18s ease both}
.ks-panel .ks-ptabs{animation:ks-panel-in 0.35s 0.30s ease both}
@keyframes ks-panel-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.ks-pdf-btn{border:none;background:#f5f2eb;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px;color:#5e5d59;display:flex;align-items:center;gap:4px}
.ks-pdf-btn:hover{background:#c96442;color:#fff}
.ks-pclose{border:none;background:none;padding:6px;border-radius:6px;cursor:pointer;color:#b8b4aa;display:flex}
.ks-pclose:hover{background:#f0ede4;color:#303133}
.ks-pbody{flex:1;overflow-y:auto}
.ks-detail{padding:14px 18px}
.ks-dmeta{margin-bottom:10px}.ks-dchap{font-size:13px;font-weight:600;color:#303133}.ks-dpage{font-size:12px;color:#999;margin-left:8px;display:inline-flex;align-items:center;gap:3px}
.ks-dctx{margin:10px 0}.ks-dctx-mrk{font-size:11px;color:#c0bdb3;margin:4px 0}.ks-dctx-txt{font-size:13px;color:#999;line-height:1.7;margin:0}
.ks-dcontent{font-size:14px;line-height:1.8;color:#3d3d3a;padding:12px;background:#fdfcf9;border:1px solid #f0eee6;border-radius:10px;margin:10px 0}
.ks-dcontent :deep(.ks-hl){background:#fef0e0;color:#c96442;font-weight:600;border-radius:2px;padding:0 2px}
.ks-dims{margin:10px 0}.ks-dims-label{font-size:12px;font-weight:600;color:#6b6b66;margin-bottom:6px;display:flex;align-items:center;gap:4px}
.ks-dims-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.ks-dim{cursor:pointer;text-align:center}.ks-dim img{width:100%;aspect-ratio:1;object-fit:contain;border-radius:4px;border:1px solid #e8e4da;background:#fafaf8}.ks-dim span{font-size:10px;color:#999;display:block}
.ks-dnav{display:flex;align-items:center;justify-content:space-between;margin-top:14px;padding-top:10px;border-top:1px solid #f0eee6}
.ks-dnav-btn{border:1px solid #e0ddd3;background:#fff;padding:5px 12px;border-radius:8px;font-size:12px;color:#5e5d59;cursor:pointer;display:flex;align-items:center;gap:4px}
.ks-dnav-btn:hover:not(:disabled){border-color:#c96442;color:#c96442}
.ks-dnav-btn:disabled{opacity:0.3;cursor:not-allowed}
.ks-dnav-info{font-size:12px;color:#b8b4aa}
.ks-ptabs{display:flex;border-bottom:1px solid #f0eee6;padding:0 14px}
.ks-ptabs button{border:none;background:none;padding:8px 14px;font-size:12px;font-weight:500;color:#999;cursor:pointer;display:flex;align-items:center;gap:4px;border-bottom:2px solid transparent;transition:all 0.15s}
.ks-ptabs button.active{color:#c96442;border-bottom-color:#c96442}
.ks-ptab{padding:12px 16px}
.ks-outline-filter{width:100%;padding:6px 10px;border:1px solid #e8e6dc;border-radius:6px;font-size:12px;margin-bottom:10px;outline:none;box-sizing:border-box}
.ks-outline-filter:focus{border-color:#c96442}
.ks-pimg{padding:14px}.ks-pimg-main{width:100%;max-height:320px;object-fit:contain;border-radius:8px;cursor:pointer}
.ks-pimg-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.ks-pimg-item{cursor:pointer;text-align:center}.ks-pimg-item img{width:100%;aspect-ratio:1;object-fit:contain;border-radius:6px;border:1px solid #e8e4da;background:#fafaf8}.ks-pimg-item span{font-size:10px;color:#999;display:block;margin-top:2px}
.ks-related-img-row{display:flex;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid #f0eee6;overflow-x:auto}
.ks-related-img-thumb{flex-shrink:0;width:72px;cursor:pointer;text-align:center}
.ks-related-img-thumb img{width:72px;height:72px;object-fit:contain;border-radius:6px;border:1px solid #e8e4da;background:#fafaf8}
.ks-related-img-thumb span{font-size:9px;color:#999;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:72px}
.ks-lib-pop{position:fixed;top:80px;right:24px;width:360px;max-height:calc(100vh - 96px);overflow-y:auto;background:#fff;border:1px solid #e8e6dc;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.1);z-index:10000002}.ks-lib-inner{padding:14px}
.ks-lib-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.ks-upload-btn{display:flex;align-items:center;gap:4px;padding:6px 14px;border:1.5px dashed #e0ddd3;background:#fafaf8;border-radius:8px;font-size:13px;color:#6b6b66;cursor:pointer;transition:all 0.2s}
.ks-upload-btn:hover{border-color:#c96442;color:#c96442}.ks-upload-icon{font-size:18px;line-height:1}
.ks-lib-stats{display:flex;gap:6px;font-size:11px;color:#888}.ks-lib-stats span{background:#f5f2eb;padding:2px 6px;border-radius:4px}
.ks-lib-books{display:flex;flex-direction:column;gap:2px;max-height:160px;overflow-y:auto;margin-bottom:10px}
.ks-lib-book{display:flex;align-items:center;justify-content:space-between;padding:4px 6px;border-radius:4px}.ks-lib-book:hover{background:#fdfcf9}
.ks-lib-bl{display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;flex:1;min-width:0}
.ks-lib-bn{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#303133}
.ks-lib-bs{font-size:10px;padding:1px 4px;border-radius:4px;flex-shrink:0}
.ks-lib-bs.completed{background:#eaf7ea;color:#5a7d5a}.ks-lib-bs.processing{background:#fef7e8;color:#b8860b}.ks-lib-bs.failed{background:#fef0ed;color:#c96442}
.ks-lib-bacts{display:flex;gap:2px}
.ks-lib-act{border:none;background:none;padding:3px;border-radius:4px;cursor:pointer;color:#b8b4aa;display:flex}
.ks-lib-act:hover{color:#6b6b66;background:#f0ede4}.ks-lib-act.del:hover{color:#c96442}
.ks-lib-empty{font-size:13px;color:#c0bdb3;text-align:center;padding:12px 0}
.ks-lib-sep{height:1px;background:#e8e6dc;margin:10px 0}
.ks-lib-section-title{font-size:12px;font-weight:600;color:#8a877e;margin-bottom:6px}
.ks-lib-chunks{font-size:10px;color:#999;flex-shrink:0}
.ks-upload-btn-sm{padding:4px 10px;font-size:12px}
.ks-upload-btn:disabled{opacity:0.5;cursor:not-allowed}
.ks-source-badge{font-size:12px;line-height:1;flex-shrink:0}
.ks-source-badge.private{color:#c96442}
.ks-source-badge.public{color:#b8a47e}
.ks-preview-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:10000003;display:flex;align-items:center;justify-content:center}
.ks-preview-img{max-width:90vw;max-height:90vh;object-fit:contain;border-radius:4px}
.ks-preview-close{position:absolute;top:20px;right:20px;border:none;background:rgba(255,255,255,0.15);color:#fff;width:40px;height:40px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center}
.ks-preview-close:hover{background:rgba(255,255,255,0.3)}
.ks-preview-nav{position:absolute;top:50%;transform:translateY(-50%);border:none;background:rgba(255,255,255,0.15);color:#fff;width:44px;height:44px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background 0.15s}
.ks-preview-nav:hover{background:rgba(255,255,255,0.3)}
.ks-preview-prev{left:24px}
.ks-preview-next{right:24px}
.ks-preview-counter{position:absolute;bottom:24px;left:50%;transform:translateX(-50%);color:#fff;font-size:13px;background:rgba(0,0,0,0.5);padding:4px 12px;border-radius:10px}

.view-switch-enter-active,.view-switch-leave-active{transition:all 0.32s cubic-bezier(0.4,0,0.2,1)}
.view-switch-enter-from{opacity:0;transform:translateY(10px)}
.view-switch-leave-to{opacity:0;transform:translateY(-10px)}
.slide-right-enter-active,.slide-right-leave-active{transition:all 0.3s}.slide-right-enter-from,.slide-right-leave-to{transform:translateX(100%);opacity:0}
.drop-enter-active,.drop-leave-active{transition:all 0.2s}.drop-enter-from,.drop-leave-to{opacity:0;transform:translateY(-8px)}
.fade-enter-active,.fade-leave-active{transition:all 0.35s ease}.fade-enter-from,.fade-leave-to{opacity:0;transform:translateY(8px)}

.icon{width:20px;height:20px}.icon-sm{width:16px;height:16px}.icon-xs{width:12px;height:12px}
.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

@media(max-width:1024px){.ks-panel{width:100vw;min-width:auto;top:64px;height:calc(100vh - 64px);z-index:10000002}.ks-body-wrap.with-panel .ks-main{margin-right:0}.ks-lib-pop{right:12px;width:calc(100vw-24px)}}


.ks-cite{cursor:pointer;color:#c96442;font-size:12px;font-weight:600;vertical-align:super;padding:0 2px;border-radius:2px;transition:background 0.15s}
.ks-cite:hover{background:rgba(201,100,66,0.08);text-decoration:underline}
.ks-csrc-link{color:#c96442;text-decoration:none;font-weight:500;flex-shrink:0;margin-left:4px}
.ks-csrc-link:hover{text-decoration:underline}
.citation-overlay{position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center}
.citation-modal{background:#fff;border-radius:12px;width:480px;max-width:90vw;max-height:70vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,0.18)}
.citation-modal-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid #eee}
.citation-modal-title{font-size:15px;font-weight:600;color:#141413}
.citation-modal-close{background:none;border:none;font-size:20px;cursor:pointer;color:#8a877e;padding:0 4px}
.citation-modal-close:hover{color:#141413}
.citation-modal-body{padding:16px 20px}
.citation-modal-row{display:flex;gap:12px;margin-bottom:10px}
.citation-modal-label{font-size:12px;color:#8a877e;min-width:48px;flex-shrink:0}
.citation-modal-value{font-size:13px;color:#2c2c2c;line-height:1.5}
.citation-snippet{font-style:italic;color:#6b6b66}
.citation-modal-link{color:#c96442;text-decoration:none;font-weight:500;font-size:13px}
.citation-modal-link:hover{text-decoration:underline}

</style>
