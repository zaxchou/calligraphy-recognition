<template>
  <div class="batch-upload-progress-section">
    <div class="batch-progress-header">
      <h4 class="form-section-title">阶段一：快速上传</h4>
      <span class="batch-progress-count">{{ uploadStore.uploadedCount + uploadStore.errorCount }} / {{ uploadStore.totalCount }}</span>
    </div>

    <div class="glow-progress-container batch-progress-bar">
      <div class="glow-progress-bar">
        <div class="glow-progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <span class="glow-progress-text">{{ progress }}%</span>
    </div>

    <div class="batch-overall-progress">
      <span>已上传: {{ uploadStore.uploadedCount }} / {{ uploadStore.totalCount }}</span>
      <span v-if="uploadStore.errorCount > 0" class="batch-fail-count">失败: {{ uploadStore.errorCount }}</span>
    </div>

    <!-- 失败项列表 -->
    <div v-if="failedItems.length > 0" class="batch-failed-list">
      <div v-for="item in failedItems" :key="item.id" class="batch-failed-item">
        <span class="batch-failed-name">{{ item.fileName }}</span>
        <span class="batch-failed-error">{{ item.errorMessage || '上传失败' }}</span>
        <el-button v-if="item.rawFile" size="small" type="primary" @click="retryItem(item)">重试</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  uploadStore: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['retry'])

const progress = computed(() => {
  if (props.uploadStore.totalCount === 0) return 0
  return Math.round(((props.uploadStore.uploadedCount + props.uploadStore.errorCount) / props.uploadStore.totalCount) * 100)
})

const failedItems = computed(() => props.uploadStore.failedItems || [])

function retryItem(item) {
  emit('retry', item)
}
</script>

<style scoped>
/* === Claude 风格上传进度 === */
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
  letter-spacing: 0.02em;
}

/* 进度条 — Claude 暖色渐变 */
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

.batch-fail-count {
  color: var(--error-crimson, #b53333);
  font-weight: 500;
}

/* 失败项列表 */
.batch-failed-list {
  margin-top: 20px;
  max-height: 160px;
  overflow-y: auto;
  padding-top: 4px;
}

.batch-failed-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: rgba(181, 51, 51, 0.04);
  border: 1px solid rgba(181, 51, 51, 0.12);
  border-radius: var(--radius-md, 8px);
  margin-bottom: 8px;
  transition: background var(--transition-fast);
}

.batch-failed-item:hover {
  background: rgba(181, 51, 51, 0.08);
}

.batch-failed-name {
  font-size: 13px;
  color: var(--near-black, #141413);
  font-family: var(--font-sans);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 12px;
}

.batch-failed-error {
  font-size: 12px;
  color: var(--error-crimson, #b53333);
  margin-right: 12px;
  flex-shrink: 0;
}
</style>
