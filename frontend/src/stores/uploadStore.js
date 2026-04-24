/**
 * uploadStore — 批量上传状态管理
 * - 两阶段上传模型：快速上传 → 后台轮询分析结果
 * - localStorage 断点续传
 * - 失败项重试队列
 */
import { reactive, watch } from 'vue'

const STORAGE_KEY = 'tubi_upload_state'

// 单个上传项的状态
const ITEM_STATUSES = {
  PENDING: 'pending',       // 等待上传
  UPLOADING: 'uploading',   // 正在上传
  UPLOADED: 'uploaded',     // 上传完成，等待入队
  QUEUED: 'queued',         // 已入队，等待分析
  ANALYZING: 'analyzing',   // AI分析中
  DONE: 'done',             // 完成
  ERROR: 'error',           // 失败
}

// 错误码 → 用户友好提示
const ERROR_CODE_MAP = {
  REDIS_UNAVAILABLE: '队列服务不可用，已切换到备用模式',
  VL_TIMEOUT: 'AI分析超时，请重试',
  VL_FAILED: 'AI分析失败，请重试',
  OCR_FAILED: '文字识别失败，但图片已上传',
  FILE_NOT_FOUND: '图像文件不存在',
  WORKER_CRASHED: '分析服务已重启，请等待',
  FILE_TOO_LARGE: '文件过大，请压缩后重试',
  UPLOAD_FAILED: '上传失败，请重试',
  NETWORK_ERROR: '网络错误，正在重试...',
  QUEUE_UNAVAILABLE: '队列入列失败',
  ANALYSIS_TIMEOUT: '分析超时，请重试',
}

function getErrorMessage(errorCode, fallback = '') {
  return ERROR_CODE_MAP[errorCode] || fallback || '未知错误'
}

// 从 localStorage 恢复状态
function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const state = JSON.parse(raw)
    // 只恢复未完成的项
    if (state.items) {
      state.items = state.items.filter(
        item => ![ITEM_STATUSES.DONE].includes(item.status)
      )
    }
    return state
  } catch {
    return null
  }
}

function saveState(state) {
  try {
    const toSave = {
      items: state.items.map(item => ({
        id: item.id,
        fileId: item.fileId,
        fileName: item.fileName,
        fileUrl: item.fileUrl,
        status: item.status,
        errorCode: item.errorCode,
        errorMessage: item.errorMessage,
        position: item.position,
        estimatedWait: item.estimatedWait,
        uploadedAt: item.uploadedAt,
        imageId: item.imageId,
      })),
      batchId: state.batchId,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch {
    // localStorage 满了或不可用，忽略
  }
}

function clearState() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

// 创建响应式 store
export function createUploadStore() {
  const saved = loadState()

  const store = reactive({
    items: saved?.items || [],
    batchId: saved?.batchId || null,
    phase: 'idle',  // idle | uploading | enqueuing | polling | completed

    // 计算属性
    get totalCount() { return this.items.length },
    get pendingCount() { return this.items.filter(i => i.status === ITEM_STATUSES.PENDING).length },
    get uploadedCount() { return this.items.filter(i => [ITEM_STATUSES.UPLOADED, ITEM_STATUSES.QUEUED, ITEM_STATUSES.ANALYZING].includes(i.status)).length },
    get doneCount() { return this.items.filter(i => i.status === ITEM_STATUSES.DONE).length },
    get errorCount() { return this.items.filter(i => i.status === ITEM_STATUSES.ERROR).length },
    get failedItems() { return this.items.filter(i => i.status === ITEM_STATUSES.ERROR) },
    get isAllDone() { return this.items.length > 0 && this.items.every(i => i.status === ITEM_STATUSES.DONE || i.status === ITEM_STATUSES.ERROR) },
    get activeCount() { return this.items.filter(i => ![ITEM_STATUSES.DONE, ITEM_STATUSES.ERROR, ITEM_STATUSES.PENDING].includes(i.status)).length },

    // 进度百分比
    get progressPercent() {
      if (this.items.length === 0) return 0
      const done = this.doneCount + this.errorCount
      return Math.round((done / this.items.length) * 100)
    },
  })

  // 自动持久化
  watch(() => store.items, () => saveState(store), { deep: true })

  // ── 方法 ──

  /**
   * 初始化批量上传
   * @param {Array<{file: File, name: string}>} files
   */
  function initBatch(files) {
    store.items = files.map((f, idx) => ({
      id: `upload_${Date.now()}_${idx}`,
      fileId: null,
      fileName: f.name,
      fileUrl: null,
      rawFile: f.raw || f,  // 保留原始文件引用（不持久化）
      status: ITEM_STATUSES.PENDING,
      errorCode: null,
      errorMessage: null,
      position: null,
      estimatedWait: null,
      uploadedAt: null,
      imageId: null,
    }))
    store.batchId = `batch_${Date.now()}`
    store.phase = 'uploading'
    saveState(store)
  }

  /**
   * 更新单个项的状态
   */
  function updateItem(id, updates) {
    const item = store.items.find(i => i.id === id)
    if (!item) return
    Object.assign(item, updates)
  }

  /**
   * 标记上传成功
   */
  function markUploaded(id, imageId, fileUrl) {
    updateItem(id, {
      status: ITEM_STATUSES.UPLOADED,
      imageId,
      fileUrl,
      uploadedAt: new Date().toISOString(),
      errorCode: null,
      errorMessage: null,
    })
  }

  /**
   * 标记已入队
   */
  function markQueued(id, position, estimatedWait) {
    updateItem(id, {
      status: ITEM_STATUSES.QUEUED,
      position,
      estimatedWait,
    })
  }

  /**
   * 标记分析中
   */
  function markAnalyzing(id) {
    updateItem(id, {
      status: ITEM_STATUSES.ANALYZING,
      position: null,
      estimatedWait: null,
    })
  }

  /**
   * 标记完成
   */
  function markDone(id) {
    updateItem(id, {
      status: ITEM_STATUSES.DONE,
      position: null,
      estimatedWait: null,
      errorCode: null,
      errorMessage: null,
    })
    // 全部完成时清理 localStorage
    if (store.isAllDone) {
      store.phase = 'completed'
      // 延迟清理，让用户看到完成状态
      setTimeout(() => clearState(), 5000)
    }
  }

  /**
   * 标记失败
   */
  function markError(id, errorCode, errorMessage) {
    updateItem(id, {
      status: ITEM_STATUSES.ERROR,
      errorCode,
      errorMessage: getErrorMessage(errorCode, errorMessage),
    })
    if (store.isAllDone) {
      store.phase = 'completed'
    }
  }

  /**
   * 重置失败项以便重试
   */
  function resetForRetry(id) {
    updateItem(id, {
      status: ITEM_STATUSES.PENDING,
      errorCode: null,
      errorMessage: null,
      position: null,
      estimatedWait: null,
      imageId: null,
      uploadedAt: null,
    })
  }

  /**
   * 重试所有失败项
   */
  function retryAllFailed() {
    store.failedItems.forEach(item => resetForRetry(item.id))
    store.phase = 'uploading'
  }

  /**
   * 清空 store
   */
  function reset() {
    store.items = []
    store.batchId = null
    store.phase = 'idle'
    clearState()
  }

  /**
   * 从 localStorage 恢复（用于页面刷新后）
   * 注意：rawFile 引用会丢失，无法重试上传，只能继续轮询分析结果
   */
  function restore() {
    const saved = loadState()
    if (!saved || !saved.items.length) return false
    store.items = saved.items
    store.batchId = saved.batchId
    store.phase = 'polling'  // 恢复后只轮询
    return true
  }

  return {
    store,
    ITEM_STATUSES,
    getErrorMessage,
    initBatch,
    updateItem,
    markUploaded,
    markQueued,
    markAnalyzing,
    markDone,
    markError,
    resetForRetry,
    retryAllFailed,
    reset,
    restore,
  }
}

// 全局单例
let _instance = null
export function useUploadStore() {
  if (!_instance) {
    _instance = createUploadStore()
  }
  return _instance
}

export { ITEM_STATUSES, ERROR_CODE_MAP, getErrorMessage }
