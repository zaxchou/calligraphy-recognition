<template>
  <div class="phase-done">
    <div class="done-icon-wrap">
      <el-icon class="done-icon"><CircleCheck /></el-icon>
    </div>
    <h4 class="done-title">全部完成</h4>
    <div class="done-stats">
      <div class="done-stat">
        <span class="done-stat-num succ">{{ uploadStore.doneCount }}</span>
        <span class="done-stat-lbl">成功</span>
      </div>
      <div class="done-stat">
        <span class="done-stat-num fail">{{ uploadStore.errorCount }}</span>
        <span class="done-stat-lbl">失败</span>
      </div>
      <div class="done-stat">
        <span class="done-stat-num">{{ uploadStore.totalCount }}</span>
        <span class="done-stat-lbl">总计</span>
      </div>
    </div>
    <p class="done-tip">画作信息可在作品库中编辑完善</p>
    <div v-if="uploadStore.errorCount > 0" class="done-retry">
      <el-button type="warning" @click="retryAll">重试所有失败项</el-button>
    </div>
  </div>
</template>

<script setup>
import { CircleCheck } from '@element-plus/icons-vue'
const props = defineProps({ uploadStore: { type: Object, required: true } })
const emit = defineEmits(['retry-all'])
function retryAll() { emit('retry-all') }
</script>

<style scoped>
.phase-done { text-align: center; padding: 20px 0; }
.done-icon-wrap {
  display: inline-flex; align-items: center; justify-content: center;
  width: 64px; height: 64px; border-radius: 50%;
  background: #f0f7ed; margin-bottom: 14px;
}
.done-icon { font-size: 32px; color: #5a8a4a; }
.done-title {
  font-size: 18px; font-weight: 600; color: #3a3222; margin: 0 0 22px;
  font-family: 'Noto Serif SC', serif;
}
.done-stats { display: flex; justify-content: center; gap: 24px; margin-bottom: 20px; }
.done-stat { text-align: center; }
.done-stat-num { font-size: 24px; font-weight: 700; display: block; }
.done-stat-num.succ { color: #5a8a4a; }
.done-stat-num.fail { color: #d03030; }
.done-stat-lbl { font-size: 12px; color: #b0a890; }
.done-tip { font-size: 13px; color: #8c7a5c; margin: 0 0 14px; }
.done-retry { margin-top: 8px; }
</style>
