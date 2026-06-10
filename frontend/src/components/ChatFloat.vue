<template>
  <div class="cf-shell" v-if="authStore.isLoggedIn">
    <!-- 浮动按钮 -->
    <button v-if="!open" :class="['cf-fab', isExpertMode ? 'cf-fab-expert' : '']" @click="openChat" :title="isExpertMode ? artistName + '研究专家' : '小墨'">
      <MessageCircle class="cf-fab-icon" />
      <span v-if="isExpertMode" class="cf-fab-badge">{{ artistName.charAt(0) }}</span>
    </button>

    <!-- 浮窗模式 -->
    <transition name="cf-panel">
      <div v-if="open && !expanded" class="cf-panel">
        <div :class="['cf-hdr', isExpertMode ? 'cf-hdr-expert' : '']">
          <span class="cf-hdr-title">{{ isExpertMode ? artistName + '研究专家' : '小墨' }}</span>
          <div class="cf-hdr-actions">
            <button class="cf-hdr-btn" @click="expanded = true" title="展开完整模式">
              <Maximize2 class="icon-sm" />
            </button>
            <button class="cf-hdr-btn" @click="open=false"><X class="icon-sm" /></button>
          </div>
        </div>
        <div class="cf-body">
          <div class="cf-msgs" ref="msgsRef">
            <div v-if="messages.length===0" class="cf-welcome">
              <Sparkles class="cf-welcome-icon" />
              <p>{{ isExpertMode ? '有关于' + artistName + '的问题，随时问我' : '有任何关于中国画的问题，随时问我' }}</p>
              <div class="cf-sugs">
                <button v-for="s in suggestions" :key="s" class="cf-sug" @click="send(s)">{{ s }}</button>
              </div>
            </div>
            <div v-for="(m,i) in messages" :key="m.id||i" :class="['cf-msg',m.role]">
              <div v-if="m.thinking" class="cf-thinking"><Sparkles class="icon-xs" />思考中 {{ thinkSeconds }}s...</div>
              <div v-else class="cf-text" v-html="renderMd(m.content)" @click="onContentClick"></div>
              <div v-if="m.role==='assistant'&&m.sources&&m.sources.length" class="cf-sources">
                <div v-for="s in m.sources" :key="s.index" class="cf-src" @click="citationSource=s">
                  <span class="cf-src-idx">[{{ s.index }}]</span>
                  <span class="cf-src-book">{{ s.book }}</span>
                </div>
              </div>
              <div v-if="m.role==='assistant'&&m.sources" class="cf-gallery">
                <div class="cf-gallery-title">🖼 相关作品</div>
                <div class="cf-gallery-grid">
                  <template v-for="s in m.sources" :key="'img-'+s.index">
                    <a v-if="s.thumbnail_url" :href="chatLink(s.url)" target="_blank" class="cf-gallery-card">
                      <div class="cf-gallery-img-wrap"><img :src="s.thumbnail_url" :alt="s.name||s.book" class="cf-gallery-img" loading="lazy" @error="$event.target.parentElement.style.display='none'" /></div>
                      <div class="cf-gallery-meta"><span class="cf-gallery-name">{{ s.name || s.book }}</span></div>
                    </a>
                  </template>
                </div>
              </div>
            </div>
          </div>
          <div class="cf-input-row">
            <textarea ref="inputRef" v-model="input" class="cf-ta" placeholder="问点什么..." @keydown.enter.exact.prevent="send()" @input="autoResize" rows="1" :disabled="loading"></textarea>
            <button class="cf-send" @click="send()" :disabled="!input.trim()||loading">
              <Send v-if="!loading" class="icon-sm" /><Loader2 v-else class="icon-sm spin" />
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 完整模式（全屏） -->
    <Teleport to="body">
      <transition name="cf-fullscreen">
        <div v-if="open && expanded" class="cf-fullscreen">
          <!-- 左侧：历史会话 -->
          <aside class="cf-history">
            <div class="cf-history-hdr">
              <span class="cf-history-title">对话历史</span>
              <button class="cf-hdr-btn" @click="startNewChat" title="新对话"><Plus class="icon-sm" /></button>
            </div>
            <div class="cf-history-list">
              <div v-for="s in filteredSessions" :key="s.id" class="cf-history-item" :class="{ active: chatStore.floatSessionId === s.id || chatStore.artistExpertSessionId === s.id }" @click="switchSession(s.id)">
                <div class="cf-history-item-title">{{ s.title || '新对话' }}</div>
                <div class="cf-history-item-meta">{{ s.message_count || 0 }} 条 · {{ formatTime(s.updated_at) }}</div>
                <button class="cf-history-del" @click.stop="deleteSession(s.id)" title="删除对话"><X class="icon-xs" /></button>
              </div>
              <div v-if="filteredSessions.length === 0" class="cf-history-empty">暂无历史对话</div>
            </div>
          </aside>

          <!-- 右侧：聊天区 -->
          <div class="cf-chat-main">
            <div :class="['cf-chat-hdr', isExpertMode ? 'cf-hdr-expert' : '']">
              <div class="cf-chat-hdr-left">
                <span class="cf-chat-hdr-title">{{ isExpertMode ? artistName + '研究专家' : '小墨 · 知识问答' }}</span>
                <span class="cf-chat-hdr-sub" v-if="currentSessionTitle">{{ currentSessionTitle }}</span>
              </div>
              <div class="cf-hdr-actions">
                <button class="cf-hdr-btn" @click="expanded = false" title="收起为浮窗">
                  <Minimize2 class="icon-sm" />
                </button>
                <button class="cf-hdr-btn" @click="open=false; expanded=false"><X class="icon-sm" /></button>
              </div>
            </div>

            <div class="cf-chat-body">
              <div class="cf-msgs cf-msgs-full" ref="msgsRefFull">
                <div v-if="messages.length===0" class="cf-welcome cf-welcome-full">
                  <Sparkles class="cf-welcome-icon" />
                  <p>{{ isExpertMode ? '我是' + artistName + '研究专家，基于该画家的学术文献为您解答' : '有任何关于中国画的问题，随时问我' }}</p>
                  <div class="cf-sugs">
                    <button v-for="s in suggestions" :key="s" class="cf-sug" @click="send(s)">{{ s }}</button>
                  </div>
                </div>
                <div v-for="(m,i) in messages" :key="'full-'+(m.id||i)" :class="['cf-msg',m.role]">
                  <div v-if="m.thinking" class="cf-thinking"><Sparkles class="icon-xs" />思考中 {{ thinkSeconds }}s...</div>
                  <div v-else class="cf-text cf-text-full" v-html="renderMd(m.content)" @click="onContentClick"></div>
                  <div v-if="m.role==='assistant'&&m.sources&&m.sources.length" class="cf-sources">
                    <div v-for="s in m.sources" :key="s.index" class="cf-src" @click="citationSource=s">
                      <span class="cf-src-idx">[{{ s.index }}]</span>
                      <span class="cf-src-book">{{ s.book }}</span>
                    </div>
                  </div>
                  <div v-if="m.role==='assistant'&&m.sources" class="cf-gallery">
                    <div class="cf-gallery-title">🖼 相关作品</div>
                    <div class="cf-gallery-grid">
                      <template v-for="s in m.sources" :key="'fimg-'+s.index">
                        <a v-if="s.thumbnail_url" :href="chatLink(s.url)" target="_blank" class="cf-gallery-card">
                          <div class="cf-gallery-img-wrap"><img :src="s.thumbnail_url" :alt="s.name||s.book" class="cf-gallery-img" loading="lazy" @error="$event.target.parentElement.style.display='none'" /></div>
                          <div class="cf-gallery-meta"><span class="cf-gallery-name">{{ s.name || s.book }}</span></div>
                        </a>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="cf-input-row cf-input-full">
              <textarea ref="inputRefFull" v-model="input" class="cf-ta cf-ta-full" placeholder="输入问题..." @keydown.enter.exact.prevent="send()" @input="autoResize" rows="2" :disabled="loading"></textarea>
              <button class="cf-send cf-send-full" @click="send()" :disabled="!input.trim()||loading">
                <Send v-if="!loading" class="icon-sm" /><Loader2 v-else class="icon-sm spin" />
              </button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- 引用弹窗 -->
    <Teleport to="body">
      <div v-if="citationSource" class="cf-cite-overlay" @click="citationSource=null">
        <div class="cf-cite-modal" @click.stop>
          <div class="cf-cite-hd">
            <span class="cf-cite-idx">[{{ citationSource.index }}]</span>
            <span class="cf-cite-title">{{ citationSource.book }}</span>
            <button class="cf-cite-close" @click="citationSource=null"><X class="icon-sm" /></button>
          </div>
          <div class="cf-cite-body">
            <div v-if="citationSource._source==='database'" class="cf-cite-db">
              <span class="cf-cite-type">{{ {artwork:'画作',artist:'艺术家',seal:'印章'}[citationSource.type]||'实体' }}</span>
              <a v-if="citationSource.url" :href="chatLink(citationSource.url)" class="cf-cite-go">查看详情 →</a>
            </div>
            <div v-else class="cf-cite-book">
              <span v-if="citationSource.book">《{{ citationSource.book }}》</span>
              <span v-if="citationSource.page">第{{ citationSource.page }}页</span>
            </div>
            <p v-if="citationSource.snippet" class="cf-cite-snippet">"{{ citationSource.snippet }}"</p>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { MessageCircle, X, Sparkles, Send, Loader2, Maximize2, Minimize2, Plus } from 'lucide-vue-next'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../stores/chatStore'
import { ElMessage } from 'element-plus'

const props = defineProps({
  artistId: { type: Number, default: null },
  artistName: { type: String, default: null },
})

const isExpertMode = computed(() => props.artistId && props.artistName)

// 切换画家时清除专家 session 和消息
watch(() => props.artistId, (newId, oldId) => {
  if (newId !== oldId) {
    chatStore.setArtistExpertSession(null)
    messages.value = []
  }
})

const authStore = useAuthStore()
const chatStore = useChatStore()
const open = ref(false)
const expanded = ref(false)
const messages = ref([])
const input = ref('')
const loading = ref(false)
const msgsRef = ref(null)
const msgsRefFull = ref(null)
const inputRef = ref(null)
const inputRefFull = ref(null)
const citationSource = ref(null)
const thinkSeconds = ref(0)
let thinkTimer = null

// 完整模式：历史会话
const filteredSessions = computed(() => {
  if (isExpertMode.value) {
    return chatStore.sessions.filter(s => s.artist_id === props.artistId)
  }
  return chatStore.sessions.filter(s => !s.artist_id)
})
const currentSessionTitle = computed(() => {
  const sid = isExpertMode.value ? chatStore.artistExpertSessionId : chatStore.floatSessionId
  const s = chatStore.sessions.find(x => x.id === sid)
  return s?.title || null
})

async function loadHistory() {
  await chatStore.fetchSessions()
}

async function switchSession(sessionId) {
  const sid = isExpertMode.value ? chatStore.artistExpertSessionId : chatStore.floatSessionId
  if (sid === sessionId) return
  if (isExpertMode.value) chatStore.setArtistExpertSession(sessionId)
  else chatStore.setFloatSession(sessionId)
  messages.value = []
  const msgs = await chatStore.fetchMessages(sessionId)
  messages.value = msgs
  nextTick(scrollToBottom)
}

function startNewChat() {
  if (isExpertMode.value) chatStore.setArtistExpertSession(null)
  else chatStore.setFloatSession(null)
  messages.value = []
}

async function deleteSession(sessionId) {
  await chatStore.deleteSession(sessionId)
  // 如果删的是当前会话，清空消息
  const sid = isExpertMode.value ? chatStore.artistExpertSessionId : chatStore.floatSessionId
  if (!sid) messages.value = []
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const suggestions = computed(() => isExpertMode.value
  ? [`${props.artistName}的代表作有哪些？`, `${props.artistName}的艺术风格特点？`, `${props.artistName}的创作分期？`]
  : ['写意画中的气韵生动是什么意思？', '潘天寿的构图法则有哪些？', '李鱓最消极的一幅画是哪幅？']
)

function openChat() {
  open.value = true
  loadHistory()
  nextTick(scrollToBottom)
}

function scrollToBottom() {
  const el = expanded.value ? msgsRefFull.value : msgsRef.value
  if (el) el.scrollTop = el.scrollHeight
  const inp = expanded.value ? inputRefFull.value : inputRef.value
  if (inp) inp.focus()
}

// 展开/收起时同步滚动和焦点
watch(expanded, () => nextTick(scrollToBottom))

function autoResize() {
  if (inputRef.value) {
    inputRef.value.style.height = 'auto'
    inputRef.value.style.height = Math.min(inputRef.value.scrollHeight, 80) + 'px'
  }
}

function chatLink(url) {
  if (!url) return ''
  const t = url.match(/\/tiba\/[a-f0-9-]{8,}/)
  if (t) return '#' + t[0]
  const a = url.match(/\/artist\/[^)\s]+/)
  if (a) return '#' + a[0]
  return url.startsWith('/') ? '#' + url : url
}

function onContentClick(e) {
  const cite = e.target.closest('.ks-cite')
  if (!cite) return
  const idx = parseInt(cite.getAttribute('data-idx') || cite.textContent.replace(/[\[\]]/g, ''))
  if (!idx) return
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'assistant' && m.sources) {
      const s = m.sources.find(x => x.index === idx)
      if (s) { citationSource.value = s; return }
    }
  }
}

function renderMd(t) {
  if (!t) return ''
  let h = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  h = h.replace(/^---$/gm, '<hr>')
  h = h.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/`([^`\n]+)`/g, '<code>$1</code>')
  // Markdown 图片 ![alt](url) → <img> 缩略图（必须在链接之前处理）
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="chat-thumb" loading="lazy" onerror="this.style.display=\'none\'" />')
  // Markdown 链接 [text](url) — 提取 /tiba/UUID 或 /artist/名 路径转为 hash 格式
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
    const tibaMatch = url.match(/\/tiba\/[a-f0-9-]{8,}/)
    const artistMatch = url.match(/\/artist\/[^)\s]+/)
    let href = url
    if (tibaMatch) href = '#' + tibaMatch[0]
    else if (artistMatch) href = '#' + artistMatch[0]
    else if (url.startsWith('/')) href = '#' + url
    return `<a href="${href}" target="_blank">${text}</a>`
  })
  h = h.replace(/^- (.+)$/gm, '<li>$1</li>')
  h = h.replace(/\[(\d+)\]/g, '<sup class="ks-cite" data-idx="$1">[$1]</sup>')
  h = h.replace(/\n/g, '<br>')
  return h
}

async function send(msg) {
  const t = (msg || input.value).trim()
  if (!t || loading.value) return
  if (!msg) input.value = ''

  messages.value.push({ role: 'user', content: t })
  messages.value.push({ role: 'assistant', content: '', thinking: true, loading: true })
  loading.value = true
  thinkSeconds.value = 0
  if (thinkTimer) clearInterval(thinkTimer)
  thinkTimer = setInterval(() => { thinkSeconds.value++ }, 1000)
  nextTick(scrollToBottom)

  try {
    const body = { prompt: t }
    if (isExpertMode.value) {
      body.artist_id = props.artistId
      body.artist_name = props.artistName
      if (chatStore.artistExpertSessionId) body.session_id = chatStore.artistExpertSessionId
    } else {
      if (chatStore.floatSessionId) body.session_id = chatStore.floatSessionId
    }

    const r = await fetch('/api/v1/knowledge/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authStore.token}` },
      body: JSON.stringify(body),
    })

    if (!r.ok) {
      const errText = await r.text().catch(() => '')
      throw new Error(`HTTP ${r.status}: ${errText.slice(0, 100)}`)
    }

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
        if (line.startsWith('event: ')) { textEvent = line.slice(7).trim() === 'text'; continue }
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6))
            const last = messages.value[messages.value.length - 1]
            if (!last || last.role !== 'assistant') continue
            if (last.thinking) { last.thinking = false; last.content = ''; if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null } }
            if (textEvent) { last.content += d.content || '' }
            else if (d.sources) { last.sources = d.sources }
            if (d.session_id) {
              if (isExpertMode.value && !chatStore.artistExpertSessionId) chatStore.setArtistExpertSession(d.session_id)
              else if (!isExpertMode.value && !chatStore.floatSessionId) chatStore.setFloatSession(d.session_id)
            }
          } catch {}
        }
      }
    }

    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.thinking = false; last.loading = false
      if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
      if (!last.content) last.content = '未找到相关信息'
    }
  } catch(e) {
    console.error('[小墨] 发送失败:', e)
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.thinking = false; last.loading = false; last.content = '查询失败，请重试'
    }
    if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
    try { ElMessage.error('小墨暂时无法回答，请稍后重试') } catch {}
  } finally {
    loading.value = false
    nextTick(scrollToBottom)
  }
}
</script>

<style scoped>
.cf-shell{position:fixed;bottom:20px;right:20px;z-index:99998}
.cf-fab{width:52px;height:52px;border-radius:50%;border:none;background:#c96442;color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 16px rgba(201,100,66,0.35);transition:all 0.2s;position:relative}
.cf-fab:hover{transform:scale(1.08);box-shadow:0 6px 20px rgba(201,100,66,0.45)}
.cf-fab-expert{background:#2d6a4f;box-shadow:0 4px 16px rgba(45,106,79,0.35)}
.cf-fab-expert:hover{box-shadow:0 6px 20px rgba(45,106,79,0.45)}
.cf-fab-badge{position:absolute;bottom:-2px;right:-2px;width:20px;height:20px;border-radius:50%;background:#fff;color:#2d6a4f;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;border:2px solid #2d6a4f}
.cf-fab-icon{width:22px;height:22px}
.cf-hdr-expert{background:#f0f7f4;border-bottom-color:#b7e4c7}
.cf-hdr-expert .cf-hdr-title{color:#2d6a4f}
.cf-panel-enter-active{transition:all 0.25s cubic-bezier(0.4,0,0.2,1)}
.cf-panel-leave-active{transition:all 0.2s ease}
.cf-panel-enter-from,.cf-panel-leave-to{opacity:0;transform:translateY(16px) scale(0.95)}
.cf-panel{position:fixed;bottom:20px;right:20px;width:420px;height:600px;background:#fafaf8;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.18),0 2px 12px rgba(0,0,0,0.08);display:flex;flex-direction:column;overflow:hidden;z-index:99999;transition:all 0.3s cubic-bezier(0.4,0,0.2,1)}
.cf-hdr{display:flex;align-items:center;justify-content:space-between;padding:0 16px;height:48px;border-bottom:1px solid #e8e6dc;background:#fff;flex-shrink:0}
.cf-hdr-title{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600;color:#141413}
.cf-hdr-actions{display:flex;align-items:center;gap:4px}
.cf-hdr-btn{border:none;background:transparent;color:#999;cursor:pointer;padding:6px;border-radius:6px;display:flex;align-items:center;transition:all 0.15s}
.cf-hdr-btn:hover{background:#f5f2eb;color:#3d3d3a}
.cf-body{flex:1;display:flex;flex-direction:column;overflow:hidden}
.cf-msgs{flex:1;overflow-y:auto;padding:12px 16px;scroll-behavior:smooth}
.cf-msgs::-webkit-scrollbar{width:6px}
.cf-msgs::-webkit-scrollbar-track{background:transparent}
.cf-msgs::-webkit-scrollbar-thumb{background:#d8d4cc;border-radius:3px}
.cf-msgs::-webkit-scrollbar-thumb:hover{background:#c0bbb3}
.cf-welcome{text-align:center;padding:40px 16px;margin-top:20px}
.cf-welcome-icon{color:#c96442;width:32px;height:32px;margin-bottom:10px}
.cf-welcome p{font-size:14px;color:#8a877e;margin:0 0 14px}
.cf-sugs{display:flex;flex-wrap:wrap;justify-content:center;gap:6px}
.cf-sug{border:1px solid #d8d4cc;background:#fff;padding:6px 14px;border-radius:20px;font-size:13px;color:#5e5d59;cursor:pointer;transition:all 0.2s}
.cf-sug:hover{border-color:#c96442;color:#c96442;background:#fdf8f5}
.cf-msg{padding:8px 0;animation:cf-msg-in 0.2s ease both}
@keyframes cf-msg-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.cf-msg.assistant{background:#fff;padding:12px 16px;border-radius:10px;margin-bottom:2px}
.cf-msg.user{display:flex;justify-content:flex-end;padding:6px 0}
.cf-msg.user .cf-text{background:#e8e4dc;border-radius:16px;padding:9px 14px;display:inline-block;max-width:85%;min-width:fit-content;font-size:14px;color:#333;word-break:break-word;white-space:pre-wrap}
.cf-msg.assistant .cf-text{font-size:14px;line-height:1.65;color:#333;padding:0}
.cf-msg.assistant .cf-text :deep(*){font-family:'Arial','PingFang SC','Microsoft YaHei',sans-serif;line-height:1.65}
.cf-msg.assistant .cf-text :deep(h2),.cf-msg.assistant .cf-text :deep(h3){margin:10px 0 4px;color:#333;font-weight:600;font-size:14px}
.cf-msg.assistant .cf-text :deep(p){margin:0 0 8px}
.cf-msg.assistant .cf-text :deep(strong){color:#333;font-weight:600}
.cf-msg.assistant .cf-text :deep(blockquote){margin:8px 0;padding:8px 12px;border-left:3px solid #c96442;background:#faf9f7;color:#555;border-radius:0 6px 6px 0}
.cf-msg.assistant .cf-text :deep(ul),.cf-msg.assistant .cf-text :deep(ol){margin:4px 0;padding-left:20px}
.cf-msg.assistant .cf-text :deep(li){margin:2px 0;line-height:1.6}
.cf-msg.assistant .cf-text :deep(li)::marker{color:#c96442}
.cf-msg.assistant .cf-text :deep(code){background:#f0eee6;padding:1px 4px;border-radius:3px;font-size:12px;color:#c96442}
.cf-msg.assistant .cf-text :deep(a){color:#c96442;text-decoration:underline;text-underline-offset:2px}
.cf-thinking{font-size:13px;color:#8a877e;padding:4px 0;display:flex;align-items:center;gap:4px;animation:cf-pulse 1.5s ease-in-out infinite}
@keyframes cf-pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.cf-sources{margin-top:8px;padding:8px 12px;background:#faf9f7;border-radius:8px;border:1px solid #ece9e0}
.cf-src{display:flex;align-items:center;gap:3px;padding:3px 6px;border-radius:4px;font-size:12px;cursor:pointer;transition:background 0.15s}
.cf-src:hover{background:#f0ede5}
.cf-src-idx{color:#c96442;font-weight:600;flex-shrink:0}
.cf-src-book{color:#8a877e}
.cf-input-row{display:flex;align-items:flex-end;gap:6px;padding:10px 14px;border-top:1px solid #e8e6dc;background:#fff}
.cf-ta{flex:1;border:1px solid #d8d4cc;border-radius:12px;padding:8px 12px;font-size:13px;line-height:1.4;resize:none;outline:none;background:#fff;font-family:inherit;max-height:80px}
.cf-ta:focus{border-color:#c96442}
.cf-ta::placeholder{color:#b0aca2}
.cf-send{border:none;background:#141413;color:#fff;width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;transition:background 0.15s}
.cf-send:hover{background:#333}
.cf-send:disabled{opacity:0.3;cursor:not-allowed}
.spin{animation:cf-spin 1s linear infinite}
@keyframes cf-spin{to{transform:rotate(360deg)}}

/* 引用弹窗 */
.cf-cite-overlay{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center}
.cf-cite-modal{background:#fff;border-radius:12px;max-width:380px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.15);overflow:hidden}
.cf-cite-hd{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #ece9e0}
.cf-cite-idx{color:#c96442;font-weight:700;font-size:14px}
.cf-cite-title{font-size:14px;font-weight:600;color:#141413;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cf-cite-close{border:none;background:transparent;color:#999;cursor:pointer;padding:4px;border-radius:4px}
.cf-cite-body{padding:14px}
.cf-cite-db{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.cf-cite-type{background:#fef0e8;color:#c96442;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600}
.cf-cite-go{color:#c96442;font-size:12px;text-decoration:none;font-weight:600}
.cf-cite-book{font-size:13px;color:#5e5d59;margin-bottom:8px}
.cf-cite-snippet{font-size:13px;line-height:1.6;color:#3d3d3a;background:#faf9f7;padding:10px;border-radius:6px;border-left:3px solid #c96442;margin:0}
.chat-thumb{display:block;max-width:160px;max-height:120px;border-radius:6px;margin:8px 0;cursor:pointer;border:1px solid #e8e4d8;object-fit:cover;transition:transform 0.2s}
.chat-thumb:hover{transform:scale(1.05)}
.cf-gallery{margin-top:10px;border-top:1px solid #eae6de;padding-top:10px}
.cf-gallery-title{font-size:12px;font-weight:600;color:#5c5346;margin-bottom:8px}
.cf-gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px}
.cf-gallery-card{display:block;text-decoration:none;border-radius:6px;overflow:hidden;background:#fff;border:1px solid #e8e4d8;transition:box-shadow 0.2s,transform 0.15s}
.cf-gallery-card:hover{box-shadow:0 3px 10px rgba(0,0,0,0.1);transform:translateY(-2px)}
.cf-gallery-img-wrap{width:100%;aspect-ratio:4/3;overflow:hidden;background:#f5f0e8}
.cf-gallery-img{width:100%;height:100%;object-fit:cover;display:block;transition:transform 0.3s}
.cf-gallery-card:hover .cf-gallery-img{transform:scale(1.06)}
.cf-gallery-meta{padding:4px 6px}
.cf-gallery-name{font-size:11px;color:#3a3222;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ─── 完整模式（全屏）照搬知识库小墨样式 ─── */
.cf-fullscreen-enter-active{transition:all 0.3s cubic-bezier(0.4,0,0.2,1)}
.cf-fullscreen-leave-active{transition:all 0.2s ease}
.cf-fullscreen-enter-from,.cf-fullscreen-leave-to{opacity:0}
.cf-fullscreen{position:fixed;top:0;left:0;right:0;bottom:0;z-index:100000;display:flex;background:#fafaf8;overflow:hidden}
.cf-history{width:260px;flex-shrink:0;background:#fff;border-right:1px solid #e8e6dc;display:flex;flex-direction:column}
.cf-history-hdr{display:flex;align-items:center;justify-content:space-between;padding:0 16px;height:48px;border-bottom:1px solid #e8e6dc}
.cf-history-title{font-size:14px;font-weight:600;color:#141413}
.cf-history-list{flex:1;overflow-y:auto;padding:8px}
.cf-history-item{padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:2px;transition:background 0.12s;position:relative}
.cf-history-item:hover{background:#f5f2eb}
.cf-history-item.active{background:#fdf8f5;border-left:3px solid #c96442}
.cf-history-item-title{font-size:13px;color:#141413;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:20px}
.cf-history-item-meta{font-size:11px;color:#b0aca2;margin-top:2px}
.cf-history-del{position:absolute;top:10px;right:8px;border:none;background:transparent;color:#ccc;cursor:pointer;padding:2px;border-radius:4px;opacity:0;transition:opacity 0.15s}
.cf-history-item:hover .cf-history-del{opacity:1}
.cf-history-del:hover{color:#e74c3c;background:#fef2f2}
.cf-history-empty{text-align:center;padding:40px 16px;color:#b0aca2;font-size:13px}
.cf-chat-main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh;overflow:hidden}
.cf-chat-hdr{display:flex;align-items:center;gap:8px;padding:0 20px;height:48px;border-bottom:1px solid #e8e6dc;background:#fff;flex-shrink:0}
.cf-chat-hdr-left{display:flex;align-items:baseline;gap:12px;min-width:0;flex:1}
.cf-chat-hdr-title{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600;color:#141413}
.cf-chat-hdr-sub{font-size:13px;color:#8a877e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cf-chat-body{flex:1;display:flex;flex-direction:column;overflow:hidden;max-width:920px;width:100%;margin:0 auto;padding:0 32px;position:relative}
.cf-msgs-full{flex:1;overflow-y:auto;padding:16px 8px 8px;scroll-behavior:smooth}
.cf-msgs-full::-webkit-scrollbar{width:6px}
.cf-msgs-full::-webkit-scrollbar-track{background:transparent}
.cf-msgs-full::-webkit-scrollbar-thumb{background:#d8d4cc;border-radius:3px}
.cf-welcome-full{text-align:center;padding:40px 16px;margin-top:10vh}
.cf-welcome-full .cf-welcome-icon{color:#c96442;width:40px;height:40px;margin-bottom:12px}
.cf-welcome-full p{font-size:14px;color:#8a877e;margin:0 0 16px;max-width:480px;margin-left:auto;margin-right:auto}
.cf-welcome-full .cf-sugs{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}
.cf-welcome-full .cf-sug{border:1px solid #d8d4cc;background:#fff;padding:6px 14px;border-radius:20px;font-size:13px;color:#5e5d59;cursor:pointer;transition:all 0.2s}
.cf-welcome-full .cf-sug:hover{border-color:#c96442;color:#c96442;background:#fdf8f5}
/* 消息气泡 — 照搬知识库 */
.cf-fullscreen .cf-msg{padding:8px 0;max-width:860px;margin:0 auto}
.cf-fullscreen .cf-msg.assistant{background:#fff;padding:14px 20px;border-radius:10px;margin-bottom:2px}
.cf-fullscreen .cf-msg.user{display:flex;justify-content:flex-end;padding:6px 0}
.cf-fullscreen .cf-msg.user .cf-text{background:#e8e4dc;border-radius:16px;padding:9px 14px;display:inline-block;max-width:85%;font-size:14px;color:#333;word-break:break-word;white-space:pre-wrap}
.cf-fullscreen .cf-msg.assistant .cf-text{font-size:15px;line-height:1.7;color:#333;padding:0}
.cf-fullscreen .cf-text :deep(*){font-family:'Arial','PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7}
.cf-fullscreen .cf-text :deep(h1),.cf-fullscreen .cf-text :deep(h2),.cf-fullscreen .cf-text :deep(h3){margin:16px 0 8px;color:#333;font-weight:600}
.cf-fullscreen .cf-text :deep(h2){font-size:16px}.cf-fullscreen .cf-text :deep(h3){font-size:15px}
.cf-fullscreen .cf-text :deep(p){margin:0 0 10px}
.cf-fullscreen .cf-text :deep(strong){color:#333;font-weight:600}
.cf-fullscreen .cf-text :deep(blockquote){margin:10px 0;padding:10px 14px;border-left:3px solid #c96442;background:#faf9f7;color:#555;border-radius:0 6px 6px 0}
.cf-fullscreen .cf-text :deep(ul),.cf-fullscreen .cf-text :deep(ol){margin:8px 0;padding-left:22px}
.cf-fullscreen .cf-text :deep(li){margin:4px 0}
.cf-fullscreen .cf-text :deep(li)::marker{color:#c96442}
.cf-fullscreen .cf-text :deep(code){background:#f0eee6;padding:2px 5px;border-radius:3px;font-size:13px;color:#c96442}
.cf-fullscreen .cf-text :deep(hr){border:none;border-top:1px solid #e8e6dc;margin:14px 0}
.cf-fullscreen .cf-text :deep(a){color:#c96442;text-decoration:underline;text-underline-offset:2px}
/* Sources card */
.cf-fullscreen .cf-sources{margin-top:12px;padding:10px 14px;background:#faf9f7;border-radius:8px;border:1px solid #ece9e0}
.cf-fullscreen .cf-src{display:flex;align-items:center;gap:3px;padding:3px 6px;border-radius:4px;font-size:12px;cursor:pointer;transition:background 0.15s}
.cf-fullscreen .cf-src:hover{background:#f0ede5}
.cf-fullscreen .cf-src-idx{color:#c96442;font-weight:600}
.cf-fullscreen .cf-src-book{color:#8a877e}
/* 输入区 */
.cf-input-full{display:flex;align-items:flex-end;gap:6px;padding:12px 20px;border-top:1px solid #e8e6dc;background:#fff;max-width:920px;width:100%;margin:0 auto;box-sizing:border-box}
.cf-ta-full{flex:1;border:1px solid #d8d4cc;border-radius:12px;padding:8px 12px;font-size:14px;line-height:1.5;resize:none;outline:none;background:#fff;font-family:inherit;max-height:120px;min-height:44px}
.cf-ta-full:focus{border-color:#c96442}
.cf-send-full{border:none;background:#141413;color:#fff;width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0}
.cf-send-full:disabled{opacity:0.3;cursor:not-allowed}
</style>
