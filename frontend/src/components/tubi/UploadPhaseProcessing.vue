<template>
  <div class="batch-upload-progress-section">
    <div class="batch-progress-header">
      <h4 class="form-section-title">阶段二：AI分析</h4>
      <span class="batch-progress-count">{{ uploadStore.doneCount + uploadStore.errorCount }} / {{ uploadStore.totalCount }}</span>
    </div>

    <!-- 总体进度条 -->
    <div class="glow-progress-container batch-progress-bar">
      <div class="glow-progress-bar">
        <div class="glow-progress-fill" :style="{ width: uploadStore.progressPercent + '%' }"></div>
      </div>
      <span class="glow-progress-text">{{ uploadStore.progressPercent }}%</span>
    </div>

    <!-- 统计 -->
    <div class="batch-overall-progress">
      <span>已完成: {{ uploadStore.doneCount }} / {{ uploadStore.totalCount }}</span>
      <span v-if="uploadStore.activeCount > 0" class="batch-analyzing-count">分析中: {{ uploadStore.activeCount }}</span>
      <span v-if="uploadStore.errorCount > 0" class="batch-fail-count">失败: {{ uploadStore.errorCount }}</span>
    </div>

    <!-- 单项状态列表 -->
    <div class="batch-item-list">
      <div
        v-for="item in uploadStore.items"
        :key="item.id"
        class="batch-status-item"
        :class="item.status"
      >
        <div class="batch-status-icon">
          <el-icon v-if="item.status === 'done'" color="var(--tubi-success, #5a8a4a)"><CircleCheck /></el-icon>
          <el-icon v-else-if="item.status === 'error'" color="var(--el-color-danger)"><Close /></el-icon>
          <el-icon v-else-if="item.status === 'analyzing'" class="is-loading" color="var(--el-color-primary)"><Loading /></el-icon>
          <el-icon v-else color="var(--el-color-warning)"><Clock /></el-icon>
        </div>
        <div class="batch-status-info">
          <div class="batch-status-name">{{ item.fileName }}</div>
          <div class="batch-status-text">
            <template v-if="item.status === 'queued'">
              排队中<span v-if="item.position"> (第{{ item.position }}位<span v-if="item.estimatedWait">，约{{ Math.ceil(item.estimatedWait / 60) }}分钟</span>)</span>
            </template>
            <template v-else-if="item.status === 'analyzing'">AI分析中...</template>
            <template v-else-if="item.status === 'done'">分析完成</template>
            <template v-else-if="item.status === 'error'">
              {{ item.errorMessage || '分析失败' }}
              <span v-if="item.errorCode" class="error-code-tag">{{ item.errorCode }}</span>
            </template>
            <template v-else-if="item.status === 'uploaded'">等待入队...</template>
            <template v-else>{{ item.status }}</template>
          </div>
        </div>
        <el-button
          v-if="item.status === 'error' && item.rawFile"
          size="small"
          type="primary"
          @click="retryItem(item)"
        >
          重试
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { CircleCheck, Close, Loading, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  uploadStore: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['retry'])

function retryItem(item) {
  emit('retry', item)
}
</script>

<style scoped>
/* === Claude 风格 AI 分析进度 === */
.batch-upload-progress-section {
  padding: 8px 0;
}

.batch-progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
}

.batch-progress-count {
  font-size: 14px;
  color: var(--cinnabar, #c96442);
  font-family: var(--font-sans);
  font-weight: 600;
}

/* 进度条 */
.batch-progress-bar {
  margin-bottom: 20px;
}

.glow-progress-container {
  display: flex;
  align-items: center;
  gap: 14px;
}

.glow-progress-bar {
  flex: 1;
  height: 8px;
  background: var(--border-cream, #f0eee6);
  border-radius: var(--radius-full, 9999px);
  overflow: hidden;
}

.glow-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--cinnabar, #c96442) 0%, var(--gold, #b8a47e) 100%);
  border-radius: var(--radius-full, 9999px);
  transition: width 0.4s ease;
}

.glow-progress-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--cinnabar, #c96442);
  font-family: var(--font-sans);
  min-width: 40px;
  text-align: right;
}

/* 统计 */
.batch-overall-progress {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  font-family: var(--font-sans);
}

.batch-analyzing-count {
  color: var(--focus-blue, #3898ec);
  font-weight: 500;
}

.batch-fail-count {
  color: var(--error-crimson, #b53333);
  font-weight: 500;
}

/* 状态列表 */
.batch-item-list {
  margin-top: 20px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}

.batch-status-item {
  display: flex;
  align-items: center;
  padding: 12px 14px;
  border-radius: var(--radius-md, 8px);
  margin-bottom: 8px;
  background: var(--pure-white, #ffffff);
  border: 1px solid var(--border-cream, #f0eee6);
  transition: all var(--transition-fast);
}

.batch-status-item:hover {
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}

.batch-status-item.done {
  background: rgba(90, 138, 74, 0.04);
  border-color: rgba(90, 138, 74, 0.15);
}

.batch-status-item.error {
  background: rgba(181, 51, 51, 0.04);
  border-color: rgba(181, 51, 51, 0.12);
}

.batch-status-icon {
  margin-right: 14px;
  flex-shrink: 0;
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.batch-status-info {
  flex: 1;
  min-width: 0;
}

.batch-status-name {
  font-size: 13px;
  color: var(--near-black, #141413);
  font-family: var(--font-sans);
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-status-text {
  font-size: 12px;
  color: var(--stone-gray, #87867f);
  font-family: var(--font-sans);
  line-height: 1.4;
}

.error-code-tag {
  margin-left: 6px;
  padding: 1px 6px;
  background: rgba(181, 51, 51, 0.08);
  color: var(--error-crimson, #b53333);
  border-radius: var(--radius-sm, 6px);
  font-size: 10px;
  font-family: var(--font-mono);
}
</style>
