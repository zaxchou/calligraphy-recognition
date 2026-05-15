<template>
  <div class="admin-settings">
    <div class="page-header">
      <h1 class="page-title">系统信息</h1>
      <p class="page-subtitle">当前系统配额与参数配置</p>
    </div>

    <el-card class="config-card" shadow="never" v-loading="loading" v-if="config">
      <template #header>
        <span class="card-header-title">AI 调用配额</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="免费用户每月调用次数">
          <span class="config-value">{{ config.free_ai_calls_per_month ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付费用户每月调用次数">
          <span class="config-value">{{ config.paid_ai_calls_per_month ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="当前 AI 模型">
          <span class="config-value">{{ config.ai_model ?? '--' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="config-card" shadow="never" v-loading="loading" v-if="config">
      <template #header>
        <span class="card-header-title">存储配额</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="免费用户存储空间">
          <span class="config-value">{{ formatStorage(config.free_storage_bytes) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付费用户存储空间">
          <span class="config-value">{{ formatStorage(config.paid_storage_bytes) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="免费用户作品库数量">
          <span class="config-value">{{ config.free_library_limit ?? '--' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <div v-if="!config && !loading" class="empty-state">
      暂无配置数据
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '../../api/adminApi'

const loading = ref(false)
const config = ref(null)

function formatStorage(val) {
  if (val === null || val === undefined) return '--'
  if (typeof val === 'string') return val
  if (typeof val === 'number') {
    if (val === 0) return '无限制'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(val) / Math.log(k))
    return parseFloat((val / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }
  return String(val)
}

onMounted(async () => {
  loading.value = true
  try {
    config.value = await adminApi.getConfig()
  } catch (e) {
    console.error('获取系统配置失败:', e)
    config.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.admin-settings {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: var(--space-2xl);
}

.page-header {
  margin-bottom: var(--space-2xl);
}

.page-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-h2);
  font-weight: 500;
  color: var(--near-black);
  letter-spacing: 0.06em;
  margin: 0 0 var(--space-sm) 0;
}

.page-subtitle {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  color: var(--stone-gray);
  margin: 0;
}

.config-card {
  margin-bottom: var(--space-xl);
}

.card-header-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--near-black);
}

.config-value {
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  color: var(--charcoal-warm);
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: var(--space-3xl) 0;
  color: var(--stone-gray);
  font-size: var(--text-caption);
}

.footer-note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-xl) 0;
  color: var(--warm-silver);
  font-size: var(--text-label);
}
</style>
