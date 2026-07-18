import { ref, onUnmounted } from 'vue'

/**
 * SSE (Server-Sent Events) 连接管理 composable
 *
 * 用于实时接收筛选任务的进度更新，包括：
 * - 进度百分比变化（progress 事件）
 * - 任务完成通知（complete 事件）
 * - 错误信息推送（error 事件）
 *
 * @param url - SSE 接口地址（相对于 API 基础路径）
 * @returns 响应式状态对象及连接/断开控制方法
 */
export const useSSE = (url: string) => {
  // 最近一次收到的消息数据（JSON 解析后）
  const data = ref<any>(null)
  // 当前是否已建立 SSE 连接
  const isConnected = ref(false)
  // 连接错误信息
  const error = ref<string | null>(null)

  let eventSource: EventSource | null = null

  /**
   * 建立 SSE 连接
   * 自动解析服务端推送的 JSON 消息，并注册 progress / complete / error 事件监听。
   */
  const connect = () => {
    if (eventSource) {
      disconnect()
    }

    try {
      eventSource = new EventSource(url, { withCredentials: false })

      // 连接成功建立
      eventSource.onopen = () => {
        isConnected.value = true
        error.value = null
      }

      // 通用消息接收：后端将事件类型作为 JSON 字段嵌入 data 行
      eventSource.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data)
          data.value = parsed
          // 服务端发送 __done__ 哨兵后关闭流，主动断开以防止浏览器无限重连
          if (parsed.event === '__done__') {
            disconnect()
          }
        } catch {
          // 非 JSON 数据则以原始字符串保存
          data.value = event.data
        }
      }

      // 连接层面的错误处理（网络断开等）
      eventSource.onerror = () => {
        isConnected.value = false
        // EventSource 会自动重连，不立即设置 error
        // 仅当连接永久关闭时才标记错误
        if (eventSource?.readyState === EventSource.CLOSED) {
          error.value = 'SSE 连接已断开'
          isConnected.value = false
        }
      }
    } catch (e: any) {
      error.value = e.message || 'SSE 连接失败'
      isConnected.value = false
    }
  }

  /**
   * 断开 SSE 连接并清理资源
   */
  const disconnect = () => {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
  }

  // 组件卸载时自动断开连接，防止内存泄漏
  onUnmounted(() => {
    disconnect()
  })

  return {
    data,
    isConnected,
    error,
    connect,
    disconnect
  }
}
