<template>
  <div class="recognize-page">
    <h1 class="page-title">书法字体识别</h1>
    <p class="page-subtitle">使用 SiliconFlow AI + Kimi-K2.5 模型</p>
    
    <div class="content-wrapper">
      <!-- 左侧：上传区域 -->
      <div class="upload-section">
        <el-card shadow="hover" class="upload-card">
          <template #header>
            <div class="card-header">
              <span>上传书法图片</span>
              <el-button 
                type="info" 
                size="small" 
                @click="showHistoryDialog"
                :icon="Clock"
              >
                历史记录
              </el-button>
            </div>
          </template>
          
          <el-upload
            class="upload-area"
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="false"
            accept="image/*"
          >
            <el-icon class="el-icon--upload" size="60"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽图片到此处或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 JPG、PNG、BMP 格式，建议上传清晰的单字书法图片
              </div>
            </template>
          </el-upload>

          <!-- 预览区域 -->
          <div v-if="previewImage" class="preview-area">
            <h4>预览</h4>
            <img :src="previewImage" alt="预览" class="preview-image">
            <el-button 
              type="primary" 
              @click="startRecognize"
              :loading="isRecognizing"
              :disabled="isRecognizing"
              class="recognize-btn"
            >
              <el-icon v-if="!isRecognizing"><Search /></el-icon>
              {{ isRecognizing ? 'AI分析中...' : '开始识别' }}
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- 右侧：结果区域 -->
      <div class="result-section">
        <el-card shadow="hover" class="result-card" v-loading="isRecognizing" :element-loading-text="loadingText">
          <template #header>
            <div class="card-header">
              <span>识别结果</span>
              <el-tag v-if="result" :type="result.is_confident ? 'success' : 'warning'">
                {{ result.is_confident ? '高置信度' : '低置信度' }}
              </el-tag>
            </div>
          </template>

          <!-- AI分析中状态 -->
          <div v-if="isRecognizing" class="analyzing-status">
            <el-progress 
              :percentage="progressPercentage" 
              :stroke-width="20"
              :status="progressStatus"
              striped
              striped-flow
              :duration="10"
            />
            <p class="analyzing-text">{{ analyzingStep }}</p>
            <p class="analyzing-subtext">Kimi-K2.5 正在分析图片...</p>
          </div>

          <!-- 无结果状态 -->
          <div v-else-if="!result" class="empty-result">
            <el-icon size="80" color="#dcdfe6"><Document /></el-icon>
            <p>请上传图片进行识别</p>
          </div>

          <!-- 识别结果 -->
          <div v-else class="result-content">
            <!-- 上传的原图 -->
            <div class="original-image-section" v-if="result.uploaded_image_url">
              <h3>上传的原图</h3>
              <div class="original-image-wrapper">
                <img :src="result.uploaded_image_url" alt="上传的原图" class="original-image">
              </div>
            </div>

            <el-divider />

            <!-- 最佳匹配 -->
            <div class="best-match">
              <h3>最佳匹配</h3>
              <div class="match-info">
                <div class="character-display">
                  <span class="character">{{ result.recognized_character }}</span>
                </div>
                <div class="similarity-circle">
                  <el-progress
                    type="circle"
                    :percentage="Math.round(result.similarity || 0)"
                    :color="similarityColor"
                    :stroke-width="12"
                    :width="120"
                  />
                  <span class="similarity-label">相似度</span>
                </div>
              </div>
              
              <!-- AI分析理由 -->
              <div v-if="result.ai_reason" class="ai-reason">
                <el-alert
                  :title="'AI分析: ' + result.ai_reason"
                  type="info"
                  :closable="false"
                  show-icon
                />
              </div>
              
              <!-- 碑帖信息 -->
              <div v-if="result.best_match?.stele" class="stele-info">
                <h4>出自碑帖</h4>
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="碑帖名称">
                    {{ result.best_match.stele.name }}
                  </el-descriptions-item>
                  <el-descriptions-item label="书法家">
                    {{ result.best_match.stele.calligrapher }}
                  </el-descriptions-item>
                  <el-descriptions-item label="朝代">
                    {{ result.best_match.stele.dynasty }}
                  </el-descriptions-item>
                  <el-descriptions-item label="字体风格">
                    <el-tag>{{ result.best_match.stele.style }}</el-tag>
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </div>

            <el-divider />

            <!-- 其他候选 - 只显示相似度 >= 40% 的 -->
            <div class="other-matches" v-if="filteredTopMatches.length > 0">
              <h4>其他候选</h4>
              <el-table :data="filteredTopMatches" style="width: 100%">
                <el-table-column prop="rank" label="排名" width="80">
                  <template #default="scope">
                    <el-tag size="small">{{ scope.row.rank }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="character" label="字形" width="100">
                  <template #default="scope">
                    <span class="table-character">{{ scope.row.character }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="similarity" label="相似度">
                  <template #default="scope">
                    <el-progress 
                      :percentage="Math.round(scope.row.similarity)" 
                      :color="getSimilarityColor(scope.row.similarity)"
                    />
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- 处理信息 -->
            <div class="process-info">
              <el-tag size="small" type="info">
                处理时间: {{ result.processing_time_ms }}ms
              </el-tag>
              <el-tag v-if="result.recognition_method" size="small" :type="result.recognition_method === 'ai_primary' ? 'success' : 'warning'">
                {{ result.recognition_method === 'ai_primary' ? 'AI识别' : '特征匹配' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 历史记录对话框 -->
    <el-dialog
      v-model="historyDialogVisible"
      title="识别历史记录"
      width="900px"
      :close-on-click-modal="false"
    >
      <div class="history-content">
        <el-table :data="historyList" style="width: 100%" v-loading="historyLoading">
          <el-table-column label="上传图片" width="120">
            <template #default="scope">
              <img 
                :src="getImageUrl(scope.row.uploaded_image_path)" 
                class="history-image"
                @click="previewHistoryImage(scope.row)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="recognized_character" label="识别结果" width="100">
            <template #default="scope">
              <span class="history-character">{{ scope.row.recognized_character }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="similarity_score" label="相似度" width="120">
            <template #default="scope">
              <el-progress 
                :percentage="Math.round(scope.row.similarity_score || 0)" 
                :color="getSimilarityColor(scope.row.similarity_score)"
                :stroke-width="8"
              />
            </template>
          </el-table-column>
          <el-table-column prop="processing_time_ms" label="耗时" width="100">
            <template #default="scope">
              {{ scope.row.processing_time_ms }}ms
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="识别时间" width="180">
            <template #default="scope">
              {{ formatDate(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="scope">
              <el-button 
                type="primary" 
                size="small" 
                @click="loadHistoryResult(scope.row)"
              >
                查看
              </el-button>
              <el-button 
                type="danger" 
                size="small" 
                @click="deleteHistoryItem(scope.row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <div class="history-pagination">
          <el-pagination
            v-model:current-page="historyPage"
            v-model:page-size="historyPageSize"
            :page-sizes="[10, 20, 50]"
            :total="historyTotal"
            layout="total, sizes, prev, pager, next"
            @size-change="loadHistory"
            @current-change="loadHistory"
          />
        </div>
      </div>
    </el-dialog>

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="previewDialogVisible"
      title="图片预览"
      width="600px"
      :close-on-click-modal="true"
    >
      <img :src="previewImageUrl" style="width: 100%;" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { UploadFilled, Search, Document, Clock } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { recognitionApi } from '../api'

const previewImage = ref('')
const currentFile = ref(null)
const isRecognizing = ref(false)
const result = ref(null)
const loadingText = ref('正在识别...')

// 进度条相关
const progressPercentage = ref(0)
const progressStatus = ref('')
const analyzingStep = ref('准备分析...')

// 历史记录相关
const historyDialogVisible = ref(false)
const historyList = ref([])
const historyLoading = ref(false)
const historyPage = ref(1)
const historyPageSize = ref(10)

// 过滤后的候选列表（只显示相似度 >= 40% 且不是最佳匹配的）
const filteredTopMatches = computed(() => {
  if (!result.value?.top_matches) return []
  // 过滤掉第一个（最佳匹配）和相似度低于40%的
  return result.value.top_matches
    .slice(1) // 去掉第一个（最佳匹配）
    .filter(match => match.similarity >= 40) // 只保留相似度 >= 40% 的
})
const historyTotal = ref(0)

// 图片预览
const previewDialogVisible = ref(false)
const previewImageUrl = ref('')

// 相似度颜色
const similarityColor = computed(() => {
  if (!result.value) return '#409EFF'
  const sim = result.value.similarity
  if (sim >= 80) return '#67C23A'
  if (sim >= 60) return '#E6A23C'
  return '#F56C6C'
})

const getSimilarityColor = (similarity) => {
  if (!similarity) return '#F56C6C'
  if (similarity >= 80) return '#67C23A'
  if (similarity >= 60) return '#E6A23C'
  return '#F56C6C'
}

// 模拟进度条
const startProgress = () => {
  progressPercentage.value = 0
  progressStatus.value = ''
  analyzingStep.value = '正在上传图片...'
  
  const steps = [
    { percent: 15, text: '正在预处理图像...' },
    { percent: 30, text: '正在提取特征...' },
    { percent: 45, text: '正在匹配候选字形...' },
    { percent: 60, text: 'AI正在分析图片...' },
    { percent: 80, text: 'AI正在识别字体...' },
    { percent: 95, text: '正在生成结果...' }
  ]
  
  let stepIndex = 0
  const interval = setInterval(() => {
    if (!isRecognizing.value) {
      clearInterval(interval)
      progressPercentage.value = 100
      return
    }
    
    if (stepIndex < steps.length) {
      const step = steps[stepIndex]
      progressPercentage.value = step.percent
      analyzingStep.value = step.text
      stepIndex++
    }
  }, 1500)
  
  return interval
}

// 处理文件选择
const handleFileChange = (file) => {
  if (!file) return
  
  const isImage = file.raw.type.startsWith('image/')
  if (!isImage) {
    ElMessage.error('请上传图片文件')
    return
  }
  
  const isLt10M = file.raw.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('图片大小不能超过10MB')
    return
  }
  
  currentFile.value = file.raw
  
  const reader = new FileReader()
  reader.onload = (e) => {
    previewImage.value = e.target.result
  }
  reader.readAsDataURL(file.raw)
  
  result.value = null
}

// 开始识别
const startRecognize = async () => {
  if (!currentFile.value) {
    ElMessage.warning('请先上传图片')
    return
  }
  
  isRecognizing.value = true
  result.value = null
  
  const progressInterval = startProgress()
  
  try {
    const response = await recognitionApi.recognize(currentFile.value)
    
    if (response.success) {
      result.value = response.data
      progressPercentage.value = 100
      progressStatus.value = 'success'
      analyzingStep.value = '识别完成！'
      ElMessage.success('识别完成')
      // 刷新历史记录
      loadHistory()
    } else {
      progressStatus.value = 'exception'
      analyzingStep.value = '识别失败'
      ElMessage.error(response.message || '识别失败')
    }
  } catch (error) {
    console.error('识别错误:', error)
    progressStatus.value = 'exception'
    analyzingStep.value = '识别出错'
    ElMessage.error('识别失败，请重试')
  } finally {
    clearInterval(progressInterval)
    setTimeout(() => {
      isRecognizing.value = false
    }, 500)
  }
}

// 显示历史记录对话框
const showHistoryDialog = () => {
  historyDialogVisible.value = true
  loadHistory()
}

// 加载历史记录
const loadHistory = async () => {
  historyLoading.value = true
  try {
    const response = await recognitionApi.getHistory(historyPage.value, historyPageSize.value)
    if (response.success) {
      historyList.value = response.data
      historyTotal.value = response.total
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
    ElMessage.error('加载历史记录失败')
  } finally {
    historyLoading.value = false
  }
}

// 获取图片URL
const getImageUrl = (path) => {
  if (!path) return ''
  // 从路径中提取文件名
  const filename = path.split('\\').pop().split('/').pop()
  return `/static/uploads/${filename}`
}

// 预览历史图片
const previewHistoryImage = (row) => {
  previewImageUrl.value = getImageUrl(row.uploaded_image_path)
  previewDialogVisible.value = true
}

// 加载历史记录结果
const loadHistoryResult = (row) => {
  result.value = {
    recognized_character: row.recognized_character,
    similarity: row.similarity_score,
    processing_time_ms: row.processing_time_ms,
    top_matches: row.top_matches || [],
    best_match: row.best_match || null,
    recognition_method: row.recognition_method || 'feature_match',
    uploaded_image_url: getImageUrl(row.uploaded_image_path)
  }
  historyDialogVisible.value = false
  ElMessage.success('已加载历史记录')
}

// 删除历史记录
const deleteHistoryItem = async (row) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这条历史记录吗？',
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    console.log('正在删除记录:', row.id)
    const response = await recognitionApi.deleteHistory(row.id)
    console.log('删除响应:', response)
    
    if (response.success) {
      ElMessage.success('删除成功')
      // 刷新历史记录列表
      loadHistory()
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    console.error('删除失败详细错误:', error)
    if (error !== 'cancel') {
      if (error.response) {
        // 服务器返回了错误响应
        ElMessage.error(`删除失败: ${error.response.data?.detail || error.response.statusText}`)
      } else if (error.request) {
        // 请求发送但没有收到响应
        ElMessage.error('删除失败: 无法连接到服务器')
      } else {
        // 其他错误
        ElMessage.error(`删除失败: ${error.message || '未知错误'}`)
      }
    }
  }
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  // 页面加载时可以自动加载历史记录
})
</script>

<style scoped>
.recognize-page {
  padding: 20px 0;
}

.page-title {
  text-align: center;
  font-size: 32px;
  margin-bottom: 10px;
  color: #333;
}

.page-subtitle {
  text-align: center;
  font-size: 14px;
  color: #666;
  margin-bottom: 30px;
}

.content-wrapper {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30px;
  max-width: 1200px;
  margin: 0 auto;
}

.upload-card,
.result-card {
  height: 100%;
  min-height: 500px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 200px;
}

.preview-area {
  margin-top: 20px;
  text-align: center;
}

.preview-area h4 {
  margin-bottom: 10px;
  color: #666;
}

.preview-image {
  max-width: 100%;
  max-height: 200px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  margin-bottom: 15px;
}

.recognize-btn {
  width: 100%;
  font-size: 16px;
  padding: 12px;
}

.empty-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #909399;
}

.empty-result p {
  margin-top: 20px;
  font-size: 16px;
}

.analyzing-status {
  padding: 40px 20px;
  text-align: center;
}

.analyzing-text {
  margin-top: 20px;
  font-size: 18px;
  color: #409EFF;
  font-weight: bold;
}

.analyzing-subtext {
  margin-top: 10px;
  font-size: 14px;
  color: #909399;
}

.result-content {
  padding: 10px 0;
}

/* 上传原图样式 */
.original-image-section {
  margin-bottom: 20px;
}

.original-image-section h3 {
  margin-bottom: 15px;
  color: #333;
  font-size: 18px;
}

.original-image-wrapper {
  text-align: center;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.original-image {
  max-width: 100%;
  max-height: 200px;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.best-match h3 {
  margin-bottom: 20px;
  color: #333;
}

.match-info {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-bottom: 30px;
}

.character-display {
  text-align: center;
}

.character {
  font-size: 80px;
  font-family: "KaiTi", "STKaiti", serif;
  color: #333;
}

.similarity-circle {
  text-align: center;
}

.similarity-label {
  display: block;
  margin-top: 10px;
  color: #666;
  font-size: 14px;
}

.ai-reason {
  margin-bottom: 20px;
}

.stele-info h4 {
  margin-bottom: 15px;
  color: #333;
}

.other-matches h4 {
  margin-bottom: 15px;
  color: #333;
}

.table-character {
  font-size: 24px;
  font-family: "KaiTi", "STKaiti", serif;
}

.process-info {
  margin-top: 20px;
  text-align: right;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

/* 历史记录样式 */
.history-content {
  max-height: 600px;
  overflow-y: auto;
}

.history-image {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
}

.history-image:hover {
  border-color: #409EFF;
}

.history-character {
  font-size: 28px;
  font-family: "KaiTi", "STKaiti", serif;
}

.history-pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 圆角胶囊按钮样式 */
:deep(.el-button) {
  border-radius: 50px;
  padding: 12px 32px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #ffa726 0%, #ff9800 100%);
  color: white;
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #ffb74d 0%, #ffa726 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(255, 167, 38, 0.4);
}

:deep(.el-button--success) {
  background: linear-gradient(135deg, #cddc39 0%, #8bc34a 100%);
  color: #333;
}

:deep(.el-button--success:hover) {
  background: linear-gradient(135deg, #d4e157 0%, #9ccc65 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 195, 74, 0.4);
}

:deep(.el-button--warning) {
  background: linear-gradient(135deg, #cddc39 0%, #8bc34a 100%);
  color: #333;
}

:deep(.el-button--warning:hover) {
  background: linear-gradient(135deg, #d4e157 0%, #9ccc65 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 195, 74, 0.4);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
  color: white;
}

:deep(.el-button--danger:hover) {
  background: linear-gradient(135deg, #e57373 0%, #ef5350 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(239, 83, 80, 0.4);
}

:deep(.el-button--default) {
  background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
  color: #666;
}

:deep(.el-button--default:hover) {
  background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}

:deep(.el-button--info) {
  background: linear-gradient(135deg, #90a4ae 0%, #78909c 100%);
  color: white;
}

:deep(.el-button--info:hover) {
  background: linear-gradient(135deg, #b0bec5 0%, #90a4ae 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(144, 164, 174, 0.4);
}

:deep(.el-button.is-small) {
  padding: 8px 20px;
  font-size: 13px;
}

@media (max-width: 968px) {
  .content-wrapper {
    grid-template-columns: 1fr;
  }
}
</style>
