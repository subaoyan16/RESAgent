/**
 * API 请求封装 composable — 统一管理 ResAgent 后端所有接口调用
 *
 * 基于 Nuxt 的 $fetch 封装，提供类型化的请求方法。
 * 涵盖岗位管理、简历上传、候选人查询、筛选任务、报告导出等功能。
 * 每个方法自动处理错误并抛出标准化的 Nuxt 错误对象。
 */
export const useApi = () => {
  const baseURL = '/api'

  // ─── 岗位管理 ──────────────────────────────────────────────────────────

  /**
   * 获取分页岗位列表
   * @param params.page - 页码（从 1 开始）
   * @param params.page_size - 每页条数
   * @param params.status - 按状态筛选
   * @param params.search - 按关键词搜索
   */
  const fetchJobs = async (params?: {
    page?: number
    page_size?: number
    status?: string
    search?: string
  }) => {
    try {
      return await $fetch(`${baseURL}/jobs`, { params })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取岗位列表失败' })
    }
  }

  /**
   * 获取单个岗位详情
   * @param id - 岗位 ID
   */
  const fetchJob = async (id: string) => {
    try {
      return await $fetch(`${baseURL}/jobs/${id}`)
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取岗位详情失败' })
    }
  }

  /**
   * 创建新岗位
   * @param data.title - 岗位名称
   * @param data.company - 公司名称
   * @param data.department - 部门（可选）
   * @param data.description - 岗位描述（可选）
   * @param data.hard_requirements - 硬性要求列表（可选）
   * @param data.nice_to_have - 加分项列表（可选）
   */
  const createJob = async (data: {
    title: string
    company: string
    department?: string
    description?: string
    hard_requirements?: string[]
    nice_to_have?: string[]
  }) => {
    try {
      return await $fetch(`${baseURL}/jobs`, {
        method: 'POST',
        body: data
      })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '创建岗位失败' })
    }
  }

  /**
   * 更新已有岗位信息
   * @param id - 岗位 ID
   * @param data - 需要更新的字段（部分更新）
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
    try {
      return await $fetch(`${baseURL}/jobs/${id}`, {
        method: 'PUT',
        body: data
      })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '更新岗位失败' })
    }
  }

  /**
   * 删除指定岗位
   * @param id - 要删除的岗位 ID
   */
  const deleteJob = async (id: string) => {
    try {
      return await $fetch(`${baseURL}/jobs/${id}`, { method: 'DELETE' })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '删除岗位失败' })
    }
  }

  // ─── 简历 / 候选人管理 ───────────────────────────────────────────────

  /**
   * 上传单个简历文件
   * @param file - 要上传的 File 对象（PDF/Word/TXT）
   */
  const uploadResume = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      return await $fetch(`${baseURL}/resumes/upload`, {
        method: 'POST',
        body: formData
      })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '简历上传失败' })
    }
  }

  /**
   * 获取分页候选人列表
   * @param params.job_id - 按岗位筛选（可选）
   * @param params.search - 按关键词搜索（可选）
   */
  const fetchCandidates = async (params?: {
    page?: number
    page_size?: number
    job_id?: string
    search?: string
  }) => {
    try {
      return await $fetch(`${baseURL}/candidates`, { params })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取候选人列表失败' })
    }
  }

  /**
   * 获取单个候选人详情
   * @param id - 候选人 ID
   */
  const fetchCandidate = async (id: string) => {
    try {
      return await $fetch(`${baseURL}/candidates/${id}`)
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取候选人详情失败' })
    }
  }

  // ─── 筛选任务 ─────────────────────────────────────────────────────────

  /**
   * 创建并运行新的筛选任务
   * @param jobId - 目标岗位 ID
   * @param resumeIds - 待筛选的简历 ID 列表
   */
  const runScreening = async (jobId: string, resumeIds: string[]) => {
    try {
      return await $fetch(`${baseURL}/screening`, {
        method: 'POST',
        body: { job_id: jobId, resume_ids: resumeIds }
      })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '创建筛选任务失败' })
    }
  }

  /**
   * 获取分页筛选任务列表
   * @param params.status - 按状态筛选（可选）
   */
  const fetchScreeningTasks = async (params?: {
    page?: number
    page_size?: number
    status?: string
  }) => {
    try {
      return await $fetch(`${baseURL}/screening`, { params })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取筛选任务列表失败' })
    }
  }

  /**
   * 获取单个筛选任务详情
   * @param id - 任务 ID
   */
  const fetchScreeningTask = async (id: string) => {
    try {
      return await $fetch(`${baseURL}/screening/${id}`)
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取筛选任务详情失败' })
    }
  }

  // ─── 报告 ─────────────────────────────────────────────────────────────

  /**
   * 获取候选人评估报告
   * @param reportId - 报告 ID（即候选人 ID）
   */
  const fetchReport = async (reportId: string) => {
    try {
      return await $fetch(`${baseURL}/reports/${reportId}`)
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '获取报告失败' })
    }
  }

  /**
   * 导出报告为指定格式（默认 PDF）
   * @param reportId - 报告 ID
   * @param format - 导出格式（默认 "pdf"）
   * @returns Blob 对象，可直接触发浏览器下载
   */
  const exportReport = async (reportId: string, format: string = 'pdf') => {
    try {
      return await $fetch(`${baseURL}/reports/${reportId}/export`, {
        params: { format },
        responseType: 'blob'
      })
    } catch (err: any) {
      throw createError({ statusCode: err.status || 500, message: err.message || '导出报告失败' })
    }
  }

  return {
    fetchJobs,
    fetchJob,
    createJob,
    updateJob,
    deleteJob,
    uploadResume,
    fetchCandidates,
    fetchCandidate,
    runScreening,
    fetchScreeningTasks,
    fetchScreeningTask,
    fetchReport,
    exportReport
  }
}
