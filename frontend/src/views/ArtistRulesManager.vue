<template>
  <div class="artist-rules-manager">
    <div class="toolbar">
      <el-select v-model="selectedArtist" size="small" placeholder="选择画家" @change="loadRules" style="width: 160px;">
        <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
      </el-select>
      <el-button size="small" type="primary" plain @click="handleAiDiscover" :loading="aiDiscoverLoading" :disabled="!selectedArtist">
        <el-icon><MagicStick /></el-icon>AI 规则发现
      </el-button>
      <el-button size="small" @click="refreshRules">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <div v-loading="loading" class="rules-content">
      <div v-if="!selectedArtist" class="empty-state">
        <el-empty description="请选择画家查看规则" />
      </div>
      <div v-else-if="error" class="empty-state">
        <el-empty :description="error" />
      </div>
      <div v-else-if="currentRule" class="rule-detail">
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh } from '@element-plus/icons-vue'
import { artistRulesApi } from '../api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const props = defineProps({
  artist: { type: String, default: '李鱓' }
})

const selectedArtist = ref(props.artist)
const loading = ref(false)
const aiDiscoverLoading = ref(false)
const currentRule = ref(null)
const error = ref('')
const artistList = ref([])

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
    loadRules()
  }
})

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
</style>
