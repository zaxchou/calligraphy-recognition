<template>
<div class="ks-root">
  <!-- ===== 居中欢迎态 ===== -->
  <transition name="fade">
    <div v-if="centered" class="ks-center-wrap" key="center">
      <div class="ks-center-body">
        <h1 class="ks-center-title">写意知识库</h1>
        <p class="ks-center-sub">潘天寿构图法则 · 写意花鸟画技法</p>
        <div class="ks-center-search">
          <Search class="ks-search-icon" />
          <input v-model="searchInput" type="text" class="ks-center-input" placeholder="搜索写意花鸟画、潘天寿构图法则等专业知识..." @keyup.enter="performSearch" :disabled="store.searchLoading" ref="searchInputRef" @input="centered=true" />
          <button class="ks-search-btn" @click="performSearch" :disabled="store.searchLoading"><Loader2 v-if="store.searchLoading" class="icon spin" /><span v-else>搜索</span></button>
        </div>
        <div class="ks-mode-row">
          <button :class="['ks-mode-pill',{active:activeMode==='search'}]" @click="activeMode='search'"><Search class="icon-xs" /> 搜索</button>
          <button :class="['ks-mode-pill',{active:activeMode==='chat'}]" @click="switchMode('chat')"><MessageCircle class="icon-xs" /> 专家</button>
          <button :class="['ks-mode-pill',{active:activeMode==='graph'}]" @click="switchMode('graph');fetchGraph()"><Share2 class="icon-xs" /> 图谱</button>
          <button class="ks-mode-pill ks-mode-pill-icon" @click="switchMode('lib')" :class="{active:libOpen}" title="书库管理"><BookOpen class="icon-xs" /></button>
        </div>
        <div class="ks-tags"><span class="ks-tag-label">搜索历史：</span><button v-for="t in store.searchHistory.slice(0,8)" :key="t.id" class="ks-tag" @click="searchByTag(t.query)">{{ t.query }}</button></div>
      </div>
    </div>
  </transition>

  <!-- ===== 搜索态（带顶栏） ===== -->
  <transition name="fade">
    <div v-if="!centered && activeMode==='search'" class="ks-search-view" key="search">
      <header class="ks-bar"><h1 class="ks-bar-title">写意知识库</h1>
        <div class="ks-bar-search"><Search class="ks-search-icon" /><input v-model="searchInput" type="text" class="ks-bar-input" placeholder="搜索专业知识..." @keyup.enter="performSearch" :disabled="store.searchLoading" @input="centered=true" />
          <button v-if="searchInput" class="ks-bar-clear" @click="clearSearch"><X class="icon-sm" /></button><button class="ks-search-btn" @click="performSearch" :disabled="store.searchLoading"><Loader2 v-if="store.searchLoading" class="icon spin" /><span v-else>搜索</span></button>
        </div>
        <button class="ks-barlib-btn" @click="libOpen=!libOpen; if(libOpen&&centered)centered=false" :class="{active:libOpen}" title="书库管理"><BookOpen class="icon-sm" /></button>
      </header>
      <div class="ks-mode-row ks-mode-row-inline"><button :class="['ks-mode-pill',{active:true}]" @click="goCentered"><Search class="icon-xs" /> 搜索</button><button :class="['ks-mode-pill']" @click="switchMode('chat')"><MessageCircle class="icon-xs" /> 专家</button><button :class="['ks-mode-pill']" @click="switchMode('graph');fetchGraph()"><Share2 class="icon-xs" /> 图谱</button></div>
      <div class="ks-body-wrap" :class="{'with-panel':rightPanelOpen}">
        <div class="ks-main">
          <div class="ks-search-panel">
            <div v-if="store.searchLoading" class="ks-progress"><div class="ks-progress-fill" :style="{width:store.searchProgress+'%'}"></div></div>
            <div v-if="store.aiSummary?.answer" class="ks-card"><div class="ks-card-hd"><Sparkles class="ks-summary-spark" /><span>AI概述</span><span class="ks-summary-conf" :class="'conf-'+getConfClass(store.aiSummary.confidence)">{{ getConfLabel(store.aiSummary.confidence) }}</span></div>
              <div class="ks-card-body" v-html="renderCitations(store.aiSummary.answer)" @click="onCitationClick($event)"></div>
              <div v-if="store.relatedImages?.length" class="ks-related-img-row"><div v-for="ri in store.relatedImages.slice(0,6)" :key="ri.url" class="ks-related-img-thumb" @click="openImagePreview(ri)"><img :src="getImageUrl(ri.stored_url||ri.url)" /><span>{{ ri.display_label||ri.figure_id||'' }}</span></div></div>
              <div v-if="store.aiSummary.key_points?.length" class="ks-points"><div class="ks-points-label">核心要点</div><ul><li v-for="(p,i) in store.aiSummary.key_points" :key="i">{{ cleanLatex(p) }}</li></ul></div>
              <div v-if="store.aiSummary.sources?.length" class="ks-sources"><span class="ks-sources-label">参考来源：</span><button v-for="(s,i) in store.aiSummary.sources" :key="i" class="ks-src" @click="scrollToResult(s)">《{{ (s.book||'').replace(/[《》]/g,'') }}》p.{{ s.page||'?' }}</button></div>
            </div>
            <div v-if="hasSearched&&!store.searchLoading" class="ks-results">
              <div class="ks-rbar"><span>共{{ store.searchResults.length }}条结果</span><button class="ks-clear-btn" @click="clearSearch">清除</button></div>
              <div v-if="store.searchResults.length===0" class="ks-empty"><FileSearch class="ks-empty-icon" /><p>未找到相关结果</p></div>
              <div class="ks-rlist"><div v-for="(r,i) in store.searchResults" :key="r.chunk_id||r.vector_id||i" :class="['ks-rcard',{'active':highlightedIndex===i,'img':r.result_type==='image'}]" @click="openDetail(r,i)">
                <template v-if="r.result_type==='image'"><div class="ks-rimg"><img :src="getImageUrl(r.image?.stored_url||r.image?.url||r.associated_images?.[0]?.stored_url||r.associated_images?.[0]?.url)" /></div><div class="ks-rbody"><div class="ks-rhead"><span class="ks-badge"><ImageIcon class="icon-xs" />配图</span><span class="ks-rscore" :class="getScoreClass(r.score)">{{ formatScore(r.score) }}%</span></div><div class="ks-rfoot"><span>{{ r.book_title }}</span><span class="ks-raction">查看大图 <ChevronRight class="icon-xs" /></span></div></div></template>
                <template v-else-if="r.result_type==='table'"><TableResultCard :result="r" @click="openDetail(r,i)" /></template>
                <template v-else><div class="ks-rbody"><div class="ks-rhead"><span class="ks-rchap">{{ getChapter(r) }}</span><span class="ks-rscore" :class="getScoreClass(r.score)">{{ formatScore(r.score) }}%</span></div><p class="ks-rsnip" v-html="highlightSnippet(r)"></p><div class="ks-rfoot"><span><BookOpen class="icon-xs" />{{ r.book_title }}·p.{{ r.page_start||'?' }}</span><span class="ks-raction">查看原文 <ChevronRight class="icon-xs" /></span></div></div></template>
              </div></div>
            </div>
          </div>
        </div>
        <transition name="slide-right"><div v-if="rightPanelOpen" class="ks-panel">
          <div class="ks-phdr"><span class="ks-ptitle">{{ activeResult?.book_title||'文档查看' }}</span><div class="ks-phdr-acts"><button v-if="pdfUrl" class="ks-pdf-btn" @click="openPdf"><FileDown class="icon-sm" />PDF</button><button class="ks-pclose" @click="closePanel"><X class="icon" /></button></div></div>
          <div class="ks-pbody">
            <div v-if="activeResult?.result_type==='image'" class="ks-pimg"><img :src="getFullImageUrl(activeResult)" class="ks-pimg-main" @click="openImagePreview(getFullImageUrl(activeResult))" /><ImageRelatedChunks v-if="activeResult.image?.id" :chunks="relatedChunks" :loading="loadingRelated" @chunk-click="onRelatedClick" /></div>
            <div v-if="activeResult?.result_type!=='image'" class="ks-detail"><div class="ks-dmeta"><span class="ks-dchap">{{ getChapter(activeResult) }}</span><span class="ks-dpage" v-if="activeResult.page_start"><BookOpen class="icon-xs" />第{{ activeResult.page_start }}{{ activeResult.page_end!==activeResult.page_start?'-'+activeResult.page_end:'' }}页</span></div>
              <div v-if="activeResult.context_before" class="ks-dctx"><p class="ks-dctx-txt">{{ cleanLatex(activeResult.context_before) }}</p><div class="ks-dctx-mrk">⋯上文⋯</div></div>
              <div class="ks-dcontent" v-html="highlightDetail(activeResult)"></div>
              <div v-if="activeResult.associated_images?.length" class="ks-dims"><div class="ks-dims-label"><ImageIcon class="icon-xs" />关联配图</div><div class="ks-dims-grid"><div v-for="(img,i) in activeResult.associated_images" :key="i" class="ks-dim" @click="openImagePreview(img)"><img :src="getImageUrl(img.stored_url||img.url||img.id)" @error="e=>{e.target.src='/placeholder.png'}" /><span v-if="img.figure_id">{{ img.figure_id }}</span></div></div></div>
              <div v-if="activeResult.context_after" class="ks-dctx"><div class="ks-dctx-mrk">⋯下文⋯</div><p class="ks-dctx-txt">{{ cleanLatex(activeResult.context_after) }}</p></div>
              <div class="ks-dnav"><button class="ks-dnav-btn" :disabled="loadingChunk||chunkIndex<=0" @click="loadPrevChunk"><ChevronLeft class="icon-xs" />上一段</button><span class="ks-dnav-info" v-if="chunkIndex>0">第{{ chunkIndex+1 }}段</span><button class="ks-dnav-btn" :disabled="loadingChunk" @click="loadNextChunk">下一段<ChevronRight class="icon-xs" /></button></div>
            </div>
            <div class="ks-ptabs"><button :class="{active:panelTab==='outline'}" @click="panelTab='outline'"><ListTree class="icon-xs" />大纲</button><button v-if="markdownContent" :class="{active:panelTab==='markdown'}" @click="panelTab='markdown'"><FileCode class="icon-xs" />原文</button><button v-if="activeResult?.associated_images?.length" :class="{active:panelTab==='images'}" @click="panelTab='images'"><ImageIcon class="icon-xs" />配图</button></div>
            <div v-show="panelTab==='outline'" class="ks-ptab"><input v-model="outlineFilter" class="ks-outline-filter" placeholder="筛选大纲标题..." /><DocumentOutline :outline="filteredOutline" :loading="loadingOutline" @item-click="onOutlineClick" /></div>
            <div v-show="panelTab==='markdown'" class="ks-ptab" ref="mdContentRef"><MarkdownViewer :markdown="markdownContent" :loading="loadingMarkdown" /></div>
            <div v-show="panelTab==='images'" class="ks-ptab"><div class="ks-pimg-grid"><div v-for="(img,i) in activeResult?.associated_images" :key="i" class="ks-pimg-item" @click="openImagePreview(img)"><img :src="getImageUrl(img.stored_url||img.url||img.id)" /><span v-if="img.figure_id">{{ img.figure_id }}</span></div></div></div>
          </div>
        </div></transition>
      </div>
    </div>
  </transition>

  <!-- ===== 专家/图谱全屏态（无顶栏） ===== -->
  <transition name="fade">
    <div v-if="!centered && activeMode!=='search'" class="ks-full-view" :key="activeMode">
      <div class="ks-full-top">
        <div class="ks-mode-row">
          <button :class="['ks-mode-pill',{active:activeMode==='search'}]" @click="goCentered"><Search class="icon-xs" /> 搜索</button>
          <button :class="['ks-mode-pill',{active:activeMode==='chat'}]" @click="activeMode='chat'"><MessageCircle class="icon-xs" /> 专家</button>
          <button :class="['ks-mode-pill',{active:activeMode==='graph'}]" @click="activeMode='graph';fetchGraph()"><Share2 class="icon-xs" /> 图谱</button>
          <button class="ks-mode-pill ks-mode-pill-icon" @click="libOpen=!libOpen" :class="{active:libOpen}" title="书库管理"><BookOpen class="icon-xs" /></button>
        </div>
      </div>
      <div class="ks-full-body">
        <div v-if="activeMode==='graph'" class="ks-graph-box" ref="graphCanvasRef"
               @wheel.prevent="onGraphWheel"
               @mousedown="onGraphMouseDown"
               @mousemove="onGraphMouseMove"
               @mouseup="onGraphMouseUp"
               @mouseleave="onGraphMouseUp">
            <div class="ks-graph-viewport">
               <svg :viewBox="`0 0 ${graphSvgW} ${graphSvgH}`" class="ks-graph-svg" :style="{transform:`translate(${graphPanX}px,${graphPanY}px) scale(${graphZoom})`,willChange:'transform'}"><line v-for="(e,i) in graphEdges" :key="'e'+i" :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2" stroke="#ddd" stroke-width="1" /><g v-for="n in graphNodes" :key="n.id" :transform="`translate(${n.x},${n.y})`" class="ks-gnode"><circle :r="n.r" :fill="n.color" stroke="#fff" stroke-width="2" /><text :y="n.r+12" text-anchor="middle" :font-size="n.fontSize" fill="#3d3d3a">{{ n.label }}</text></g></svg>
             </div>
            <div class="ks-graph-hint">滚轮缩放 · 拖拽平移</div>
          <div v-if="!graphNodes.length&&!graphLoading" class="ks-gempty">点击"图谱"加载知识关系</div>
          <div v-if="graphLoading" class="ks-gloading"><Loader2 class="icon spin" /> 加载中...</div>
          </div>
          <div v-if="activeMode==='graph'" class="ks-glegend"><span><span class="ks-ldot" style="background:#c96442"></span>画家</span><span><span class="ks-ldot" style="background:#e8a060"></span>作品</span><span><span class="ks-ldot" style="background:#5a7d5a"></span>朝代</span><span><span class="ks-ldot" style="background:#4a7ab8"></span>画册</span><span><span class="ks-ldot" style="background:#6b8eb5"></span>章节</span><span><span class="ks-ldot" style="background:#b8a47e"></span>技法</span></div>
          <div v-if="activeMode==='chat'" class="ks-chat"><div class="ks-chat-msgs" ref="chatMsgsRef">
          <div v-if="chatMessages.length===0" class="ks-chat-welcome"><Sparkles class="ks-chat-welcome-icon" /><h3>写意画专家助手</h3><p>基于专业知识库，解答写意花鸟画、构图法则、笔墨技法等问题</p><div class="ks-chat-sugs"><button v-for="s in chatSuggestions" :key="s" class="ks-sug-btn" @click="sendChat(s)">{{ s }}</button></div></div>
          <div v-for="(m,i) in chatMessages" :key="i" :class="['ks-cmsg',m.role]"><div class="ks-cavatar"><Bot v-if="m.role==='assistant'" class="icon" /><User v-else class="icon" /></div><div class="ks-ccontent"><div class="ks-crole">{{ m.role==='user'?'你':'专家助手' }}</div><div v-if="m.thinking" class="ks-cthinking"><Sparkles class="icon-xs" />思考中...</div><div v-else class="ks-ctext" v-html="renderMd(m.content,m.loading)"></div></div></div>
        </div><div class="ks-chat-input"><textarea ref="chatInputRef" v-model="chatInput" class="ks-chat-ta" placeholder="输入问题..." @keydown.enter.exact.prevent="sendChat()" @input="autoResize" rows="2" :disabled="chatLoading"></textarea><button class="ks-chat-send" @click="sendChat()" :disabled="!chatInput.trim()||chatLoading"><Send class="icon" /></button></div></div>
      </div>
    </div>
  </transition>

  <!-- 书库面板 & 浮层 -->
  <transition name="drop"><div v-if="libOpen" class="ks-lib-pop">
    <div class="ks-lib-inner"><div class="ks-lib-row"><button class="ks-upload-btn" @click="showUploadModal=true"><span class="ks-upload-icon">+</span>上传PDF</button><div class="ks-lib-stats" v-if="store.stats"><span>{{ store.stats.books?.total||0 }}书</span><span>{{ store.stats.contents?.chunks||0 }}块</span><span>{{ store.stats.contents?.images||0 }}图</span></div></div>
      <div class="ks-lib-books" v-if="store.books.length"><div v-for="b in store.books" :key="b.id" class="ks-lib-book"><label class="ks-lib-bl"><input type="checkbox" v-model="selectedBooks" :value="b.id" :disabled="b.status==='processing'" /><span class="ks-lib-bn">{{ b.title||b.file_name }}</span><span :class="['ks-lib-bs',b.status]">{{ statusLabel(b.status) }}</span></label><div class="ks-lib-bacts"><button class="ks-lib-act" @click="reingest(b.id)" :disabled="reingestingId===b.id"><RefreshCw v-if="reingestingId!==b.id" class="icon-xs" /><Loader2 v-else class="icon-xs spin" /></button><button class="ks-lib-act del" @click="delBook(b.id)"><Trash2 class="icon-xs" /></button></div></div></div>
      <p v-else class="ks-lib-empty">暂无已入库的书籍</p>
      <div v-if="store.searchHistory.length" class="ks-lib-hist"><div class="ks-lib-hdr"><History class="icon-xs" />搜索历史<button class="ks-lib-act" @click="clearHistory">清空</button></div><div class="ks-lib-hlist"><button v-for="h in store.searchHistory.slice(0,8)" :key="h.id" class="ks-hist-item" @click="searchByTag(h.query)">{{ h.query }}</button></div></div>
    </div>
  </div></transition>

  <UploadModal v-model:visible="showUploadModal" @upload-success="onUploaded" />
  <div v-if="previewVisible" class="ks-preview-overlay" @click="previewVisible=false"><img :src="previewImageUrl" class="ks-preview-img" @click.stop /><button class="ks-preview-close" @click="previewVisible=false"><X class="icon" /></button></div>
</div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { Search, Loader2, BookOpen, History, Clock, ChevronRight, ChevronLeft, Library, RefreshCw, Trash2, X, Sparkles, Image as ImageIcon, MessageCircle, Bot, User, Send, FileSearch, ListTree, FileCode, Share2, FileDown } from 'lucide-vue-next'
import { useKnowledgeStore } from '@/stores/knowledgeStore'
import { ElMessage, ElMessageBox } from 'element-plus'
import UploadModal from '@/components/UploadModal.vue'
import TableResultCard from '@/components/TableResultCard.vue'
import DocumentOutline from '@/components/DocumentOutline.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import ImageRelatedChunks from '@/components/ImageRelatedChunks.vue'

const store = useKnowledgeStore()
const searchInput = ref(''), hasSearched = ref(false), centered = ref(true), selectedBooks = ref([]), showUploadModal = ref(false), highlightedIndex = ref(-1), reingestingId = ref(null), searchInputRef = ref(null), activeMode = ref('search'), activeResult = ref(null), rightPanelOpen = ref(false), panelTab = ref('outline'), pdfUrl = ref('')
const documentOutline = ref([]), loadingOutline = ref(false), markdownContent = ref(''), loadingMarkdown = ref(false), relatedChunks = ref([]), loadingRelated = ref(false), libOpen = ref(false), previewVisible = ref(false), previewImageUrl = ref(''), mdContentRef = ref(null), chunkIndex = ref(0), loadingChunk = ref(false)
const outlineFilter = ref(''), filteredOutline = computed(()=>{var f=outlineFilter.value.trim();if(!f)return documentOutline.value;f=f.toLowerCase();return documentOutline.value.filter(o=>(o.title||'').toLowerCase().includes(f))})
const chatMessages = ref([]), chatInput = ref(''), chatLoading = ref(false), chatMsgsRef = ref(null), chatInputRef = ref(null)
const graphNodes = ref([]), graphEdges = ref([]), graphSvgW = ref(1000), graphSvgH = ref(700), graphLoading = ref(false), graphCanvasRef = ref(null), graphZoom = ref(1), graphPanX = ref(0), graphPanY = ref(0), graphDragging = ref(false), graphDragStart = ref({x:0,y:0})
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
function renderCitations(t){return(t||'').replace(/\[(\d+)\]/g,'<sup class="ks-cite">[$1]</sup>')}
function escapeHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function renderMd(t,l){if(!t)return l?'<span class="ks-loading-dots">...</span>':'';return t.replace(/\n/g,'<br>')}

function switchMode(m){
  if(m==='lib'){libOpen.value=!libOpen.value;if(libOpen.value)centered.value=false;return}
  centered.value=false
  activeMode.value=m
  libOpen.value=false
}

function goCentered(){centered.value=true;activeMode.value='search';closePanel();searchInput.value='';hasSearched.value=false;store.clearSearchResults();nextTick(()=>searchInputRef.value?.focus())}

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

async function performSearch(){if(!searchInput.value.trim())return;centered.value=false;hasSearched.value=true;highlightedIndex.value=-1;closePanel();activeMode.value='search';await store.search(searchInput.value,{bookIds:selectedBooks.value,limit:20})}
function searchByTag(t){searchInput.value=t;performSearch()}
function clearSearch(){searchInput.value='';hasSearched.value=false;centered.value=true;store.clearSearchResults();closePanel();nextTick(()=>searchInputRef.value?.focus())}
function onCitationClick(e){const c=e.target.closest('.ks-cite');if(!c)return;const m=c.textContent.match(/\d+/);if(!m)return;const s=(store.aiSummary?.sources||[])[parseInt(m[0])-1];if(s)scrollToResult(s)}
function scrollToResult(src){const i=store.searchResults.findIndex(r=>r.page_start===src.page&&r.book_title?.includes((src.book||'').replace(/[《》]/g,'')));if(i>=0)openDetail(store.searchResults[i],i)}
function closePanel(){rightPanelOpen.value=false;activeResult.value=null;pdfUrl.value='';documentOutline.value=[];markdownContent.value='';relatedChunks.value=[];outlineFilter.value=''}
function openDetail(r,i){activeResult.value=r;highlightedIndex.value=i;rightPanelOpen.value=true;panelTab.value='outline';documentOutline.value=[];markdownContent.value='';relatedChunks.value=[];outlineFilter.value='';chunkIndex.value=r.chunk_index??0;const b=r.book_id;if(r.result_type!=='image'&&b){pdfUrl.value=`/api/v1/knowledge/books/${b}/pdf`;loadOutline(b);loadMarkdown(b)}else if(r.result_type==='image'){pdfUrl.value='';if(r.image?.id)loadRelated(r.image.id)}}
async function loadPrevChunk(){if(loadingChunk.value||chunkIndex.value<=0)return;const id=activeResult.value?.book_id;if(!id)return;loadingChunk.value=true;try{const i=chunkIndex.value-1;const r=await fetch(`/api/v1/knowledge/books/${id}/chunks?offset=${i}&limit=1`);if(r.ok){const d=await r.json();if(d.length>0){chunkIndex.value=i;activeResult.value={...activeResult.value,...d[0],chunk_index:i}}}}catch{}finally{loadingChunk.value=false}}
async function loadNextChunk(){if(loadingChunk.value)return;const id=activeResult.value?.book_id;if(!id)return;loadingChunk.value=true;try{const i=(chunkIndex.value??0)+1;const r=await fetch(`/api/v1/knowledge/books/${id}/chunks?offset=${i}&limit=1`);if(r.ok){const d=await r.json();if(d.length>0){chunkIndex.value=i;activeResult.value={...activeResult.value,...d[0],chunk_index:i}}}}catch{}finally{loadingChunk.value=false}}
async function loadOutline(id){loadingOutline.value=true;try{const r=await fetch(`/api/v1/knowledge/books/${id}/outline`);if(r.ok)documentOutline.value=(await r.json()).outline||[]}catch{}finally{loadingOutline.value=false}}
async function loadMarkdown(id){loadingMarkdown.value=true;try{const r=await fetch(`/api/v1/knowledge/books/${id}/markdown`);if(r.ok)markdownContent.value=(await r.json()).markdown||''}catch{}finally{loadingMarkdown.value=false}}
async function loadRelated(id){loadingRelated.value=true;try{const r=await fetch(`/api/v1/knowledge/images/${id}/related-chunks`);if(r.ok)relatedChunks.value=(await r.json()).chunks||[]}catch{}finally{loadingRelated.value=false}}
function onOutlineClick(item){var isCross=item.target_book_id&&item.page&&item.target_book_id!==activeResult.value?.book_id;if(!isCross&&item.title&&markdownContent.value){panelTab.value='markdown';nextTick(()=>{if(mdContentRef.value){const el=mdContentRef.value.querySelector(`[data-section-id="${item.id}"]`)||[...mdContentRef.value.querySelectorAll('h1,h2,h3,h4')].find(h=>h.textContent?.trim()===item.title?.trim());if(el)el.scrollIntoView({behavior:'smooth',block:'start'})}})};if(isCross){window.open(`/api/v1/knowledge/books/${item.target_book_id}/pdf#page=${item.page}`,'_blank')}else if(item.page&&pdfUrl.value&&!item.target_book_id){window.open(`${pdfUrl.value}#page=${item.page}`,'_blank')}}
async function sendChat(msg){const t=(msg||chatInput.value).trim();if(!t||chatLoading.value)return;if(!msg)chatInput.value='';chatMessages.value.push({role:'user',content:t});chatMessages.value.push({role:'assistant',content:'',thinking:true});chatLoading.value=true;try{var ctx=chatMessages.value.filter(m=>m.role==='user').slice(-4).map(m=>m.content).join('\n');var query=ctx||t;const r=await fetch('/api/v1/knowledge/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:t,limit:5})});const d=await r.json();chatMessages.value.pop();chatMessages.value.push({role:'assistant',content:d.ai_summary?.answer||'未找到相关信息',thinking:false})}catch{chatMessages.value.pop();chatMessages.value.push({role:'assistant',content:'查询失败，请重试',thinking:false})}finally{chatLoading.value=false;nextTick(()=>{if(chatMsgsRef.value)chatMsgsRef.value.scrollTop=chatMsgsRef.value.scrollHeight})}}
function autoResize(){if(chatInputRef.value){chatInputRef.value.style.height='auto';chatInputRef.value.style.height=Math.min(chatInputRef.value.scrollHeight,120)+'px'}}
async function fetchGraph(){if(graphNodes.value.length)return;graphLoading.value=true;try{const r=await fetch('/api/v1/knowledge/graph');const d=await r.json(),raw=d.nodes||[],edges=d.edges||[];const colors={artist:'#c96442',artwork:'#e8a060',era:'#5a7d5a',book:'#4a7ab8',section:'#6b8eb5',technique:'#b8a47e'};const sizeMap={artist:{r:18,fs:11},artwork:{r:12,fs:10},era:{r:16,fs:11},book:{r:12,fs:10},section:{r:10,fs:9},technique:{r:9,fs:9}};const byType={};for(const n of raw)(byType[n.type]||=[]).push(n);const types=['artist','artwork','era','book','section','technique'];const cxMap={artist:120,artwork:330,era:530,book:730,section:880,technique:980};const W=1060,H=520;const pos=[];for(const t of types){const arr=byType[t]||[];const cx=cxMap[t]||500;const sz=sizeMap[t]||{r:10,fs:9};const rad=Math.max(40,Math.min(180,arr.length*13));for(let i=0;i<arr.length;i++){const a=(i/Math.max(arr.length-1,1))*Math.PI-Math.PI*0.5;const x=cx+Math.cos(a)*rad*0.5,y=H/2+Math.sin(a)*rad*0.4;const cnt=arr[i].count||1;const r=Math.max(sz.r-4,Math.min(sz.r,sz.r-4+Math.log(cnt+1)*3));pos.push({...arr[i],x,y,r,color:colors[arr[i].type]||'#888',fontSize:sz.fs})}}const nm={};for(const n of pos)nm[n.id]=n;const pe=[];for(const e of edges){const f=nm[e.from],t=nm[e.to];if(f&&t)pe.push({x1:f.x,y1:f.y,x2:t.x,y2:t.y})};graphNodes.value=pos;graphEdges.value=pe;graphSvgW.value=W;graphSvgH.value=H;graphZoom.value=1;graphPanX.value=0;graphPanY.value=0}catch{}finally{graphLoading.value=false}}
function onGraphWheel(e){e.preventDefault();const d=e.deltaY>0?0.9:1.1;const nv=Math.max(0.3,Math.min(5,graphZoom.value*d));graphZoom.value=nv}
function onGraphMouseDown(e){graphDragging.value=true;graphDragStart.value={x:e.clientX-graphPanX.value,y:e.clientY-graphPanY.value}}
function onGraphMouseMove(e){if(!graphDragging.value)return;graphPanX.value=e.clientX-graphDragStart.value.x;graphPanY.value=e.clientY-graphDragStart.value.y}
function onGraphMouseUp(){graphDragging.value=false}
function onUploaded(){store.fetchBooks();store.fetchStats()}
async function reingest(id){reingestingId.value=id;try{await store.reingestBook(id)}catch{}finally{reingestingId.value=null}}
async function delBook(id){try{await ElMessageBox.confirm('确定删除此书及其所有关联数据？','确认删除',{type:'warning'});await store.deleteBook(id)}catch{}}
async function clearHistory(){try{await ElMessageBox.confirm('确定清空所有搜索历史？','确认',{type:'warning'});await store.clearSearchHistory()}catch{}}
function openImagePreview(img){previewImageUrl.value=getImageUrl(img.stored_url||img.url||img.id||img);previewVisible.value=true}
onMounted(async()=>{await Promise.all([store.fetchBooks(),store.fetchStats(),store.fetchSearchHistory()]);nextTick(()=>searchInputRef.value?.focus())})
</script>

<style scoped>
.ks-root{min-height:100vh;background:#fafaf8}
/* ===== 居中欢迎态 ===== */
.ks-center-wrap{display:flex;justify-content:center;align-items:center;min-height:100vh;padding:24px}
.ks-center-body{text-align:center;max-width:640px;width:100%;margin-top:-80px}
.ks-center-title{font-family:'Noto Serif SC',serif;font-size:36px;font-weight:700;color:#141413;margin:0 0 6px}
.ks-center-sub{font-size:15px;color:#b0aca2;margin:0 0 32px}
.ks-center-search{display:flex;align-items:center;background:#fff;border:1.5px solid #e0ddd3;border-radius:12px;overflow:hidden;width:100%;margin-bottom:16px;transition:all 0.2s}
.ks-center-search:focus-within,.ks-bar-search:focus-within{border-color:#c96442;box-shadow:0 0 0 3px rgba(201,100,66,0.08)}
.ks-search-icon{color:#b8b4aa;margin-left:14px;width:18px;height:18px;flex-shrink:0}
.ks-center-input{flex:1;border:none;outline:none;padding:12px 10px;font-size:15px;color:#141413;background:transparent}
.ks-center-input::placeholder{color:#c0bdb3}
.ks-search-btn{border:none;background:#c96442;color:#fff;padding:12px 24px;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.2s;white-space:nowrap}
.ks-search-btn:hover{background:#a8513a}
.ks-search-btn:disabled{opacity:0.6;cursor:not-allowed}
.ks-mode-row{display:flex;justify-content:center;gap:8px;margin-bottom:16px}
.ks-mode-pill{border:1px solid #e0ddd3;background:#fff;padding:6px 16px;border-radius:20px;font-size:13px;color:#5e5d59;cursor:pointer;display:flex;align-items:center;gap:4px;transition:all 0.15s}
.ks-mode-pill:hover{border-color:#c96442;color:#c96442}
.ks-mode-pill.active{background:#c96442;color:#fff;border-color:#c96442}
.ks-mode-pill-icon{padding:6px 10px}
.ks-tags{display:flex;justify-content:center;flex-wrap:wrap;gap:8px}
.ks-tag-label{font-size:13px;color:#6b6b66;line-height:32px;margin-right:4px}
.ks-tag{border:1px solid #e0ddd3;background:#fff;padding:5px 16px;border-radius:20px;font-size:14px;color:#5e5d59;cursor:pointer;transition:all 0.15s}
.ks-tag:hover{border-color:#c96442;color:#c96442;background:#fdf8f5}

/* ===== 搜索视图 ===== */
.ks-search-view{padding:16px 24px 32px}
.ks-bar{display:flex;align-items:center;gap:12px;margin-bottom:0}
.ks-bar-title{font-family:'Noto Serif SC',serif;font-size:18px;font-weight:700;color:#141413;margin:0;white-space:nowrap}
.ks-bar-search{flex:1;max-width:520px;display:flex;align-items:center;background:#fff;border:1.5px solid #e0ddd3;border-radius:12px;overflow:hidden;transition:all 0.2s}
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
.ks-progress{height:3px;background:#f0ede4;border-radius:2px;margin-bottom:16px;overflow:hidden}
.ks-progress-fill{height:100%;background:#c96442;border-radius:2px;transition:width 0.3s}

/* AI摘要 */
.ks-card{background:#fff;border:1px solid #e8e4da;border-radius:14px;padding:16px 20px;margin-bottom:16px}
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
.ks-rcard{background:#fff;border:1px solid #e8e6dc;border-radius:12px;overflow:hidden;cursor:pointer;transition:all 0.15s;display:flex}
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

/* ===== 全屏视图（专家/图谱） ===== */
.ks-full-view{min-height:100vh;display:flex;flex-direction:column;padding:16px 24px}
.ks-full-top{display:flex;justify-content:center;margin-bottom:8px}
.ks-full-body{flex:1;display:flex;flex-direction:column;max-width:800px;width:100%;margin:0 auto}

/* 图谱 */
.ks-graph-box{flex:1;background:#fff;border:1px solid #e8e6dc;border-radius:12px;overflow:hidden;display:flex;align-items:center;justify-content:center;position:relative;min-height:300px;cursor:grab;touch-action:none}
.ks-graph-box:active{cursor:grabbing}
.ks-graph-viewport{width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden}
.ks-graph-svg{max-width:100%;max-height:100%;flex-shrink:0;will-change:transform}
.ks-graph-hint{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);font-size:11px;color:#ccc;pointer-events:none}
.ks-gnode circle{transition:r 0.2s;cursor:pointer}
.ks-gnode:hover circle{filter:brightness(0.9)}
.ks-gempty,.ks-gloading{color:#c0bdb3;font-size:14px;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);display:flex;align-items:center;gap:8px}
.ks-glegend{display:flex;justify-content:center;gap:16px;padding:8px 0;font-size:12px;color:#888}
.ks-ldot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}

/* 聊天 */
.ks-chat{display:flex;flex-direction:column;flex:1;min-height:200px;max-height:calc(100vh - 180px)}
.ks-chat-msgs{flex:1;overflow-y:auto;padding:8px 0}
.ks-chat-welcome{text-align:center;padding:24px 16px;color:#6b6b66}
.ks-chat-welcome-icon{color:#c96442;width:32px;height:32px;margin-bottom:8px}
.ks-chat-welcome h3{font-size:22px;margin:0 0 4px;color:#141413;font-family:'Noto Serif SC',serif}
.ks-chat-welcome p{font-size:13px;margin:0 0 12px;color:#999;max-width:480px;margin-left:auto;margin-right:auto}
.ks-chat-sugs{display:flex;flex-wrap:wrap;justify-content:center;gap:6px}
.ks-sug-btn{border:1px solid #e0ddd3;background:#fff;padding:5px 12px;border-radius:20px;font-size:12px;color:#5e5d59;cursor:pointer}
.ks-sug-btn:hover{border-color:#c96442;color:#c96442}
.ks-cmsg{display:flex;gap:8px;margin-bottom:12px}
.ks-cmsg.user{flex-direction:row-reverse}
.ks-cavatar{width:28px;height:28px;border-radius:50%;background:#f5f2eb;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ks-cmsg.user .ks-cavatar{background:#c96442;color:#fff}
.ks-ccontent{max-width:75%}
.ks-crole{font-size:11px;color:#999;margin-bottom:2px}
.ks-cmsg.user .ks-crole{text-align:right}
.ks-ctext{font-size:14px;line-height:1.6;padding:8px 12px;border-radius:10px;background:#fff;border:1px solid #e8e6dc;color:#3d3d3a}
.ks-cmsg.user .ks-ctext{background:#fdf8f5;border-color:#f0d4c8}
.ks-cthinking{font-size:13px;color:#b8b4aa;padding:8px 12px;display:flex;align-items:center;gap:6px}
.ks-chat-input{display:flex;gap:8px;padding:8px 0;border-top:1px solid #f0eee6}
.ks-chat-ta{flex:1;border:1.5px solid #e0ddd3;border-radius:10px;padding:8px 12px;font-size:14px;resize:none;outline:none;line-height:1.5}
.ks-chat-ta:focus{border-color:#c96442}
.ks-chat-send{border:none;background:#c96442;color:#fff;width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0}
.ks-chat-send:hover{background:#a8513a}
.ks-chat-send:disabled{opacity:0.5;cursor:not-allowed}

/* 右面板 */
.ks-panel{position:fixed;top:0;right:0;width:60vw;max-width:960px;min-width:480px;height:100vh;background:#fff;border-left:1px solid #e8e6dc;display:flex;flex-direction:column;z-index:100;box-shadow:-4px 0 20px rgba(0,0,0,0.06)}
.ks-phdr{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #f0eee6;flex-shrink:0}
.ks-ptitle{font-size:14px;font-weight:600;color:#141413;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ks-phdr-acts{display:flex;align-items:center;gap:6px}
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

/* 书库 */
.ks-lib-pop{position:fixed;top:64px;right:24px;width:360px;max-height:calc(100vh - 80px);overflow-y:auto;background:#fff;border:1px solid #e8e6dc;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.1);z-index:99}.ks-lib-inner{padding:14px}
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
.ks-lib-hdr{font-size:13px;font-weight:600;color:#303133;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.ks-lib-hlist{display:flex;flex-wrap:wrap;gap:4px}
.ks-hist-item{border:1px solid #e0ddd3;background:#fff;padding:3px 10px;border-radius:6px;font-size:12px;color:#6b6b66;cursor:pointer;transition:all 0.15s}
.ks-hist-item:hover{background:#fdf8f5;color:#c96442}

.ks-preview-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;z-index:999}
.ks-preview-img{max-width:90vw;max-height:90vh;object-fit:contain;border-radius:4px}
.ks-preview-close{position:absolute;top:24px;right:24px;border:none;background:rgba(255,255,255,0.15);color:#fff;width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer}
.ks-preview-close:hover{background:rgba(255,255,255,0.3)}

/* 动画 */
.fade-enter-active,.fade-leave-active{transition:all 0.35s ease}.fade-enter-from,.fade-leave-to{opacity:0;transform:translateY(8px)}
.slide-right-enter-active,.slide-right-leave-active{transition:all 0.3s}.slide-right-enter-from,.slide-right-leave-to{transform:translateX(100%);opacity:0}
.drop-enter-active,.drop-leave-active{transition:all 0.2s}.drop-enter-from,.drop-leave-to{opacity:0;transform:translateY(-8px)}

.icon{width:20px;height:20px}.icon-sm{width:16px;height:16px}.icon-xs{width:12px;height:12px}
.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

@media(max-width:1024px){.ks-panel{width:100vw;min-width:auto}.ks-body-wrap.with-panel .ks-main{margin-right:0}.ks-lib-pop{right:12px;width:calc(100vw-24px)}}
</style>
