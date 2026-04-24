<template>
  <!-- 词云卡片 -->
  <div class="friend-circle-module" style="flex: 1;">
    <el-card shadow="hover" class="friend-circle-card">
      <template #header>
        <div class="module-header">
          <h3 class="module-title">云关键词</h3>
          <div class="header-actions">
            <el-select v-model="selectedAuthor" size="small" @change="onAuthorChange" style="width: 100px;">
              <el-option label="全部" value="all"></el-option>
              <el-option
                v-for="artist in wordCloudArtists"
                :key="artist.name"
                :label="artist.name"
                :value="artist.name"
              />
            </el-select>
          </div>
        </div>
      </template>
      <div class="word-cloud-content">
        <div class="word-cloud-container">
          <div v-if="wordCloudLoading" class="word-cloud-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>生成词云中...</p>
          </div>
          <div v-else-if="wordCloudData.length === 0" class="word-cloud-empty">
            <el-icon size="48"><Document /></el-icon>
            <p>暂无关键词数据</p>
            <p class="empty-tip">上传画作后将自动生成词云</p>
          </div>
          <div v-else class="word-cloud-items">
            <div
              v-for="(item, index) in wordCloudData"
              :key="index"
              class="word-cloud-item"
              :style="{
                fontSize: `${wordFontSize(item.value)}px`,
                color: wordCloudColors[index % wordCloudColors.length]
              }"
              @mouseover="handleWordMouseOver"
              @mouseout="handleWordMouseOut"
              @click="showKeywordWorks(item.word)"
              :title="`出现次数: ${item.value}次`"
            >
              {{ item.word }}
            </div>
          </div>
        </div>
        <div class="word-cloud-stats">
          <div class="stats-row">
            <span class="stats-label">关键词统计：</span>
            <span class="stats-value">共 {{ totalKeywords }} 个关键词 | 总引用次数：{{ totalCount }} 次</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">提示：</span>
            <span class="stats-value">点击关键词可查看包含该词的画作列表</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 关键词画作列表对话框 -->
    <el-dialog
      v-model="keywordWorksDialogVisible"
      :title="`包含关键词 '${currentKeyword}' 的画作`"
      width="80%"
      :close-on-click-modal="true"
      class="keyword-works-dialog"
    >
      <div class="keyword-works-content">
        <div v-if="keywordWorksLoading" class="keyword-works-loading">
          <el-icon class="is-loading" size="32"><Loading /></el-icon>
          <p>正在加载画作...</p>
        </div>
        <div v-else-if="keywordWorks.length === 0" class="keyword-works-empty">
          <el-icon size="64" color="#dcdfe6"><Picture /></el-icon>
          <p>未找到包含关键词「{{ currentKeyword }}」的画作</p>
        </div>
        <el-table v-else :data="keywordWorks" style="width: 100%">
          <el-table-column label="图片" width="100">
            <template #default="scope">
              <img v-if="scope.row.thumbnailUrl || scope.row.url" :src="scope.row.thumbnailUrl || scope.row.url" class="history-thumb" @click="$emit('preview-image', scope.row)" />
              <div v-else class="history-thumb-placeholder">
                <el-icon size="24"><Picture /></el-icon>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="200">
            <template #default="scope">
              {{ scope.row.title || '未命名' }}
            </template>
          </el-table-column>
          <el-table-column prop="artist" label="作者" width="120">
            <template #default="scope">
              {{ scope.row.artist || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="题跋占比" width="100">
            <template #default="scope">
              <el-tag v-if="scope.row.inscriptionPercent !== undefined" type="danger">
                {{ scope.row.inscriptionPercent }}%
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="绘画占比" width="100">
            <template #default="scope">
              <el-tag v-if="scope.row.paintingPercent !== undefined" type="success">
                {{ scope.row.paintingPercent }}%
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { Loading, Document, Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { tubiApi } from '../api'
import { WORD_CLOUD_COLORS, WORD_CLOUD_FONT } from './constants'

// Props
const props = defineProps({
  /** 历史记录列表，用于关键词筛选 */
  historyList: {
    type: Array,
    default: () => []
  }
})

// Emits
defineEmits(['preview-image', 'load-history-item'])

// 词云相关数据
const wordCloudLoading = ref(false)
const wordCloudData = ref([])
const totalKeywords = ref(0)
const totalCount = ref(0)
const selectedAuthor = ref('all')
const wordCloudArtists = ref([])
const wordCloudArtistAliases = computed(() => {
  const a = wordCloudArtists.value.find(x => x.name === selectedAuthor.value)
  return a?.aliases || []
})

// 关键词画作列表
const keywordWorksDialogVisible = ref(false)
const currentKeyword = ref('')
const keywordWorks = ref([])
const keywordWorksLoading = ref(false)

// 词云颜色（引用常量）
const wordCloudColors = WORD_CLOUD_COLORS

// 计算最大词频
const maxWordCount = computed(() => {
  if (wordCloudData.value.length === 0) return 1
  return Math.max(...wordCloudData.value.map(item => item.value))
})

function wordFontSize(value) {
  const { MIN: minFont, MAX: maxFont } = WORD_CLOUD_FONT
  const v = Number(value)
  if (!Number.isFinite(v) || v <= 0) return minFont
  const max = Number(maxWordCount.value) || 0
  if (max <= 0) return minFont
  const ratio = Math.log1p(v) / Math.log1p(max)
  const out = minFont + ratio * (maxFont - minFont)
  return Math.round(out)
}

async function loadWordCloudArtists() {
  try {
    const response = await tubiApi.getWordCloudArtists()
    if (response?.success) {
      wordCloudArtists.value = response.data || []
      if (selectedAuthor.value !== 'all' && !wordCloudArtists.value.some(x => x.name === selectedAuthor.value)) {
        selectedAuthor.value = 'all'
      }
      if (selectedAuthor.value === 'all' && wordCloudArtists.value.length > 0) {
        selectedAuthor.value = wordCloudArtists.value[0].name
      }
    }
  } catch (error) {
    console.error('加载词云作者失败:', error)
  }
}

async function generateWordCloud() {
  wordCloudLoading.value = true
  try {
    const response = await tubiApi.getWordCloud({
      artist: selectedAuthor.value,
      top_k: 40
    })

    if (!response?.success) {
      wordCloudData.value = []
      totalKeywords.value = 0
      totalCount.value = 0
      return
    }

    const list = (response.data || []).map(item => ({
      word: item.word,
      value: item.count
    }))

    wordCloudData.value = list
    totalKeywords.value = response.total_keywords ?? list.length
    totalCount.value = response.total_count ?? list.reduce((sum, item) => sum + item.value, 0)

    await nextTick()
  } catch (error) {
    console.error('生成词云失败:', error)
    ElMessage.error('生成词云失败')
  } finally {
    wordCloudLoading.value = false
  }
}

function onAuthorChange(value) {
  selectedAuthor.value = value
  generateWordCloud()
}

/** 显示包含关键词的画作列表 */
function showKeywordWorks(keyword) {
  currentKeyword.value = keyword
  keywordWorksLoading.value = true

  nextTick(() => {
    try {
      const filteredWorks = props.historyList.filter(item => {
        if (selectedAuthor.value !== 'all') {
          const aliases = wordCloudArtistAliases.value || []
          if (aliases.length > 0) {
            if (!aliases.includes(item.artist)) return false
          } else {
            if (item.artist !== selectedAuthor.value) return false
          }
        }
        const titleMatch = item.title && item.title.includes(keyword)
        const noteMatch = item.analysisNote && item.analysisNote.includes(keyword)
        const notesMatch = item.notes && item.notes.includes(keyword)
        const inscriptionMatch = item.inscriptionContent && item.inscriptionContent.includes(keyword)
        return titleMatch || noteMatch || notesMatch || inscriptionMatch
      })

      keywordWorks.value = filteredWorks
      keywordWorksLoading.value = false
      keywordWorksDialogVisible.value = true
    } catch (error) {
      console.error('Error showing keyword works:', error)
      keywordWorksLoading.value = false
    }
  })
}

function handleWordMouseOver(event) {
  const element = event.target
  element.style.transform = 'scale(1.15)'
  element.style.backgroundColor = 'rgba(0, 0, 0, 0.08)'
  element.style.zIndex = '10'
}

function handleWordMouseOut(event) {
  const element = event.target
  element.style.transform = 'scale(1)'
  element.style.backgroundColor = 'transparent'
  element.style.zIndex = '1'
}

/** 刷新词云 */
async function refresh() {
  await loadWordCloudArtists()
  await generateWordCloud()
}

onMounted(() => {
  refresh()
})

// 暴露刷新方法供父组件调用
defineExpose({ refresh })
</script>

<style>
/* 模块标题样式 */
.module-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  height: 32px;
}

.module-header:not(:has(.el-button)) {
  justify-content: flex-start;
}

.module-header:has(.el-button) {
  justify-content: space-between;
}

.module-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 100%;
  flex: 1;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* 词云模块 */
.friend-circle-module {
  min-height: 450px;
}

.friend-circle-card {
  height: 100%;
  overflow: hidden;
  background-color: #FFFFFF;
  border-radius: 8px;
  padding: 16px;
}

.word-cloud-content {
  display: flex;
  flex-direction: column;
  height: calc(100% - 60px);
}

.word-cloud-container {
  flex: 1;
  min-height: 490px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background-color: #f8f9fa;
  border-radius: 8px;
  overflow: hidden;
}

.word-cloud-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #666;
}

.word-cloud-loading .el-icon {
  font-size: 32px;
}

.word-cloud-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #999;
  text-align: center;
}

.word-cloud-empty .empty-tip {
  font-size: 12px;
  color: #ccc;
  margin-top: 4px;
}

.word-cloud-items {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  padding: 20px;
  gap: 8px;
  width: 100%;
  min-height: 400px;
}

.word-cloud-item {
  font-weight: bold;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 2px;
  transition: all 0.2s ease;
  user-select: none;
}

.word-cloud-stats {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e9ecef;
  font-size: 14px;
}

.stats-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.stats-label {
  font-weight: 600;
  color: #333;
}

.stats-value {
  color: #666;
}

/* 关键词画作列表对话框样式 */
.keyword-works-dialog .el-dialog__body {
  padding: 20px;
}

.keyword-works-content {
  min-height: 300px;
}

.keyword-works-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.keyword-works-loading p {
  margin-top: 10px;
  color: #606266;
}

.keyword-works-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.keyword-works-empty p {
  margin-top: 10px;
  color: #909399;
}

.keyword-works-empty .el-icon {
  margin-bottom: 10px;
}

/* 历史缩略图样式（用于关键词画作对话框） */
.history-thumb {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid #e4e7ed;
  transition: all 0.3s ease;
}

.history-thumb:hover {
  border-color: #409EFF;
  transform: scale(1.05);
}

.history-thumb-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  border: 1px dashed #dcdfe6;
}
</style>
