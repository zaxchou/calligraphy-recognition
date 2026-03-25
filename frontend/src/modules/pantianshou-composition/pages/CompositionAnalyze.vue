<template>
  <div class="page">
    <el-card class="card" shadow="never">
      <div class="upload-layout">
        <div class="upload-left">
          <div class="upload-title">上传画作</div>
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
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">将文件拖到此区域，或点击上传</div>
            <div class="upload-hint">支持 JPG/PNG，建议清晰拍摄或扫描稿</div>
          </el-upload>

          <div class="upload-actions">
            <div class="action-row primary-row">
              <el-button class="btn-analyze" :disabled="!selectedFile || uploading" @click="startAnalyze">开始分析</el-button>
            </div>
            <div class="action-row secondary-row">
              <el-button v-if="taskId" class="btn-danger" :disabled="deleting" @click="deleteTask">删除数据</el-button>
              <el-button class="btn-ghost" @click="openHistory">历史记录</el-button>
              <el-button class="btn-ghost" @click="$router.push('/composition/knowledge')">训练</el-button>
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
        <el-button :loading="historyLoading" @click="loadHistory">刷新</el-button>
      </div>
      <el-table :data="historyItems" :height="historyTableHeight" style="width: 100%">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="预览">
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
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="viewHistory(row.task_id, row.file_name || `历史记录 ${row.created_at}`)"
            >
              查看
            </el-button>
            <el-button size="small" type="danger" @click="deleteHistory(row.task_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-card v-if="report" class="card report" shadow="never">
      <div class="report-layout">
        <div class="main">
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">AI分析</div>
              <div class="panel-sub" v-if="report.llm?.model">模型：{{ report.llm.model }}</div>
            </div>
            <div class="md" v-html="llmHtml"></div>
          </div>
        </div>

        <div class="side">
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">作品预览</div>
              <div class="score-stamp" v-if="totalScore !== null">
                <div class="score-stamp-label">总评</div>
                <div class="score-stamp-num">{{ totalScore }}<span class="score-stamp-max">/100</span></div>
              </div>
            </div>
            <div class="img-block">
              <div class="img-title">原图</div>
              <div class="image-wrap">
                <img
                  v-if="report?.assets?.original_url"
                  class="img"
                  :src="report.assets.original_url"
                  @load="onImageLoad"
                />
              </div>
            </div>

            <div class="img-block">
              <div class="img-title">处理图</div>
              <div class="image-wrap">
                <img v-if="report?.assets?.original_url" class="img" :src="report.assets.original_url" />
                <SvgOverlay
                  v-if="imgWidth > 0 && imgHeight > 0"
                  :width="imgWidth"
                  :height="imgHeight"
                  :annotations="report.annotations || {}"
                />
              </div>
            </div>
            <div class="panel-actions">
              <el-button type="primary" @click="downloadPdf">下载 PDF</el-button>
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">五项雷达</div>
            </div>
            <div ref="radarEl" class="radar"></div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { compositionApi } from '../api/composition'
import SvgOverlay from '../components/SvgOverlay.vue'

const fileList = ref([])
const selectedFile = ref(null)
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

const viewportWidth = ref(1200)

const historyVisible = ref(false)
const historyLoading = ref(false)
const historyItems = ref([])

const bookCoverUrl = '/static/uploads/composition/c5bab166b0e141df9e096f9180348c3e.png'
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
  return viewportWidth.value < 768 ? '100%' : '520px'
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

function isSafeImageUrl(url) {
  const u = String(url || '')
  if (!u) return false
  if (u.startsWith('/static/')) return true
  if (u.startsWith('http://') || u.startsWith('https://')) return true
  return false
}

function renderInline(text) {
  const tokens = []
  const imgs = []
  const src = String(text || '').replace(/`([^`]+)`/g, (_, code) => {
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
  let s = escapeHtml(src2)
  s = s.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\*([^\*]+)\*/g, '<em>$1</em>')
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

    const bq = trimmed.match(/^>\s?(.*)$/)
    if (bq) {
      flushPara()
      closeUl()
      out.push(`<blockquote>${renderInline(bq[1])}</blockquote>`)
      i += 1
      continue
    }

    if (trimmed.startsWith('- ')) {
      flushPara()
      if (!inUl) {
        out.push('<ul>')
        inUl = true
      }
      out.push(`<li>${renderInline(trimmed.slice(2))}</li>`)
      i += 1
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

function buildRadarData() {
  const dims = report.value?.dimensions || []
  const getDim = (name) => dims.find((d) => d?.name === name)
  const open = getDim('开合之势')
  const voidDim = getDim('虚实相生')
  const dense = getDim('疏密有致')
  const checks = report.value?.checks || []
  const getCheck = (name) => checks.find((c) => c?.name === name)
  const force = getCheck('破平行风险')
  const ins = getCheck('题款经营')

  const to10 = (score, max) => {
    const s = Number(score || 0)
    const m = Number(max || 0)
    if (m <= 0) return 0
    return Math.round((s / m) * 10)
  }

  const values = [
    to10(open?.score, open?.max),
    to10(voidDim?.score, voidDim?.max),
    to10(dense?.score, dense?.max),
    to10(force?.score, force?.max),
    to10(ins?.score, ins?.max),
  ]
  const indicators = [
    { name: '起承转合', max: 10 },
    { name: '虚实留白', max: 10 },
    { name: '疏密节奏', max: 10 },
    { name: '势与平衡', max: 10 },
    { name: '题跋布局', max: 10 },
  ]
  return { indicators, values }
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
        axisName: { color: '#2E4057', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e8e4dc' } },
        splitArea: { areaStyle: { color: ['#F8F9FA', '#ffffff'] } },
        axisLine: { lineStyle: { color: '#e8e4dc' } },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: values,
              areaStyle: { color: 'rgba(255, 107, 53, 0.18)' },
              lineStyle: { color: '#FF6B35', width: 2 },
              itemStyle: { color: '#FF6B35' },
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
}

function onFileRemove() {
  fileList.value = []
  selectedFile.value = null
  taskName.value = ''
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
  window.open(compositionApi.getPdfUrl(taskId.value), '_blank')
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
    const d = new Date(s)
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
    report.value = await compositionApi.getReport(id)
  } catch {
    ElMessage.error('加载报告失败')
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
  width: 100%;
  margin: 0;
  padding: 20px 24px;
  background: #ffffff;
  overflow-x: hidden;
}

.card {
  width: 100%;
  border: 1px solid #efe7dd;
  border-radius: 0;
  background: #ffffff;
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
  font-size: 22px;
  font-weight: 900;
  color: #2e4057;
  margin-bottom: 14px;
}

.uploader :deep(.el-upload-dragger) {
  width: 100%;
  border: 3px dashed #cfd6e4;
  border-radius: 18px;
  background: #ffffff;
  padding: 54px 20px;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.uploader {
  width: 100%;
}

.uploader :deep(.el-upload) {
  width: 100%;
}

.upload-icon {
  font-size: 54px;
  color: #2f6bff;
  margin-bottom: 10px;
}

.upload-text {
  font-size: 24px;
  font-weight: 900;
  color: #2e4057;
}

.upload-hint {
  margin-top: 14px;
  font-size: 18px;
  color: #94a3b8;
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
  border-radius: 10px;
  background: #ff6b35;
  border: 1px solid #ff6b35;
  color: #ffffff;
  font-weight: 900;
  font-size: 18px;
}

.btn-analyze:disabled {
  opacity: 0.6;
}

.btn-ghost {
  height: 46px;
  padding: 0 26px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #d9dde6;
  color: #2e4057;
  font-weight: 700;
}

.btn-danger {
  height: 46px;
  padding: 0 26px;
  border-radius: 10px;
  background: #ff6b6b;
  border: 1px solid #ff6b6b;
  color: #ffffff;
  font-weight: 800;
}

.book {
  border: 1px solid #e8e4dc;
  border-radius: 18px;
  background: #ffffff;
  padding: 18px;
}

.book-cover {
  width: 168px;
  height: 238px;
  object-fit: cover;
  border-radius: 14px;
  border: 1px solid #eef0f6;
  background: #fff;
}

.book-head {
  font-size: 14px;
  color: #6b6b6b;
  margin-bottom: 12px;
}

.book-top {
  display: grid;
  grid-template-columns: 168px 1fr 220px;
  gap: 18px;
  align-items: start;
}

.book-name {
  font-size: 28px;
  font-weight: 900;
  color: #2e4057;
  margin-bottom: 10px;
  text-decoration: none;
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
  color: #263238;
  font-size: 14px;
}

.kv-k {
  color: #6b6b6b;
}

.kv-v {
  color: #263238;
  font-weight: 700;
}

.book-rate {
  border-left: 1px solid #e8e4dc;
  padding-left: 18px;
}

.rate-title {
  color: #6b6b6b;
  font-size: 14px;
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
  font-weight: 900;
  color: #263238;
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
  color: #2f6bff;
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
  color: #6b6b6b;
}

.bar {
  height: 8px;
  background: #f3f4f6;
  border-radius: 999px;
  overflow: hidden;
}

.bar-in {
  height: 100%;
  background: #f59e0b;
  display: block;
}

.bar-v {
  text-align: right;
}

.book-desc {
  margin-top: 18px;
  border-top: 1px solid #e8e4dc;
  padding-top: 14px;
}

.desc-title {
  font-size: 16px;
  font-weight: 900;
  color: #2e4057;
  margin: 12px 0 8px;
}

.desc-text {
  color: #263238;
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
  font-weight: 600;
  color: #2f2f2f;
  flex: 0 1 42%;
  max-width: 42%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-meta {
  color: #6b6b6b;
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
  color: #6b6b6b;
}

.error {
  color: #d32f2f;
}

.history-actions {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
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
  border: 1px solid #e8e4dc;
  background: #fff;
  border-radius: 12px;
  padding: 14px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}

.score-stamp {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.score-stamp-label {
  font-size: 12px;
  color: #6b6b6b;
}

.score-stamp-num {
  font-size: 38px;
  font-weight: 900;
  color: #ff6b35;
  line-height: 1;
}

.score-stamp-max {
  font-size: 14px;
  color: #6b6b6b;
  margin-left: 6px;
  font-weight: 800;
}

.img-block {
  margin-top: 10px;
}

.img-title {
  font-weight: 800;
  color: #2e4057;
  margin-bottom: 8px;
}

.panel-title {
  font-weight: 800;
  color: #2e4057;
  letter-spacing: 0.2px;
}

.panel-sub {
  color: #6b6b6b;
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
  border: 1px solid #e8e4dc;
  background: #fff;
  overflow: hidden;
  border-radius: 10px;
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
  color: #2e4057;
  margin: 22px 0 14px;
  font-weight: 900;
}

.md :deep(h1) {
  font-size: 20px;
}

.md :deep(h2) {
  font-size: 18px;
  border-left: 4px solid #ff6b35;
  padding-left: 10px;
}

.md :deep(h3) {
  font-size: 16px;
}

.md :deep(p) {
  margin: 18px 0;
  color: #263238;
  line-height: 2;
}

.md :deep(ul) {
  margin: 18px 0;
  padding-left: 20px;
  color: #263238;
  line-height: 2;
}

.md :deep(li) {
  margin: 10px 0;
}

.md :deep(blockquote) {
  margin: 18px 0;
  padding: 14px 14px;
  border-left: 4px solid #ff6b35;
  background: #f8f9fa;
  color: #2f2f2f;
}

.md :deep(code) {
  background: rgba(46, 64, 87, 0.08);
  padding: 2px 6px;
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}

.md :deep(pre) {
  margin: 12px 0;
  padding: 12px;
  border-radius: 12px;
  background: #0f172a;
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
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.md :deep(.md-img) {
  width: 100%;
  display: block;
}

.md :deep(.md-fig figcaption) {
  padding: 10px 12px;
  background: #f8f9fa;
  color: #3d3d3d;
  line-height: 1.6;
}

.md :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid #e8e4dc;
  table-layout: fixed;
}

.md :deep(.md-table th),
.md :deep(.md-table td) {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e4dc;
  text-align: left;
  color: #263238;
  word-break: break-word;
}

.md :deep(.md-table thead th) {
  background: #f8f9fa;
  font-weight: 900;
  color: #2e4057;
}

.md :deep(.md-table tbody tr:nth-child(2n)) td {
  background: rgba(248, 249, 250, 0.7);
}

@media (max-width: 1024px) {
  .page {
    padding: 14px 14px;
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

  .upload-title {
    font-size: 18px;
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
