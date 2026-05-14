<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <img src="/logo.png" alt="墨" class="login-logo">
        <h1 class="login-title">中国画与书法</h1>
        <p class="login-subtitle">AI 综合分析系统</p>
      </div>

      <div class="login-body">
        <!-- 模式切换 -->
        <div class="mode-tabs">
          <button
            :class="['mode-tab', { active: mode === 'code' }]"
            @click="mode = 'code'"
          >验证码登录</button>
          <button
            :class="['mode-tab', { active: mode === 'password' }]"
            @click="mode = 'password'"
          >密码登录</button>
        </div>

        <!-- 手机号输入 -->
        <div class="form-group">
          <el-input
            v-model="phone"
            placeholder="请输入手机号"
            size="large"
            maxlength="11"
            type="tel"
          />
        </div>

        <!-- 验证码模式 -->
        <template v-if="mode === 'code'">
          <div class="form-group code-group">
            <el-input
              v-model="code"
              placeholder="验证码"
              size="large"
              maxlength="6"
              class="code-input"
              @keyup.enter="handleCodeLogin"
            />
            <el-button
              size="large"
              :disabled="countdown > 0"
              :loading="sendingCode"
              @click="handleSendCode"
              class="send-code-btn"
            >
              {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
            </el-button>
          </div>

          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleCodeLogin"
            class="login-btn"
          >
            {{ loading ? '登录中...' : '登录 / 注册' }}
          </el-button>
          <p class="login-hint">未注册手机号将自动注册</p>
        </template>

        <!-- 密码模式 -->
        <template v-if="mode === 'password'">
          <div class="form-group">
            <el-input
              v-model="password"
              placeholder="请输入密码"
              size="large"
              type="password"
              show-password
              @keyup.enter="handlePasswordLogin"
            />
          </div>

          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handlePasswordLogin"
            class="login-btn"
          >
            {{ loading ? '登录中...' : '密码登录' }}
          </el-button>
          <p class="login-hint">未设置密码请使用验证码登录</p>
        </template>

        <!-- 微信登录（兼容） -->
        <div class="wechat-section">
          <div class="divider-text"><span>微信小程序用户</span></div>
          <el-input
            v-model="mockCode"
            placeholder="输入昵称模拟微信登录"
            size="large"
            class="mock-input"
            @keyup.enter="handleWechatLogin"
          />
          <el-button
            size="large"
            :loading="wechatLoading"
            @click="handleWechatLogin"
            class="wechat-btn"
          >
            {{ wechatLoading ? '登录中...' : '模拟微信登录' }}
          </el-button>
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

const mode = ref('code')  // 'code' | 'password'
const phone = ref('')
const code = ref('')
const password = ref('')
const mockCode = ref('')
const loading = ref(false)
const wechatLoading = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)

let countdownTimer = null

// ── 发送验证码 ──
async function handleSendCode() {
  const p = phone.value.trim()
  if (!p || p.length < 11) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  sendingCode.value = true
  try {
    await authStore.sendCode(p)
    ElMessage.success('验证码已发送（开发模式：123456）')
    countdown.value = 60
    countdownTimer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
    }, 1000)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.msg || '发送失败')
  } finally {
    sendingCode.value = false
  }
}

// ── 验证码登录 ──
async function handleCodeLogin() {
  const p = phone.value.trim()
  if (!p || p.length < 11) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (!code.value.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }
  loading.value = true
  try {
    const resp = await authStore.loginByCode(p, code.value.trim())
    ElMessage.success(resp.is_new_user ? '注册并登录成功' : `登录成功，欢迎 ${authStore.nickname}`)
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.msg || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}

// ── 密码登录 ──
async function handlePasswordLogin() {
  const p = phone.value.trim()
  if (!p || p.length < 11) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  loading.value = true
  try {
    await authStore.loginByPassword(p, password.value)
    ElMessage.success(`登录成功，欢迎 ${authStore.nickname}`)
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.msg || '登录失败')
  } finally {
    loading.value = false
  }
}

// ── 微信登录（兼容） ──
async function handleWechatLogin() {
  const c = mockCode.value.trim() || 'default_user'
  wechatLoading.value = true
  try {
    await authStore.login(`mock_${c}`)
    ElMessage.success(`登录成功，欢迎 ${authStore.nickname}`)
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.msg || '登录失败，请重试')
  } finally {
    wechatLoading.value = false
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
  padding: 40px 36px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  margin-bottom: 12px;
}

.login-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 20px;
  font-weight: 500;
  color: var(--near-black, #1c1c1c);
  margin-bottom: 4px;
}

.login-subtitle {
  font-size: 13px;
  color: var(--stone-gray, #8c8c8c);
}

.login-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 模式切换 */
.mode-tabs {
  display: flex;
  border: 1px solid var(--border-warm, #ddd);
  border-radius: 8px;
  overflow: hidden;
}

.mode-tab {
  flex: 1;
  padding: 10px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--stone-gray, #8c8c8c);
  cursor: pointer;
  transition: all 0.2s;
}

.mode-tab.active {
  background: var(--cinnabar, #c45a3c);
  color: #fff;
}

/* 表单 */
.form-group {
  width: 100%;
}

.code-group {
  display: flex;
  gap: 12px;
}

.code-input {
  flex: 1;
}

.send-code-btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.login-btn {
  width: 100%;
  margin-top: 4px;
}

.login-hint {
  font-size: 12px;
  color: var(--stone-gray, #8c8c8c);
  text-align: center;
  margin-top: -8px;
}

/* 微信登录区域 */
.wechat-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-cream, #e8e4d8);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.divider-text {
  text-align: center;
  font-size: 12px;
  color: var(--stone-gray, #8c8c8c);
  margin-bottom: 4px;
}

.divider-text span {
  padding: 0 12px;
}

.wechat-btn {
  width: 100%;
}
</style>
