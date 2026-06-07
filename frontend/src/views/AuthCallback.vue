<template>
  <div class="callback-container">
    <div class="callback-card">
      <div class="callback-icon">{{ icon }}</div>
      <p class="callback-text">{{ message }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const status = ref('loading')
const message = ref('正在登录...')

const icon = computed(() => {
  if (status.value === 'success') return '✓'
  if (status.value === 'error') return '✗'
  return '...'
})

onMounted(async () => {
  // 检查是否有错误参数（后端 redirect 过来的）
  const error = route.query.error
  if (error) {
    status.value = 'error'
    message.value = decodeURIComponent(error)
    return
  }

  const token = route.query.token
  const isNew = route.query.is_new === 'true'
  const rawRedirect = route.query.redirect || '/'  // 在 replaceState 前缓存

  if (!token) {
    status.value = 'error'
    message.value = '登录失败：未收到授权信息'
    return
  }

  // 清除 URL 中的 token（防泄漏）
  window.history.replaceState({}, '', '/#/auth/callback')

  // 保存 token 并验证
  localStorage.setItem('auth_token', token)
  authStore.token = token

  try {
    await authStore.refreshProfile()
    status.value = 'success'
    message.value = isNew ? '注册成功！正在跳转...' : '登录成功！正在跳转...'

    // 校验 redirect 参数（防 open redirect）
    let redirect = rawRedirect
    if (!redirect.startsWith('/') || redirect.startsWith('//')) {
      redirect = '/'
    }

    setTimeout(() => { router.push(redirect) }, 1000)
  } catch (e) {
    // token 无效，清除
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    authStore.token = null
    authStore.userInfo = null
    status.value = 'error'
    message.value = '登录失败：授权信息无效，请重试'
  }
})
</script>

<style scoped>
.callback-container {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}
.callback-card {
  text-align: center;
  background: var(--ivory, #faf9f5);
  border: 1px solid var(--border-cream, #e8e4d8);
  border-radius: 12px;
  padding: 48px 40px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}
.callback-icon {
  font-size: 48px;
  margin-bottom: 16px;
  color: var(--cinnabar, #c45a3c);
}
.callback-text {
  font-size: 16px;
  color: var(--near-black, #1c1c1c);
}
</style>
