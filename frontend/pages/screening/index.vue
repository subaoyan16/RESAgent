<template>
  <!-- 筛选任务页面 — 创建新筛选 + 任务列表 -->
  <div class="screening-page">
    <h2 class="page-title">筛选任务</h2>

    <!-- 创建筛选任务卡片：选择岗位 + 上传简历 + 开始筛选 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">创建筛选任务</span>
      </template>
      <el-form :model="taskForm" label-width="120px" class="create-form">
        <!-- 岗位选择器：从已有岗位列表中选择 -->
        <el-form-item label="选择岗位" required>
          <el-select
            v-model="taskForm.jobId"
            placeholder="请选择要筛选的岗位"
            filterable
            style="width: 400px"
            :loading="loadingJobs"
          >
            <el-option
              v-for="job in jobOptions"
              :key="job.id"
              :label="`${job.title} — ${job.company}`"
              :value="job.id"
            />
          </el-select>
        </el-form-item>
        <!-- 简历上传区域：支持拖拽、多文件上传 -->
        <el-form-item label="上传简历" required>
          <el-upload
            ref="uploadRef"
            v-model:file-list="fileList"
            :auto-upload="false"
            :limit="50"
            :on-exceed="handleExceed"
            accept=".pdf,.doc,.docx,.txt"
            drag
            multiple
            class="resume-upload"
          >
            <el-icon class="upload-icon" :size="40"><UploadFilled /></el-icon>
            <div class="upload-text">拖拽或点击上传简历文件</div>
            <template #tip>
              <div class="upload-tip">
                支持 PDF、Word、TXT 格式，单次最多 50 份
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <!-- 提交按钮：开始筛选（需选择岗位且至少上传一份简历） -->
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="creating"
            :disabled="!taskForm.jobId || fileList.length === 0"
            @click="handleCreateTask"
          >
            <el-icon><VideoPlay /></el-icon>
            开始筛选
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 筛选任务列表卡片：表格展示已创建的任务 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="section-title">筛选任务列表</span>
          <el-button text type="primary" :icon="Refresh" @click="fetchTasks">刷新</el-button>
        </div>
      </template>
      <el-table :data="tasks" v-loading="loadingTasks" stripe style="width: 100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="job_title" label="岗位" min-width="140" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="dark" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 进度条：显示筛选完成百分比 -->
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress || 0"
              :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
              :stroke-width="16"
              :text-inside="true"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" :formatter="formatTime" />
        <!-- 操作列：点击查看任务详情 -->
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewTask(row.id)">详情</el-button>
            <el-popconfirm title="确定删除此任务？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 筛选任务列表页 — 创建筛选任务 + 查看任务列表
 *
 * 加载可用的岗位列表用于创建筛选任务。
 * 支持拖拽上传多份简历，上传后创建筛选任务并自动跳转详情页。
 * 任务列表每 3 秒自动刷新进行中的任务状态。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, UploadFilled, Refresh } from '@element-plus/icons-vue'
import type { UploadProps, UploadUserFile } from 'element-plus'

const router = useRouter()
const uploadRef = ref<any>(null)

const tasks = ref<any[]>([])
const jobOptions = ref<any[]>([])
const fileList = ref<UploadUserFile[]>([])
const loadingJobs = ref(false)
const loadingTasks = ref(false)
const creating = ref(false)

const taskForm = ref({
  jobId: ''
})

let refreshTimer: ReturnType<typeof setInterval> | null = null

// 任务状态对应的 Element Plus 标签类型
const formatTime = (row: any, _col: any, val: string) => val ? new Date(val).toLocaleString('zh-CN', { year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit' }) : '-'
const statusType = (status: string): 'info' | 'warning' | 'success' | 'danger' => {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

// 任务状态的中文标签
const statusLabel = (status: string): string => {
  const map: Record<string, string> = {
    pending: '待处理',
    running: '进行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

// 文件数量超出限制时的提示
const handleExceed: UploadProps['onExceed'] = () => {
  ElMessage.warning('单次最多上传 50 份简历')
}

// 获取岗位列表（用于下拉选择）
const fetchJobs = async () => {
  loadingJobs.value = true
  try {
    const res: any = await $fetch('/api/jobs/', { params: { page: 1, page_size: 100 } })
    jobOptions.value = res.items || res || []
  } catch {
    ElMessage.error('获取岗位列表失败')
  } finally {
    loadingJobs.value = false
  }
}

// 获取筛选任务列表
const fetchTasks = async () => {
  try {
    const res: any = await $fetch('/api/screening/', { params: { page: 1, page_size: 20 } })
    tasks.value = res.items || res || []
  } catch {
    // 静默处理刷新错误
  } finally {
    loadingTasks.value = false
  }
}

// 创建筛选任务：先逐份上传简历，然后调用筛选接口
const handleCreateTask = async () => {
  if (!taskForm.value.jobId || fileList.value.length === 0) {
    ElMessage.warning('请选择岗位并上传简历')
    return
  }

  creating.value = true
  try {
    // 逐份上传简历并收集返回的 ID
    const resumeIds: string[] = []
    for (const file of fileList.value) {
      const rawFile = file.raw
      if (!rawFile) continue
      const formData = new FormData()
      formData.append('file', rawFile)
      const uploadRes: any = await $fetch('/api/resumes/upload', {
        method: 'POST',
        body: formData
      })
      if (uploadRes.id) {
        resumeIds.push(uploadRes.id)
      }
    }

    if (resumeIds.length === 0) {
      ElMessage.error('简历上传失败')
      return
    }

    // 调用筛选接口创建任务
    const task: any = await $fetch('/api/screening/run', {
      method: 'POST',
      body: {
        job_id: taskForm.value.jobId,
        resume_ids: resumeIds
      }
    })

    ElMessage.success('筛选任务已创建')
    fileList.value = []
    taskForm.value.jobId = ''
    await fetchTasks()
    router.push(`/screening/${task.id || task.task_id}`)
  } catch (e: any) {
    ElMessage.error('创建筛选任务失败')
  } finally {
    creating.value = false
  }
}

// 查看任务详情
const viewTask = (id: string) => {
  router.push(`/screening/${id}`)
}

const handleDelete = async (id: string) => {
  try {
    await $fetch(`/api/screening/${id}`, { method: 'DELETE' })
    ElMessage.success('任务已删除')
    await fetchTasks()
  } catch {
    ElMessage.error('删除失败')
  }
}

// 页面初始化：并发加载岗位列表和任务列表
onMounted(async () => {
  loadingTasks.value = true
  await Promise.all([fetchJobs(), fetchTasks()])

  // 自动刷新：每 3 秒检查是否有进行中的任务，有则刷新列表
  refreshTimer = setInterval(async () => {
    const hasRunning = tasks.value.some(t => t.status === 'running' || t.status === 'pending')
    if (hasRunning) {
      await fetchTasks()
    }
  }, 3000)
})

// 页面卸载时清除定时器，防止内存泄漏
onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.screening-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 20px 0;
}

.section-card {
  border-radius: 8px;
  margin-bottom: 20px;
}

.section-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.create-form {
  max-width: 700px;
}

.resume-upload {
  width: 100%;
}

.upload-icon {
  margin-bottom: 8px;
}

.upload-text {
  font-size: 14px;
  color: #606266;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
