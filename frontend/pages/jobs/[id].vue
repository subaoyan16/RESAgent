<template>
  <!-- 岗位详情页面 — 展示单个岗位的完整信息 -->
  <div class="job-detail" v-loading="loading">
    <template v-if="job">
      <!-- 返回上一级导航 -->
      <div class="back-row">
        <el-button text @click="router.push('/jobs')">
          <el-icon><ArrowLeft /></el-icon>
          返回岗位列表
        </el-button>
      </div>

      <!-- 基本信息卡片：标题、状态、公司、部门、描述 -->
      <el-card shadow="never" class="detail-card">
        <template #header>
          <div class="card-header">
            <div class="title-group">
              <h2>{{ job.title }}</h2>
              <el-tag :type="job.status === 'open' ? 'success' : 'info'" size="small" effect="plain">
                {{ job.status === 'open' ? '启用' : '已关闭' }}
              </el-tag>
            </div>
            <div class="header-actions">
              <el-button type="primary" size="small" @click="router.push(`/screening?job_id=${job.id}`)">
                <el-icon><VideoPlay /></el-icon>
                开始筛选
              </el-button>
              <el-button size="small" @click="router.push(`/jobs?edit=${job.id}`)">编辑</el-button>
            </div>
          </div>
        </template>

        <!-- 岗位属性描述表格：公司、部门、创建/更新时间、描述 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="公司" :span="1">{{ job.company }}</el-descriptions-item>
          <el-descriptions-item label="部门" :span="1">{{ job.department || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="1">{{ job.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="1">{{ job.updated_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="岗位描述" :span="2">
            <div class="desc-text">{{ job.description || '暂无描述' }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 左右分栏：硬性要求 + 加分项 -->
      <el-row :gutter="20" class="detail-row">
        <!-- 硬性要求列表 -->
        <el-col :span="12">
          <el-card shadow="never" class="detail-card">
            <template #header>
              <span class="section-title">
                <el-icon color="#f56c6c"><WarningFilled /></el-icon>
                硬性要求
              </span>
            </template>
            <div class="req-list" v-if="job.requirements?.hard?.length">
              <div class="req-item" v-for="(req, i) in job.requirements.hard" :key="i">
                <span class="req-skill">{{ req.skill || req }}</span>
                <span class="req-meta" v-if="req.min_years">要求 {{ req.min_years }} 年以上经验</span>
              </div>
            </div>
            <el-empty v-else description="暂无硬性要求" :image-size="60" />
          </el-card>
        </el-col>
        <!-- 加分项列表 -->
        <el-col :span="12">
          <el-card shadow="never" class="detail-card">
            <template #header>
              <span class="section-title">
                <el-icon color="#e6a23c"><StarFilled /></el-icon>
                加分项
              </span>
            </template>
            <div class="req-list" v-if="job.requirements?.nice_to_have?.length">
              <div class="req-item" v-for="(req, i) in job.requirements.nice_to_have" :key="i">
                <span class="req-skill">{{ req.skill || req }}</span>
              </div>
            </div>
            <el-empty v-else description="暂无加分项" :image-size="60" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 评分权重配置：以进度条展示各维度权重占比 -->
      <el-card shadow="never" class="detail-card">
        <template #header>
          <span class="section-title">评分权重配置</span>
        </template>
        <div v-if="job.scoring_weights" class="weights-wrap">
          <div class="weight-item" v-for="(value, key) in job.scoring_weights" :key="key">
            <div class="weight-label">{{ weightLabel(key) }}</div>
            <el-progress
              :percentage="Math.round(value * 100)"
              :color="weightColor(value)"
              :stroke-width="18"
              :text-inside="true"
            />
          </div>
        </div>
        <el-empty v-else description="暂无权重配置" :image-size="60" />
      </el-card>

      <!-- 匹配候选人列表：使用 ResumeCard 组件展示 -->
      <el-card shadow="never" class="detail-card" v-if="candidates.length > 0">
        <template #header>
          <span class="section-title">匹配候选人</span>
        </template>
        <div class="candidate-grid">
          <ResumeCard
            v-for="candidate in candidates"
            :key="candidate.id"
            :candidate="candidate"
            @select="router.push(`/reports/${candidate.id}`)"
          />
        </div>
      </el-card>
    </template>

    <!-- 岗位不存在时的空状态 -->
    <el-empty v-else-if="!loading" description="岗位不存在" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
/**
 * 岗位详情页面 — 展示单个岗位的完整信息
 *
 * 加载岗位基本信息、硬性要求、加分项、评分权重配置。
 * 同时加载该岗位下的匹配候选人列表。
 * 提供「开始筛选」和「编辑」快捷操作入口。
 */
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  VideoPlay,
  WarningFilled,
  StarFilled
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const job = ref<any>(null)
const candidates = ref<any[]>([])
const loading = ref(false)

// 评分维度的中文标签映射
const weightLabel = (key: string): string => {
  const labels: Record<string, string> = {
    skill_match: '技能匹配',
    experience_relevance: '经验相关性',
    education: '教育背景',
    career_trajectory: '职业轨迹',
    other: '其他因素'
  }
  return labels[key] || key
}

// 根据权重值返回进度条颜色：高权重绿色，中权重黄色，低权重红色
const weightColor = (value: number): string => {
  if (value >= 0.3) return '#67c23a'
  if (value >= 0.2) return '#e6a23c'
  return '#f56c6c'
}

// 页面初始化：并发请求岗位详情和候选人列表
onMounted(async () => {
  const id = route.params.id as string
  loading.value = true
  try {
    const jobData = await $fetch(`/api/jobs/${id}`).catch(() => null)
    if (jobData) {
      job.value = jobData as any
    } else {
      ElMessage.error('获取岗位详情失败')
    }
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.job-detail {
  max-width: 1200px;
  margin: 0 auto;
}

.back-row {
  margin-bottom: 16px;
}

.detail-card {
  border-radius: 8px;
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-group h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.section-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
}

.desc-text {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #606266;
  font-size: 13px;
}

.detail-row {
  margin-bottom: 0;
}

.req-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.req-item {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}

.req-skill {
  font-weight: 500;
}

.req-meta {
  margin-left: 8px;
  font-size: 13px;
  color: #909399;
}

.weights-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.weight-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.weight-label {
  min-width: 80px;
  font-size: 13px;
  color: #606266;
  text-align: right;
}

.weight-item .el-progress {
  flex: 1;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
</style>
