import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 岗位管理状态 Pinia Store
 *
 * 管理岗位的 CRUD 操作及本地状态同步。
 * 提供响应式的岗位列表、当前编辑的岗位对象和加载状态。
 */
export const useJobsStore = defineStore('jobs', () => {
  /** 岗位列表数据 */
  const jobs = ref<any[]>([])
  /** 当前正在查看或编辑的岗位 */
  const currentJob = ref<any>(null)
  /** 接口请求加载状态 */
  const isLoading = ref(false)

  /**
   * 从 API 获取分页岗位列表
   * @param params.page - 页码
   * @param params.page_size - 每页条数
   * @param params.search - 搜索关键词
   * @param params.status - 按状态过滤
   * @returns 岗位列表
   */
  const fetchJobs = async (params?: {
    page?: number
    page_size?: number
    search?: string
    status?: string
  }) => {
    isLoading.value = true
    try {
      const res: any = await $fetch('/api/jobs/', { params })
      jobs.value = res.items || res || []
      return jobs.value
    } catch (err) {
      console.error('[JobsStore] fetchJobs failed:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 创建新岗位
   * @param data.title - 岗位名称
   * @param data.company - 公司名称
   * @param data.department - 部门
   * @param data.description - 岗位描述
   * @param data.hard_requirements - 硬性要求列表
   * @param data.nice_to_have - 加分项列表
   * @returns 创建的岗位对象
   */
  const createJob = async (data: {
    title: string
    company: string
    department?: string
    description?: string
    hard_requirements?: string[]
    nice_to_have?: string[]
  }) => {
    isLoading.value = true
    try {
      const job: any = await $fetch('/api/jobs/', {
        method: 'POST',
        body: data
      })
      // 将新岗位插入列表头部
      jobs.value.unshift(job)
      return job
    } catch (err) {
      console.error('[JobsStore] createJob failed:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 更新已有岗位
   * @param id - 岗位 ID
   * @param data - 需要更新的字段
   * @returns 更新后的岗位对象
   */
  const updateJob = async (
    id: string,
    data: Partial<{
      title: string
      company: string
      department: string
      description: string
      hard_requirements: string[]
      nice_to_have: string[]
      is_active: boolean
    }>
  ) => {
    isLoading.value = true
    try {
      const job: any = await $fetch(`/api/jobs/${id}`, {
        method: 'PUT',
        body: data
      })
      // 同步更新本地列表中对应的岗位
      const idx = jobs.value.findIndex((j: any) => j.id === id)
      if (idx !== -1) {
        jobs.value[idx] = job
      }
      if (currentJob.value?.id === id) {
        currentJob.value = job
      }
      return job
    } catch (err) {
      console.error('[JobsStore] updateJob failed:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 删除指定岗位
   * @param id - 要删除的岗位 ID
   */
  const deleteJob = async (id: string) => {
    isLoading.value = true
    try {
      await $fetch(`/api/jobs/${id}`, { method: 'DELETE' })
      // 从本地列表中移除
      jobs.value = jobs.value.filter((j: any) => j.id !== id)
      if (currentJob.value?.id === id) {
        currentJob.value = null
      }
    } catch (err) {
      console.error('[JobsStore] deleteJob failed:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    jobs,
    currentJob,
    isLoading,
    fetchJobs,
    createJob,
    updateJob,
    deleteJob
  }
})
