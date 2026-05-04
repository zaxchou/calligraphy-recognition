/**
 * 管理后台密码验证
 *
 * 简单的前端鉴权，密码缓存在 localStorage。
 * 仅用于隐藏编辑/删除按钮和限制管理页面访问，非真正安全措施。
 */
import { ref, computed } from 'vue'

const STORAGE_KEY = 'admin_auth'
const CACHE_HOURS = 24
const DEFAULT_PASSWORD = 'ilovehouhan'

const _authenticated = ref(!!localStorage.getItem(STORAGE_KEY))
const _expiry = localStorage.getItem(STORAGE_KEY)
if (_expiry) {
  const expired = Date.now() > parseInt(_expiry, 10)
  if (expired) {
    localStorage.removeItem(STORAGE_KEY)
    _authenticated.value = false
  }
}

export function useAdminAuth() {
  const isAuthenticated = computed(() => _authenticated.value)

  function login(password) {
    if (password === DEFAULT_PASSWORD) {
      const expiry = Date.now() + CACHE_HOURS * 60 * 60 * 1000
      localStorage.setItem(STORAGE_KEY, String(expiry))
      _authenticated.value = true
      return true
    }
    return false
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY)
    _authenticated.value = false
  }

  return { isAuthenticated, login, logout }
}
