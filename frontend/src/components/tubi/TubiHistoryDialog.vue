<template>
  <el-dialog
    v-model="localVisible"
    title="题跋分析历史记录"
    width="85%"
    :close-on-click-modal="true"
    class="history-dialog-wide"
  >
    <div class="history-dialog-content">
      <el-table :data="historyList" style="width: 100%" v-loading="loading">
        <el-table-column label="图片" width="100">
          <template #default="scope">
            <img v-if="scope.row.thumbnail_url || scope.row.url" :src="scope.row.thumbnail_url || scope.row.url" class="history-thumb" loading="lazy" @click="previewImage(scope.row)" />
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
        <el-table-column prop="created_at" label="分析时间" width="160">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="scope">
            <div class="action-buttons">
              <el-button plain size="small" class="btn-edit" @click="viewItem(scope.row)">
                查看
              </el-button>
              <el-button plain size="small" class="btn-edit" @click="editItem(scope.row)">
                编辑
              </el-button>
              <el-button plain size="small" class="btn-edit" @click="deleteItem(scope.row)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div class="history-pagination" v-if="total > localPageSize">
        <el-pagination
          v-model:current-page="localCurrentPage"
          :page-size="localPageSize"
          :total="total"
          layout="total, prev, pager, next, jumper"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Picture } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  historyList: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  total: {
    type: Number,
    default: 0
  },
  currentPage: {
    type: Number,
    default: 1
  },
  pageSize: {
    type: Number,
    default: 500
  }
})

const emit = defineEmits(['update:modelValue', 'view', 'edit', 'delete', 'preview', 'page-change'])

const localVisible = ref(props.modelValue)
const localCurrentPage = ref(props.currentPage)
const localPageSize = ref(props.pageSize)

watch(() => props.modelValue, (val) => {
  localVisible.value = val
})

watch(localVisible, (val) => {
  emit('update:modelValue', val)
})

watch(() => props.currentPage, (val) => {
  localCurrentPage.value = val
})

watch(() => props.pageSize, (val) => {
  localPageSize.value = val
})

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

function handlePageChange(page) {
  localCurrentPage.value = page
  emit('page-change', page)
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN')
}
</script>

<style scoped>
.history-dialog-content {
  min-height: 400px;
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

.history-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
