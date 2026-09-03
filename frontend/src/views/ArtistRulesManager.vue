<template>
  <div class="artist-rules-manager">
    <div class="toolbar">
      <el-select v-model="selectedArtist" size="small" placeholder="选择画家" @change="loadRules" style="width: 160px;">
        <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
      </el-select>
      <el-button size="small" @click="refreshRules" :disabled="editing">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
      <div style="flex:1"></div>
      <template v-if="currentRule && !editing">
        <el-button size="small" @click="exportRule">
          <el-icon><DocumentCopy /></el-icon>复制JSON
        </el-button>
        <el-button size="small" @click="startEdit">
          <el-icon><Edit /></el-icon>编辑JSON
        </el-button>
      </template>
      <template v-if="editing">
        <el-button size="small" @click="cancelEdit">取消</el-button>
        <el-button size="small" type="primary" @click="saveFromJson" :loading="saving">
          <el-icon><Check /></el-icon>保存
        </el-button>
      </template>
      <el-button v-if="!editing" size="small" @click="showImportDialog = true">
        <el-icon><Upload /></el-icon>导入
      </el-button>
    </div>

    <div v-loading="loading" class="rules-content">
      <div v-if="!selectedArtist" class="empty-state">
        <el-empty description="请选择画家查看规则" />
      </div>
      <div v-else-if="error && !editing" class="empty-state">
        <el-empty :description="error">
          <el-button type="primary" @click="showImportDialog = true">导入规则</el-button>
        </el-empty>
      </div>

      <!-- 视图模式：结构化展示 -->
      <div v-else-if="currentRule && !editing" class="json-view">
        <div class="json-header">
          <span class="json-artist">{{ currentRule.artist_name }}</span>
          <el-tag size="small" type="info">v{{ currentRule.rules_version || '5.7' }}</el-tag>
          <el-tag size="small" :type="currentRule.emotion_baseline < 0 ? 'danger' : currentRule.emotion_baseline > 0 ? 'success' : 'info'">
            baseline: {{ (currentRule.emotion_baseline ?? 0).toFixed(1) }}
          </el-tag>
        </div>

        <!-- 生命周期时间线 -->
        <div class="json-section" v-if="lifeStages.length">
          <div class="json-section-title">生命周期</div>
          <div class="timeline">
            <div v-for="(s, i) in lifeStages" :key="i" class="timeline-item">
              <div class="timeline-dot" :style="{ background: s.mood_offset > 0 ? '#67c23a' : s.mood_offset < 0 ? '#f56c6c' : '#909399' }"></div>
              <div class="timeline-line" v-if="i < lifeStages.length - 1"></div>
              <div class="timeline-content">
                <div class="timeline-name">{{ s.name }}</div>
                <div class="timeline-years">{{ s.year_start }}–{{ s.year_end }}</div>
                <div class="timeline-meta">
                  权重 {{ s.weight }} · 偏移 {{ (s.mood_offset ?? 0).toFixed(1) }}
                  <span v-if="s.description"> · {{ s.description }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- LLM 提示词 -->
        <div class="json-section" v-if="currentRule.sentiment_note || currentRule.theme_note">
          <div class="json-section-title">LLM 提示词</div>
          <div class="note-card" v-if="currentRule.sentiment_note">
            <div class="note-label">情感倾向</div>
            <div class="note-text">{{ currentRule.sentiment_note }}</div>
          </div>
          <div class="note-card" v-if="currentRule.theme_note">
            <div class="note-label">主题倾向</div>
            <div class="note-text">{{ currentRule.theme_note }}</div>
          </div>
        </div>

        <!-- 主题例外 -->
        <div class="json-section" v-if="Object.keys(themeExceptions).length">
          <div class="json-section-title">主题情感例外</div>
          <div class="exception-row" v-for="(exc, code) in themeExceptions" :key="code">
            <span class="exc-theme">主题 {{ code }}</span>
            <span class="exc-keywords" v-if="exc.override_if_contains">触发词: {{ exc.override_if_contains.join(', ') }}</span>
            <span class="exc-arrow">→</span>
            <el-tag size="small" :type="exc.override_to === 'negative' ? 'danger' : 'success'">{{ exc.override_to }}</el-tag>
          </div>
        </div>

        <!-- 印章规则 -->
        <div class="json-section" v-if="Object.keys(sealRules).length">
          <div class="json-section-title">印章情感规则</div>
          <div class="seal-rules-grid">
            <div v-for="(rule, name) in sealRules" :key="name" class="seal-rule-item"
              :class="{ positive: rule.score > 0, negative: rule.score < 0 }">
              <span class="seal-rule-name">{{ name }}</span>
              <span class="seal-rule-score">{{ rule.score > 0 ? '+' : '' }}{{ rule.score.toFixed(1) }}</span>
              <span class="seal-rule-cat">{{ rule.category }}</span>
              <span class="seal-rule-desc" v-if="rule.desc">{{ rule.desc }}</span>
            </div>
          </div>
        </div>

        <!-- 预期分布 -->
        <div class="json-section" v-if="Object.keys(expectedTheme).length">
          <div class="json-section-title">预期分布</div>
          <div class="dist-bars">
            <div v-for="(range, theme) in expectedTheme" :key="theme" class="dist-bar-row">
              <span class="dist-bar-label">{{ theme }}</span>
              <div class="dist-bar-track">
                <div class="dist-bar-fill" :style="{ left: range[0] + '%', width: (range[1] - range[0]) + '%' }"></div>
              </div>
              <span class="dist-bar-range">{{ range[0] }}–{{ range[1] }}%</span>
            </div>
          </div>
          <div class="sentiment-meta" v-if="Object.keys(expectedSentiment).length">
            消极下限 {{ expectedSentiment.negative_min }}% · 积极上限 {{ expectedSentiment.positive_max }}% · 均值上限 {{ expectedSentiment.emotion_mean_max }}
          </div>
        </div>

        <!-- 原始 JSON 折叠 -->
        <el-collapse class="json-raw-collapse">
          <el-collapse-item title="查看原始 JSON" name="raw">
            <pre class="json-raw">{{ formattedJson }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 编辑模式：JSON 编辑器 -->
      <div v-else-if="editing" class="json-editor-wrap">
        <div class="editor-toolbar">
          <el-button size="small" text @click="formatJson">格式化</el-button>
          <el-button size="small" text @click="copyTemplateToEditor">插入模板</el-button>
          <span class="editor-status" :class="{ error: !!jsonError, valid: !jsonError && editing }">
            {{ jsonError || 'JSON 格式正确' }}
          </span>
        </div>
        <textarea ref="jsonEditorRef" v-model="jsonText" class="json-editor" spellcheck="false" @input="validateJson"></textarea>
      </div>
    </div>

    <!-- 导入/AI生成对话框 -->
    <el-dialog v-model="showImportDialog" title="导入 / AI 生成画家规则" width="640px">
      <!-- AI 一键生成 -->
      <div class="ai-generate-section">
        <div class="ai-section-header">
          <el-icon><MagicStick /></el-icon>
          <span>AI 一键生成</span>
        </div>
        <div class="ai-section-body">
          <el-select v-model="aiTargetArtist" size="small" placeholder="选择画家" filterable allow-create style="width: 180px;">
            <el-option v-for="a in artistList" :key="a" :label="a" :value="a" />
          </el-select>
          <el-button size="small" type="primary" @click="handleAiGenerate" :loading="aiGenerating" :disabled="!aiTargetArtist">
            <el-icon><MagicStick /></el-icon>生成规则
          </el-button>
          <span class="ai-hint">基于该画家的题跋样本自动生成规则包</span>
        </div>
      </div>

      <el-divider content-position="left">或手动导入</el-divider>

      <div class="import-actions">
        <el-button size="small" @click="insertTemplate">插入模板</el-button>
        <el-button size="small" @click="pasteFromClipboard">从剪贴板粘贴</el-button>
      </div>
      <textarea v-model="importJson" class="json-editor import-editor" spellcheck="false" @input="validateImportJson" placeholder="粘贴 JSON 或由 AI 生成..."></textarea>
      <div class="import-validation">
        <span v-if="!importJson.trim()" class="validation-idle">等待输入...</span>
        <span v-else-if="importJsonError" class="validation-error">
          <el-icon><CircleClose /></el-icon> {{ importJsonError }}
        </span>
        <span v-else class="validation-ok">
          <el-icon><CircleCheck /></el-icon> 格式正确 — {{ importPreview }}
        </span>
      </div>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="handleImport" :loading="importing" :disabled="!!importJsonError || !importJson.trim()">导入并保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Edit, Plus, Upload, DocumentCopy, Check, CircleCheck, CircleClose, MagicStick } from '@element-plus/icons-vue'
import api, { artistRulesApi } from '../api'

const RULE_SCHEMA_FIELDS = [
  'artist_name', 'emotion_baseline', 'life_stages', 'sentiment_note',
  'theme_note', 'theme_exceptions', 'seal_rules',
  'expected_theme_distribution', 'expected_sentiment_distribution', 'rules_version'
]

const props = defineProps({
  artist: { type: String, default: '李鱓' }
})

const selectedArtist = ref(props.artist)
const loading = ref(false)
const saving = ref(false)
const currentRule = ref(null)
const error = ref('')
const artistList = ref([])

// Edit state
const editing = ref(false)
const jsonText = ref('')
const jsonError = ref('')
const jsonEditorRef = ref(null)

// Import state
const showImportDialog = ref(false)
const importJson = ref('')
const importJsonError = ref('')
const importing = ref(false)
const aiTargetArtist = ref('')
const aiGenerating = ref(false)

const importPreview = computed(() => {
  try {
    const d = JSON.parse(importJson.value)
    const name = d.artist_name || '(未命名)'
    const stages = Array.isArray(d.life_stages) ? d.life_stages.length : 0
    return `画家「${name}」${stages} 个阶段`
  } catch { return '' }
})

// ── View computed ──
const lifeStages = computed(() => {
  if (!currentRule.value) return []
  return Array.isArray(currentRule.value.life_stages) ? currentRule.value.life_stages : []
})

const themeExceptions = computed(() => {
  if (!currentRule.value) return {}
  const exc = currentRule.value.theme_exceptions
  return typeof exc === 'object' && exc !== null ? exc : {}
})

const sealRules = computed(() => {
  if (!currentRule.value) return {}
  const sr = currentRule.value.seal_rules
  return typeof sr === 'object' && sr !== null ? sr : {}
})

const expectedTheme = computed(() => {
  if (!currentRule.value) return {}
  const et = currentRule.value.expected_theme_distribution
  return typeof et === 'object' && et !== null && !Array.isArray(et) ? et : {}
})

const expectedSentiment = computed(() => {
  if (!currentRule.value) return {}
  const es = currentRule.value.expected_sentiment_distribution
  return typeof es === 'object' && es !== null ? es : {}
})

const formattedJson = computed(() => {
  if (!currentRule.value) return ''
  const data = {}
  for (const f of RULE_SCHEMA_FIELDS) {
    if (currentRule.value[f] !== undefined && currentRule.value[f] !== null) {
      data[f] = currentRule.value[f]
    }
  }
  return JSON.stringify(data, null, 2)
})

watch(() => props.artist, (val) => {
  if (val) {
    selectedArtist.value = val
    editing.value = false
    loadRules()
  }
})

// ── Data loading ──
async function loadArtistList() {
  try {
    const data = await api.get('/content-analysis/artists')
    artistList.value = data.artists || []
  } catch (e) { /* ignore */ }
}

async function loadRules() {
  if (!selectedArtist.value || selectedArtist.value === 'all') return
  loading.value = true
  editing.value = false
  error.value = ''
  try {
    const res = await artistRulesApi.getByName(selectedArtist.value)
    currentRule.value = res.rule
    if (!res.rule) error.value = `画家「${selectedArtist.value}」尚无规则数据`
  } catch (e) {
    currentRule.value = null
    error.value = '加载规则失败: ' + (e.message || e)
  } finally {
    loading.value = false
  }
}

// ── Edit mode ──
function startEdit() {
  jsonText.value = formattedJson.value
  jsonError.value = ''
  editing.value = true
  nextTick(() => {
    if (jsonEditorRef.value) jsonEditorRef.value.focus()
  })
}

function cancelEdit() {
  editing.value = false
  jsonText.value = ''
  jsonError.value = ''
}

function validateJson() {
  try {
    const data = JSON.parse(jsonText.value)
    if (!data.artist_name) { jsonError.value = '缺少 artist_name'; return }
    if (!Array.isArray(data.life_stages)) { jsonError.value = 'life_stages 应为数组'; return }
    jsonError.value = ''
  } catch (e) {
    jsonError.value = e.message.replace(/^JSON\.parse: /, '')
  }
}

function formatJson() {
  try {
    const data = JSON.parse(jsonText.value)
    jsonText.value = JSON.stringify(data, null, 2)
    jsonError.value = ''
  } catch { /* keep as is */ }
}

function copyTemplateToEditor() {
  jsonText.value = JSON.stringify(makeTemplate(), null, 2)
  jsonError.value = ''
}

async function saveFromJson() {
  validateJson()
  if (jsonError.value) {
    ElMessage.warning('JSON 格式有误，请先修正')
    return
  }

  let data
  try { data = JSON.parse(jsonText.value) } catch { return }

  saving.value = true
  try {
    const existing = await artistRulesApi.getByName(data.artist_name)
    if (existing.rule) {
      await artistRulesApi.update(existing.rule.id, data)
    } else {
      await artistRulesApi.create(data)
    }
    ElMessage.success(`画家「${data.artist_name}」规则已保存`)
    editing.value = false
    selectedArtist.value = data.artist_name
    await loadRules()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    saving.value = false
  }
}

// ── Export ──
function exportRule() {
  const json = formattedJson.value
  navigator.clipboard.writeText(json).then(() => {
    ElMessage.success('JSON 已复制到剪贴板，可直接粘贴给 AI')
  }).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = json; document.body.appendChild(ta)
    ta.select(); document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success('已复制')
  })
}

// ── Import ──
function makeTemplate() {
  return {
    artist_name: "画家名称",
    emotion_baseline: 0.0,
    life_stages: [
      { name: "早期", year_start: 1700, year_end: 1730, weight: 1.0, mood_offset: 0.0, description: "" },
      { name: "中期", year_start: 1731, year_end: 1760, weight: 1.5, mood_offset: -0.2, description: "" },
      { name: "晚期", year_start: 1761, year_end: 1790, weight: 2.0, mood_offset: -0.4, description: "" }
    ],
    sentiment_note: "",
    theme_note: "",
    theme_exceptions: {},
    seal_rules: {
      "苦李": { "score": -1.0, "category": "spirit", "desc": "苦涩自况" },
      "卖画不为官": { "score": 1.0, "category": "spirit", "desc": "以画自立" }
    },
    expected_theme_distribution: {
      "身世自况": [5, 15], "咏物寄兴": [35, 55], "画理自叙": [3, 10],
      "时事讽喻": [3, 10], "吉语祥瑞": [3, 10], "交游赠答": [3, 10]
    },
    expected_sentiment_distribution: { negative_min: 30, positive_max: 45, emotion_mean_max: 0.0 },
    rules_version: "5.7"
  }
}

// Pre-fill AI target when dialog opens
watch(showImportDialog, (val) => {
  if (val) {
    aiTargetArtist.value = selectedArtist.value || ''
    importJson.value = ''
    importJsonError.value = ''
  }
})

async function handleAiGenerate() {
  if (!aiTargetArtist.value) return
  aiGenerating.value = true
  try {
    const res = await artistRulesApi.aiDiscover(aiTargetArtist.value)
    if (res.success) {
      // AI discover created the rule in DB — now load it and show in editor
      const ruleRes = await artistRulesApi.getByName(aiTargetArtist.value)
      if (ruleRes.rule) {
        const data = {}
        for (const f of RULE_SCHEMA_FIELDS) {
          if (ruleRes.rule[f] !== undefined) data[f] = ruleRes.rule[f]
        }
        importJson.value = JSON.stringify(data, null, 2)
        importJsonError.value = ''
        ElMessage.success(`AI 已为「${aiTargetArtist.value}」生成规则，请审查后保存`)
      }
    } else {
      ElMessage.error(res.message || 'AI 生成失败')
    }
  } catch (e) {
    ElMessage.error('AI 生成失败: ' + (e.response?.data?.detail || e.message || e))
  } finally {
    aiGenerating.value = false
  }
}

function insertTemplate() {
  importJson.value = JSON.stringify(makeTemplate(), null, 2)
  importJsonError.value = ''
}

async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText()
    importJson.value = text
    validateImportJson()
  } catch {
    ElMessage.warning('无法读取剪贴板，请手动粘贴')
  }
}

function validateImportJson() {
  if (!importJson.value.trim()) { importJsonError.value = ''; return }
  try {
    const data = JSON.parse(importJson.value)
    if (!data.artist_name) { importJsonError.value = '缺少 artist_name 字段'; return }
    for (const f of ['emotion_baseline', 'life_stages', 'sentiment_note']) {
      if (data[f] === undefined) { importJsonError.value = `缺少必需字段: ${f}`; return }
    }
    importJsonError.value = ''
  } catch (e) {
    importJsonError.value = 'JSON 解析错误: ' + e.message.replace(/^JSON\.parse: /, '')
  }
}

async function handleImport() {
  validateImportJson()
  if (importJsonError.value) return

  const data = JSON.parse(importJson.value)
  importing.value = true
  try {
    const existing = await artistRulesApi.getByName(data.artist_name)
    if (existing.rule) {
      await artistRulesApi.update(existing.rule.id, data)
      ElMessage.success(`画家「${data.artist_name}」规则已更新`)
    } else {
      await artistRulesApi.create(data)
      ElMessage.success(`画家「${data.artist_name}」规则已创建`)
    }
    showImportDialog.value = false
    importJson.value = ''
    selectedArtist.value = data.artist_name
    await loadRules()
  } catch (e) {
    importJsonError.value = '导入失败: ' + (e.response?.data?.detail || e.message || e)
  } finally {
    importing.value = false
  }
}

function refreshRules() { loadRules() }

onMounted(() => { loadArtistList(); loadRules() })
</script>

<style scoped>
.artist-rules-manager { padding: 0; }
.toolbar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
.rules-content { min-height: 300px; }
.empty-state { padding: 60px 0; }

/* ── JSON View ── */
.json-view { }
.json-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
}
.json-artist { font-size: 18px; font-weight: 700; color: #333; }

.json-section {
  background: white; border-radius: 10px; padding: 16px 20px;
  margin-bottom: 12px; box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.json-section-title {
  font-size: 13px; font-weight: 700; color: #666;
  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;
}

/* Timeline */
.timeline { position: relative; padding-left: 20px; }
.timeline-item { position: relative; padding-bottom: 16px; }
.timeline-item:last-child { padding-bottom: 0; }
.timeline-dot {
  position: absolute; left: -20px; top: 4px;
  width: 10px; height: 10px; border-radius: 50%;
}
.timeline-line {
  position: absolute; left: -16px; top: 14px; bottom: 0;
  width: 2px; background: #e8e4da;
}
.timeline-name { font-size: 14px; font-weight: 600; color: #333; }
.timeline-years { font-size: 12px; color: #999; font-family: monospace; }
.timeline-meta { font-size: 12px; color: #888; margin-top: 2px; }

/* Notes */
.note-card { margin-bottom: 10px; }
.note-card:last-child { margin-bottom: 0; }
.note-label { font-size: 11px; color: #999; font-weight: 600; margin-bottom: 4px; }
.note-text { font-size: 13px; color: #555; line-height: 1.7; background: #faf9f7; padding: 8px 12px; border-radius: 6px; }

/* Exceptions */
.exception-row {
  display: flex; align-items: center; gap: 10px; padding: 6px 0;
  border-bottom: 1px solid #f5f0e8; font-size: 13px;
}
.exception-row:last-child { border-bottom: none; }
.exc-theme { font-weight: 600; color: #c96442; min-width: 60px; }
.exc-keywords { color: #666; flex: 1; }
.exc-arrow { color: #ccc; }

/* Seal rules */
.seal-rules-grid { display: flex; flex-direction: column; gap: 4px; }
.seal-rule-item {
  display: flex; align-items: center; gap: 10px; padding: 6px 10px;
  background: #faf9f7; border-radius: 6px; font-size: 13px;
  border-left: 3px solid #ddd;
}
.seal-rule-item.positive { border-left-color: #67c23a; }
.seal-rule-item.negative { border-left-color: #f56c6c; }
.seal-rule-name { font-weight: 600; color: #333; min-width: 90px; }
.seal-rule-score { font-family: monospace; font-weight: 600; min-width: 40px; }
.seal-rule-item.positive .seal-rule-score { color: #67c23a; }
.seal-rule-item.negative .seal-rule-score { color: #f56c6c; }
.seal-rule-cat { color: #999; font-size: 11px; min-width: 90px; }
.seal-rule-desc { color: #666; font-size: 12px; }

/* Distribution bars */
.dist-bars { display: flex; flex-direction: column; gap: 6px; }
.dist-bar-row { display: flex; align-items: center; gap: 10px; }
.dist-bar-label { width: 70px; font-size: 12px; color: #666; text-align: right; flex-shrink: 0; }
.dist-bar-track {
  flex: 1; height: 8px; background: #f0ebe0; border-radius: 4px;
  position: relative; overflow: hidden;
}
.dist-bar-fill {
  position: absolute; top: 0; height: 100%;
  background: linear-gradient(90deg, #d4a899, #a3c9a1); border-radius: 4px;
}
.dist-bar-range { font-size: 11px; color: #999; font-family: monospace; min-width: 60px; }
.sentiment-meta {
  margin-top: 10px; font-size: 12px; color: #999; text-align: center;
  padding-top: 8px; border-top: 1px solid #f0ebe0;
}

/* Raw JSON collapse */
.json-raw-collapse { margin-top: 12px; }
.json-raw {
  font-family: 'Consolas', 'Monaco', monospace; font-size: 12px;
  line-height: 1.6; color: #555; background: #faf9f7;
  padding: 12px 16px; border-radius: 6px; overflow-x: auto;
  white-space: pre; margin: 0;
}

/* ── JSON Editor ── */
.json-editor-wrap { display: flex; flex-direction: column; height: calc(100vh - 200px); min-height: 400px; }
.editor-toolbar {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: #f8f6f2; border-radius: 8px 8px 0 0; border: 1px solid #e8e4da;
  border-bottom: none;
}
.editor-status {
  margin-left: auto; font-size: 12px;
}
.editor-status.error { color: #f56c6c; }
.editor-status.valid { color: #67c23a; }
.json-editor {
  flex: 1; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px;
  line-height: 1.6; padding: 16px; border: 1px solid #e8e4da;
  border-radius: 0 0 8px 8px; resize: none; outline: none;
  background: #fff; color: #333; tab-size: 2;
}
.json-editor:focus { border-color: #409eff; }

/* ── Import Dialog ── */
.import-intro { font-size: 13px; color: #666; margin-bottom: 10px; line-height: 1.6; }
.import-actions { display: flex; gap: 8px; margin-bottom: 10px; }
.import-editor { height: 300px; width: 100%; }
.import-validation {
  margin-top: 8px; font-size: 13px; display: flex; align-items: center; gap: 4px;
}
.validation-idle { color: #999; }
.validation-error { color: #f56c6c; }
.validation-ok { color: #67c23a; }

/* AI Generate */
.ai-generate-section {
  background: #f0f7ff; border: 1px solid #d9ecff; border-radius: 8px;
  padding: 14px 16px; margin-bottom: 12px;
}
.ai-section-header {
  display: flex; align-items: center; gap: 6px; margin-bottom: 10px;
  font-size: 14px; font-weight: 600; color: #409eff;
}
.ai-section-body {
  display: flex; align-items: center; gap: 10px;
}
.ai-hint { font-size: 12px; color: #999; }
</style>
