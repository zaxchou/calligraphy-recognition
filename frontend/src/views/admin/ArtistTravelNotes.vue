<template>
  <div class="travel-notes-page">
    <div class="page-toolbar">
      <div class="toolbar-left">
        <h2 class="page-title">行旅编辑：{{ artistName }}</h2>
        <span v-if="travelData" class="meta-info">
          {{ travelData.locations?.length || 0 }}个城市 · {{ travelData.periods?.length || 0 }}个时期
          <template v-if="travelData.generated_at">
            · AI生成于 {{ formatDate(travelData.generated_at) }}
          </template>
        </span>
      </div>
      <div class="toolbar-actions">
        <el-button :loading="generating" type="warning" @click="generateAI" :disabled="!artistName">
          🤖 AI 一键生成
        </el-button>
        <el-button :loading="saving" type="primary" @click="save" :disabled="!editedJson || !artistName">
          保存
        </el-button>
        <el-button @click="resetEdit" :disabled="!hasChanges">撤销</el-button>
      </div>
    </div>

    <div v-if="loading" class="loading-box">
      <el-skeleton :rows="8" animated />
    </div>

    <template v-else>
      <div class="content-area">
        <!-- JSON 编辑器 -->
        <div class="editor-panel">
          <div class="panel-title">JSON 编辑器</div>
          <textarea
            v-model="editedJson"
            class="json-editor"
            spellcheck="false"
            @input="onEditChange"
          ></textarea>
          <div v-if="jsonError" class="json-error">{{ jsonError }}</div>
        </div>

        <!-- 预览 -->
        <div class="preview-panel">
          <div class="panel-title">预览</div>
          <div v-if="!previewData" class="preview-empty">
            {{ travelData ? 'JSON 格式错误，无法预览' : '暂无数据，点击"AI 一键生成"或手动粘贴 JSON' }}
          </div>
          <template v-else>
            <!-- 时期 -->
            <div class="preview-section">
              <div class="section-label">时期（{{ previewData.periods?.length || 0 }}）</div>
              <div v-for="p in previewData.periods" :key="p.id" class="preview-period">
                <span class="period-dot" :style="{ background: getPeriodColor(p.order) }"></span>
                <span class="period-label">{{ p.label }}</span>
                <span class="period-range">{{ (p.year_range || []).join('-') }}</span>
              </div>
            </div>
            <!-- 城市 -->
            <div class="preview-section">
              <div class="section-label">城市（{{ previewData.locations?.length || 0 }}）</div>
              <div v-for="loc in previewData.locations" :key="loc.name" class="preview-city">
                <div class="city-header">
                  <strong>{{ loc.name }}</strong>
                  <span class="city-coord">{{ loc.lat?.toFixed(2) }}, {{ loc.lng?.toFixed(2) }}</span>
                  <span class="city-count">{{ loc.painting_ids?.length || 0 }}幅画 · {{ loc.events?.length || 0 }}条记录</span>
                </div>
                <div class="city-summary" v-if="loc.summary">{{ loc.summary }}</div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const route = useRoute()
const artistName = ref('')
const loading = ref(true)
const saving = ref(false)
const generating = ref(false)
const travelData = ref(null)
const editedJson = ref('')
const originalJson = ref('')
const jsonError = ref('')

const PERIOD_COLORS = ['#a08060', '#c96442', '#5b7a8c', '#8b6d4b', '#6b8b5a', '#8b5a8c', '#4a7a8c', '#c9a06c']

const hasChanges = computed(() => editedJson.value !== originalJson.value)

const previewData = computed(() => {
  if (!editedJson.value) return null
  try {
    return JSON.parse(editedJson.value)
  } catch {
    return null
  }
})

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function getPeriodColor(order: number) {
  return PERIOD_COLORS[(order || 0) % PERIOD_COLORS.length]
}

function onEditChange() {
  jsonError.value = ''
  if (!editedJson.value.trim()) return
  try { JSON.parse(editedJson.value) } catch (e) {
    jsonError.value = 'JSON 格式错误: ' + e.message
  }
}

function resetEdit() {
  editedJson.value = originalJson.value
  jsonError.value = ''
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.get(`/artists/by-name/${encodeURIComponent(artistName.value)}`)
    const artist = res.artist || res
    const raw = artist.travel_notes
    if (raw) {
      travelData.value = typeof raw === 'string' ? JSON.parse(raw) : raw
      const formatted = JSON.stringify(travelData.value, null, 2)
      editedJson.value = formatted
      originalJson.value = formatted
    } else {
      travelData.value = null
      editedJson.value = ''
      originalJson.value = ''
    }
  } catch (e) {
    ElMessage.error('加载数据失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!editedJson.value) return
  try {
    const parsed = JSON.parse(editedJson.value)
    saving.value = true
    await api.put(`/artists/by-name/${encodeURIComponent(artistName.value)}/travel-notes`, {
      travel_notes: JSON.stringify(parsed),
    })
    originalJson.value = editedJson.value
    travelData.value = parsed
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function generateAI() {
  generating.value = true
  try {
    const res = await api.post(`/artists/by-name/${encodeURIComponent(artistName.value)}/travel-notes/generate`)
    if (res.success && res.travel_notes) {
      travelData.value = res.travel_notes
      const formatted = JSON.stringify(res.travel_notes, null, 2)
      editedJson.value = formatted
      originalJson.value = formatted
      ElMessage.success(res.message || `AI已生成${res.travel_notes.locations?.length || 0}个城市的行旅数据`)
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '未知错误'
    ElMessage.error('AI生成失败: ' + msg)
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  const nameFromQuery = route.query.artist
  if (nameFromQuery) {
    artistName.value = decodeURIComponent(String(nameFromQuery))
  }
  // Also try URL path or lib context
  if (!artistName.value) {
    artistName.value = route.params.name as string || ''
  }
  if (artistName.value) {
    loadData()
  } else {
    loading.value = false
  }
})

watch(() => route.query.artist, (val) => {
  if (val && decodeURIComponent(String(val)) !== artistName.value) {
    artistName.value = decodeURIComponent(String(val))
    loadData()
  }
})
</script>

<style scoped>
.travel-notes-page {
  padding: 20px 24px;
  max-width: 1400px;
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-shrink: 0;
}
.toolbar-left { display: flex; align-items: baseline; gap: 16px; }
.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.1rem;
  color: #2c2416;
  margin: 0;
}
.meta-info { font-size: 0.82rem; color: #8b7d6b; }
.toolbar-actions { display: flex; gap: 8px; }

.loading-box { padding: 40px 0; }

.content-area {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.panel-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #8b7d6b;
  margin-bottom: 8px;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}
.json-editor {
  flex: 1;
  width: 100%;
  min-height: 300px;
  padding: 16px;
  border: 1px solid #e0dccf;
  border-radius: 8px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  color: #3a3222;
  background: #fdfcf8;
  resize: none;
  outline: none;
  tab-size: 2;
}
.json-editor:focus { border-color: #c9a96e; }
.json-error {
  margin-top: 6px;
  font-size: 0.78rem;
  color: #e74c3c;
  flex-shrink: 0;
}

.preview-panel {
  width: 380px;
  flex-shrink: 0;
  overflow-y: auto;
  border: 1px solid #e8e4d8;
  border-radius: 8px;
  padding: 16px;
  background: #fdfcf8;
}
.preview-empty {
  color: #b8a990;
  font-size: 0.84rem;
  text-align: center;
  padding: 40px 0;
}

.preview-section { margin-bottom: 20px; }
.section-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #8b7d6b;
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}
.preview-period {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.84rem;
}
.period-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.period-range { color: #b8a990; font-size: 0.78rem; margin-left: auto; }

.preview-city {
  padding: 10px 0;
  border-bottom: 1px solid #f0ece4;
}
.preview-city:last-child { border-bottom: none; }
.city-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 0.84rem;
}
.city-coord { font-size: 0.72rem; color: #b8a990; font-family: monospace; }
.city-count { font-size: 0.72rem; color: #8b7d6b; margin-left: auto; }
.city-summary {
  margin-top: 4px;
  font-size: 0.78rem;
  color: #5e5d59;
  line-height: 1.6;
}
</style>
