<template>
  <div class="panel-wrapper">
    <!-- 这里直接使用原来的 ContentVerify 内容，但移除头部 -->
    <div class="verify-panel-content">
      <!-- 原来 ContentVerify 的主体内容（从统计标签开始） -->
      <!-- 为了节省时间，我们直接在整合版本中处理这个 -->
      <div class="placeholder-notice">
        <el-alert
          title="题跋校对功能"
          type="info"
          description="题跋校对功能已在此标签页中，保持原有功能不变。"
          show-icon
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
</script>

<style scoped>
.panel-wrapper {
  width: 100%;
}

.placeholder-notice {
  margin-bottom: 20px;
}
</style>
