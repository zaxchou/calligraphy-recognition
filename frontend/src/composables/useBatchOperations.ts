import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useSSEStream } from './useSSEStream'

export interface BatchProgress {
  current: number
  total: number
  status: string
  percent: number
}

export interface UseBatchOperationsOptions {
  apiBase: string
  fetchRecords: () => Promise<void>
  getArtist: () => string
}

export function useBatchOperations(options: UseBatchOperationsOptions) {
  const { apiBase, fetchRecords, getArtist } = options

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

  // 批量重跑结果展示
  const batchResultData = ref<any>(null)
  const showBatchResultDialog = ref(false)

  function closeBatchResultDialog() {
    showBatchResultDialog.value = false
    batchResultData.value = null
  }

  const translateProgressColor = computed(() => {
    const pct = translateProgress.value.percent
    if (pct < 30) return '#b8a47e'
    if (pct < 70) return '#c96442'
    return '#5a7d5a'
  })

  async function startBatchAnalyze(mode: 'incremental' | 'full') {
    // mode 参数保留兼容性，但本地规则引擎始终全量重跑
    showAnalyzeModeDialog.value = false
    analyzing.value = true
    showAnalyzeProgress.value = true
    analyzeProgress.value = { current: 0, total: 0, status: 'analyzing', percent: 0 }

    try {
      const artist = getArtist()
      const response = await fetch(
        `${apiBase}/content-analysis/batch-reanalyze?artist=${encodeURIComponent(artist)}`,
        { method: 'POST' }
      )
      const data = await response.json()

      if (data.success) {
        analyzeProgress.value = { current: data.total, total: data.total, status: 'done', percent: 100 }

        // 存储结果供前端调试展示
        if (data.updated_records && data.updated_records.length > 0) {
          batchResultData.value = {
            total: data.total,
            updated: data.updated,
            errors: data.errors,
            records: data.updated_records,
          }
          showBatchResultDialog.value = true
        } else {
          ElMessage.success(`批量重跑完成：${data.updated} 幅更新，${data.errors} 幅错误`)
        }

        fetchRecords()
      } else {
        ElMessage.error(data.detail || '批量重跑失败')
      }
    } catch (err: any) {
      ElMessage.error('批量重跑失败: ' + (err.message || err))
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
      const response = await fetch(
        `${apiBase}/content-analysis/translate/batch/stream?artist=${encodeURIComponent(artist)}&force_retranslate=${forceRetranslate}`,
        { method: 'POST' }
      )

      await streamTranslateSSE(response, {
        onEvent: (event) => {
          if (event.type === 'start') {
            translateProgress.value.total = event.total
            translateProgress.value.status = 'translating'
          } else if (event.type === 'progress' || event.type === 'record_done') {
            translateProgress.value.current = event.current
            translateProgress.value.total = event.total
            translateProgress.value.status = 'translating'
            translateProgress.value.percent = Math.round((event.current / event.total) * 100)
          } else if (event.type === 'done') {
            translateProgress.value.current = event.total
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
    // 方法
    startBatchAnalyze,
    cancelBatchAnalyze,
    startBatchTranslate,
    cancelBatchTranslate,
  }
}
