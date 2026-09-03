import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useSSEStream } from './useSSEStream'

export interface BatchProgress {
  current: number
  total: number
  status: string
  percent: number
}

interface AnalyzeEvent extends Record<string, unknown> { type: string; total?: number; current?: number; updated?: number; errors?: number; message?: string; report?: Record<string, unknown> & { updated_at?: string; llm_corrected?: number } }
interface TranslateEvent extends Record<string, unknown> { type: string; total?: number; current?: number; translated?: number; failed?: number }

export interface UseBatchOperationsOptions {
  apiBase: string
  fetchRecords: () => Promise<void>
  getArtist: () => string
  getLibraryId?: () => number | null
}

export function useBatchOperations(options: UseBatchOperationsOptions) {
  const { apiBase, fetchRecords, getArtist, getLibraryId } = options

  // 批量分析状态
  const analyzing = ref(false)
  const showAnalyzeModeDialog = ref(false)
  const showAnalyzeProgress = ref(false)
  const analyzeProgress = ref<BatchProgress>({ current: 0, total: 0, status: '', percent: 0 })

  // 批量翻译状态
  const batchTranslating = ref(false)
  const showTranslateModeDialog = ref(false)
  const showTranslateProgress = ref(false)
  const translateProgress = ref<BatchProgress>({ current: 0, total: 0, status: '', percent: 0 })

  // SSE 流实例
  const { streamSSE: streamAnalyzeSSE, cancel: cancelAnalyzeStream } = useSSEStream()
  const { streamSSE: streamTranslateSSE, cancel: cancelTranslateStream } = useSSEStream()

  // 批量重跑结果展示 —— 持久化到 localStorage，页面刷新不丢失
  const getCacheKey = () => {
    const libId = getLibraryId ? getLibraryId() : null
    return libId ? `batch-reanalyze-result_lib${libId}` : `batch-reanalyze-result_${getArtist()}`
  }
  interface BatchResultData {
    total: number
    updated: number
    errors: number
    message: string
    report: Record<string, unknown> & { updated_at: string; llm_corrected?: number }
  }
  const _loadCached = (): BatchResultData | null => { try { const v = localStorage.getItem(getCacheKey()); return v ? JSON.parse(v) as BatchResultData : null } catch { return null } }
  const batchResultData = ref<BatchResultData | null>(_loadCached())

  function _saveToStorage(data: BatchResultData) {
    try { localStorage.setItem(getCacheKey(), JSON.stringify(data)) } catch { /* quota exceeded, ignore */ }
  }

  const showBatchResultDialog = ref(false)

  function closeBatchResultDialog() {
    showBatchResultDialog.value = false
  }

  const translateProgressColor = computed(() => {
    const pct = translateProgress.value.percent
    if (pct < 30) return '#b8a47e'
    if (pct < 70) return '#c96442'
    return '#5a7d5a'
  })

  const analyzeProgressColor = computed(() => {
    const pct = analyzeProgress.value.percent
    if (pct < 30) return '#4e8cff'
    if (pct < 70) return '#ff9800'
    return '#67c23a'
  })

  async function startBatchAnalyze(mode: 'incremental' | 'full') {
    showAnalyzeModeDialog.value = false
    analyzing.value = true
    showAnalyzeProgress.value = true
    analyzeProgress.value = { current: 0, total: 0, status: 'analyzing', percent: 0 }

    try {
      const artist = getArtist()
      const libraryId = getLibraryId ? getLibraryId() : null
      const incremental = mode === 'incremental'
      const params = new URLSearchParams()
      if (artist && artist !== 'all') params.set('artist', artist)
      if (libraryId) params.set('library_id', String(libraryId))
      params.set('incremental', String(incremental))
      const response = await fetch(
        `${apiBase}/content-analysis/batch-reanalyze/stream?${params.toString()}`,
        { method: 'POST' }
      )

      await streamAnalyzeSSE<AnalyzeEvent>(response, {
        onEvent: (event) => {
          if (event.type === 'total') {
            analyzeProgress.value = { current: 0, total: event.total ?? 0, status: 'analyzing', percent: 0 }
          } else if (event.type === 'progress') {
            const cur = event.current ?? 0
            const tot = event.total ?? 0
            const pct = tot > 0 ? Math.round((cur / tot) * 100) : 0
            analyzeProgress.value = { current: cur, total: tot, status: 'analyzing', percent: pct }
          } else if (event.type === 'complete') {
            batchResultData.value = {
              total: event.total ?? 0,
              updated: event.updated ?? 0,
              errors: event.errors ?? 0,
              message: event.message ?? '',
              report: { ...event.report, updated_at: new Date().toLocaleString() },
            }
            _saveToStorage(batchResultData.value)
            analyzeProgress.value = { current: event.total ?? 0, total: event.total ?? 0, status: 'done', percent: 100 }
            showBatchResultDialog.value = true
            const llmCorrected = event.report?.llm_corrected ?? 0
            if (llmCorrected > 0) {
              ElMessage.success(`完成！DeepSeek 自动修正了 ${llmCorrected} 幅`)
            }
            fetchRecords()
          }
        },
        onError: (err) => {
          ElMessage.error('批量重跑失败: ' + err.message)
        },
      })
    } catch (err) {
      ElMessage.error('批量重跑失败: ' + (err instanceof Error ? err.message : String(err)))
    } finally {
      analyzing.value = false
    }
  }

  function cancelBatchAnalyze() {
    cancelAnalyzeStream()
    showAnalyzeProgress.value = false
    analyzeProgress.value = { current: 0, total: 0, status: '', percent: 0 }
    analyzing.value = false
    ElMessage.warning('已取消批量分析')
  }

  async function startBatchTranslate(mode: 'untranslated' | 'all') {
    const forceRetranslate = mode === 'all'

    showTranslateModeDialog.value = false
    batchTranslating.value = true
    showTranslateProgress.value = true
    translateProgress.value = { current: 0, total: 0, status: '', percent: 0 }

    try {
      const artist = getArtist()
      const libraryId = getLibraryId ? getLibraryId() : null
      const params = new URLSearchParams()
      if (artist && artist !== 'all') params.set('artist', artist)
      if (libraryId) params.set('library_id', String(libraryId))
      params.set('force_retranslate', String(forceRetranslate))
      const response = await fetch(
        `${apiBase}/content-analysis/translate/batch/stream?${params.toString()}`,
        { method: 'POST' }
      )

      await streamTranslateSSE<TranslateEvent>(response, {
        onEvent: (event) => {
          if (event.type === 'start') {
            translateProgress.value.total = event.total ?? 0
            translateProgress.value.status = 'translating'
          } else if (event.type === 'progress' || event.type === 'record_done') {
            translateProgress.value.current = event.current ?? 0
            translateProgress.value.total = event.total ?? 0
            translateProgress.value.status = 'translating'
            const tCur = event.current ?? 0
            const tTot = event.total ?? 0
            translateProgress.value.percent = tTot > 0 ? Math.round((tCur / tTot) * 100) : 0
          } else if (event.type === 'done') {
            translateProgress.value.current = event.total ?? 0
            translateProgress.value.percent = 100
            translateProgress.value.status = 'done'
            ElMessage.success(`批量翻译完成：成功 ${event.translated} 条，失败 ${event.failed} 条`)
            fetchRecords()
          }
        },
        onError: (err) => {
          ElMessage.error('批量翻译失败: ' + err.message)
        },
        onComplete: () => {
          batchTranslating.value = false
        },
      })
    } catch {
      batchTranslating.value = false
    }
  }

  function cancelBatchTranslate() {
    cancelTranslateStream()
    showTranslateProgress.value = false
    translateProgress.value = { current: 0, total: 0, status: '', percent: 0 }
    batchTranslating.value = false
    ElMessage.warning('已取消批量翻译')
  }

  return {
    // 状态
    analyzing,
    batchTranslating,
    showAnalyzeModeDialog,
    showTranslateModeDialog,
    showAnalyzeProgress,
    showTranslateProgress,
    analyzeProgress,
    translateProgress,
    // 批量重跑结果弹窗
    batchResultData,
    showBatchResultDialog,
    closeBatchResultDialog,
    // computed
    translateProgressColor,
    analyzeProgressColor,
    // 方法
    startBatchAnalyze,
    cancelBatchAnalyze,
    startBatchTranslate,
    cancelBatchTranslate,
  }
}
