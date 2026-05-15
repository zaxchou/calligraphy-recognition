<template>
  <el-dialog
    v-model="localVisible"
    :title="'搜索结果 - ' + keyword"
    width="85%"
    :close-on-click-modal="true"
    class="search-dialog-wide"
  >
    <div class="search-dialog-content">
      <div style="display:flex;justify-content:flex-end;margin-bottom:8px;">
        <el-button
          v-if="authStore.isEditor"
          size="small"
          :type="isAdmin ? 'warning' : 'default'"
          @click="toggleAdmin"
        >
          {{ isAdmin ? '锁定' : '管理' }}
        </el-button>
      </div>
      <div v-if="loading" class="search-loading">
        <el-icon class="is-loading" size="32"><Loading /></el-icon>
        <p>正在搜索...</p>
      </div>
      <div v-else-if="results.length === 0" class="search-empty">
        <el-icon size="64" color="var(--ring-warm, #d1cfc5)"><Search /></el-icon>
        <p>未找到匹配「{{ keyword }}」的画作</p>
        <p class="search-tip">试试搜索：竹、梅、兰、菊、题跋内容、印章文字、1750等关键词</p>
      </div>
      <el-table v-else :data="results" style="width: 100%">
        <el-table-column label="图片" width="100">
          <template #default="scope">
            <img v-if="scope.row.url" :src="scope.row.url" class="history-thumb" @click="previewImage(scope.row)" />
            <div v-else class="history-thumb-placeholder">
              <el-icon size="24"><Picture /></el-icon>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="scope">
            <div class="search-title">
              {{ scope.row.title || '未命名' }}
              <el-tag v-if="scope.row.title && scope.row.title.toLowerCase().includes(keywordLowerCase)" type="success" size="small" effect="plain">标题匹配</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="artist" label="作者" width="120">
          <template #default="scope">
            <div class="search-artist">
              {{ scope.row.artist || '-' }}
              <el-tag v-if="scope.row.artist && scope.row.artist.toLowerCase().includes(keywordLowerCase)" type="warning" size="small" effect="plain">作者匹配</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="年份" width="80">
          <template #default="scope">
            <div class="search-year">
              {{ scope.row.year || '-' }}
              <el-tag v-if="scope.row.year && String(scope.row.year) === keyword" type="info" size="small" effect="plain">年份匹配</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="题跋" min-width="180">
          <template #default="scope">
            <div class="search-inscription">
              <span v-if="scope.row.inscriptionContent" class="inscription-preview">{{ truncateText(scope.row.inscriptionContent, 30) }}</span>
              <span v-else class="inscription-empty">-</span>
              <el-tag v-if="scope.row.inscriptionContent && scope.row.inscriptionContent.toLowerCase().includes(keywordLowerCase)" type="primary" size="small" effect="plain">题跋匹配</el-tag>
              <el-tag v-else-if="scope.row.inscriptionModern && scope.row.inscriptionModern.toLowerCase().includes(keywordLowerCase)" type="" size="small" effect="plain">翻译匹配</el-tag>
              <el-tag v-if="scope.row.sealContent && scope.row.sealContent.toLowerCase().includes(keywordLowerCase)" type="danger" size="small" effect="plain">印章匹配</el-tag>
            </div>
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
        <el-table-column prop="created_at" label="分析时间" width="160">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <div class="action-buttons">
              <el-button plain size="small" class="btn-edit" @click="viewItem(scope.row)">
                查看
              </el-button>
              <el-button v-if="isAdmin" plain size="small" class="btn-edit" @click="editItem(scope.row)">
                编辑
              </el-button>
              <el-button v-if="isAdmin" plain size="small" type="danger" @click="deleteItem(scope.row)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Picture, Loading, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/authStore'

const authStore = useAuthStore()
const isAdmin = ref(authStore.isEditor)

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  keyword: {
    type: String,
    default: ''
  },
  results: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'view', 'edit', 'delete', 'preview'])

const localVisible = ref(props.modelValue)

const keywordLowerCase = computed(() => (props.keyword || '').toLowerCase())

watch(() => props.modelValue, (val) => {
  localVisible.value = val
})

watch(localVisible, (val) => {
  emit('update:modelValue', val)
})

function toggleAdmin() {
  isAdmin.value = !isAdmin.value
}

function viewItem(row) {
  emit('view', row)
  localVisible.value = false
}

function editItem(row) {
  emit('edit', row)
}

function deleteItem(row) {
  emit('delete', row)
}

function previewImage(row) {
  emit('preview', row)
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN')
}

function truncateText(text, maxLen) {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}
</script>

<style scoped>
.search-dialog-content {
  min-height: 300px;
}

.search-loading, .search-empty {
  text-align: center;
  padding: 48px 0;
  color: var(--el-text-color-secondary);
}

.search-loading p, .search-empty p {
  margin-top: 16px;
  font-size: 14px;
}

.search-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 8px;
}

.search-title, .search-artist, .search-year, .search-inscription {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.inscription-preview {
  font-size: 12px;
  color: #6b6b66;
  line-height: 1.4;
}

.inscription-empty {
  color: #c0c0b8;
}

.history-thumb {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  cursor: pointer;
}

.history-thumb-placeholder {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  color: var(--el-text-color-placeholder);
}

.action-buttons {
  display: flex;
  gap: 8px;
}
</style>
