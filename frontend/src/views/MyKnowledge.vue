<template>
  <div class="my-knowledge-page">
    <div class="page-header">
      <h1>{{ $t('myknowledge.t1') }}</h1>
      <p class="page-desc">{{ $t('myknowledge.t2') }}</p>
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
          <div class="el-upload__text">{{ $t('myknowledge.t3') }}</div>
          <div class="el-upload__tip">{{ $t('myknowledge.t4') }}</div>
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
        <h3>{{ $t('myknowledge.t5') }}</h3>
        <el-table :data="documents" v-loading="docsLoading" style="width: 100%">
          <el-table-column prop="title" :label="$t('myknowledge.a1')" min-width="200">
            <template #default="{ row }">
              {{ row.title || row.filename || '未命名文档' }}
            </template>
          </el-table-column>
          <el-table-column prop="status" :label="$t('contentverify.a22')" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'ready'" type="success" size="small">{{ $t('myknowledge.t6') }}</el-tag>
              <el-tag v-else-if="row.status === 'processing'" type="warning" size="small">{{ $t('myknowledge.t7') }}</el-tag>
              <el-tag v-else-if="row.status === 'failed'" type="danger" size="small">{{ $t('common.failed') }}</el-tag>
              <el-tag v-else type="info" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunk_count" :label="$t('myknowledge.a2')" width="80" />
          <el-table-column :label="$t('engine.actions')" width="100">
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
        <p>{{ $t('myknowledge.t8') }}</p>
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
import { translate as t } from '@/locales'

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
    ElMessage.error(t('myknowledge.s1'))
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
    ElMessage.success(t('myknowledge.s2'))
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
    await ElMessageBox.confirm(t('myknowledge.s3'), '确认', { type: 'warning' })
    await store.deleteMyDocument(doc.id)
    ElMessage.success(t('knowledgesearch.s2'))
    await loadDocuments()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(t('engine.delete_error'))
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
