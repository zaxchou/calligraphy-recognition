<template>
  <div class="page">
    <div class="page-header">
      <h1 class="title">构图知识库训练</h1>
      <div class="subtitle">将 pan.md 规则与附图样本入库，用于后续相似参考与评分对比</div>
    </div>

    <el-card class="card" shadow="never">
      <div class="row">
        <el-button type="primary" :loading="starting" @click="startIngest(false)">导入 pan.md（增量）</el-button>
        <el-button type="danger" :loading="starting" @click="startIngest(true)">重建并导入</el-button>
        <el-button @click="$router.push('/composition')">返回构图分析</el-button>
      </div>

      <el-divider />

      <div class="block">
        <div class="block-title">上传原书 PDF</div>
        <div class="block-sub">先上传保存到服务器，等你确认后再做“附图分离并按图号入库”</div>
        <div class="row">
          <el-upload
            :auto-upload="false"
            :limit="1"
            :file-list="bookFileList"
            :on-change="onBookChange"
            :on-remove="onBookRemove"
            accept=".pdf"
          >
            <el-button>选择 PDF</el-button>
          </el-upload>
          <el-button type="primary" :disabled="!bookFile || uploadingBook" :loading="uploadingBook" @click="uploadBook">
            上传
          </el-button>
          <el-button
            type="success"
            :disabled="!bookStoredPath || extractingFromPdf"
            :loading="extractingFromPdf"
            @click="extractFromPdf"
          >
            提取附图并入库
          </el-button>
        </div>
        <div v-if="bookStoredUrl" class="hint">
          已接收：<a :href="bookStoredUrl" target="_blank" rel="noreferrer">{{ bookStoredUrl }}</a>
        </div>
      </div>

      <el-divider />

      <div class="block">
        <div class="block-title">上传附图样本并入库</div>
        <div class="block-sub">支持多张图片或一个 zip（文件名建议直接用“图一/图二(一)/图一①…”）</div>
        <div class="row">
          <el-upload
            :auto-upload="false"
            :multiple="true"
            :file-list="imagesFileList"
            :on-change="onImagesChange"
            :on-remove="onImagesRemove"
            accept="image/*,.zip"
          >
            <el-button>选择图片/zip</el-button>
          </el-upload>
          <el-upload
            :auto-upload="false"
            :limit="1"
            :file-list="mappingFileList"
            :on-change="onMappingChange"
            :on-remove="onMappingRemove"
            accept=".json"
          >
            <el-button>选择映射 JSON（可选）</el-button>
          </el-upload>
          <el-button type="success" :disabled="imagesFiles.length === 0 || ingestingImages" :loading="ingestingImages" @click="startImagesIngest">
            上传并入库
          </el-button>
        </div>
      </div>

      <div v-if="taskId" class="status">
        <div class="status-title">任务：{{ taskId }}</div>
        <el-progress :percentage="progress" :status="progressStatus" />
        <div class="status-text">
          <span v-if="stage">{{ stage }}</span>
          <span v-if="message">· {{ message }}</span>
          <span v-if="errorMessage" class="error">· {{ errorMessage }}</span>
        </div>
      </div>

      <div v-if="result" class="result">
        <div class="result-title">入库结果</div>
        <div v-if="result.mapping_json_url" class="hint">
          映射文件：<a :href="result.mapping_json_url" target="_blank" rel="noreferrer">{{ result.mapping_json_url }}</a>
        </div>
        <pre class="result-json">{{ JSON.stringify(result, null, 2) }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { compositionApi } from '../api/composition'

const starting = ref(false)
const uploadingBook = ref(false)
const ingestingImages = ref(false)
const extractingFromPdf = ref(false)

const bookFileList = ref([])
const bookFile = ref(null)
const bookStoredUrl = ref('')
const bookStoredPath = ref('')

const imagesFileList = ref([])
const imagesFiles = ref([])
const mappingFileList = ref([])
const mappingFile = ref(null)

const taskId = ref('')
const progress = ref(0)
const stage = ref('')
const message = ref('')
const errorMessage = ref('')
const result = ref(null)
let pollTimer = null

const progressStatus = computed(() => {
  if (errorMessage.value) return 'exception'
  if (progress.value >= 100 && result.value) return 'success'
  return ''
})

function resetState() {
  taskId.value = ''
  progress.value = 0
  stage.value = ''
  message.value = ''
  errorMessage.value = ''
  result.value = null
}

function onBookChange(file, files) {
  bookFileList.value = files.slice(-1)
  bookFile.value = file.raw || null
}

function onBookRemove() {
  bookFileList.value = []
  bookFile.value = null
  bookStoredUrl.value = ''
  bookStoredPath.value = ''
}

async function uploadBook() {
  if (!bookFile.value) return
  uploadingBook.value = true
  bookStoredUrl.value = ''
  bookStoredPath.value = ''
  try {
    const res = await compositionApi.uploadBook(bookFile.value)
    bookStoredUrl.value = res.stored_url || ''
    bookStoredPath.value = res.stored_path || ''
    ElMessage.success('已上传')
  } catch (e) {
    ElMessage.error('上传失败')
  } finally {
    uploadingBook.value = false
  }
}

async function extractFromPdf() {
  if (!bookStoredPath.value) return
  extractingFromPdf.value = true
  resetState()
  try {
    const res = await compositionApi.ingestBookPdf({
      pdf_path: bookStoredPath.value,
      mapping: mappingFile.value,
      ruleset_version: ''
    })
    taskId.value = res.task_id
    await pollStatus()
    pollTimer = setInterval(pollStatus, 1000)
  } catch (e) {
    ElMessage.error('启动失败')
  } finally {
    extractingFromPdf.value = false
  }
}

function onImagesChange(file, files) {
  imagesFileList.value = files
  imagesFiles.value = files.map((x) => x.raw).filter(Boolean)
}

function onImagesRemove(file, files) {
  imagesFileList.value = files
  imagesFiles.value = files.map((x) => x.raw).filter(Boolean)
}

function onMappingChange(file, files) {
  mappingFileList.value = files.slice(-1)
  mappingFile.value = file.raw || null
}

function onMappingRemove() {
  mappingFileList.value = []
  mappingFile.value = null
}

async function startIngest(recreate) {
  starting.value = true
  resetState()
  try {
    const res = await compositionApi.ingestRules({
      pan_md_path: 'pan.md',
      recreate: !!recreate
    })
    taskId.value = res.task_id
    await pollStatus()
    pollTimer = setInterval(pollStatus, 1000)
  } catch (e) {
    ElMessage.error('启动失败')
  } finally {
    starting.value = false
  }
}

async function startImagesIngest() {
  if (imagesFiles.value.length === 0) return
  ingestingImages.value = true
  resetState()
  try {
    const res = await compositionApi.ingestImages({
      files: imagesFiles.value,
      mapping: mappingFile.value,
      ruleset_version: ''
    })
    taskId.value = res.task_id
    await pollStatus()
    pollTimer = setInterval(pollStatus, 1000)
  } catch (e) {
    ElMessage.error('启动失败')
  } finally {
    ingestingImages.value = false
  }
}

async function pollStatus() {
  if (!taskId.value) return
  try {
    const s = await compositionApi.getIngestTask(taskId.value)
    progress.value = s.progress || 0
    stage.value = s.stage || ''
    message.value = s.message || ''
    errorMessage.value = s.error_message || ''
    if (s.status === 'done') {
      result.value = s.result || null
      stopPolling()
    } else if (s.status === 'failed') {
      stopPolling()
    }
  } catch (e) {
    stopPolling()
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 20px;
}

.page-header {
  margin-bottom: 16px;
}

.title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
}

.subtitle {
  margin-top: 8px;
  color: #666;
}

.card {
  border-radius: 10px;
}

.row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.block {
  margin-top: 8px;
}

.block-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.block-sub {
  color: #666;
  font-size: 13px;
  margin-bottom: 10px;
}

.hint {
  margin-top: 10px;
  font-size: 13px;
  color: #666;
}

.status {
  margin-top: 18px;
}

.status-title {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
}

.status-text {
  margin-top: 8px;
  color: #666;
  font-size: 13px;
}

.error {
  color: #d9534f;
}

.result {
  margin-top: 18px;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.result-json {
  margin: 0;
  padding: 12px;
  background: #f6f6f6;
  border-radius: 8px;
  overflow: auto;
}
</style>
