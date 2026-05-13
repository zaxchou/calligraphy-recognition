import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // ============ State ============
  
  // 书籍列表
  const books = ref([])
  const booksLoading = ref(false)
  const booksError = ref(null)
  
  // 任务列表
  const tasks = ref([])
  const tasksLoading = ref(false)
  
  // 当前书籍详情
  const currentBook = ref(null)
  const bookChunks = ref([])
  const bookImages = ref([])
  
  // 搜索
  const searchQuery = ref('')
  const searchResults = ref([])
  const searchLoading = ref(false)
  const searchProgress = ref(0)
  const searchHistory = ref([])
  
  // AI 摘要
  const aiSummary = ref(null)
  const aiSummaryLoading = ref(false)
  const queryRewrite = ref(null)
  const relatedImages = ref([])  // 相关配图（跨模态搜索结果中的图像）
  
  // 上传状态
  const uploadProgress = ref(0)
  const uploadStatus = ref('') // 'idle' | 'uploading' | 'processing' | 'completed' | 'error'
  const uploadError = ref(null)
  const processingProgress = ref(0)
  const processingStage = ref('')
  const currentTaskId = ref(null)
  let processingInterval = null
  
  // 统计
  const stats = ref(null)
  
  // ============ Getters ============
  
  const completedBooks = computed(() => 
    books.value.filter(b => b.status === 'completed')
  )
  
  const processingBooks = computed(() => 
    books.value.filter(b => b.status === 'processing')
  )
  
  const activeTasks = computed(() => 
    tasks.value.filter(t => t.status === 'processing' || t.status === 'queued')
  )
  
  const failedTasks = computed(() => 
    tasks.value.filter(t => t.status === 'failed')
  )
  
  // ============ Actions ============
  
  // 获取书籍列表
  async function fetchBooks(params = {}) {
    booksLoading.value = true
    booksError.value = null
    
    try {
      const response = await api.get(`/knowledge/books`, { params })
      books.value = response
      return response
    } catch (error) {
      booksError.value = error.message || '获取书籍列表失败'
      throw error
    } finally {
      booksLoading.value = false
    }
  }
  
  // 获取书籍详情
  async function fetchBookDetail(bookId) {
    try {
      const response = await api.get(`/knowledge/books/${bookId}`)
      currentBook.value = response
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 轮询任务进度
  function startPollingTask(taskId) {
    if (processingInterval) {
      clearInterval(processingInterval)
    }
    
    currentTaskId.value = taskId
    processingInterval = setInterval(async () => {
      try {
        const task = await fetchTaskDetail(taskId)
        processingProgress.value = task.progress || 0
        processingStage.value = task.stage || '处理中...'
        
        if (task.status === 'completed') {
          uploadStatus.value = 'completed'
          clearInterval(processingInterval)
          processingInterval = null
        } else if (task.status === 'failed') {
          uploadStatus.value = 'error'
          uploadError.value = task.error_message || '处理失败'
          clearInterval(processingInterval)
          processingInterval = null
        }
      } catch (error) {
        console.error('获取任务进度失败:', error)
      }
    }, 1000)
  }
  
  // 上传 PDF
  async function uploadPdf(file, config = {}, onProgress) {
    uploadStatus.value = 'uploading'
    uploadProgress.value = 0
    uploadError.value = null
    processingProgress.value = 0
    processingStage.value = ''
    
    const formData = new FormData()
    formData.append('file', file)
    formData.append('chunk_strategy', config.chunkStrategy || 'semantic')
    formData.append('chunk_size', config.chunkSize || 500)
    formData.append('parser_backend', config.parserBackend || 'mineru')
    if (config.seriesId) {
      formData.append('series_id', config.seriesId)
    }
    formData.append('page_offset', config.pageOffset || 1)
    
    try {
      const response = await api.post(`/knowledge/books/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            uploadProgress.value = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            )
          }
          if (onProgress) {
            onProgress(uploadProgress.value)
          }
        }
      })
      
      uploadStatus.value = 'processing'
      // 开始轮询任务进度
      if (response.task_id) {
        startPollingTask(response.task_id)
      }
      return response
    } catch (error) {
      uploadStatus.value = 'error'
      uploadError.value = error.response?.data?.detail || '上传失败'
      throw error
    }
  }
  
  // 删除书籍
  async function deleteBook(bookId) {
    try {
      await api.delete(`/knowledge/books/${bookId}`)
      // 从列表中移除
      books.value = books.value.filter(b => b.id !== bookId)
      return true
    } catch (error) {
      throw error
    }
  }
  
  // 重新入库书籍 - 异步模式：返回 task_id，轮询进度
  async function reingestBook(bookId, config = {}) {
    try {
      const formData = new FormData()
      formData.append('chunk_strategy', config.chunkStrategy || 'semantic')
      formData.append('chunk_size', config.chunkSize || 500)
      formData.append('parser_backend', config.parserBackend || 'mineru')
      
      const response = await api.post(`/knowledge/books/${bookId}/reingest`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      // 后端立即返回 task_id，开始轮询进度
      if (response.task_id) {
        startPollingTask(response.task_id)
      }
      
      // 刷新书籍列表
      await fetchBooks()
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 获取任务列表
  async function fetchTasks(params = {}) {
    tasksLoading.value = true
    
    try {
      const response = await api.get(`/knowledge/tasks`, { params })
      tasks.value = response
      return response
    } catch (error) {
      throw error
    } finally {
      tasksLoading.value = false
    }
  }
  
  // 获取任务详情
  async function fetchTaskDetail(taskId) {
    try {
      const response = await api.get(`/knowledge/tasks/${taskId}`)
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 重试任务
  async function retryTask(taskId) {
    try {
      const response = await api.post(`/knowledge/tasks/${taskId}/retry`)
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 取消任务
  async function cancelTask(taskId) {
    try {
      await api.post(`/knowledge/tasks/${taskId}/cancel`)
      return true
    } catch (error) {
      throw error
    }
  }
  
  // 获取书籍文本块
  async function fetchBookChunks(bookId, params = {}) {
    try {
      const response = await api.get(`/knowledge/books/${bookId}/chunks`, { params })
      bookChunks.value = response
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 获取书籍单个文本块的完整内容（用于翻页）
  async function fetchChunkDetail(bookId, chunkIndex) {
    try {
      const response = await api.get(`/knowledge/books/${bookId}/chunks`, {
        params: { offset: chunkIndex, limit: 1 }
      })
      if (response && response.length > 0) {
        return response[0]
      }
      return null
    } catch (error) {
      throw error
    }
  }
  
  // 获取书籍图像
  async function fetchBookImages(bookId, params = {}) {
    try {
      const response = await api.get(`/knowledge/books/${bookId}/images`, { params })
      bookImages.value = response
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 搜索
  async function search(query, options = {}) {
    searchQuery.value = query
    searchLoading.value = true
    searchProgress.value = 0
    aiSummary.value = null
    aiSummaryLoading.value = false
    queryRewrite.value = null
    relatedImages.value = []

    // 模拟进度条
    const progressInterval = setInterval(() => {
      if (searchProgress.value < 80) {
        searchProgress.value += Math.random() * 15
      }
    }, 200)

    try {
      const response = await api.post(`/knowledge/search`, {
        query,
        book_ids: options.bookIds || [],
        limit: options.limit || 10,
        include_private: options.includePrivate || false,  // Phase 3b
      })

      clearInterval(progressInterval)
      searchProgress.value = 100

      searchResults.value = response.results || []

      // AI 摘要和改写信息（直接从响应获取，后端已并行完成）
      if (response.ai_summary && response.ai_summary.answer) {
        aiSummary.value = response.ai_summary
      }
      if (response.query_rewrite) {
        queryRewrite.value = response.query_rewrite
      }
      // 相关配图
      if (response.related_images && response.related_images.length > 0) {
        relatedImages.value = response.related_images
      }

      return response
    } catch (error) {
      clearInterval(progressInterval)
      throw error
    } finally {
      setTimeout(() => {
        searchLoading.value = false
        searchProgress.value = 0
      }, 300)
    }
  }

  // ═══ Phase 3a: 私人文档管理 ═══

  // 我的文档列表
  const myDocuments = ref([])
  const myDocsLoading = ref(false)

  async function fetchMyDocuments() {
    myDocsLoading.value = true
    try {
      const response = await api.get(`/knowledge/documents`)
      myDocuments.value = response
      return response
    } catch (error) {
      throw error
    } finally {
      myDocsLoading.value = false
    }
  }

  // 上传私人文档
  async function uploadPrivateDocument(file, title, onProgress) {
    const formData = new FormData()
    formData.append('file', file)
    if (title) formData.append('title', title)

    try {
      const response = await api.post(`/knowledge/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total))
          }
        },
      })
      await fetchMyDocuments()
      return response
    } catch (error) {
      throw error
    }
  }

  // 删除私人文档
  async function deleteMyDocument(documentId) {
    try {
      await api.delete(`/knowledge/documents/${documentId}`)
      myDocuments.value = myDocuments.value.filter(d => d.id !== documentId)
      return true
    } catch (error) {
      throw error
    }
  }

  // 获取私人文档分块
  async function fetchDocumentChunks(documentId, params = {}) {
    try {
      return await api.get(`/knowledge/documents/${documentId}/chunks`, { params })
    } catch (error) {
      throw error
    }
  }

  // 搜索是否包含私人文档
  const includePrivateInSearch = ref(false)
  
  // 获取搜索历史
  async function fetchSearchHistory(limit = 20) {
    try {
      const response = await api.get(`/knowledge/search/history`, {
        params: { limit }
      })
      searchHistory.value = response
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 删除单条搜索历史
  async function deleteSearchHistoryItem(historyId) {
    try {
      await api.delete(`/knowledge/search/history/${historyId}`)
      // 从本地列表中移除
      searchHistory.value = searchHistory.value.filter(h => h.id !== historyId)
      return true
    } catch (error) {
      throw error
    }
  }
  
  // 清空搜索历史
  async function clearSearchHistory() {
    try {
      await api.delete(`/knowledge/search/history`)
      searchHistory.value = []
      return true
    } catch (error) {
      throw error
    }
  }
  
  // 获取统计
  async function fetchStats() {
    try {
      const response = await api.get(`/knowledge/stats`)
      stats.value = response
      return response
    } catch (error) {
      throw error
    }
  }
  
  // 重置上传状态
  function resetUploadStatus() {
    uploadStatus.value = 'idle'
    uploadProgress.value = 0
    uploadError.value = null
    processingProgress.value = 0
    processingStage.value = ''
    currentTaskId.value = null
    if (processingInterval) {
      clearInterval(processingInterval)
      processingInterval = null
    }
  }
  
  // 清空搜索结果
  function clearSearchResults() {
    searchResults.value = []
    searchQuery.value = ''
    aiSummary.value = null
    queryRewrite.value = null
    relatedImages.value = []
  }
  
  return {
    // State
    books,
    booksLoading,
    booksError,
    tasks,
    tasksLoading,
    currentBook,
    bookChunks,
    bookImages,
    searchQuery,
    searchResults,
    searchLoading,
    searchProgress,
    searchHistory,
    aiSummary,
    aiSummaryLoading,
    queryRewrite,
    relatedImages,
    uploadProgress,
    uploadStatus,
    uploadError,
    processingProgress,
    processingStage,
    currentTaskId,
    stats,

    // Phase 3a: 私人文档
    myDocuments,
    myDocsLoading,
    includePrivateInSearch,

    // Getters
    completedBooks,
    processingBooks,
    activeTasks,
    failedTasks,

    // Actions
    fetchBooks,
    fetchBookDetail,
    uploadPdf,
    deleteBook,
    reingestBook,
    fetchTasks,
    fetchTaskDetail,
    retryTask,
    cancelTask,
    fetchBookChunks,
    fetchChunkDetail,
    fetchBookImages,
    search,
    fetchSearchHistory,
    deleteSearchHistoryItem,
    clearSearchHistory,
    fetchStats,
    resetUploadStatus,
    clearSearchResults,

    // Phase 3a: 私人文档 actions
    fetchMyDocuments,
    uploadPrivateDocument,
    deleteMyDocument,
    fetchDocumentChunks,
  }
})
