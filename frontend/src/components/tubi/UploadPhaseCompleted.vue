<template>
  <div class="batch-upload-complete">
    <div class="batch-complete-icon">
      <el-icon size="64" color="var(--tubi-success, #5a8a4a)"><CircleCheck /></el-icon>
    </div>
    <h4 class="batch-complete-title">上传完成</h4>
    <div class="batch-complete-stats">
      <div class="batch-stat-item">
        <span class="batch-stat-label">成功</span>
        <span class="batch-stat-value success">{{ uploadStore.doneCount }}</span>
      </div>
      <div class="batch-stat-item">
        <span class="batch-stat-label">失败</span>
        <span class="batch-stat-value fail">{{ uploadStore.errorCount }}</span>
      </div>
      <div class="batch-stat-item">
        <span class="batch-stat-label">总计</span>
        <span class="batch-stat-value">{{ uploadStore.totalCount }}</span>
      </div>
    </div>
    <p class="batch-complete-tip">画作信息可在作品库中编辑</p>
    <div v-if="uploadStore.errorCount > 0" class="batch-retry-all">
      <el-button type="warning" @click="retryAll">重试所有失败项</el-button>
    </div>
  </div>
</template>

<script setup>
import { CircleCheck } from '@element-plus/icons-vue'

const props = defineProps({
  uploadStore: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['retry-all'])

function retryAll() {
  emit('retry-all')
}
</script>

<style scoped>
/* === Claude 风格完成页面 === */
.batch-upload-complete {
  text-align: center;
  padding: 32px 24px;
}

.batch-complete-icon {
  margin-bottom: 20px;
  color: var(--tubi-success, #5a8a4a);
}

.batch-complete-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--near-black, #141413);
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  margin-bottom: 28px;
  letter-spacing: 0.04em;
}

/* 统计卡片 */
.batch-complete-stats {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 24px;
}

.batch-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 28px;
  background: var(--pure-white, #ffffff);
  border: 1px solid var(--border-cream, #f0eee6);
  border-radius: var(--radius-lg, 12px);
  min-width: 90px;
  transition: box-shadow var(--transition-fast);
}

.batch-stat-item:hover {
  box-shadow: var(--shadow-whisper, rgba(0,0,0,0.05) 0px 4px 24px);
}

.batch-stat-label {
  font-size: 12px;
  color: var(--stone-gray, #87867f);
  font-family: var(--font-sans);
  margin-bottom: 6px;
  letter-spacing: 0.03em;
}

.batch-stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--near-black, #141413);
  font-family: var(--font-sans);
  line-height: 1;
}

.batch-stat-value.success {
  color: var(--tubi-success, #5a8a4a);
}

.batch-stat-value.fail {
  color: var(--error-crimson, #b53333);
}

.batch-complete-tip {
  font-size: 13px;
  color: var(--stone-gray, #87867f);
  font-family: var(--font-sans);
  margin-bottom: 20px;
}

.batch-retry-all {
  margin-top: 12px;
}
</style>
