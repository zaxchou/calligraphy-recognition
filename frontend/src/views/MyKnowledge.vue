<template>
  <div class="my-knowledge-page">
    <div class="page-header">
      <h1>📁 我的知识库</h1>
      <p class="page-desc">上传私人文档，建立个人书画知识搜索引擎</p>
    </div>

    <div class="my-knowledge-content">
      <!-- 上传区 -->
      <div class="upload-section">
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".pdf"
          :on-change="handleFileChange"
          :show-file-list="false"
          drag
        >
          <el-icon :size="40"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽 PDF 文件到此处，或点击选择</div>
          <div class="el-upload__tip">仅支持 PDF 格式，上传后将自动解析和向量化</div>
        </el-upload>
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="!pendingFile"
          @click="handleUpload"
          style="margin-top: 12px; width: 100%"
        >
          {{ uploading ? '上传并解析中...' : '上传文档' }}
        </el-button>
      </div>

      <!-- 文档列表 -->
      <div class="docs-section" v-if="documents.length > 0 || docsLoading">
        <h3>我的文档</h3>
        <el-table :data="documents" v-loading="docsLoading" style="width: 100%">
          <el-table-column prop="title" label="文档名称" min-width="200">
            <template #default="{ row }">
              {{ row.title || row.filename || '未命名文档' }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'ready'" type="success" size="small">就绪</el-tag>
              <el-tag v-else-if="row.status === 'processing'" type="warning" size="small">处理中</el-tag>
              <el-tag v-else-if="row.status === 'failed'" type="danger" size="small">失败</el-tag>
              <el-tag v-else type="info" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="分块数" width="80" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="danger" size="small" text @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-else-if="!docsLoading" class="empty-state">
        <el-icon :size="48" color="#ccc"><Document /></el-icon>
        <p>还没有上传任何文档</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, Document } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import { useKnowledgeStore } from '../stores/knowledgeStore'

const authStore = useAuthStore()
const store = useKnowledgeStore()
const pendingFile = ref(null)
const uploading = ref(false)
const documents = ref([])
const docsLoading = ref(false)

onMounted(() => {
  if (authStore.isLoggedIn) loadDocuments()
})

async function loadDocuments() {
  docsLoading.value = true
  try {
    await store.fetchMyDocuments()
    documents.value = store.myDocuments || []
  } catch (e) {
    ElMessage.error('加载文档列表失败')
  } finally {
    docsLoading.value = false
  }
}

function handleFileChange(file) {
  pendingFile.value = file.raw
}

async function handleUpload() {
  if (!pendingFile.value) return
  uploading.value = true
  try {
    await store.uploadPrivateDocument(pendingFile.value)
    ElMessage.success('上传成功，正在后台处理...')
    pendingFile.value = null
    await loadDocuments()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleDelete(doc) {
  try {
    await ElMessageBox.confirm('确定删除此文档？向量数据和文件将被永久删除。', '确认', { type: 'warning' })
    await store.deleteMyDocument(doc.id)
    ElMessage.success('已删除')
    await loadDocuments()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.my-knowledge-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
}

.page-header {
  text-align: center;
  margin-bottom: 2rem;
}

.page-header h1 {
  font-family: 'Noto Serif SC', serif;
  font-size: 24px;
  color: var(--near-black);
  margin: 0 0 8px 0;
}

.page-desc {
  font-size: 14px;
  color: var(--stone-gray);
}

.upload-section {
  margin-bottom: 2rem;
}

.docs-section h3 {
  font-size: 16px;
  margin-bottom: 12px;
  color: var(--near-black);
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--stone-gray);
}
</style>
