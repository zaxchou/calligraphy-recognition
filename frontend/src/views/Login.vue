<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <img src="/logo.png" alt="墨" class="login-logo">
        <h1 class="login-title">中国画与书法</h1>
        <p class="login-subtitle">AI 综合分析系统</p>
      </div>

      <div class="login-body">
        <p class="login-desc">登录后可收藏作品、管理个人画库</p>

        <div class="mock-section">
          <p class="mock-tip">开发模式下使用模拟登录</p>
          <el-input
            v-model="mockCode"
            placeholder="输入任意昵称作为 mock code"
            size="large"
            class="mock-input"
            @keyup.enter="handleLogin"
          />
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            class="login-btn"
          >
            {{ loading ? '登录中...' : '模拟登录' }}
          </el-button>
        </div>

        <div class="login-footer-text">
          <p>正式环境将使用微信扫码登录</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const mockCode = ref('')
const loading = ref(false)

async function handleLogin() {
  const code = mockCode.value.trim() || 'default_user'
  loading.value = true
  try {
    await authStore.login(`mock_${code}`)
    ElMessage.success(`登录成功，欢迎 ${authStore.nickname}`)
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.msg || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.login-card {
  background: var(--ivory, #faf9f5);
  border: 1px solid var(--border-cream, #e8e4d8);
  border-radius: 12px;
  padding: 3rem 2rem;
  width: 100%;
  max-width: 400px;
  text-align: center;
}

.login-header {
  margin-bottom: 2rem;
}

.login-logo {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.login-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--near-black, #1a1a1a);
  margin: 0 0 4px 0;
}

.login-subtitle {
  font-size: 13px;
  color: var(--stone-gray, #888);
  margin: 0;
}

.login-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.login-desc {
  font-size: 14px;
  color: var(--olive-gray, #666);
  margin: 0;
}

.mock-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.mock-tip {
  font-size: 12px;
  color: var(--gold, #c8a45c);
  margin: 0;
}

.mock-input {
  width: 100%;
}

.login-btn {
  width: 100%;
}

.login-footer-text {
  margin-top: 1rem;
}

.login-footer-text p {
  font-size: 12px;
  color: var(--warm-silver, #999);
  margin: 0;
}
</style>
