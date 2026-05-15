<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <img src="/logo.png" alt="墨" class="login-logo">
        <h1 class="login-title">墨林百科</h1>
        <p class="login-subtitle">最智能的中国画与书法大库</p>
      </div>

      <div class="login-body">
        <!-- 模式切换 -->
        <div class="mode-tabs">
          <button :class="['mode-tab', { active: mode === 'code' }]" @click="mode = 'code'">验证码登录</button>
          <button :class="['mode-tab', { active: mode === 'password' }]" @click="mode = 'password'">密码登录</button>
        </div>

        <!-- 手机号 / 账号 -->
        <input
          class="login-input"
          v-model="phone"
          :placeholder="mode === 'password' ? 'UID / 手机号 / 邮箱 / 昵称' : '请输入手机号'"
          maxlength="20"
          type="tel"
          @keyup.enter="mode === 'code' ? handleCodeLogin() : handlePasswordLogin()"
        />

        <!-- 验证码模式 -->
        <template v-if="mode === 'code'">
          <div class="code-row">
            <input class="login-input code-field" v-model="code" placeholder="验证码" maxlength="6" @keyup.enter="handleCodeLogin" />
            <button class="send-code-btn" :disabled="countdown > 0 || sendingCode" @click="handleSendCode">
              {{ countdown > 0 ? `${countdown}s` : (sendingCode ? '...' : '获取验证码') }}
            </button>
          </div>
          <button class="login-submit" :disabled="loading" @click="handleCodeLogin">
            {{ loading ? '登录中...' : '登录 / 注册' }}
          </button>
          <p class="login-hint">未注册手机号将自动注册</p>
        </template>

        <!-- 密码模式 -->
        <template v-if="mode === 'password'">
          <div class="password-row">
            <input class="login-input" v-model="password" placeholder="请输入密码" :type="showPwd ? 'text' : 'password'" @keyup.enter="handlePasswordLogin" />
            <button class="pwd-toggle" @click="showPwd = !showPwd" tabindex="-1">{{ showPwd ? '隐' : '显' }}</button>
          </div>
          <button class="login-submit" :disabled="loading" @click="handlePasswordLogin">
            {{ loading ? '登录中...' : '密码登录' }}
          </button>
          <p class="login-hint">未设置密码请使用验证码登录</p>
        </template>

        <!-- 微信登录 -->
        <div class="wechat-section">
          <div class="divider-text"><span>微信小程序用户</span></div>
          <input class="login-input" v-model="mockCode" placeholder="输入昵称模拟微信登录" @keyup.enter="handleWechatLogin" />
          <button class="login-submit wechat-submit" :disabled="wechatLoading" @click="handleWechatLogin">
            {{ wechatLoading ? '登录中...' : '模拟微信登录' }}
          </button>
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

const mode = ref('password')
const phone = ref('')
const code = ref('')
const password = ref('')
const mockCode = ref('')
const loading = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
const showPwd = ref(false)
const wechatLoading = ref(false)
let countdownTimer = null

function startCountdown() {
  countdown.value = 60
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) clearInterval(countdownTimer)
  }, 1000)
}

async function handleSendCode() {
  if (!phone.value.trim()) { ElMessage.warning('请输入手机号'); return }
  sendingCode.value = true
  try {
    await authStore.sendCode(phone.value.trim())
    ElMessage.success('验证码已发送（开发模式：123456）')
    startCountdown()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '发送失败')
  } finally { sendingCode.value = false }
}

async function handleCodeLogin() {
  if (!phone.value.trim() || !code.value.trim()) { ElMessage.warning('请输入手机号和验证码'); return }
  loading.value = true
  try {
    await authStore.loginByCode(phone.value.trim(), code.value.trim())
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '登录失败')
  } finally { loading.value = false }
}

async function handlePasswordLogin() {
  if (!phone.value.trim() || !password.value) { ElMessage.warning('请输入账号和密码'); return }
  loading.value = true
  try {
    await authStore.loginByPassword(phone.value.trim(), password.value)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '登录失败')
  } finally { loading.value = false }
}

async function handleWechatLogin() {
  const c = mockCode.value.trim() || 'default_user'
  wechatLoading.value = true
  try {
    await authStore.login(`mock_${c}`)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '登录失败')
  } finally { wechatLoading.value = false }
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

.login-header { text-align: center; margin-bottom: 32px; }
.login-logo { width: 48px; height: 48px; border-radius: 8px; margin-bottom: 12px; }
.login-title { font-family: 'Noto Serif SC', 'KaiTi', serif; font-size: 20px; font-weight: 500; color: var(--near-black, #1c1c1c); margin-bottom: 4px; }
.login-subtitle { font-size: 13px; color: var(--stone-gray, #8c8c8c); }

.login-body { display: flex; flex-direction: column; gap: 12px; }

/* 模式切换 */
.mode-tabs { display: flex; border: 1px solid var(--border-warm, #ddd); border-radius: 8px; overflow: hidden; }
.mode-tab { flex: 1; padding: 10px; border: none; background: transparent; font-size: 14px; color: var(--stone-gray, #8c8c8c); cursor: pointer; transition: all 0.2s; }
.mode-tab.active { background: var(--cinnabar, #c45a3c); color: #fff; }

/* === 原生 input，全部统一宽度 === */
.login-input {
  width: 100%;
  padding: 10px 14px;
  font-size: 15px;
  border: 1px solid #d0ccc0;
  border-radius: 8px;
  background: #fff;
  color: #2c2416;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
  line-height: 1.5;
}
.login-input:focus { border-color: #c8a45c; box-shadow: 0 0 0 2px rgba(200,164,92,0.15); }
.login-input::placeholder { color: #b0a890; }

/* 验证码行 */
.code-row { display: flex; gap: 10px; }
.code-field { flex: 1; }
.send-code-btn {
  flex-shrink: 0;
  padding: 0 16px;
  border: 1px solid #c8a45c;
  border-radius: 8px;
  background: transparent;
  color: #c8a45c;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.send-code-btn:hover { background: #fdf8f0; }
.send-code-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 密码行 */
.password-row { position: relative; }
.password-row .login-input { padding-right: 44px; }
.pwd-toggle {
  position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
  width: 36px; height: 32px; border: none; background: transparent;
  color: #999; font-size: 13px; cursor: pointer;
}

/* 提交按钮 */
.login-submit {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: var(--cinnabar, #c45a3c);
  color: #fff;
  font-size: 16px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.login-submit:hover { opacity: 0.9; }
.login-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.login-hint { font-size: 12px; color: var(--stone-gray, #8c8c8c); text-align: center; margin-top: -4px; }

/* 微信登录 */
.wechat-section { margin-top: 16px; padding-top: 16px; border-top: 1px solid #e8e4d8; display: flex; flex-direction: column; gap: 12px; }
.wechat-submit { background: #07c160; }
.wechat-submit:hover { background: #06ad56; }
.divider-text { text-align: center; font-size: 12px; color: var(--stone-gray, #8c8c8c); margin-bottom: 4px; }
.divider-text span { padding: 0 12px; }
</style>
