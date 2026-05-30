<template>
  <div class="phase-uploading">
    <div class="phase-hd">
      <div>
        <h4 class="phase-title">正在上传</h4>
        <p class="phase-sub">请勿关闭页面</p>
      </div>
      <span class="phase-badge">{{ uploadStore.uploadedCount }}/{{ uploadStore.totalCount }}</span>
    </div>

    <!-- 总体进度条 -->
    <div class="prog-wrap">
      <div class="prog-bar"><div class="prog-fill" :style="{ width: progress + '%' }" /></div>
      <span class="prog-pct">{{ progress }}%</span>
    </div>

    <div class="prog-info">
      <span>已上传 {{ uploadStore.uploadedCount }} / {{ uploadStore.totalCount }}</span>
      <span v-if="uploadStore.errorCount" class="prog-err">失败 {{ uploadStore.errorCount }}</span>
    </div>

    <!-- 每文件状态 -->
    <div class="item-list">
      <div v-for="item in uploadStore.items" :key="item.id" class="item-row" :class="item.status">
        <span class="item-icon">
          <el-icon v-if="item.status === 'uploaded'" color="#5a8a4a"><CircleCheck /></el-icon>
          <el-icon v-else-if="item.status === 'uploading'" class="is-loading" color="#c45a3c"><Loading /></el-icon>
          <el-icon v-else-if="item.status === 'error'" color="#d03030"><Close /></el-icon>
          <el-icon v-else color="#b0a890"><Clock /></el-icon>
        </span>
        <span class="item-name">{{ item.fileName }}</span>
        <span class="item-status-text">
          <template v-if="item.status === 'uploaded'">已上传</template>
          <template v-else-if="item.status === 'uploading'">上传中...</template>
          <template v-else-if="item.status === 'error'">{{ item.errorMessage || '失败' }}</template>
          <template v-else>等待中</template>
        </span>
        <el-button v-if="item.status === 'error'" size="small" @click="retryItem(item)">重试</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { CircleCheck, Loading, Close, Clock } from '@element-plus/icons-vue'

const props = defineProps({ uploadStore: { type: Object, required: true } })
const emit = defineEmits(['retry'])

const progress = computed(() => {
  if (!props.uploadStore.totalCount) return 0
  return Math.round(((props.uploadStore.uploadedCount + props.uploadStore.errorCount) / props.uploadStore.totalCount) * 100)
})

function retryItem(item) { emit('retry', item) }
</script>

<style scoped>
.phase-uploading {}

.phase-hd {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 18px;
}
.phase-title {
  margin: 0 0 2px; font-size: 16px; font-weight: 600; color: #3a3222;
  font-family: 'Noto Serif SC', serif;
}
.phase-sub { margin: 0; font-size: 12px; color: #b0a890; }
.phase-badge {
  font-size: 18px; font-weight: 700; color: #c45a3c;
}

/* 进度条 */
.prog-wrap { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.prog-bar {
  flex: 1; height: 7px; background: #eeece4; border-radius: 99px; overflow: hidden;
}
.prog-fill {
  height: 100%; border-radius: 99px;
  background: linear-gradient(90deg, #c45a3c, #d4896a);
  transition: width 0.4s ease;
}
.prog-pct { font-size: 14px; font-weight: 700; color: #c45a3c; min-width: 38px; text-align: right; }

.prog-info {
  display: flex; justify-content: space-between;
  font-size: 12px; color: #8c7a5c; margin-bottom: 22px;
}
.prog-err { color: #d03030; font-weight: 500; }

/* 文件列表 */
.item-list {
  max-height: 300px; overflow-y: auto;
  border: 1px solid #eeece4; border-radius: 10px;
}
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-bottom: 1px solid #f5f2eb;
  font-size: 13px;
}
.item-row:last-child { border-bottom: none; }
.item-row.error { background: #fef5f5; }
.item-row.uploaded { background: #f8faf7; }

.item-icon { flex-shrink: 0; display: flex; font-size: 16px; }
.item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #3a3222; }
.item-status-text { font-size: 12px; color: #8c7a5c; flex-shrink: 0; }
.item-row.error .item-status-text { color: #d03030; }
.item-row.uploaded .item-status-text { color: #5a8a4a; }
</style>
