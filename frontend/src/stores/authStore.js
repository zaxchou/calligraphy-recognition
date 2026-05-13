import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || null)
  const userInfo = ref(JSON.parse(localStorage.getItem(USER_KEY) || 'null'))
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const nickname = computed(() => userInfo.value?.nickname || '用户')
  const avatarUrl = computed(() => userInfo.value?.avatar_url || '')

  async function login(code) {
    loading.value = true
    try {
      const resp = await api.post('/auth/wechat-login', { code })
      token.value = resp.token
      userInfo.value = {
        user_id: resp.user_id,
        nickname: resp.nickname || `用户${resp.user_id}`,
        avatar_url: resp.avatar_url || '',
        is_new_user: resp.is_new_user,
      }
      localStorage.setItem(TOKEN_KEY, resp.token)
      localStorage.setItem(USER_KEY, JSON.stringify(userInfo.value))
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

  return {
    token, userInfo, loading,
    isLoggedIn, nickname, avatarUrl,
    login, logout, getAuthHeader,
  }
})
