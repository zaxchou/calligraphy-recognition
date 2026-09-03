<template>
  <div class="print-page" :class="{ 'print-mode': isPrinting }">
    <!-- 加载中 -->
    <div v-if="loading" class="loading-wrap">
      <p>正在加载报告数据...</p>
    </div>
    <!-- 错误 -->
    <div v-else-if="error" class="error-wrap">
      <p>{{ error }}</p>
    </div>
    <!-- 报告内容 -->
    <div v-else-if="report" class="report">
      <!-- 标题头 -->
      <header class="report-header">
        <h1>潘天寿教你构图 — 智能专家分析报告</h1>
        <div class="report-meta">
          <span>任务编号：{{ taskId }}</span>
          <span v-if="report.summary">{{ report.summary.grade }} · {{ report.summary.total_score }}分</span>
        </div>
      </header>

      <!-- 原图 + 起承转合箭头图 -->
      <section class="images-section">
        <div class="img-group">
          <h3>原始图片</h3>
          <img v-if="imgSrc" :src="imgSrc" class="report-img" />
          <div v-else class="img-placeholder">（图片文件不可用）</div>
        </div>
        <div class="img-group" v-if="arrowOverlayUrl">
          <h3>起承转合分析图</h3>
          <img :src="arrowOverlayUrl" class="report-img" />
          <div v-if="report.arrow_analysis" class="arrow-info">
            <span class="path-badge">路径类型：{{ report.arrow_analysis.path_type || '未知' }}</span>
            <span v-if="cvData" class="cv-badge">CV+AI 融合分析</span>
          </div>
        </div>
      </section>

      <!-- CV 预处理数据面板 -->
      <section v-if="cvData" class="cv-section">
        <h2>CV 预分析数据</h2>
        <div class="cv-grid">
          <div class="cv-item" v-if="cvData.material_count > 0">
            <span class="cv-label">检测画材</span>
            <span class="cv-value">{{ cvData.material_count }} 个（主要 {{ cvData.major_material_count }} 个）</span>
          </div>
          <div class="cv-item" v-if="cvData.edge_density">
            <span class="cv-label">主导入画边缘</span>
            <span class="cv-value">{{ cvData.edge_density.dominant_entry_edge || '均匀' }}</span>
          </div>
          <div class="cv-item" v-if="cvData.main_direction">
            <span class="cv-label">主干方向</span>
            <span class="cv-value">{{ cvData.main_direction }}</span>
          </div>
          <div class="cv-item" v-if="cvData.seal_count > 0">
            <span class="cv-label">印章</span>
            <span class="cv-value">{{ cvData.seal_count }} 个</span>
          </div>
        </div>
        <!-- 路径验证结果 -->
        <div v-if="cvData.path_validation" class="path-validation">
          <div class="validation-header">
            <span class="validation-label">路径验证</span>
            <span :class="['validation-score', cvData.path_validation.passed ? 'pass' : 'warn']">
              {{ cvData.path_validation.score }}分
            </span>
          </div>
          <div v-if="cvData.path_validation.issues && cvData.path_validation.issues.length" class="validation-issues">
            <p v-for="(issue, i) in cvData.path_validation.issues" :key="i" class="issue-item">⚠️ {{ issue }}</p>
          </div>
        </div>
      </section>

      <!-- 起承转合详细分析 -->
      <section v-if="report.arrow_analysis && report.arrow_analysis.llm_analysis" class="arrow-section">
        <h2>起承转合解读</h2>
        <div class="arrow-points" v-if="report.arrow_analysis.points">
          <div class="arrow-point qi">
            <span class="point-label">起</span>
            <span class="point-reason">{{ report.arrow_analysis.points.qi?.reason || '' }}</span>
          </div>
          <div class="arrow-point cheng" v-for="(c, i) in (report.arrow_analysis.points.cheng_list || [])" :key="i">
            <span class="point-label">承{{ (report.arrow_analysis.points.cheng_list || []).length > 1 ? (i + 1) : '' }}</span>
            <span class="point-reason">{{ c.reason || '' }}</span>
          </div>
          <div class="arrow-point zhuan">
            <span class="point-label">转</span>
            <span class="point-reason">{{ report.arrow_analysis.points.zhuan?.reason || '' }}</span>
          </div>
          <div class="arrow-point he">
            <span class="point-label">合</span>
            <span class="point-reason">{{ report.arrow_analysis.points.he?.reason || '' }}</span>
          </div>
        </div>
        <p class="arrow-analysis-text">{{ report.arrow_analysis.llm_analysis }}</p>
      </section>

      <!-- 评分摘要 -->
      <section v-if="report.summary" class="score-section">
        <h2>综合评分</h2>
        <div class="score-big">{{ report.summary.total_score }}<span class="score-unit">/100</span></div>
        <div class="grade-badge">{{ report.summary.grade }}</div>
        <table v-if="report.summary.dimensions && report.summary.dimensions.length" class="dim-table">
          <thead>
            <tr><th>维度</th><th>得分</th><th>满分</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in report.summary.dimensions" :key="d.name">
              <td>{{ d.name }}</td>
              <td>{{ d.score }}</td>
              <td>{{ d.max_score }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- LLM 分析正文 -->
      <section v-if="report.llm && report.llm.text" class="llm-section">
        <h2>智能专家分析</h2>
        <div class="md" v-html="$sanitize(renderedMarkdown)"></div>
      </section>

      <!-- 页脚 -->
      <footer class="report-footer">
        <p>由「潘天寿教你构图」AI 系统生成 — 仅供参考</p>
      </footer>
    </div>

    <!-- 打印按钮 -->
    <div v-if="report && !isPrinting" class="print-actions">
      <button class="btn-print" @click="doPrint">🖨️ 打印 / 保存为 PDF</button>
      <button class="btn-back" @click="goBack">← 返回分析页面</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../../../api'

const route = useRoute()
const router = useRouter()

const taskId = route.params.taskId
const loading = ref(true)
const error = ref('')
const report = ref(null)
const isPrinting = ref(false)

// ---------- Markdown renderer (lightweight, print-safe) ----------
function escapeHtml(t) {
  return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function isSafeImageUrl(u) {
  const s = String(u || '').trim()
  return s.startsWith('/static/') || s.startsWith('/api/') || s.startsWith('http://') || s.startsWith('https://') || s.startsWith('data:image')
}

function _extractInlineSafe(text) {
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
    const parts = processed.split(/(<strong>[\s\S]*?<\/strong>)/)
    let s = parts.map(part => {
      if (part.startsWith('<strong>')) return part
      return escapeHtml(part)
    }).join('')
    s = s.split(/(<em>[\s\S]*?<\/em>)/).map(part => {
      if (part.startsWith('<em>')) return part
      return part
    }).join('')
    s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
    s = s.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
    s = s.replace(/\*\*/g, '')
    return _restoreInline(s, tokens, imgs)
  }

  // No <strong> tags — original path for raw **text** markdown
  let s = escapeHtml(processed)
  s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
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
  let para = []

  const flushPara = () => {
    if (para.length === 0) return
    const txt = para.join(' ').trim()
    if (txt) out.push(`<p>${renderInline(txt)}</p>`)
    para = []
  }

  const closeUl = () => {
    if (inUl) { out.push('</ul>'); inUl = false }
  }

  for (; i < lines.length; i++) {
    const trimmed = lines[i].trim()

    if (trimmed === '```') {
      if (inCode) {
        out.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
        codeLines = []
        inCode = false
      } else {
        flushPara()
        closeUl()
        inCode = true
      }
      continue
    }
    if (inCode) { codeLines.push(lines[i]); continue }
    if (trimmed === '') { flushPara(); continue }

    const h = trimmed.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      flushPara()
      closeUl()
      const level = h[1].length
      out.push(`<h${level}>${renderInline(h[2])}</h${level}>`)
      continue
    }

    const numHead = trimmed.match(/^(\d{1,2})[.、．]\s+/)
    if (numHead) {
      flushPara()
      closeUl()
      const prefix = escapeHtml(numHead[0].trim())
      let dimClean = ''
      let restText = trimmed.slice(numHead[0].length).trim()

      // Case 1: Backend pre-processed: "<strong>title</strong>"
      const htmlBoldMatch = restText.match(/^<strong>([\s\S]*?)<\/strong>\s*[:：]?\s*(.*)/)
      // Case 2: Raw markdown: "**title**"
      const mdBoldMatch = restText.match(/^(\*\*[^*]+?\*\*)\s*[:：]?\s*(.*)/)

      if (htmlBoldMatch) {
        dimClean = htmlBoldMatch[1]
        restText = htmlBoldMatch[2] || ''
      } else if (mdBoldMatch) {
        dimClean = mdBoldMatch[1].replace(/^\*\*?/, '').replace(/\*\*?$/, '')
        restText = mdBoldMatch[2] || ''
      } else {
        const firstToken = restText.match(/^(\S+)/)
        if (firstToken) {
          dimClean = firstToken[1].replace(/^\*\*?/, '').replace(/\*\*?$/, '')
          restText = restText.slice(firstToken[0].length).trim()
        }
      }

      const rest = renderInline(restText).trim()
      const dimHtml = dimClean
        ? `<strong>${prefix} ${escapeHtml(dimClean)}</strong>`
        : `<strong>${prefix}</strong>`
      const lineHtml = rest ? `${dimHtml} ${rest}` : dimHtml
      out.push(`<h3>${lineHtml}</h3>`)
      continue
    }

    const bq = trimmed.match(/^>\s?(.*)$/)
    if (bq) { flushPara(); closeUl(); out.push(`<blockquote>${renderInline(bq[1])}</blockquote>`); continue }

    if (trimmed.startsWith('- ')) {
      flushPara()
      if (!inUl) { out.push('<ul>'); inUl = true }
      out.push(`<li>${renderInline(trimmed.slice(2))}</li>`)
      continue
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
        bodyRows.push(rowLine.split('|').map((x) => x.trim()).filter((x) => x.length > 0))
        i += 1
      }
      i -= 1
      const thead = `<thead><tr>${headerCells.map((c) => `<th>${renderInline(c)}</th>`).join('')}</tr></thead>`
      const tbody = `<tbody>${bodyRows.map((row) => `<tr>${row.map((c) => `<td>${renderInline(c)}</td>`).join('')}</tr>`).join('')}</tbody>`
      out.push(`<table class="md-table">${thead}${tbody}</table>`)
      continue
    }

    para.push(trimmed)
  }
  flushPara()
  closeUl()
  return out.join('\n')
}

const renderedMarkdown = computed(() => {
  if (!report.value?.llm?.text) return ''
  return renderMarkdown(report.value.llm.text)
})

// Image source: try assets.original_url first, then top-level original_url
const imgSrc = computed(() => {
  const r = report.value
  if (!r) return ''
  if (r.assets?.original_url) return r.assets.original_url
  if (r.original_url) return r.original_url
  // Fallback: derive from task_id
  return `/static/uploads/composition/${taskId}.png`
})

// Arrow overlay image URL
const arrowOverlayUrl = computed(() => {
  const r = report.value
  if (!r) return ''
  return r.assets?.arrow_overlay_url || ''
})

// CV 预处理数据
const cvData = computed(() => {
  const r = report.value
  if (!r?.arrow_analysis?.cv_preprocess) return null
  return r.arrow_analysis.cv_preprocess
})

// ---------- Data loading ----------
onMounted(async () => {
  try {
    const res = await api.get(`/composition/report/${taskId}`)
    report.value = res
  } catch (e) {
    error.value = '加载报告失败：' + (e.response?.data?.detail || e.message)
  } finally {
    loading.value = false
  }
})

// ---------- Print ----------
function doPrint() {
  isPrinting.value = true
  setTimeout(() => {
    window.print()
    isPrinting.value = false
  }, 300)
}

function goBack() {
  router.push('/composition')
}
</script>

<style scoped>
.print-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 30px 24px;
  font-family: var(--font-sans, "Noto Sans SC", system-ui, sans-serif);
  color: var(--dark-warm, #3d3d3a);
  background: var(--pure-white, #fff);
}

.loading-wrap, .error-wrap {
  text-align: center;
  padding: 80px 20px;
  color: var(--stone-gray, #87867f);
  font-size: 18px;
}

/* ---- Header ---- */
.report-header {
  text-align: center;
  margin-bottom: 36px;
  border-bottom: 3px solid var(--cinnabar, #c96442);
  padding-bottom: 20px;
}
.report-header h1 {
  font-size: 26px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin: 0 0 10px;
  letter-spacing: 0.06em;
}
.report-meta {
  font-size: 14px;
  color: var(--stone-gray, #87867f);
}
.report-meta span + span::before {
  content: ' · ';
}

/* ---- Images ---- */
.images-section {
  display: flex;
  gap: 24px;
  margin-bottom: 36px;
  page-break-inside: avoid;
}
.img-group {
  flex: 1;
}
.img-group h3 {
  font-size: 14px;
  font-weight: 500;
  color: var(--olive-gray, #5e5d59);
  margin: 0 0 10px;
}
.report-img {
  width: 100%;
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-md, 8px);
  display: block;
}

/* ---- Score ---- */
.score-section {
  text-align: center;
  margin-bottom: 36px;
  page-break-inside: avoid;
}
.score-section h2 {
  font-size: 20px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  border-bottom: 2px solid var(--border-cream, #f0eee6);
  padding-bottom: 10px;
}
.score-big {
  font-size: 64px;
  font-weight: 600;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--cinnabar, #c96442);
  line-height: 1.2;
}
.score-unit {
  font-size: 24px;
  color: var(--stone-gray, #87867f);
}
.grade-badge {
  display: inline-block;
  background: var(--cinnabar, #c96442);
  color: var(--pure-white, #fff);
  font-size: 22px;
  font-weight: 600;
  padding: 4px 20px;
  border-radius: var(--radius-md, 8px);
  margin-top: 6px;
}
.dim-table {
  margin: 20px auto 0;
  border-collapse: collapse;
  width: 80%;
}
.dim-table th, .dim-table td {
  border: 1px solid var(--border-warm, #e8e6dc);
  padding: 8px 16px;
  font-size: 14px;
  text-align: center;
}
.dim-table th {
  background: var(--ivory, #faf9f5);
  font-weight: 500;
}
.dim-table td:first-child {
  text-align: left;
}

/* ---- LLM Analysis ---- */
.llm-section {
  margin-bottom: 36px;
}
.llm-section h2 {
  font-size: 20px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  border-bottom: 2px solid var(--border-cream, #f0eee6);
  padding-bottom: 10px;
  margin-bottom: 20px;
}

/* ---- Arrow Analysis ---- */
.arrow-info {
  margin-top: 10px;
  text-align: center;
}
.path-badge {
  display: inline-block;
  background: var(--near-black, #141413);
  color: var(--pure-white, #fff);
  font-size: 13px;
  font-weight: 600;
  padding: 4px 14px;
  border-radius: var(--radius-lg, 12px);
}
.cv-badge {
  display: inline-block;
  background: var(--cinnabar, #c96442);
  color: var(--pure-white, #fff);
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: var(--radius-md, 8px);
  margin-left: 8px;
}
/* CV 预分析数据面板 */
.cv-section {
  margin-bottom: 32px;
  padding: 16px 20px;
  background: var(--ivory, #faf9f5);
  border-radius: var(--radius-md, 8px);
  border-left: 4px solid var(--cinnabar, #c96442);
}
.cv-section h2 {
  font-size: 16px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin-bottom: 12px;
}
.cv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px 16px;
}
.cv-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cv-label {
  font-size: 12px;
  color: var(--stone-gray, #87867f);
  font-weight: 500;
}
.cv-value {
  font-size: 14px;
  color: var(--dark-warm, #3d3d3a);
  font-weight: 600;
}
/* 路径验证 */
.path-validation {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--pure-white, #fff);
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--border-cream, #f0eee6);
}
.validation-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.validation-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--olive-gray, #5e5d59);
}
.validation-score {
  font-size: 14px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}
.validation-score.pass {
  background: #e6f7ee;
  color: #1a7f37;
}
.validation-score.warn {
  background: #fff3e0;
  color: #e65100;
}
.issue-item {
  font-size: 12px;
  color: #b45309;
  margin: 3px 0;
  padding-left: 4px;
}
.arrow-section {
  margin-bottom: 36px;
}
.arrow-section h2 {
  font-size: 20px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  border-bottom: 2px solid var(--border-cream, #f0eee6);
  padding-bottom: 10px;
  margin-bottom: 16px;
}
.arrow-points {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.arrow-point {
  flex: 1 1 45%;
  background: var(--ivory, #faf9f5);
  border-radius: var(--radius-md, 8px);
  padding: 12px 14px;
  border-left: 4px solid var(--ring-warm, #d1cfc5);
}
.arrow-point.qi { border-left-color: #E53935; }
.arrow-point.cheng { border-left-color: #FF9800; }
.arrow-point.zhuan { border-left-color: #1976D2; }
.arrow-point.he { border-left-color: #2E7D32; }
.point-label {
  display: inline-block;
  font-size: 15px;
  font-weight: 600;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
  color: var(--near-black, #141413);
  margin-right: 8px;
}
.point-reason {
  font-size: 13px;
  color: var(--olive-gray, #5e5d59);
}
.arrow-analysis-text {
  font-size: 14px;
  color: var(--dark-warm, #3d3d3a);
  line-height: 1.9;
  text-align: justify;
}

/* Markdown styles */
.md :deep(h2),
.md :deep(h3),
.md :deep(h4) {
  color: var(--near-black, #141413);
  margin: 22px 0 14px;
  font-weight: 500;
  font-family: var(--font-serif, "Noto Serif SC", Georgia, serif);
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
  margin: 12px 0;
  color: var(--dark-warm, #3d3d3a);
  line-height: 1.9;
  text-align: justify;
}
.md :deep(ul) {
  margin: 12px 0;
  padding-left: 20px;
  color: var(--dark-warm, #3d3d3a);
  line-height: 1.9;
}
.md :deep(strong) {
  color: var(--near-black, #141413);
}
.md :deep(code) {
  background: var(--parchment, #f5f4ed);
  padding: 2px 6px;
  border-radius: var(--radius-sm, 6px);
  font-size: 13px;
}
.md :deep(table.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}
.md :deep(table.md-table th),
.md :deep(table.md-table td) {
  border: 1px solid var(--border-warm, #e8e6dc);
  padding: 8px 12px;
  font-size: 13px;
}
.md :deep(table.md-table th) {
  background: var(--ivory, #faf9f5);
  font-weight: 500;
}
.md :deep(figure.md-fig) {
  margin: 16px 0;
  text-align: center;
}
.md :deep(figure.md-fig img) {
  max-width: 50%;
  width: auto;
  display: block;
  margin: 0 auto;
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-sm, 6px);
}
.md :deep(figcaption) {
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  margin-top: 6px;
}

/* ---- Footer ---- */
.report-footer {
  text-align: center;
  font-size: 12px;
  color: var(--stone-gray, #87867f);
  border-top: 1px solid var(--border-cream, #f0eee6);
  padding-top: 16px;
  margin-top: 40px;
}

/* ---- Print actions (screen only) ---- */
.print-actions {
  position: fixed;
  bottom: 30px;
  right: 30px;
  display: flex;
  gap: 12px;
  z-index: 100;
}
.btn-print {
  padding: 12px 28px;
  border-radius: var(--radius-md, 8px);
  background: var(--cinnabar, #c96442);
  border: none;
  color: var(--pure-white, #fff);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(201,100,66,0.3);
  transition: background 0.2s;
}
.btn-print:hover {
  background: var(--cinnabar-light, #d97757);
}
.btn-back {
  padding: 12px 20px;
  border-radius: var(--radius-md, 8px);
  background: var(--pure-white, #fff);
  border: 1px solid var(--border-warm, #e8e6dc);
  color: var(--charcoal-warm, #4d4c48);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-back:hover {
  background: var(--ivory, #faf9f5);
  border-color: var(--cinnabar-light, #d97757);
  color: var(--cinnabar, #c96442);
}

/* ---- Print styles ---- */
@media print {
  .print-page {
    max-width: none;
    padding: 0;
  }
  .print-actions {
    display: none !important;
  }
  .report-img, .md-fig img {
    max-width: 100% !important;
  }
  section {
    page-break-inside: avoid;
  }
  .score-big {
    color: var(--near-black, #141413) !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .grade-badge {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
</style>
