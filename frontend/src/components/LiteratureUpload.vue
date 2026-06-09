<template>
  <el-dialog title="上传文献" :model-value="true" width="520px" :close-on-click-modal="false" @close="$emit('close')">
    <div class="alu-upload-area">
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf"
        :on-change="onFileChange"
        :on-exceed="onExceed"
      >
        <div class="alu-upload-content">
          <div class="alu-upload-icon">PDF</div>
          <div class="alu-upload-text">拖拽 PDF 文件到此处，或 <em>点击选择</em></div>
          <div class="alu-upload-hint">仅支持 PDF 格式</div>
        </div>
      </el-upload>
    </div>

    <el-form label-position="top" class="alu-form" v-if="file">
      <el-form-item label="标题（可选）">
        <el-input v-model="form.title" placeholder="文献标题" />
      </el-form-item>
      <div class="alu-form-row">
        <el-form-item label="期刊/出版社（可选）" class="alu-form-item-half">
          <el-input v-model="form.journal" placeholder="期刊或出版社" />
        </el-form-item>
        <el-form-item label="发表年份（可选）" class="alu-form-item-half">
          <el-input-number v-model="form.publish_year" :min="1000" :max="2100" controls-position="right" style="width:100%" />
        </el-form-item>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" :disabled="!file" :loading="uploading" @click="doUpload">上传</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/authStore'

const props = defineProps({ artistId: { type: Number, required: true } })
const emit = defineEmits(['uploaded', 'close'])

const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const uploadRef = ref(null)
const file = ref(null)
const uploading = ref(false)
const form = reactive({ title: '', journal: '', publish_year: null })

function onFileChange(f) { file.value = f.raw }
function onExceed() { ElMessage.warning('只能上传一个文件，请先移除已选文件') }

async function doUpload() {
  if (!file.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    if (form.title) fd.append('title', form.title)
    if (form.journal) fd.append('journal', form.journal)
    if (form.publish_year) fd.append('publish_year', form.publish_year)

    const res = await fetch(`${API_BASE}/knowledge/artists/${props.artistId}/literature/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authStore.token}` },
      body: fd,
    })
    if (!res.ok) {
      const err = await res.text()
      throw new Error(err || '上传失败')
    }
    ElMessage.success('文献上传成功')
    emit('uploaded')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally { uploading.value = false }
}
</script>

<style scoped>
.alu-upload-area { margin-bottom: 16px; }
.alu-upload-content { padding: 24px 0; }
.alu-upload-icon { font-size: 28px; font-weight: 700; color: #c45a3c; margin-bottom: 8px; }
.alu-upload-text { font-size: 14px; color: #3a3222; }
.alu-upload-text em { color: #c45a3c; font-style: normal; }
.alu-upload-hint { font-size: 12px; color: #b0a890; margin-top: 6px; }
.alu-form-row { display: flex; gap: 12px; }
.alu-form-item-half { flex: 1; }
</style>
