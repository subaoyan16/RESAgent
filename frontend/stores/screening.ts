import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 筛选任务状态管理 Pinia Store
 *
 * 管理筛选任务的 CRUD 操作及实时进度跟踪。
 * 提供响应式的任务列表、当前任务对象和加载状态。
 */
export const useScreeningStore = defineStore('screening', () => {
  /** 筛选任务列表 */
  const tasks = ref<any[]>([])
  /** 当前查看/处理的筛选任务 */
  const currentTask = ref<any>(null)
  /** 接口请求加载状态 */
  const isLoading = ref(false)

  /**
   * 从 API 获取筛选任务列表
   * @param params.page - 页码
   * @param params.page_size - 每页条数
   * @param params.status - 按状态过滤
   * @returns 任务列表
   */
  const fetchTasks = async (params?: { page?: number; page_size?: number; status?: string }) => {
    isLoading.value = true
    try {
      const res: any = await $fetch('/api/screening', { params })
      tasks.value = res.items || res || []
      return tasks.value
    } catch (err) {
      console.error('[ScreeningStore] fetchTasks failed:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 创建并启动新的筛选任务
   * @param jobId - 目标岗位 ID
   * @param resumeIds - 待筛选简历 ID 列表
   * @returns 创建的任务对象
   */
  const runScreening = async (jobId: string, resumeIds: string[]) => {
    isLoading.value = true
    try {
      const task: any = await $fetch('/api/screening', {
        method: 'POST',
        body: {
          job_id: jobId,
          resume_ids: resumeIds
        }
      })
      // 将新任务插入列表头部
      tasks.value.unshift(task)
      return task
    } catch (err) {
      console.error('[ScreeningStore] runScreening failed:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 获取指定筛选任务的进度和状态
   * @param taskId - 任务 ID
   * @returns 任务详情（含进度）
   */
  const getTaskProgress = async (taskId: string) => {
    try {
      const task: any = await $fetch(`/api/screening/${taskId}`)
      // 同步更新列表中对应任务的状态
      const idx = tasks.value.findIndex((t: any) => t.id === taskId)
      if (idx !== -1) {
        tasks.value[idx] = task
      }
      currentTask.value = task
      return task
    } catch (err) {
      console.error('[ScreeningStore] getTaskProgress failed:', err)
      throw err
    }
  }

  return {
    tasks,
    currentTask,
    isLoading,
    fetchTasks,
    runScreening,
    getTaskProgress
  }
})
