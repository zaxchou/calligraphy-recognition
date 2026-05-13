<template>
  <div class="admin-settings">
    <div class="page-header">
      <h1 class="page-title">系统配置</h1>
      <p class="page-subtitle">查看当前系统配额与参数配置</p>
    </div>

    <el-card class="config-card" shadow="never" v-loading="loading">
      <template #header>
        <span class="card-header-title">配额配置</span>
      </template>
      <el-descriptions :column="2" border v-if="config">
        <el-descriptions-item label="免费用户AI调用次数">
          <span class="config-value">{{ config.free_ai_calls ?? config.free_user?.ai_calls ?? config.ai_calls_free ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付费用户AI调用次数">
          <span class="config-value">{{ config.premium_ai_calls ?? config.premium_user?.ai_calls ?? config.ai_calls_premium ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="免费用户存储空间">
          <span class="config-value">{{ formatStorage(config.free_storage ?? config.free_user?.storage ?? config.storage_free) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付费用户存储空间">
          <span class="config-value">{{ formatStorage(config.premium_storage ?? config.premium_user?.storage ?? config.storage_premium) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="免费用户作品库数量">
          <span class="config-value">{{ config.free_libraries ?? config.free_user?.libraries ?? config.libraries_free ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付费用户作品库数量">
          <span class="config-value">{{ config.premium_libraries ?? config.premium_user?.libraries ?? config.libraries_premium ?? '--' }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <div v-else-if="!loading" class="empty-state">
        暂无配置数据
      </div>
    </el-card>

    <el-card class="config-card" shadow="never" v-loading="loading" v-if="config">
      <template #header>
        <span class="card-header-title">其他参数</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="最大上传文件大小">
          <span class="config-value">{{ formatStorage(config.max_upload_size) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="允许的文件类型">
          <span class="config-value">{{ config.allowed_file_types?.join(', ') ?? config.allowed_types?.join(', ') ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="注册是否需要审核">
          <el-tag :type="config.registration_review ? 'warning' : 'success'" size="small">
            {{ config.registration_review ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="系统维护模式">
          <el-tag :type="config.maintenance_mode ? 'danger' : 'success'" size="small">
            {{ config.maintenance_mode ? '开启' : '关闭' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="config-card" shadow="never" v-loading="loading" v-if="config">
      <template #header>
        <span class="card-header-title">管理员信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="管理员账号">
          <span class="config-value">{{ config.admin_email ?? config.admin_username ?? config.admin_account ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="API版本">
          <span class="config-value">{{ config.api_version ?? 'v1' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="服务器时间">
          <span class="config-value">{{ config.server_time ?? '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="服务状态">
          <el-tag :type="config.service_status === 'healthy' ? 'success' : 'warning'" size="small">
            {{ config.service_status === 'healthy' ? '正常运行' : (config.service_status ?? '--') }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <div class="footer-note">
      <el-icon><InfoFilled /></el-icon>
      <span>配置修改功能将在后续版本中开放</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
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
