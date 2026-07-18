<template>
  <!-- 首页仪表盘 — 系统概览面板 -->
  <div class="dashboard">
    <!-- 欢迎区域：应用名称 + 简短介绍 -->
    <div class="welcome-section">
      <h1 class="welcome-title">欢迎使用 ResAgent</h1>
      <p class="welcome-desc">
        智能简历筛选系统 — 基于 AI Agent 的高效简历分析与岗位匹配平台。
        上传简历、创建岗位、启动筛选流程，快速找到最合适的候选人。
      </p>
    </div>

    <!-- 统计卡片行 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="12">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">岗位总数</div>
              <div class="stat-value">{{ stats.totalJobs }}</div>
            </div>
            <el-icon class="stat-icon" :size="40" color="#409eff"><Briefcase /></el-icon>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">已完成任务</div>
              <div class="stat-value">{{ stats.completedTasks }}</div>
            </div>
            <el-icon class="stat-icon" :size="40" color="#e6a23c"><DataAnalysis /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 内容区域：最近筛选任务表 + 快捷操作面板 -->
    <el-row :gutter="20" class="content-row">
      <!-- 左侧：最近筛选任务列表 -->
      <el-col :span="24">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>最近筛选任务</span>
              <el-button text type="primary" size="small" @click="navigateTo('/screening')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentTasks" stripe style="width: 100%" size="small" v-loading="loadingTasks">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="job_title" label="岗位" min-width="140" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="160">
              <template #default="{ row }">
                <el-progress :percentage="row.progress || 0" :status="row.status === 'completed' ? 'success' : undefined" :stroke-width="14" />
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160" :formatter="formatTime" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
/**
 * 首页 Dashboard — 系统概览面板
 *
 * 加载岗位总数、候选人总数、完成任务数、平均匹配分等统计卡片数据。
 * 显示最近 5 条筛选任务列表（含进度条和状态标签）。
 * 提供上传简历、创建岗位、开始筛选三个快捷入口。
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Briefcase,
  DataAnalysis
} from '@element-plus/icons-vue'

const router = useRouter()

// 统计卡片数据 — 岗位数、候选人数、已完成任务数、平均匹配分
const stats = ref({
  totalJobs: 0,
  totalCandidates: 0,
  completedTasks: 0,
})

// 最近筛选任务列表（最多 5 条）
const recentTasks = ref<any[]>([])
const loadingTasks = ref(false)

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

// 跳转到指定路由
const navigateTo = (path: string) => {
  router.push(path)
}

// 页面初始化：并发请求岗位列表和筛选任务列表
onMounted(async () => {
  try {
    const [statsRes, tasksRes] = await Promise.allSettled([
      $fetch('/api/stats'),
      $fetch('/api/screening/?page=1&page_size=5')
    ])

    if (statsRes.status === 'fulfilled') {
      const d = statsRes.value as any
      stats.value.totalJobs = d.totalJobs || 0
      stats.value.totalCandidates = d.totalCandidates || 0
      stats.value.completedTasks = d.completedTasks || 0
    }

    if (tasksRes.status === 'fulfilled') {
      const tasksData = tasksRes.value as any
      const tasks = tasksData.items || tasksData || []
      recentTasks.value = tasks.slice(0, 5)
    }
  } catch { /* 后端不可用时显示默认值 */ }
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.welcome-section {
  margin-bottom: 24px;
}

.welcome-title {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px 0;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  margin: 0;
  line-height: 1.6;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 8px;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-icon {
  opacity: 0.8;
}

.content-row {
  margin-bottom: 0;
}

.section-card {
  border-radius: 8px;
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 15px;
}

</style>
