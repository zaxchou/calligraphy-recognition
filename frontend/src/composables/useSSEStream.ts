/**
 * 通用 SSE 流式响应解析 composable
 * 用于处理服务端发送事件（Server-Sent Events）的流式数据
 */

export interface SSEEvent {
  type: string
  [key: string]: any
}

export interface SSEOptions {
  onEvent: (event: SSEEvent) => void | Promise<void>
  onError?: (error: Error) => void
  onComplete?: () => void
}

export function useSSEStream() {
  let abortController: AbortController | null = null

  async function streamSSE(response: Response, options: SSEOptions): Promise<void> {
    abortController = new AbortController()

    try {
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        // 检查是否已取消
        if (abortController.signal.aborted) {
          reader.cancel()
          break
        }

        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event: SSEEvent = JSON.parse(line.slice(6))
            await options.onEvent(event)
          } catch {
            // ignore parse errors
          }
        }
      }

      options.onComplete?.()
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error))
      options.onError?.(err)
      throw err
    } finally {
      abortController = null
    }
  }

  function cancel(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
  }

  return { streamSSE, cancel }
}
