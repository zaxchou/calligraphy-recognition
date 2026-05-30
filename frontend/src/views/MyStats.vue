<template>
  <div class="my-stats-page">
    <div class="page-header">
      <h1>📈 我的统计</h1>
      <p class="page-desc">我的作品库数据分析</p>
    </div>

    <div v-if="!authStore.isLoggedIn" class="login-hint">
      <el-icon :size="40"><Lock /></el-icon>
      <p>请先登录后查看个人统计</p>
    </div>

    <div v-else-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <el-button @click="loadStats">重试</el-button>
    </div>

    <div v-else-if="!stats || stats.total_artworks === 0" class="empty-state">
      <el-icon :size="48" color="#ccc"><DataAnalysis /></el-icon>
      <p>还没有上传任何作品，统计数据为空</p>
      <el-button type="primary" @click="$router.push('/libraries')">去上传作品</el-button>
    </div>

    <template v-else>
      <!-- 概览卡片 -->
      <div class="overview-cards">
        <div class="stat-card">
          <span class="stat-value">{{ stats.total_artworks }}</span>
          <span class="stat-label">我的作品总数</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ stats.total_libraries || 0 }}</span>
          <span class="stat-label">我的作品库</span>
        </div>
      </div>

      <!-- 情感分布 -->
      <div class="stat-section" v-if="stats.sentiment_distribution">
        <h3>题跋情感分布</h3>
        <table class="d-table">
          <tr class="d-tr d-th">
            <td class="d-td">情感</td><td class="d-td">数量</td><td class="d-td">占比</td>
          </tr>
          <tr class="d-tr" v-for="(v, k) in stats.sentiment_distribution" :key="k">
            <td class="d-td">
              <span class="d-dot" :style="{ background: k === 'positive' ? '#8fbc8f' : k === 'negative' ? '#cd8c8c' : '#ccc' }"></span>
              {{ { positive: '正面', negative: '负面', neutral: '中性' }[k] || k }}
            </td>
            <td class="d-td">{{ v }}</td>
            <td class="d-td">{{ stats.total_artworks ? ((v / stats.total_artworks) * 100).toFixed(1) + '%' : '-' }}</td>
          </tr>
        </table>
      </div>

      <!-- 时期分布 -->
      <div class="stat-section" v-if="stats.period_distribution">
        <h3>时期分布</h3>
        <table class="d-table">
          <tr class="d-tr d-th">
            <td class="d-td">时期</td><td class="d-td">数量</td><td class="d-td">占比</td>
          </tr>
          <tr class="d-tr" v-for="(v, k) in stats.period_distribution" :key="k">
            <td class="d-td">{{ k || '未知' }}</td>
            <td class="d-td">{{ v }}</td>
            <td class="d-td">{{ stats.total_artworks ? ((v / stats.total_artworks) * 100).toFixed(1) + '%' : '-' }}</td>
          </tr>
        </table>
      </div>

      <!-- 尺寸分布 -->
      <div class="stat-section" v-if="stats.size_distribution">
        <h3>尺寸分布</h3>
        <table class="d-table">
          <tr class="d-tr d-th">
            <td class="d-td">分类</td><td class="d-td">数量</td>
          </tr>
          <tr class="d-tr" v-for="(v, k) in stats.size_distribution" :key="k">
            <td class="d-td">{{ k }}</td>
            <td class="d-td">{{ v }}</td>
          </tr>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, Loading, DataAnalysis } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import api from '../api'

const authStore = useAuthStore()
const stats = ref(null)
const loading = ref(false)
const error = ref('')

onMounted(() => {
  if (authStore.isLoggedIn) loadStats()
})

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get('/tiba/stats/my')
    stats.value = data
  } catch (e) {
    error.value = e?.response?.data?.detail || '加载统计失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.my-stats-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

.page-header {
  text-align: center;
  margin-bottom: 2rem;
}

.page-header h1 {
  font-family: 'Noto Serif SC', serif;
  font-size: 24px;
  color: var(--near-black);
  margin: 0 0 8px 0;
}

.page-desc { font-size: 14px; color: var(--stone-gray); }

.overview-cards {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  flex: 1;
  text-align: center;
  padding: 1.5rem;
  background: var(--ivory, #faf9f5);
  border: 1px solid var(--border-cream, #e8e4d8);
  border-radius: 12px;
}

.stat-value { display: block; font-size: 32px; font-weight: 700; color: var(--gold, #c8a45c); }
.stat-label { display: block; font-size: 13px; color: var(--stone-gray); margin-top: 4px; }

.stat-section { margin-bottom: 1.5rem; }
.stat-section h3 { font-size: 16px; margin-bottom: 8px; color: var(--near-black); }

.d-table { width: 100%; border: 1px solid #e0d8c8; border-radius: 12px; overflow: hidden; }
.d-tr { display: flex; border-bottom: 1px solid #f0ebe0; }
.d-tr:last-child { border-bottom: none; }
.d-tr.d-th { background: #faf8f5; }
.d-tr.d-th .d-td { font-weight: 600; color: #5b7a8c; font-size: 14px; }
.d-td { flex: 1; padding: 12px 16px; font-size: 14px; color: #2c2416; text-align: center; }
.d-td:first-child { text-align: left; }
.d-dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: middle; }

.login-hint, .loading-state, .empty-state, .error-state {
  text-align: center; padding: 3rem; color: var(--stone-gray);
}
</style>
