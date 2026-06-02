import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])          // 会话列表
  const currentSessionId = ref(null) // 当前活跃会话ID
  const loading = ref(false)

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) || null
  )

  // 获取会话列表
  async function fetchSessions() {
    loading.value = true
    try {
      const data = await api.get('/knowledge/chat/sessions')
      sessions.value = (data || [])
    } catch (e) {
      // 未登录时静默失败
      if (e?.response?.status !== 401) console.error('获取会话列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 获取会话历史消息
  async function fetchMessages(sessionId) {
    try {
      const data = await api.get(`/knowledge/chat/sessions/${sessionId}/messages`)
      return (data || []).map(m => ({
        role: m.role,
        content: m.content,
        sources: m.sources || null,
      }))
    } catch (e) {
      console.error('获取消息失败:', e)
      return []
    }
  }

  // 删除会话
  async function deleteSession(sessionId) {
    try {
      await api.delete(`/knowledge/chat/sessions/${sessionId}`)
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
      }
    } catch (e) {
      console.error('删除会话失败:', e)
    }
  }

  // 创建新会话（后端会自动创建，这里只设本地状态）
  function startNewSession() {
    currentSessionId.value = null
  }

  function setCurrentSession(sessionId) {
    currentSessionId.value = sessionId
  }

  return {
    sessions, currentSessionId, currentSession, loading,
    fetchSessions, fetchMessages, deleteSession,
    startNewSession, setCurrentSession,
  }
})
