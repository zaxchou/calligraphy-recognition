<template>
  <div class="artist-rules-manager">
    <div class="toolbar">
      <el-select v-model="selectedArtist" size="small" placeholder="选择画家" @change="loadRules" style="width: 160px;">
        <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
      </el-select>
      <el-button v-if="!editing" size="small" type="primary" plain @click="handleAiDiscover" :loading="aiDiscoverLoading" :disabled="!selectedArtist">
        <el-icon><MagicStick /></el-icon>AI 规则发现
      </el-button>
      <el-button size="small" @click="refreshRules" :disabled="editing">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
      <div style="flex:1"></div>
      <template v-if="editing">
        <el-button size="small" @click="cancelEdit">取消</el-button>
        <el-button size="small" type="primary" @click="saveRules" :loading="saving">保存</el-button>
      </template>
      <template v-else-if="currentRule">
        <el-button size="small" @click="startEdit">
          <el-icon><Edit /></el-icon>编辑
        </el-button>
        <el-button size="small" @click="exportRule">
          <el-icon><Download /></el-icon>导出
        </el-button>
      </template>
      <template v-else-if="selectedArtist && !loading">
        <el-button size="small" type="success" @click="startCreate">
          <el-icon><Plus /></el-icon>新建规则
        </el-button>
        <el-button size="small" @click="showImportDialog = true">
          <el-icon><Upload /></el-icon>导入规则
        </el-button>
      </template>
    </div>

    <div v-loading="loading" class="rules-content">
      <div v-if="!selectedArtist" class="empty-state">
        <el-empty description="请选择画家查看规则" />
      </div>
      <div v-else-if="error && !editing" class="empty-state">
        <el-empty :description="error" />
      </div>

      <!-- 只读展示 -->
      <div v-else-if="currentRule && !editing" class="rule-detail">
        <!-- 基本信息 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">基本信息</span>
            <el-tag size="small" type="info">v{{ currentRule.rules_version || '5.4' }}</el-tag>
          </div>
          <div class="rule-grid">
            <div class="rule-item">
              <span class="rule-label">情感基线</span>
              <span class="rule-value" :class="{ negative: currentRule.emotion_baseline < 0, positive: currentRule.emotion_baseline > 0 }">
                {{ (currentRule.emotion_baseline ?? 0).toFixed(1) }}
              </span>
            </div>
            <div class="rule-item">
              <span class="rule-label">生命周期阶段</span>
              <span class="rule-value">{{ lifeStageCount }}</span>
            </div>
            <div class="rule-item">
              <span class="rule-label">主题例外规则</span>
              <span class="rule-value">{{ themeExceptionCount }}</span>
            </div>
            <div class="rule-item">
              <span class="rule-label">更新时间</span>
              <span class="rule-value text-sm">{{ (currentRule.updated_at || '').slice(0, 10) }}</span>
            </div>
          </div>
        </div>

        <!-- 生命周期 -->
        <div class="rule-section" v-if="lifeStages.length > 0">
          <div class="section-header">
            <span class="section-title">生命周期</span>
          </div>
          <div class="stage-list">
            <div v-for="(stage, idx) in lifeStages" :key="idx" class="stage-item">
              <div class="stage-header">
                <span class="stage-name">{{ stage.name }}</span>
                <span class="stage-years">{{ stage.year_start }} ~ {{ stage.year_end }}</span>
              </div>
              <div class="stage-detail">
                <span>权重: {{ stage.weight }}</span>
                <span>心境偏移: {{ (stage.mood_offset ?? 0).toFixed(1) }}</span>
              </div>
              <div v-if="stage.description" class="stage-desc">{{ stage.description }}</div>
            </div>
          </div>
        </div>

        <!-- 情感/主题提示 -->
        <div class="rule-section" v-if="currentRule.sentiment_note">
          <div class="section-header">
            <span class="section-title">情感倾向说明（LLM 注入）</span>
          </div>
          <div class="rule-text">{{ currentRule.sentiment_note }}</div>
        </div>
        <div class="rule-section" v-if="currentRule.theme_note">
          <div class="section-header">
            <span class="section-title">主题倾向说明（LLM 注入）</span>
          </div>
          <div class="rule-text">{{ currentRule.theme_note }}</div>
        </div>

        <!-- 主题例外 -->
        <div class="rule-section" v-if="Object.keys(themeExceptions).length > 0">
          <div class="section-header">
            <span class="section-title">主题情感例外</span>
          </div>
          <div class="exception-list">
            <div v-for="(exc, themeCode) in themeExceptions" :key="themeCode" class="exception-item">
              <span class="exception-theme">主题{{ themeCode }}</span>
              <span v-if="exc.override_if_contains">触发词: [{{ exc.override_if_contains.join(', ') }}]</span>
              <span>→ {{ exc.override_to }}</span>
            </div>
          </div>
        </div>

        <!-- 预期分布 -->
        <div class="rule-section" v-if="Object.keys(expectedTheme).length > 0">
          <div class="section-header">
            <span class="section-title">预期主题分布（偏差检测）</span>
          </div>
          <div class="distribution-grid">
            <div v-for="(range, theme) in expectedTheme" :key="theme" class="dist-item">
              <span class="dist-theme">{{ theme }}</span>
              <span class="dist-range">{{ range[0] }}% - {{ range[1] }}%</span>
            </div>
          </div>
        </div>
        <div class="rule-section" v-if="Object.keys(expectedSentiment).length > 0">
          <div class="section-header">
            <span class="section-title">预期情感分布（偏差检测）</span>
          </div>
          <div class="rule-grid">
            <div class="rule-item">
              <span class="rule-label">消极下限</span>
              <span class="rule-value">{{ expectedSentiment.negative_min }}%</span>
            </div>
            <div class="rule-item">
              <span class="rule-label">积极上限</span>
              <span class="rule-value">{{ expectedSentiment.positive_max }}%</span>
            </div>
            <div class="rule-item">
              <span class="rule-label">情感均值上限</span>
              <span class="rule-value">{{ expectedSentiment.emotion_mean_max }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 编辑模式 -->
      <div v-else-if="editing" class="rule-edit">
        <!-- 基本信息编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">基本信息</span>
          </div>
          <el-form label-width="100px" size="small">
            <el-form-item label="画家名称" v-if="creating">
              <el-input v-model="editForm.artist_name" placeholder="输入画家名称" style="width: 200px;" />
            </el-form-item>
            <el-form-item label="画家名称" v-else>
              <span style="font-weight: 600;">{{ editForm.artist_name }}</span>
            </el-form-item>
            <el-form-item label="情感基线">
              <el-input-number v-model="editForm.emotion_baseline" :min="-1" :max="1" :step="0.1" :precision="1" />
              <span style="margin-left: 12px; font-size: 12px; color: #999;">负值=偏消极，正值=偏积极</span>
            </el-form-item>
            <el-form-item label="版本号">
              <el-input v-model="editForm.rules_version" style="width: 120px;" />
            </el-form-item>
          </el-form>
        </div>

        <!-- 生命周期编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">生命周期</span>
            <el-button size="small" text type="primary" @click="generateFromEncyclopedia" :loading="generatingStages">从百科生成</el-button>
            <el-button size="small" text type="primary" @click="addStage">+ 添加阶段</el-button>
          </div>
          <div v-if="editForm.life_stages.length === 0" style="color: #999; font-size: 13px;">暂无阶段，点击上方按钮添加</div>
          <div v-for="(stage, idx) in editForm.life_stages" :key="idx" class="stage-edit-item">
            <div class="stage-edit-row">
              <el-input v-model="stage.name" placeholder="阶段名称" size="small" style="width: 180px;" />
              <el-input-number v-model="stage.year_start" :min="1000" :max="2100" size="small" style="width: 100px;" />
              <span>~</span>
              <el-input-number v-model="stage.year_end" :min="1000" :max="2100" size="small" style="width: 100px;" />
              <el-input-number v-model="stage.weight" :min="0" :max="10" :step="0.5" :precision="1" size="small" style="width: 100px;" placeholder="权重" />
              <el-input-number v-model="stage.mood_offset" :min="-2" :max="2" :step="0.1" :precision="1" size="small" style="width: 100px;" placeholder="偏移" />
              <el-button size="small" text type="danger" @click="removeStage(idx)">删除</el-button>
            </div>
            <el-input v-model="stage.description" placeholder="阶段描述（可选）" size="small" style="margin-top: 6px;" />
          </div>
        </div>

        <!-- 情感提示词编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">情感倾向说明（LLM 注入）</span>
          </div>
          <el-input v-model="editForm.sentiment_note" type="textarea" :rows="3" placeholder="用于注入 LLM prompt 的画家情感特征描述" />
        </div>

        <!-- 主题提示词编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">主题倾向说明（LLM 注入）</span>
          </div>
          <el-input v-model="editForm.theme_note" type="textarea" :rows="3" placeholder="用于注入 LLM prompt 的画家主题倾向描述" />
        </div>

        <!-- 主题例外编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">主题情感例外</span>
            <el-button size="small" text type="primary" @click="addThemeException">+ 添加</el-button>
          </div>
          <div v-for="(exc, idx) in editThemeExceptions" :key="idx" class="exception-edit-item">
            <el-select v-model="exc.theme_code" size="small" style="width: 140px;" placeholder="主题">
              <el-option v-for="t in THEMES_LIST" :key="t.code" :label="t.name" :value="t.code" />
            </el-select>
            <el-input v-model="exc.keywords_str" size="small" placeholder="触发词（逗号分隔）" style="flex: 1;" />
            <el-select v-model="exc.override_to" size="small" style="width: 110px;">
              <el-option label="→ negative" value="negative" />
              <el-option label="→ positive" value="positive" />
              <el-option label="→ neutral" value="neutral" />
            </el-select>
            <el-button size="small" text type="danger" @click="removeThemeException(idx)">删除</el-button>
          </div>
          <div v-if="editThemeExceptions.length === 0" style="color: #999; font-size: 13px;">暂无例外规则</div>
        </div>

        <!-- 预期主题分布编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">预期主题分布（偏差检测）</span>
          </div>
          <div class="dist-edit-grid">
            <div v-for="t in THEMES_LIST" :key="t.code" class="dist-edit-item">
              <span class="dist-theme">{{ t.name }}</span>
              <el-input-number v-model="editForm.expected_theme_distribution[t.name][0]" :min="0" :max="100" size="small" style="width: 70px;" />
              <span>~</span>
              <el-input-number v-model="editForm.expected_theme_distribution[t.name][1]" :min="0" :max="100" size="small" style="width: 70px;" />
              <span style="font-size: 12px; color: #999;">%</span>
            </div>
          </div>
        </div>

        <!-- 预期情感分布编辑 -->
        <div class="rule-section">
          <div class="section-header">
            <span class="section-title">预期情感分布（偏差检测）</span>
          </div>
          <el-form label-width="100px" size="small" inline>
            <el-form-item label="消极下限">
              <el-input-number v-model="editForm.expected_sentiment_distribution.negative_min" :min="0" :max="100" />
              <span style="margin-left: 4px;">%</span>
            </el-form-item>
            <el-form-item label="积极上限">
              <el-input-number v-model="editForm.expected_sentiment_distribution.positive_max" :min="0" :max="100" />
              <span style="margin-left: 4px;">%</span>
            </el-form-item>
            <el-form-item label="情感均值上限">
              <el-input-number v-model="editForm.expected_sentiment_distribution.emotion_mean_max" :min="-2" :max="2" :step="0.1" :precision="1" />
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>

    <!-- 导入规则对话框 -->
    <el-dialog v-model="showImportDialog" title="导入画家规则" width="600px">
      <div style="margin-bottom: 12px; font-size: 13px; color: #666;">
        粘贴 JSON 格式的画家规则，或从导出的文件中复制。格式参考：
        <el-button size="small" text type="primary" @click="copyTemplate">复制模板</el-button>
      </div>
      <el-input v-model="importJson" type="textarea" :rows="16" placeholder='粘贴 JSON...' style="font-family: monospace; font-size: 12px;" />
      <div v-if="importError" style="color: #c45a3c; font-size: 12px; margin-top: 8px;">{{ importError }}</div>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="handleImport" :loading="importing">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh, Edit, Plus, Download, Upload } from '@element-plus/icons-vue'
import { artistRulesApi } from '../api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const THEMES_LIST = [
  { code: 1, name: '身世自况' },
  { code: 2, name: '咏物寄兴' },
  { code: 3, name: '画理自叙' },
  { code: 4, name: '时事讽喻' },
  { code: 5, name: '吉语祥瑞' },
  { code: 6, name: '交游赠答' },
]

const props = defineProps({
  artist: { type: String, default: '李鱓' }
})

const selectedArtist = ref(props.artist)
const loading = ref(false)
const saving = ref(false)
const aiDiscoverLoading = ref(false)
const currentRule = ref(null)
const error = ref('')
const artistList = ref([])

// Edit state
const editing = ref(false)
const creating = ref(false)
const editForm = ref(null)
const editThemeExceptions = ref([])
const generatingStages = ref(false)
const showImportDialog = ref(false)
const importJson = ref('')
const importError = ref('')
const importing = ref(false)

// ── View computed ──
const lifeStages = computed(() => {
  if (!currentRule.value) return []
  const stages = currentRule.value.life_stages
  return Array.isArray(stages) ? stages : []
})
const lifeStageCount = computed(() => lifeStages.value.length)

const themeExceptions = computed(() => {
  if (!currentRule.value) return {}
  const exc = currentRule.value.theme_exceptions
  return typeof exc === 'object' && exc !== null ? exc : {}
})
const themeExceptionCount = computed(() => Object.keys(themeExceptions.value).length)

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
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
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
  } catch (e) {
    if (e.response?.status === 404) {
      currentRule.value = null
      error.value = `画家「${selectedArtist.value}」尚无规则数据，可点击「AI 规则发现」创建`
    } else {
      error.value = '加载规则失败: ' + (e.message || e)
    }
  } finally {
    loading.value = false
  }
}

// ── Edit mode ──
function makeDefaultForm() {
  const themeDist = {}
  for (const t of THEMES_LIST) {
    themeDist[t.name] = [5, 15]
  }
  return {
    artist_name: selectedArtist.value || '',
    emotion_baseline: 0.0,
    life_stages: [],
    sentiment_note: '',
    theme_note: '',
    expected_theme_distribution: themeDist,
    expected_sentiment_distribution: {
      negative_min: 30,
      positive_max: 45,
      emotion_mean_max: 0.0,
    },
    rules_version: '5.7',
  }
}

function startEdit() {
  const r = currentRule.value
  editForm.value = {
    artist_name: r.artist_name,
    emotion_baseline: r.emotion_baseline ?? 0,
    life_stages: JSON.parse(JSON.stringify(r.life_stages || [])),
    sentiment_note: r.sentiment_note || '',
    theme_note: r.theme_note || '',
    expected_theme_distribution: JSON.parse(JSON.stringify(r.expected_theme_distribution || {})),
    expected_sentiment_distribution: JSON.parse(JSON.stringify(r.expected_sentiment_distribution || {})),
    rules_version: r.rules_version || '5.7',
  }
  // Ensure all 6 themes exist in distribution
  for (const t of THEMES_LIST) {
    if (!editForm.value.expected_theme_distribution[t.name]) {
      editForm.value.expected_theme_distribution[t.name] = [5, 15]
    }
  }
  // Parse theme exceptions
  const exc = r.theme_exceptions || {}
  editThemeExceptions.value = Object.entries(exc).map(([code, val]) => ({
    theme_code: Number(code),
    keywords_str: (val.override_if_contains || []).join(', '),
    override_to: val.override_to || 'negative',
  }))
  creating.value = false
  editing.value = true
}

function startCreate() {
  editForm.value = makeDefaultForm()
  editThemeExceptions.value = []
  creating.value = true
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  creating.value = false
  editForm.value = null
  editThemeExceptions.value = []
}

// ── Stage helpers ──
function addStage() {
  editForm.value.life_stages.push({
    name: '', year_start: 1800, year_end: 1850,
    weight: 1.0, mood_offset: 0.0, description: ''
  })
}

function removeStage(idx) {
  editForm.value.life_stages.splice(idx, 1)
}

async function generateFromEncyclopedia() {
  const name = editForm.value.artist_name
  if (!name) { ElMessage.warning('请先输入画家名称'); return }
  generatingStages.value = true
  try {
    const res = await artistRulesApi.generateLifeStages(name)
    if (res.success && res.stages) {
      editForm.value.life_stages = res.stages
      ElMessage.success(`已从百科生成 ${res.stages.length} 个阶段`)
    } else {
      ElMessage.error(res.message || '生成失败')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '生成失败'
    ElMessage.error(msg)
  } finally {
    generatingStages.value = false
  }
}

// ── Theme exception helpers ──
function addThemeException() {
  editThemeExceptions.value.push({
    theme_code: 1, keywords_str: '', override_to: 'negative'
  })
}

function removeThemeException(idx) {
  editThemeExceptions.value.splice(idx, 1)
}

// ── Save ──
async function saveRules() {
  const form = editForm.value
  if (!form) return
  if (creating.value && !form.artist_name) {
    ElMessage.warning('请输入画家名称')
    return
  }

  saving.value = true
  try {
    // Build theme_exceptions from edit format
    const themeExceptions = {}
    for (const exc of editThemeExceptions.value) {
      const kw = exc.keywords_str.split(/[,，]/).map(s => s.trim()).filter(Boolean)
      if (kw.length > 0) {
        themeExceptions[String(exc.theme_code)] = {
          override_if_contains: kw,
          override_to: exc.override_to,
        }
      }
    }

    const payload = {
      artist_name: form.artist_name,
      emotion_baseline: form.emotion_baseline,
      life_stages: form.life_stages,
      sentiment_note: form.sentiment_note,
      theme_note: form.theme_note,
      theme_exceptions: themeExceptions,
      expected_theme_distribution: form.expected_theme_distribution,
      expected_sentiment_distribution: form.expected_sentiment_distribution,
      rules_version: form.rules_version,
    }

    if (creating.value) {
      await artistRulesApi.create(payload)
      ElMessage.success('画家规则创建成功')
    } else {
      await artistRulesApi.update(currentRule.value.id, payload)
      ElMessage.success('画家规则保存成功')
    }

    editing.value = false
    creating.value = false
    await loadRules()
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '保存失败'
    ElMessage.error('保存失败: ' + msg)
  } finally {
    saving.value = false
  }
}

// ── AI Discover ──
async function handleAiDiscover() {
  if (!selectedArtist.value) return
  aiDiscoverLoading.value = true
  try {
    const res = await artistRulesApi.aiDiscover(selectedArtist.value)
    if (res.success) {
      ElMessage.success(res.message || 'AI 规则发现完成')
      await loadRules()
    } else {
      ElMessage.error(res.message || 'AI 规则发现失败')
    }
  } catch (e) {
    ElMessage.error('AI 规则发现失败: ' + (e.message || e))
  } finally {
    aiDiscoverLoading.value = false
  }
}

// ── Export / Import ──
function exportRule() {
  if (!currentRule.value) return
  const data = {
    artist_name: currentRule.value.artist_name,
    emotion_baseline: currentRule.value.emotion_baseline,
    life_stages: currentRule.value.life_stages || [],
    sentiment_note: currentRule.value.sentiment_note || '',
    theme_note: currentRule.value.theme_note || '',
    theme_exceptions: currentRule.value.theme_exceptions || {},
    expected_theme_distribution: currentRule.value.expected_theme_distribution || {},
    expected_sentiment_distribution: currentRule.value.expected_sentiment_distribution || {},
    rules_version: currentRule.value.rules_version || '5.7',
  }
  const json = JSON.stringify(data, null, 2)
  navigator.clipboard.writeText(json).then(() => {
    ElMessage.success('规则已复制到剪贴板，可直接粘贴给 AI')
  }).catch(() => {
    // Fallback: copy via textarea
    const ta = document.createElement('textarea')
    ta.value = json; document.body.appendChild(ta)
    ta.select(); document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success('规则已复制到剪贴板')
  })
}

function copyTemplate() {
  const template = {
    artist_name: "画家名称",
    emotion_baseline: 0.0,
    life_stages: [
      { name: "早期", year_start: 1700, year_end: 1730, weight: 1.0, mood_offset: 0.0, description: "描述" },
      { name: "中期", year_start: 1731, year_end: 1760, weight: 1.5, mood_offset: -0.2, description: "描述" },
      { name: "晚期", year_start: 1761, year_end: 1790, weight: 2.0, mood_offset: -0.4, description: "描述" }
    ],
    sentiment_note: "该画家的情感特征描述（注入 LLM prompt）",
    theme_note: "该画家的主题倾向描述（注入 LLM prompt）",
    theme_exceptions: {},
    expected_theme_distribution: {
      "身世自况": [5, 15], "咏物寄兴": [35, 55], "画理自叙": [3, 10],
      "时事讽喻": [3, 10], "吉语祥瑞": [3, 10], "交游赠答": [3, 10]
    },
    expected_sentiment_distribution: { negative_min: 30, positive_max: 45, emotion_mean_max: 0.0 },
    rules_version: "5.7"
  }
  importJson.value = JSON.stringify(template, null, 2)
  importError.value = ''
}

async function handleImport() {
  importError.value = ''
  if (!importJson.value.trim()) {
    importError.value = '请粘贴 JSON 数据'
    return
  }
  let data
  try {
    data = JSON.parse(importJson.value)
  } catch (e) {
    importError.value = 'JSON 格式错误: ' + e.message
    return
  }
  if (!data.artist_name) {
    importError.value = '缺少 artist_name 字段'
    return
  }

  importing.value = true
  try {
    // Check if rule already exists
    const existing = await artistRulesApi.getByName(data.artist_name)
    if (existing.rule) {
      // Update existing
      await artistRulesApi.update(existing.rule.id, data)
      ElMessage.success(`画家「${data.artist_name}」规则已更新`)
    } else {
      // Create new
      await artistRulesApi.create(data)
      ElMessage.success(`画家「${data.artist_name}」规则已创建`)
    }
    showImportDialog.value = false
    importJson.value = ''
    selectedArtist.value = data.artist_name
    await loadRules()
  } catch (e) {
    importError.value = '导入失败: ' + (e.response?.data?.detail || e.message || e)
  } finally {
    importing.value = false
  }
}

function refreshRules() {
  loadRules()
}

onMounted(() => {
  loadArtistList()
  loadRules()
})
</script>

<style scoped>
.artist-rules-manager { padding: 0; }
.toolbar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
.rules-content { min-height: 300px; }
.empty-state { padding: 60px 0; }

.rule-section {
  background: white;
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
}
.section-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.section-title { font-size: 14px; font-weight: 700; color: #333; }

.rule-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.rule-item { text-align: center; }
.rule-label { font-size: 12px; color: #999; display: block; margin-bottom: 4px; }
.rule-value { font-size: 16px; font-weight: 600; color: #333; }
.rule-value.negative { color: #c96442; }
.rule-value.positive { color: #4e8cff; }
.text-sm { font-size: 13px; font-weight: 400; }

.rule-text { font-size: 13px; color: #555; line-height: 1.7; }

.stage-list { display: flex; flex-direction: column; gap: 8px; }
.stage-item { background: #faf9f7; border-radius: 8px; padding: 10px 14px; border: 1px solid #e8e4da; }
.stage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.stage-name { font-size: 14px; font-weight: 600; color: #333; }
.stage-years { font-size: 12px; color: #999; font-family: monospace; }
.stage-detail { font-size: 12px; color: #888; display: flex; gap: 16px; }
.stage-desc { font-size: 12px; color: #666; margin-top: 4px; }

.exception-list { display: flex; flex-direction: column; gap: 6px; }
.exception-item { font-size: 13px; color: #555; display: flex; gap: 12px; align-items: baseline; }
.exception-theme { font-weight: 600; color: #c96442; }

.distribution-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.dist-item { text-align: center; padding: 6px; background: #faf9f7; border-radius: 6px; }
.dist-theme { font-size: 12px; color: #666; display: block; margin-bottom: 2px; }
.dist-range { font-size: 13px; font-weight: 600; color: #333; font-family: monospace; }

/* Edit mode styles */
.stage-edit-item {
  background: #faf9f7;
  border: 1px solid #e8e4da;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 8px;
}
.stage-edit-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.exception-edit-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dist-edit-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.dist-edit-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}
.dist-edit-item .dist-theme {
  width: 70px;
  font-size: 13px;
  color: #555;
  flex-shrink: 0;
}
</style>
