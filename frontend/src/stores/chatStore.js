import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])          // 会话列表
  const currentSessionId = ref(null) // 当前活跃会话ID（KnowledgeSearch 用）
  const floatSessionId = ref(null)   // 浮窗会话ID（ChatFloat 用，跨组件生命周期）
  const artistExpertSessionId = ref(null) // 画家专家会话ID
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
    await api.delete(`/knowledge/chat/sessions/${sessionId}`)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
    }
    if (floatSessionId.value === sessionId) {
      floatSessionId.value = null
    }
    if (artistExpertSessionId.value === sessionId) {
      artistExpertSessionId.value = null
    }
  }

  // 创建新会话（后端会自动创建，这里只设本地状态）
  function startNewSession() {
    currentSessionId.value = null
  }

  function setCurrentSession(sessionId) {
    currentSessionId.value = sessionId
  }

  function setFloatSession(sessionId) {
    floatSessionId.value = sessionId
  }

  function setArtistExpertSession(sessionId) {
    artistExpertSessionId.value = sessionId
  }

  return {
    sessions, currentSessionId, floatSessionId, artistExpertSessionId, currentSession, loading,
    fetchSessions, fetchMessages, deleteSession,
    startNewSession, setCurrentSession, setFloatSession, setArtistExpertSession,
  }
})
