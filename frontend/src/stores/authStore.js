import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || null)
  let parsedUser = null
  try { parsedUser = JSON.parse(localStorage.getItem(USER_KEY)) } catch {}
  const userInfo = ref(parsedUser)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const userId = computed(() => userInfo.value?.user_id || null)
  const nickname = computed(() => userInfo.value?.nickname || '用户')
  const avatarUrl = computed(() => userInfo.value?.avatar_url || '')
  const role = computed(() => userInfo.value?.role || 'guest')

  // 角色判断
  const isAdmin = computed(() => role.value === 'admin' || role.value === 'super_admin')
  const isSuperAdmin = computed(() => role.value === 'super_admin')
  const isEditor = computed(() => role.value === 'super_admin' || role.value === 'admin' || role.value === 'editor')
  const score = computed(() => userInfo.value?.score || 0)

  function _saveSession(data) {
    token.value = data.token
    userInfo.value = {
      user_id: data.user_id,
      uid: data.uid || '',
      nickname: data.nickname || `用户${data.user_id}`,
      avatar_url: data.avatar_url || '',
      phone: data.phone || '',
      role: data.role || 'reader',
      score: data.score || 0,
    }
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, JSON.stringify(userInfo.value))
  }

  // ── 验证码登录 ──
  async function loginByCode(phone, code) {
    loading.value = true
    try {
      const resp = await api.post('/auth/login', { phone, code })
      _saveSession(resp)
      return resp
    } finally {
      loading.value = false
    }
  }

  // ── 密码登录 ──
  async function loginByPassword(account, password) {
    loading.value = true
    try {
      const resp = await api.post('/auth/login-password', { account, password })
      _saveSession(resp)
      return resp
    } finally {
      loading.value = false
    }
  }

  // ── 发送验证码 ──
  async function sendCode(phone) {
    return api.post('/auth/send-code', { phone })
  }

  // ── 注册 ──
  async function register({ phone, code, username, nickname, password }) {
    loading.value = true
    try {
      const payload = {}
      if (phone) { payload.phone = phone; payload.code = code }
      if (username) { payload.username = username }
      if (nickname) payload.nickname = nickname
      if (password) payload.password = password
      const resp = await api.post('/auth/register', payload)
      _saveSession(resp)
      return resp
    } finally {
      loading.value = false
    }
  }

  // ── 微信登录（兼容） ──
  async function login(code) {
    loading.value = true
    try {
      const resp = await api.post('/auth/wechat-login', { code })
      _saveSession(resp)
      return resp
    } finally {
      loading.value = false
    }
  }

  function logout() {
    token.value = null
    userInfo.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  function getAuthHeader() {
    return token.value ? `Bearer ${token.value}` : null
  }

  // 启动时自动刷新用户信息（同步 DB 中最新的 role）
  async function refreshProfile() {
    if (!token.value) return
    try {
      const resp = await api.get('/auth/profile')
      userInfo.value = {
        user_id: resp.user_id,
        uid: resp.uid || '',
        nickname: resp.nickname || `用户${resp.user_id}`,
        avatar_url: resp.avatar_url || '',
        phone: resp.phone || '',
        role: resp.role || 'reader',
        score: resp.score || 0,
      }
      localStorage.setItem(USER_KEY, JSON.stringify(userInfo.value))
    } catch (e) {
      // token invalid, clear
      if (e?.response?.status === 401) logout()
    }
  }

  return {
    token, userInfo, loading,
    isLoggedIn, userId, nickname, avatarUrl, role,
    isAdmin, isSuperAdmin, isEditor, score,
    loginByCode, loginByPassword, sendCode, register, login,
    logout, getAuthHeader, refreshProfile,
  }
})
