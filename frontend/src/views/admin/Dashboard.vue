<template>
  <div class="admin-dashboard">
    <div class="page-header">
      <h1 class="page-title">管理后台</h1>
      <p class="page-subtitle">系统运行概览</p>
    </div>

    <el-row :gutter="20" class="stats-row">
      <el-col :xs="12" :sm="12" :md="6" v-for="card in statCards" :key="card.label">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon" :style="{ background: card.color }">
            <el-icon :size="22"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" v-if="detailStats" class="detail-row">
      <el-col :span="24" :md="12">
        <el-card class="detail-card" shadow="never">
          <template #header>
            <span class="card-header-title">用户概览</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="注册用户数">{{ detailStats.total_users ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="作品总数">{{ detailStats.total_artworks ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="画库总数">{{ detailStats.total_libraries ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="本月AI调用">{{ detailStats.ai_calls_today ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="24" :md="12">
        <el-card class="detail-card" shadow="never">
          <template #header>
            <span class="card-header-title">存储概览</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="总存储用量">{{ formatBytes(detailStats.total_storage_bytes ?? 0) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { User, Picture, Cpu, Coin } from '@element-plus/icons-vue'
import { adminApi } from '../../api/adminApi'

const stats = ref(null)
const detailStats = ref(null)

const statCards = ref([
  { label: '用户总数', value: '--', icon: User, color: 'var(--cinnabar)' },
  { label: '作品总数', value: '--', icon: Picture, color: 'var(--gold)' },
  { label: '今日AI调用', value: '--', icon: Cpu, color: '#5a8a4a' },
  { label: '总存储用量', value: '--', icon: Coin, color: '#3898ec' },
])

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

onMounted(async () => {
  try {
    const res = await adminApi.getStats()
    stats.value = res
    detailStats.value = res

    statCards.value[0].value = res.total_users ?? '--'
    statCards.value[1].value = res.total_artworks ?? '--'
    statCards.value[2].value = res.ai_calls_today ?? '--'
    statCards.value[3].value = formatBytes(res.total_storage_bytes ?? 0)
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
})
</script>

<style scoped>
.admin-dashboard {
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

.stats-row {
  margin-bottom: var(--space-xl);
}

.stat-card {
  margin-bottom: 20px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-xl);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--pure-white);
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 28px;
  font-weight: 600;
  color: var(--near-black);
  line-height: 1.2;
}

.stat-label {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  color: var(--stone-gray);
  margin-top: 4px;
}

.detail-row {
  margin-top: var(--space-sm);
}

.detail-card {
  margin-bottom: 20px;
}

.card-header-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--near-black);
}
</style>
