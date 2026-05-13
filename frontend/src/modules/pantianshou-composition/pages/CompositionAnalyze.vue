<template>
  <div class="page composition-page">
    <!-- 页面标题 -->
    <div class="comp-header">
      <h1>潘天寿教你构图</h1>
      <p class="sub">上传国画图片，AI 基于潘天寿构图理论进行七维结构分析与智能专家讲评</p>
      <div class="header-ornament">
        <span class="ornament-line"></span>
        <span class="ornament-dot">◇</span>
        <span class="ornament-line"></span>
      </div>
    </div>

    <el-card class="card" shadow="never">
      <div class="upload-layout">
        <div class="upload-left">
          <div class="upload-title">上传画作</div>
          <div class="upload-box" :class="{ 'has-preview': previewUrl }">
            <el-upload
              class="uploader"
              drag
              :auto-upload="false"
              :limit="1"
              :file-list="fileList"
              :on-change="onFileChange"
              :on-remove="onFileRemove"
              accept="image/*"
            >
              <!-- 有预览图时显示图片 -->
              <template v-if="previewUrl">
                <div class="preview-inner">
                  <img :src="previewUrl" class="preview-img-inline" />
                  <div class="preview-overlay">
                    <el-button class="preview-change-btn" type="primary" size="small">更换图片</el-button>
                  </div>
                </div>
              </template>
              <!-- 无图时显示提示 -->
              <template v-else>
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">将文件拖到此区域，或点击上传</div>
                <div class="upload-hint">支持 JPG/PNG，建议清晰拍摄或扫描稿</div>
              </template>
            </el-upload>
            <!-- 删除按钮放在框外右上角 -->
            <button
              v-if="previewUrl"
              class="preview-delete-btn"
              type="button"
              @click.stop="clearPreview"
              title="移除图片"
            >
              <el-icon class="delete-icon"><Close /></el-icon>
            </button>
          </div>

          <div class="upload-actions">
            <div class="action-row primary-row">
              <el-button class="btn-analyze" :disabled="!selectedFile || uploading" @click="startAnalyze">开始分析</el-button>
            </div>
            <div class="action-row secondary-row">
              <el-button v-if="taskId" class="btn-danger" :disabled="deleting" @click="deleteTask">删除数据</el-button>
              <el-button class="btn-ghost" @click="openHistory">{{ isLoggedIn ? '我的分析历史' : '历史记录' }}</el-button>
            </div>
          </div>
        </div>

        <div class="upload-right">
          <div class="book">
            <div class="book-head">本系统基于《潘天寿：关于构图问题》</div>

            <div class="book-top">
              <a class="book-link" :href="bookUrl" target="_blank" rel="noopener noreferrer">
                <img class="book-cover" :src="bookCoverUrl" />
              </a>

              <div class="book-meta">
                <a class="book-name book-link" :href="bookUrl" target="_blank" rel="noopener noreferrer">关于构图问题</a>
                <div class="book-kv">
                  <div class="kv-row"><span class="kv-k">作者</span><span class="kv-v">潘天寿</span></div>
                  <div class="kv-row"><span class="kv-k">出版社</span><span class="kv-v">浙江人民美术出版社</span></div>
                  <div class="kv-row"><span class="kv-k">出版年</span><span class="kv-v">2015-10</span></div>
                  <div class="kv-row"><span class="kv-k">ISBN</span><span class="kv-v">9787534045707</span></div>
                  <div class="kv-row"><span class="kv-k">页数</span><span class="kv-v">74</span></div>
                  <div class="kv-row"><span class="kv-k">装帧</span><span class="kv-v">平装</span></div>
                  <div class="kv-row"><span class="kv-k">定价</span><span class="kv-v">10.00元</span></div>
                  <div class="kv-row"><span class="kv-k">丛书</span><span class="kv-v">艺文志</span></div>
                </div>
              </div>

              <div class="book-rate">
                <div class="rate-title">豆瓣评分</div>
                <div class="rate-main">
                  <div class="rate-score">9.0</div>
                  <div class="rate-right">
                    <div class="stars">
                      <div class="stars-fill" :style="{ width: '90%' }"></div>
                    </div>
                    <div class="rate-count">1090人评价</div>
                  </div>
                </div>
                <div class="rate-bars">
                  <div class="bar-row"><span class="bar-k">5星</span><span class="bar"><span class="bar-in" style="width: 53.9%"></span></span><span class="bar-v">53.9%</span></div>
                  <div class="bar-row"><span class="bar-k">4星</span><span class="bar"><span class="bar-in" style="width: 38.1%"></span></span><span class="bar-v">38.1%</span></div>
                  <div class="bar-row"><span class="bar-k">3星</span><span class="bar"><span class="bar-in" style="width: 7.4%"></span></span><span class="bar-v">7.4%</span></div>
                  <div class="bar-row"><span class="bar-k">2星</span><span class="bar"><span class="bar-in" style="width: 0.5%"></span></span><span class="bar-v">0.5%</span></div>
                  <div class="bar-row"><span class="bar-k">1星</span><span class="bar"><span class="bar-in" style="width: 0.1%"></span></span><span class="bar-v">0.1%</span></div>
                </div>
              </div>
            </div>

            <div class="book-desc">
              <div class="desc-title">内容简介</div>
              <div class="desc-text">
                本系统深度内化了潘天寿先生《关于构图问题》的核心美学逻辑，将传统画论转化为可计算的视觉法则。系统不再依赖主观审美，而是围绕“起承转合”的气脉连贯性、“虚实相生”的空间辩证法，以及“造险破险”的张力平衡，对画面进行结构化解构，并给出可执行的改画建议。
              </div>
              <div class="desc-title">作者简介</div>
              <div class="desc-text">
                潘天寿（1897—1971），中国画家、美术教育家。其论述强调构图的气势、开合、虚实与险绝之法，对近现代中国画构图理论影响深远。
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="taskId" class="progress">
        <div class="progress-top">
          <div class="progress-title">任务：{{ taskDisplayName }}</div>
          <div class="progress-meta">
            <span v-if="stageText">{{ stageText }}</span>
            <span v-if="message">· {{ message }}</span>
          </div>
        </div>
        <el-progress :percentage="progress" :status="progressStatus" />
        <div class="progress-bottom">
          <span v-if="queueEtaSeconds !== null && progress === 0">排队预计：{{ formatSeconds(queueEtaSeconds) }}</span>
          <span v-else-if="etaSeconds !== null && progress < 100">
            预计剩余：{{ formatSeconds(etaSeconds) }}
            <span v-if="etaConfidence !== null">（可信度 {{ Math.round(etaConfidence * 100) }}%）</span>
          </span>
          <span v-if="errorMessage" class="error">· {{ errorMessage }}</span>
        </div>
      </div>
    </el-card>

    <el-drawer v-model="historyVisible" title="历史记录" :size="historyDrawerSize">
      <div class="history-actions">
        <el-button class="btn-history" @click="loadHistory">刷新</el-button>
      </div>
      <el-table :data="historyItems" :height="historyTableHeight" style="width: 100%">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column label="预览" width="80">
          <template #default="{ row }">
            <el-image
              v-if="row.original_url"
              style="width: 56px; height: 56px; border-radius: 8px"
              :src="row.original_url"
              :preview-src-list="[row.original_url]"
              fit="cover"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="160" align="center">
          <template #default="{ row }">
            <div class="history-btn-group">
              <el-button
                class="btn-history"
                type="primary"
                @click="viewHistory(row.task_id, row.file_name || `历史记录 ${row.created_at}`)"
              >
                查看
              </el-button>
              <el-button class="btn-history btn-history-danger" @click="deleteHistory(row.task_id)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-card v-if="report" class="card report" shadow="never">
      <div class="report-layout">
        <div class="main">
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">智能专家分析</div>
            </div>
            <div class="md" v-html="llmHtml"></div>
            <div v-if="report?.llm?.prompt" class="prompt-toggle" @click="showPrompt = !showPrompt">
              <span class="prompt-toggle-icon">{{ showPrompt ? '▾' : '▸' }}</span>
              <span>查看分析提示词</span>
            </div>
            <div v-if="showPrompt && report?.llm?.prompt" class="prompt-content">
              <pre class="prompt-pre">{{ report.llm.prompt }}</pre>
            </div>
          </div>
        </div>

        <div class="side">
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">评分</div>
              <div class="score-stamp" v-if="totalScore !== null">
                <div class="score-stamp-label">总评</div>
                <div class="score-stamp-num">{{ totalScore }}<span class="score-stamp-max">/100</span></div>
              </div>
            </div>
            <div class="img-block">
              <div class="img-title">原图 <span class="img-hint" @click="zoomOriginal = true">（点击放大）</span></div>
              <div class="image-wrap" style="cursor: zoom-in" @click="zoomOriginal = true">
                <img
                  v-if="report?.assets?.thumb_url || report?.assets?.original_url"
                  class="img"
                  :src="report.assets.thumb_url || report.assets.original_url"
                  @load="onImageLoad"
                />
              </div>
            </div>

            <div class="img-block" v-if="report?.assets?.arrow_overlay_url">
              <div class="img-title">起承转合参考图 <span class="img-hint" @click="zoomArrow = true">（点击放大）</span></div>
              <div class="image-wrap" style="cursor: zoom-in" @click="zoomArrow = true">
                <img class="img" :src="report.arrow_analysis?.thumb_url || report.assets.arrow_overlay_url" />
              </div>
            </div>
            <div class="img-block" v-else-if="report?.assets?.original_url">
              <div class="img-title">起承转合参考图 <span class="img-hint" @click="zoomOverlay = true">（点击放大）</span></div>
              <div class="image-wrap" style="cursor: zoom-in" @click="zoomOverlay = true">
                <img class="img" :src="report.assets.thumb_url || report.assets.original_url" />
                <SvgOverlay
                  v-if="imgWidth > 0 && imgHeight > 0"
                  :width="imgWidth"
                  :height="imgHeight"
                  :annotations="report.annotations || {}"
                />
              </div>
            </div>
            <div class="panel-actions">
              <el-button class="btn-download" @click="downloadPdf">下载 PDF</el-button>
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">七维雷达</div>
            </div>
            <div ref="radarEl" class="radar"></div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Zoom dialog for 原图 -->
    <teleport to="body">
      <div v-if="zoomOriginal" class="zoom-mask" @click.self="zoomOriginal = false">
        <div class="zoom-dialog">
          <button class="zoom-close" @click="zoomOriginal = false">&times;</button>
          <div class="zoom-img-wrap">
            <img v-if="report?.assets?.original_url" :src="report.assets.original_url" class="zoom-img" />
          </div>
        </div>
      </div>
    </teleport>

    <!-- Zoom dialog for 起承转合参考图 -->
    <teleport to="body">
      <div v-if="zoomArrow" class="zoom-mask" @click.self="zoomArrow = false">
        <div class="zoom-dialog">
          <button class="zoom-close" @click="zoomArrow = false">&times;</button>
          <div class="zoom-img-wrap">
            <img v-if="report?.assets?.arrow_overlay_url" :src="report.assets.arrow_overlay_url" class="zoom-img" />
          </div>
        </div>
      </div>
    </teleport>

    <!-- Zoom overlay dialog for 起承转合SVG叠加图 -->
    <teleport to="body">
      <div v-if="zoomOverlay" class="zoom-mask" @click.self="zoomOverlay = false">
        <div class="zoom-dialog">
          <button class="zoom-close" @click="zoomOverlay = false">&times;</button>
          <div class="zoom-img-wrap">
            <template v-if="report?.assets?.original_url">
              <img :src="report.assets.original_url" class="zoom-img" />
              <SvgOverlay
                v-if="imgWidth > 0 && imgHeight > 0"
                :width="imgWidth"
                :height="imgHeight"
                :annotations="report.annotations || {}"
              />
            </template>
            <div v-else class="img-placeholder">（暂无图片）</div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { compositionApi } from '../api/composition'
import SvgOverlay from '../components/SvgOverlay.vue'

const fileList = ref([])
const selectedFile = ref(null)
const previewUrl = ref('')
const uploading = ref(false)
const deleting = ref(false)

const taskId = ref('')
const taskName = ref('')
const status = ref('')
const progress = ref(0)
const stageText = ref('')
const message = ref('')
const etaSeconds = ref(null)
const etaConfidence = ref(null)
const queueEtaSeconds = ref(null)
const errorMessage = ref('')

const report = ref(null)
const imgWidth = ref(0)
const imgHeight = ref(0)

const radarEl = ref(null)
let radarChart = null

let es = null
let pollTimer = null

const zoomOverlay = ref(false)
const zoomOriginal = ref(false)
const zoomArrow = ref(false)
const showPrompt = ref(false)

const viewportWidth = ref(1200)

const historyVisible = ref(false)
const historyLoading = ref(false)
const historyItems = ref([])
const isLoggedIn = ref(!!localStorage.getItem('auth_token'))

const bookCoverUrl = '/static/assets/goutu.jpg'
const bookUrl = 'https://book.douban.com/subject/26647513/'

const progressStatus = computed(() => {
  if (status.value === 'failed') return 'exception'
  if (status.value === 'done') return 'success'
  return ''
})

const taskDisplayName = computed(() => {
  if (taskName.value) return taskName.value
  if (selectedFile.value?.name) return selectedFile.value.name
  return '分析任务'
})

const totalScore = computed(() => {
  const v = report.value?.summary?.total_score
  if (v === undefined || v === null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.round(n) : null
})

const historyDrawerSize = computed(() => {
  return viewportWidth.value < 768 ? '100%' : '640px'
})

const historyTableHeight = computed(() => {
  return viewportWidth.value < 768 ? 520 : 620
})

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function rawDir(s) {
  // Strip surrounding **bold** markers from dimension name
  return String(s).replace(/^\*\*?/, '').replace(/\*\*?$/, '')
}

function isSafeImageUrl(url) {
  const u = String(url || '')
  if (!u) return false
  if (u.startsWith('/static/')) return true
  if (u.startsWith('http://') || u.startsWith('https://')) return true
  return false
}

function _extractInlineSafe(text) {
  // Extract backtick code spans and safe images into placeholders BEFORE escapeHtml,
  // so they don't get mangled. Returns { processed, tokens, imgs }.
  const tokens = []
  const imgs = []
  const src = text.replace(/`([^`]+)`/g, (_, code) => {
    const i = tokens.push(code) - 1
    return `@@IC${i}@@`
  })
  const src2 = src.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, url) => {
    const u = String(url || '').trim()
    const a = String(alt || '').trim()
    if (!isSafeImageUrl(u)) return a ? a : ''
    const i = imgs.push({ alt: a, url: u }) - 1
    return `@@IMG${i}@@`
  })
  return { processed: src2, tokens, imgs }
}

function _restoreInline(s, tokens, imgs) {
  s = s.replace(/@@IC(\d+)@@/g, (_, i) => `<code>${escapeHtml(tokens[Number(i)] || '')}</code>`)
  s = s.replace(/@@IMG(\d+)@@/g, (_, i) => {
    const it = imgs[Number(i)]
    if (!it) return ''
    const alt = escapeHtml(it.alt || '')
    const url = escapeHtml(it.url || '')
    const cap = it.alt ? `<figcaption>${alt}</figcaption>` : ''
    return `<figure class="md-fig"><img class="md-img" src="${url}" alt="${alt}" />${cap}</figure>`
  })
  return s
}

function renderInline(text) {
  const raw = String(text || '')
  const { processed, tokens, imgs } = _extractInlineSafe(raw)

  // If text already contains <strong> tags (backend pre-processed),
  // escape only the non-tag parts to avoid double-encoding.
  if (/<strong>/.test(processed)) {
    // Split by <strong>...</strong> boundaries, escape text parts, rejoin
    const parts = processed.split(/(<strong>[\s\S]*?<\/strong>)/)
    let s = parts.map(part => {
      if (part.startsWith('<strong>')) return part // already safe HTML
      return escapeHtml(part)
    }).join('')
    // Also handle <em> if present
    s = s.split(/(<em>[\s\S]*?<\/em>)/).map(part => {
      if (part.startsWith('<em>')) return part
      return part // already escaped above or is a tag
    }).join('')
    // Convert any remaining **text** (shouldn't be needed but safe)
    s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
    s = s.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
    s = s.replace(/\*\*/g, '')
    return _restoreInline(s, tokens, imgs)
  }

  // No <strong> tags — original path for raw **text** markdown
  let s = escapeHtml(processed)
  // Convert **text** to <strong>text</strong>
  s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
  // Convert *text* to <em>text</em>
  s = s.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
  // Remove any remaining orphan **
  s = s.replace(/\*\*/g, '')
  return _restoreInline(s, tokens, imgs)
}

function renderMarkdown(md) {
  const lines = String(md || '').replace(/\r\n/g, '\n').split('\n')
  const out = []
  let i = 0
  let inCode = false
  let codeLines = []
  let inUl = false
  let inSubUl = false
  let para = []

  const flushPara = () => {
    if (para.length === 0) return
    const txt = para.join(' ').trim()
    if (txt) out.push(`<p>${renderInline(txt)}</p>`)
    para = []
  }

  const closeSubUl = () => {
    if (inSubUl) { out.push('</ul>'); inSubUl = false }
  }

  const closeUl = () => {
    closeSubUl()
    if (inUl) {
      out.push('</ul>')
      inUl = false
    }
  }

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (trimmed.startsWith('```')) {
      flushPara()
      closeUl()
      if (!inCode) {
        inCode = true
        codeLines = []
      } else {
        inCode = false
        out.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
      }
      i += 1
      continue
    }

    if (inCode) {
      codeLines.push(line)
      i += 1
      continue
    }

    if (!trimmed) {
      flushPara()
      closeUl()
      i += 1
      continue
    }

    const h = trimmed.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      flushPara()
      closeUl()
      const level = h[1].length
      out.push(`<h${level}>${renderInline(h[2])}</h${level}>`)
      i += 1
      continue
    }

    // Match numbered headings like "1. <strong>开合之势</strong>" or "1. **开合之势**：..."
    // (\S+) will capture up to the first whitespace — handle both HTML and markdown bold
    const numHead = trimmed.match(/^(\d{1,2})[.、．]\s+/)
    if (numHead) {
      flushPara()
      closeUl()
      const prefix = escapeHtml(numHead[0].trim())
      let dimClean = ''
      let restText = trimmed.slice(numHead[0].length).trim()

      // Case 1: Backend pre-processed: "<strong>title</strong>" or "<strong>title</strong>：desc"
      const htmlBoldMatch = restText.match(/^<strong>([\s\S]*?)<\/strong>\s*[:：]?\s*(.*)/)
      // Case 2: Raw markdown: "**title**" or "**title**：desc"
      const mdBoldMatch = restText.match(/^(\*\*[^*]+?\*\*)\s*[:：]?\s*(.*)/)

      if (htmlBoldMatch) {
        dimClean = htmlBoldMatch[1] // inner text, already safe
        restText = htmlBoldMatch[2] || ''
      } else if (mdBoldMatch) {
        dimClean = rawDir(mdBoldMatch[1]) // strip **
        restText = mdBoldMatch[2] || ''
      } else {
        // Fallback: use first non-whitespace token as dimension name
        const firstToken = restText.match(/^(\S+)/)
        if (firstToken) {
          dimClean = rawDir(firstToken[1])
          restText = restText.slice(firstToken[0].length).trim()
        }
      }

      const rest = renderInline(restText).trim()
      const dimHtml = dimClean
        ? `<strong>${prefix} ${escapeHtml(dimClean)}</strong>`
        : `<strong>${prefix}</strong>`
      const lineHtml = rest ? `${dimHtml} ${rest}` : dimHtml
      out.push(`<h3>${lineHtml}</h3>`)
      i += 1
      continue
    }

    const bq = trimmed.match(/^>\s?(.*)$/)
    if (bq) {
      flushPara()
      closeUl()
      out.push(`<blockquote>${renderInline(bq[1])}</blockquote>`)
      i += 1
      continue
    }

    // List items: support both "- item" and indented "* item" / "    * item"
    const listMatch = trimmed.match(/^(\s*)([-*])\s+(.*)$/)
    if (listMatch) {
      const indent = listMatch[1].length
      const content = listMatch[3]
      // Only match if not a numHead pattern (e.g. "1. **title**" with trailing **)
      if (!/^(\d{1,2})[.、．]/.test(trimmed) || indent > 0) {
        flushPara()
        const isSubList = indent >= 2
        if (isSubList && !inSubUl) {
          if (!inUl) { out.push('<ul>'); inUl = true }
          out.push('<ul class="sub-list">')
          inSubUl = true
        } else if (!isSubList) {
          closeSubUl()
          if (!inUl) { out.push('<ul>'); inUl = true }
        }
        out.push(`<li>${renderInline(content)}</li>`)
        i += 1
        continue
      }
    }

    const maybeTable = trimmed.includes('|')
    const next = i + 1 < lines.length ? lines[i + 1].trim() : ''
    const isSep = /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(next)
    if (maybeTable && isSep) {
      flushPara()
      closeUl()
      const headerCells = trimmed.split('|').map((x) => x.trim()).filter((x) => x.length > 0)
      i += 2
      const bodyRows = []
      while (i < lines.length) {
        const rowLine = lines[i].trim()
        if (!rowLine || !rowLine.includes('|')) break
        const cells = rowLine.split('|').map((x) => x.trim()).filter((x) => x.length > 0)
        bodyRows.push(cells)
        i += 1
      }
      const thead = `<thead><tr>${headerCells.map((c) => `<th>${renderInline(c)}</th>`).join('')}</tr></thead>`
      const tbody = `<tbody>${bodyRows
        .map((row) => `<tr>${row.map((c) => `<td>${renderInline(c)}</td>`).join('')}</tr>`)
        .join('')}</tbody>`
      out.push(`<table class="md-table">${thead}${tbody}</table>`)
      continue
    }

    para.push(trimmed)
    i += 1
  }

  flushPara()
  closeUl()
  return out.join('\n')
}

const llmHtml = computed(() => {
  const llm = report.value?.llm
  if (!llm) return ''
  if (llm.text) return renderMarkdown(llm.text)
  if (llm.error) return `<p>${escapeHtml(llm.error)}</p>`
  return ''
})

const objectiveMax = computed(() => 0)

// Display name mapping: backend dimension name → radar chart label
const DIMENSION_LABELS = {
  '开合之势': '起承转合',
  '虚实相生': '虚实留白',
  '疏密有致': '疏密节奏',
  '辅助元素': '题跋布局',
  '均衡节奏': '均衡节奏',
  '穿插结构': '穿插结构',
  '边角空间': '边角空间',
}

function buildRadarData() {
  const dims = report.value?.dimensions || []
  // Fallback: if dimensions has fewer than 7 items, also include checks
  const checks = report.value?.checks || []

  const to10 = (score, max) => {
    const s = Number(score || 0)
    const m = Number(max || 0)
    if (m <= 0) return 0
    return Math.round((s / m) * 10)
  }

  // Primary: use all dimensions from the API response
  if (dims.length >= 4) {
    const values = dims.map((d) => to10(d.score, d.max))
    const indicators = dims.map((d) => ({
      name: DIMENSION_LABELS[d.name] || d.name,
      max: 10,
    }))
    return { indicators, values }
  }

  // Legacy fallback: 5-item mode (3 dimensions + 2 checks)
  const getDim = (name) => dims.find((d) => d?.name === name)
  const getCheck = (name) => checks.find((c) => c?.name === name)
  const items = [
    { val: to10(getDim('开合之势')?.score, getDim('开合之势')?.max), label: '起承转合' },
    { val: to10(getDim('虚实相生')?.score, getDim('虚实相生')?.max), label: '虚实留白' },
    { val: to10(getDim('疏密有致')?.score, getDim('疏密有致')?.max), label: '疏密节奏' },
    { val: to10(getCheck('破平行风险')?.score, getCheck('破平行风险')?.max), label: '势与平衡' },
    { val: to10(getCheck('题款经营')?.score, getCheck('题款经营')?.max), label: '题跋布局' },
  ]
  return {
    indicators: items.map((it) => ({ name: it.label, max: 10 })),
    values: items.map((it) => it.val),
  }
}

function renderRadar() {
  if (!radarEl.value) return
  const { indicators, values } = buildRadarData()
  if (radarChart && radarChart.getDom && radarChart.getDom() !== radarEl.value) {
    radarChart.dispose()
    radarChart = null
  }
  if (!radarChart) radarChart = echarts.init(radarEl.value)
  radarChart.setOption(
    {
      radar: {
        indicator: indicators,
        radius: '70%',
        axisName: { color: '#141413', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e8e6dc' } },
        splitArea: { areaStyle: { color: ['#faf9f5', '#ffffff'] } },
        axisLine: { lineStyle: { color: '#e8e6dc' } },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: values,
              areaStyle: { color: 'rgba(201, 100, 66, 0.18)' },
              lineStyle: { color: '#c96442', width: 2 },
              itemStyle: { color: '#c96442' },
            },
          ],
        },
      ],
      tooltip: { trigger: 'item' },
    },
    { notMerge: true }
  )
  radarChart.resize()
}

function onResize() {
  viewportWidth.value = window.innerWidth
  if (radarChart) radarChart.resize()
}

onMounted(() => {
  viewportWidth.value = window.innerWidth
  window.addEventListener('resize', onResize)
})

watch(
  () => report.value,
  async () => {
    await nextTick()
    renderRadar()
  },
  { deep: true }
)

function onFileChange(file, files) {
  fileList.value = files.slice(-1)
  selectedFile.value = file.raw || null
  taskName.value = selectedFile.value?.name || file?.name || ''
  // 生成缩略图预览
  if (selectedFile.value) {
    previewUrl.value = URL.createObjectURL(selectedFile.value)
  } else {
    previewUrl.value = ''
  }
}

function onFileRemove() {
  fileList.value = []
  selectedFile.value = null
  previewUrl.value = ''
  taskName.value = ''
}

function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  onFileRemove()
}

function formatSeconds(s) {
  const n = Math.max(0, Math.floor(s || 0))
  if (n < 60) return `${n} 秒`
  const m = Math.floor(n / 60)
  const r = n % 60
  return `${m} 分 ${r} 秒`
}

function onImageLoad(e) {
  const img = e?.target
  if (!img) return
  imgWidth.value = img.naturalWidth || 0
  imgHeight.value = img.naturalHeight || 0
}

function resetRuntimeState() {
  status.value = ''
  progress.value = 0
  stageText.value = ''
  message.value = ''
  etaSeconds.value = null
  etaConfidence.value = null
  queueEtaSeconds.value = null
  errorMessage.value = ''
  report.value = null
  imgWidth.value = 0
  imgHeight.value = 0
  taskName.value = selectedFile.value?.name || ''
  if (radarChart) {
    radarChart.dispose()
    radarChart = null
  }
}

async function startAnalyze() {
  if (!selectedFile.value) return
  uploading.value = true
  resetRuntimeState()
  try {
    const res = await compositionApi.upload(selectedFile.value)
    taskId.value = res.task_id
    taskName.value = res.file_name || selectedFile.value?.name || ''
    await startProgressStream(res.task_id)
  } catch (e) {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

function closeStream() {
  if (es) {
    es.close()
    es = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function startProgressStream(id) {
  closeStream()
  const url = `/api/v1/composition/task/${id}/events`
  try {
    es = new EventSource(url)
    es.addEventListener('progress', (evt) => {
      try {
        const data = JSON.parse(evt.data)
        applyProgress(data)
      } catch {
        return
      }
    })
    es.onerror = async () => {
      closeStream()
      pollTimer = setInterval(async () => {
        try {
          const data = await compositionApi.getTask(id)
          applyProgress(data)
        } catch {
          return
        }
      }, 1000)
    }
  } catch {
    pollTimer = setInterval(async () => {
      try {
        const data = await compositionApi.getTask(id)
        applyProgress(data)
      } catch {
        return
      }
    }, 1000)
  }
}

async function applyProgress(data) {
  status.value = data.status || status.value
  progress.value = Number.isFinite(data.progress) ? data.progress : progress.value
  stageText.value = data.stage_text || stageText.value
  message.value = data.message || message.value
  etaSeconds.value = data.eta_seconds ?? etaSeconds.value
  etaConfidence.value = data.eta_confidence ?? etaConfidence.value
  queueEtaSeconds.value = data.queue_eta_seconds ?? queueEtaSeconds.value
  errorMessage.value = data.error_message || ''

  if (status.value === 'done' && !report.value) {
    closeStream()
    try {
      report.value = await compositionApi.getReport(taskId.value)
    } catch {
      ElMessage.error('获取报告失败')
    }
  }
}

async function downloadPdf() {
  if (!taskId.value) return
  window.open(`#/composition/print/${taskId.value}`, '_blank')
}

async function cancelTask() {
  if (!taskId.value) return
  try {
    await compositionApi.cancelTask(taskId.value)
    ElMessage.success('已提交取消')
  } catch {
    ElMessage.error('取消失败')
  }
}

async function deleteTask() {
  if (!taskId.value) return
  try {
    await ElMessageBox.confirm('确认删除该任务的图片与报告数据？', '提示', { type: 'warning' })
  } catch {
    return
  }
  deleting.value = true
  try {
    await compositionApi.deleteTask(taskId.value)
    ElMessage.success('已删除')
    closeStream()
    taskId.value = ''
    resetRuntimeState()
  } catch {
    ElMessage.error('删除失败')
  } finally {
    deleting.value = false
  }
}

function formatHistoryTime(s) {
  try {
    let d = new Date(s)
    // 后端用 datetime.utcnow() 存储无时区 ISO 时间，new Date 解析时当作本地时间
    // 实际应为 UTC，需加 8 小时修正为北京时间
    if (!s.endsWith('Z') && !s.includes('+')) {
      d = new Date(d.getTime() + 8 * 60 * 60 * 1000)
    }
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
  } catch {
    return s
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await compositionApi.getHistory(50)
    const items = (res.items || []).map((x) => ({
      ...x,
      created_at: formatHistoryTime(x.created_at)
    }))
    historyItems.value = items
  } catch {
    ElMessage.error('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function openHistory() {
  // Phase 4d: Check login state
  if (!isLoggedIn.value) {
    ElMessage.warning('登录后可查看和保存分析历史')
    return
  }
  historyVisible.value = true
  if (historyItems.value.length === 0) {
    await loadHistory()
  }
}

async function viewHistory(id, fileName = '') {
  historyVisible.value = false
  taskId.value = id
  taskName.value = fileName || ''
  resetRuntimeState()
  try {
    const st = await compositionApi.getTask(id)
    applyProgress(st)
    if (st.status !== 'done') {
      ElMessage.warning('该任务尚未完成，当前状态：' + (st.stage_text || st.status))
      return
    }
    report.value = await compositionApi.getReport(id)
  } catch (e) {
    const detail = e?.response?.data?.detail
    if (detail === 'report_not_ready') {
      ElMessage.warning('报告尚未生成，请稍后再试')
    } else if (detail === 'invalid_report_path') {
      ElMessage.error('报告路径异常，请联系管理员修复')
    } else {
      ElMessage.error('加载报告失败')
    }
  }
}

async function deleteHistory(id) {
  try {
    await ElMessageBox.confirm('确认删除该历史记录的图片与报告数据？', '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await compositionApi.deleteTask(id)
    ElMessage.success('已删除')
    await loadHistory()
  } catch {
    ElMessage.error('删除失败')
  }
}

onBeforeUnmount(() => {
  closeStream()
  window.removeEventListener('resize', onResize)
  if (radarChart) {
    radarChart.dispose()
    radarChart = null
  }
})
</script>

<style scoped>
.page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px 40px;
  background: var(--parchment, #f5f4ed);
  overflow-x: hidden;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  color: var(--near-black, #141413);
}

/* ========== 页面 Header（居中，紧凑高度） ========== */
.comp-header {
  position: relative;
  background: radial-gradient(ellipse at 50% 30%, rgba(201, 100, 66, 0.06) 0%, transparent 60%),
              linear-gradient(180deg, var(--ivory, #faf9f5) 0%, var(--parchment, #f5f4ed) 100%);
  color: var(--near-black, #141413);
  padding: 20px 40px 16px;
  text-align: center;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
  margin: -20px -24px 20px;
}

.comp-header h1 {
  margin: 0 0 4px;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  font-size: 22px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--near-black, #141413);
}

.comp-header .sub {
  margin: 0;
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  letter-spacing: 0.03em;
  line-height: 1.5;
}

.header-ornament {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 10px;
}

.ornament-line {
  width: 36px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--ring-warm, #d1cfc5), transparent);
}

.ornament-dot {
  color: var(--cinnabar, #c96442);
  font-size: 12px;
  opacity: 0.4;
}

.card {
  width: 100%;
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-lg, 12px);
  background: var(--pure-white, #fff);
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}

.card :deep(.el-card__body) {
  overflow-x: hidden;
  overflow-y: visible;
}

.upload-layout {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 24px;
  align-items: start;
  padding: 22px 26px;
}

.upload-title {
  font-size: 18px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin-bottom: 14px;
  letter-spacing: 0.04em;
}

.uploader :deep(.el-upload-dragger) {
  width: 100%;
  border: 2px dashed var(--ring-warm, #d1cfc5);
  border-radius: var(--radius-xl, 16px);
  background: var(--ivory, #faf9f5);
  padding: 54px 20px;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.upload-box {
  position: relative;
  width: 100%;
}

.uploader {
  width: 100%;
}

.uploader :deep(.el-upload) {
  width: 100%;
}

/* 有预览图时的上传框样式 */
.upload-box.has-preview :deep(.el-upload-dragger) {
  padding: 0;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ivory, #faf9f5);
  border: 2px dashed var(--ring-warm, #d1cfc5);
}

/* 内嵌预览区域 */
.preview-inner {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.preview-img-inline {
  max-width: 100%;
  max-height: 320px;
  object-fit: contain;
  display: block;
}

/* 悬停显示更换按钮 */
.preview-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.preview-inner:hover .preview-overlay {
  opacity: 1;
}

/* 更换图片按钮 - 匹配开始分析按钮样式 */
.preview-change-btn {
  height: 46px;
  padding: 0 32px;
  border-radius: var(--radius-md, 8px);
  background: var(--cinnabar, #c96442);
  border: 1px solid var(--cinnabar, #c96442);
  color: var(--pure-white, #fff);
  font-weight: 600;
  font-size: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.preview-change-btn:hover {
  opacity: 0.9;
}

/* 删除按钮 - 框外右上角，圆形居中 */
.preview-delete-btn {
  position: absolute;
  top: -12px;
  right: -12px;
  z-index: 10;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--error-crimson, #b53333);
  border: 2px solid var(--pure-white, #fff);
  color: var(--pure-white, #fff);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  transition: background 0.2s ease;
  padding: 0;
  margin: 0;
}

.preview-delete-btn:hover {
  background: #c0392b;
}

.delete-icon {
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon {
  font-size: 54px;
  color: var(--cinnabar, #c96442);
  margin-bottom: 10px;
  opacity: 0.6;
}

.upload-text {
  font-size: 20px;
  font-weight: 500;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  color: var(--charcoal-warm, #4d4c48);
}

.upload-hint {
  margin-top: 14px;
  font-size: 15px;
  color: var(--warm-silver, #b0aea5);
}

.upload-actions {
  margin-top: 18px;
  display: grid;
  gap: 14px;
}

.action-row {
  display: flex;
  gap: 14px;
  flex-wrap: nowrap;
}

.primary-row {
  justify-content: center;
}

.secondary-row {
  justify-content: center;
}

.secondary-row :deep(.el-button) {
  min-width: 140px;
}

.btn-analyze {
  height: 54px;
  padding: 0 46px;
  border-radius: var(--radius-md, 8px);
  background: var(--cinnabar, #c96442);
  border: 1px solid var(--cinnabar, #c96442);
  color: var(--pure-white, #fff);
  font-weight: 600;
  font-size: 16px;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  letter-spacing: 0.08em;
  transition: background 0.2s, opacity 0.2s;
}

.btn-analyze:disabled {
  opacity: 0.6;
}

.btn-ghost {
  height: 46px;
  padding: 0 26px;
  border-radius: var(--radius-md, 8px);
  background: var(--pure-white, #fff);
  border: 1px solid var(--border-warm, #e8e6dc);
  color: var(--charcoal-warm, #4d4c48);
  font-weight: 500;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  transition: all 0.2s;
}

.btn-ghost:hover {
  background: var(--ivory, #faf9f5);
  border-color: var(--cinnabar-light, #d97757);
  color: var(--cinnabar, #c96442);
}

.btn-danger {
  height: 46px;
  padding: 0 26px;
  border-radius: var(--radius-md, 8px);
  background: var(--pure-white, #fff);
  border: 1px solid var(--border-warm, #e8e6dc);
  color: var(--error-crimson, #b53333);
  font-weight: 600;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  transition: all 0.2s;
}

.btn-danger:hover {
  background: #fef2f2;
  border-color: #fca5a5;
  color: var(--error-crimson, #b53333);
}

.btn-download {
  height: 54px;
  padding: 0 46px;
  border-radius: var(--radius-md, 8px);
  background: var(--cinnabar, #c96442);
  border: 1px solid var(--cinnabar, #c96442);
  color: var(--pure-white, #fff);
  font-weight: 600;
  font-size: 16px;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  letter-spacing: 0.08em;
  width: 100%;
  transition: background 0.2s, opacity 0.2s;
}

.book {
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-lg, 12px);
  background: var(--pure-white, #fff);
  padding: 18px;
}

.book-cover {
  width: 168px;
  height: 238px;
  object-fit: cover;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--border-cream, #f0eee6);
  background: var(--pure-white, #fff);
}

.book-head {
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  margin-bottom: 12px;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
}

.book-top {
  display: grid;
  grid-template-columns: 168px 1fr 220px;
  gap: 18px;
  align-items: start;
}

.book-name {
  font-size: 24px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin-bottom: 10px;
  text-decoration: none;
  letter-spacing: 0.04em;
}

.book-link {
  text-decoration: none;
}

.book-kv {
  display: grid;
  gap: 8px;
}

.kv-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 10px;
  align-items: baseline;
  color: var(--dark-warm, #3d3d3a);
  font-size: 14px;
}

.kv-k {
  color: var(--stone-gray, #87867f);
}

.kv-v {
  color: var(--dark-warm, #3d3d3a);
  font-weight: 600;
}

.book-rate {
  border-left: 1px solid var(--border-cream, #f0eee6);
  padding-left: 18px;
}

.rate-title {
  color: var(--stone-gray, #87867f);
  font-size: 13px;
  margin-bottom: 10px;
}

.rate-main {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.rate-score {
  font-size: 42px;
  font-weight: 600;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  line-height: 1;
}

.rate-right {
  display: grid;
  gap: 6px;
}

.stars {
  position: relative;
  width: 110px;
  height: 18px;
  background: transparent;
  overflow: hidden;
  white-space: nowrap;
}

.stars::before {
  content: '★★★★★';
  position: absolute;
  left: 0;
  top: -2px;
  letter-spacing: 2px;
  color: #e5e7eb;
  font-size: 18px;
}

.stars-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  overflow: hidden;
}

.stars-fill::before {
  content: '★★★★★';
  position: absolute;
  left: 0;
  top: -2px;
  letter-spacing: 2px;
  color: #f59e0b;
  font-size: 18px;
}

.rate-count {
  color: var(--cinnabar, #c96442);
  font-size: 13px;
}

.rate-bars {
  display: grid;
  gap: 6px;
}

.bar-row {
  display: grid;
  grid-template-columns: 30px 1fr 44px;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  color: var(--stone-gray, #87867f);
}

.bar {
  height: 8px;
  background: var(--border-warm, #e8e6dc);
  border-radius: 999px;
  overflow: hidden;
}

.bar-in {
  height: 100%;
  background: var(--gold, #b8a47e);
  display: block;
}

.bar-v {
  text-align: right;
}

.book-desc {
  margin-top: 18px;
  border-top: 1px solid var(--border-cream, #f0eee6);
  padding-top: 14px;
}

.desc-title {
  font-size: 15px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin: 12px 0 8px;
  letter-spacing: 0.04em;
}

.desc-text {
  color: var(--dark-warm, #3d3d3a);
  line-height: 1.8;
  font-size: 14px;
}

.progress {
  width: 80%;
  margin: 18px auto 0;
}

.progress :deep(.el-progress.el-progress--line) {
  display: flex;
  align-items: center;
}

.progress :deep(.el-progress-bar) {
  flex: 1 1 auto;
  min-width: 0;
}

.progress :deep(.el-progress-bar__outer) {
  width: 100%;
}

.progress :deep(.el-progress__text) {
  flex: 0 0 auto;
  margin-left: 12px;
  white-space: nowrap;
}

.progress-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
  min-width: 0;
}

.progress-title {
  font-weight: 500;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  color: var(--near-black, #141413);
  flex: 0 1 42%;
  max-width: 42%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-meta {
  color: var(--stone-gray, #87867f);
  flex: 1 1 58%;
  max-width: 58%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
}

.progress-bottom {
  margin-top: 10px;
  color: var(--stone-gray, #87867f);
}

.error {
  color: var(--error-crimson, #b53333);
}

.history-actions {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

/* 历史记录操作列 - 按钮居中 + 统一样式 */
.history-actions {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.history-btn-group {
  display: inline-flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
}

.btn-history {
  height: 34px !important;
  padding: 0 18px !important;
  border-radius: var(--radius-md, 8px) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif) !important;
  border: none !important;
}

.btn-history.el-button--default {
  background: var(--cinnabar, #c96442) !important;
  color: var(--pure-white, #fff) !important;
}

.btn-history.el-button--primary {
  background: var(--cinnabar, #c96442) !important;
}

.btn-history-danger {
  background: var(--pure-white, #fff) !important;
  color: var(--error-crimson, #b53333) !important;
  border: 1px solid var(--border-warm, #e8e6dc) !important;
}

.btn-history-danger:hover {
  background: #fef2f2 !important;
  border-color: #fca5a5 !important;
}

.report {
  margin-top: 18px;
}

.report-layout {
  display: grid;
  grid-template-columns: 7fr 3fr;
  gap: 18px;
  align-items: start;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  border: 1px solid var(--border-cream, #f0eee6);
  background: var(--pure-white, #fff);
  border-radius: var(--radius-lg, 12px);
  padding: 14px;
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
  padding-bottom: 10px;
}

.score-stamp {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.score-stamp-label {
  font-size: 12px;
  color: var(--stone-gray, #87867f);
}

.score-stamp-num {
  font-size: 38px;
  font-weight: 600;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--cinnabar, #c96442);
  line-height: 1;
}

.score-stamp-max {
  font-size: 14px;
  color: var(--stone-gray, #87867f);
  margin-left: 6px;
  font-weight: 500;
}

.img-block {
  margin-top: 10px;
}

.img-title {
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}

.panel-title {
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  letter-spacing: 0.04em;
}

.panel-sub {
  color: var(--stone-gray, #87867f);
  font-size: 12px;
}

.panel-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}

.image-wrap {
  position: relative;
  width: 100%;
  border: 1px solid var(--border-cream, #f0eee6);
  background: var(--pure-white, #fff);
  overflow: hidden;
  border-radius: var(--radius-md, 8px);
}

.img {
  display: block;
  width: 100%;
  height: auto;
}

.radar {
  width: 100%;
  height: 260px;
}

.md :deep(h1),
.md :deep(h2),
.md :deep(h3),
.md :deep(h4) {
  color: var(--near-black, #141413);
  margin: 22px 0 14px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  letter-spacing: 0.04em;
}

.md :deep(h1) {
  font-size: 20px;
}

.md :deep(h2) {
  font-size: 18px;
  border-left: 4px solid var(--cinnabar, #c96442);
  padding-left: 10px;
}

.md :deep(h3) {
  font-size: 16px;
}

.md :deep(p) {
  margin: 18px 0;
  color: var(--dark-warm, #3d3d3a);
  line-height: 2;
}

.md :deep(ul) {
  margin: 18px 0;
  padding-left: 20px;
  color: var(--dark-warm, #3d3d3a);
  line-height: 2;
}

.md :deep(ul.sub-list) {
  margin: 4px 0 12px;
  padding-left: 0;
  list-style-type: none;
}

.md :deep(ul.sub-list li) {
  margin: 8px 0;
  padding-left: 16px;
  position: relative;
}

.md :deep(ul.sub-list li::before) {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--cinnabar, #c96442);
}

.md :deep(li) {
  margin: 10px 0;
}

.md :deep(blockquote) {
  margin: 18px 0;
  padding: 14px 14px;
  border-left: 4px solid var(--cinnabar, #c96442);
  background: var(--ivory, #faf9f5);
  color: var(--dark-warm, #3d3d3a);
}

.md :deep(code) {
  background: var(--parchment, #f5f4ed);
  padding: 2px 6px;
  border-radius: var(--radius-sm, 6px);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}

.md :deep(pre) {
  margin: 12px 0;
  padding: 12px;
  border-radius: var(--radius-lg, 12px);
  background: var(--deep-dark, #141413);
  color: #e2e8f0;
  overflow: auto;
}

.md :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.md :deep(.md-fig) {
  margin: 14px 0;
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
  background: var(--pure-white, #fff);
}

.md :deep(.md-img) {
  max-width: 50%;
  width: auto;
  display: block;
  margin: 0 auto;
}

.md :deep(.md-fig figcaption) {
  padding: 10px 12px;
  background: var(--ivory, #faf9f5);
  color: var(--dark-warm, #3d3d3a);
  line-height: 1.6;
}

.md :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  overflow: hidden;
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--border-cream, #f0eee6);
  table-layout: fixed;
}

.md :deep(.md-table th),
.md :deep(.md-table td) {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
  text-align: left;
  color: var(--dark-warm, #3d3d3a);
  word-break: break-word;
}

.md :deep(.md-table thead th) {
  background: var(--ivory, #faf9f5);
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
}

.md :deep(.md-table tbody tr:nth-child(2n)) td {
  background: rgba(250, 249, 245, 0.7);
}

.img-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--cinnabar, #c96442);
  cursor: pointer;
}

.zoom-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.zoom-dialog {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.zoom-close {
  position: absolute;
  top: -36px;
  right: 0;
  background: none;
  border: none;
  color: #fff;
  font-size: 28px;
  cursor: pointer;
  line-height: 1;
  padding: 4px 8px;
}

.zoom-img-wrap {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
}

.zoom-img {
  display: block;
  max-width: 90vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
}

.prompt-toggle {
  margin-top: 16px;
  padding: 8px 12px;
  cursor: pointer;
  color: var(--stone-gray, #87867f);
  font-size: 13px;
  border-top: 1px solid var(--border-cream, #f0eee6);
  user-select: none;
  transition: color 0.2s;
}

.prompt-toggle:hover {
  color: var(--cinnabar, #c96442);
}

.prompt-toggle-icon {
  display: inline-block;
  width: 16px;
  font-size: 12px;
}

.prompt-content {
  margin-top: 8px;
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-md, 8px);
  background: var(--ivory, #faf9f5);
  overflow: hidden;
}

.prompt-pre {
  margin: 0;
  padding: 14px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--dark-warm, #3d3d3a);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 500px;
  overflow-y: auto;
  background: transparent;
  border: none;
}

@media (max-width: 1024px) {
  .page {
    padding: 14px 14px 24px;
  }

  .comp-header {
    padding: 18px 16px 14px;
    margin: 0 -14px 16px;
  }

  .upload-layout {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 16px 14px;
  }

  .book-top {
    grid-template-columns: 168px 1fr;
  }

  .book-rate {
    border-left: none;
    padding-left: 0;
    margin-top: 12px;
  }

  .report-layout {
    grid-template-columns: 1fr;
  }

  .radar {
    height: 240px;
  }
}

@media (max-width: 768px) {
  .progress {
    width: 100%;
  }

  .comp-header h1 {
    font-size: 18px;
  }

  .comp-header .sub {
    font-size: 12px;
  }

  .upload-title {
    font-size: 16px;
    margin-bottom: 12px;
  }

  .uploader :deep(.el-upload-dragger) {
    min-height: 240px;
    padding: 32px 14px;
  }

  .upload-icon {
    font-size: 46px;
  }

  .upload-text {
    font-size: 18px;
  }

  .upload-hint {
    font-size: 14px;
  }

  .btn-analyze {
    width: 100%;
    max-width: 420px;
  }

  .secondary-row {
    justify-content: center;
  }

  .book-top {
    grid-template-columns: 1fr;
  }

  .book-cover {
    width: 100%;
    height: auto;
    aspect-ratio: 7 / 10;
  }

  .book-name {
    font-size: 22px;
  }

  .rate-main {
    flex-wrap: wrap;
  }

  .panel-actions {
    flex-wrap: wrap;
  }

  .score-stamp-num {
    font-size: 32px;
  }

  .radar {
    height: 220px;
  }

  .md :deep(h1) {
    font-size: 18px;
  }

  .md :deep(h2) {
    font-size: 16px;
  }

  .md :deep(p),
  .md :deep(ul) {
    font-size: 14px;
  }
}
</style>
