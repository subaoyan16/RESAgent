<template>
  <!-- 候选人报告详情页 — 匹配评估报告展示 -->
  <div class="report-page" v-loading="loading">
    <template v-if="report">
      <!-- 顶部工具栏：返回按钮 + PDF 导出 -->
      <div class="report-toolbar">
        <el-button text @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <el-button type="primary" :icon="Download" @click="exportPDF">
          导出 PDF
        </el-button>
      </div>

      <!-- 报告头部：候选人姓名、岗位名称、综合匹配度环形评分 -->
      <div class="report-header-card">
        <div class="report-title-section">
          <h1 class="report-title">{{ report.candidate_name || '候选人报告' }}</h1>
          <p class="report-subtitle" v-if="report.job_title">
            岗位: {{ report.job_title }}
          </p>
        </div>
        <div class="score-section">
          <div class="circular-score">
            <el-progress
              type="circle"
              :percentage="Math.round((report.overall_score || 0) * 100)"
              :width="120"
              :stroke-width="8"
              :color="scoreColor"
            />
            <div class="score-label">综合匹配度</div>
          </div>
        </div>
      </div>

      <!-- 偏见检测标识区：如有偏见标记则以警告列表展示 -->
      <div class="flags-section" v-if="report.bias_flags && report.bias_flags.length > 0">
        <h3 class="section-title">
          <el-icon color="#f56c6c"><WarningFilled /></el-icon>
          偏见检测标识
        </h3>
        <BiasFlagAlert :flags="report.bias_flags" />
      </div>

      <!-- 详细评估报告内容：Markdown 渲染为 HTML -->
      <el-card shadow="never" class="report-content-card">
        <template #header>
          <span class="section-title">详细评估报告</span>
        </template>
        <div class="markdown-content" v-html="renderedContent"></div>
      </el-card>

      <!-- 评分明细：各维度评分进度条 -->
      <el-card shadow="never" class="report-content-card" v-if="report.score_breakdown">
        <template #header>
          <span class="section-title">评分明细</span>
        </template>
        <div class="breakdown-grid">
          <div
            class="breakdown-item"
            v-for="(value, key) in report.score_breakdown"
            :key="key"
          >
            <div class="breakdown-label">{{ breakdownLabel(key) }}</div>
            <el-progress
              :percentage="Math.round(value * 100)"
              :color="scoreColor(value)"
              :stroke-width="20"
              :text-inside="true"
            />
          </div>
        </div>
      </el-card>
    </template>

    <!-- 报告不存在时的空状态 -->
    <el-empty v-else-if="!loading" description="报告未找到" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
/**
 * 候选人报告详情页 — 展示 AI 评估报告
 *
 * 加载候选人的匹配评估报告数据，包括：
 * - 综合匹配度（环形进度条）
 * - 偏见检测标识列表（如有）
 * - Markdown 格式的详细评估报告（渲染为 HTML）
 * - 各维度的评分明细（进度条）
 * 支持导出为 PDF 文件。
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Download, WarningFilled } from '@element-plus/icons-vue'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()

const report = ref<any>(null)
const loading = ref(false)

// 将 Markdown 报告内容渲染为 HTML
const renderedContent = computed(() => {
  if (!report.value?.report_content && !report.value?.content) return '<p>暂无报告内容</p>'
  const content = report.value.report_content || report.value.content || ''
  try {
    return marked(content)
  } catch {
    return `<pre>${content}</pre>`
  }
})

// 根据分数返回对应的进度条颜色：>= 0.85 绿色，>= 0.70 黄色，>= 0.50 红色，低于 0.50 灰色
const scoreColor = (score?: number): string => {
  const s = score ?? report.value?.overall_score ?? 0
  if (s >= 0.85) return '#67c23a'
  if (s >= 0.70) return '#e6a23c'
  if (s >= 0.50) return '#f56c6c'
  return '#909399'
}

// 评分维度的中文标签映射
const breakdownLabel = (key: string): string => {
  const labels: Record<string, string> = {
    skills: '技能匹配',
    experience: '经验匹配',
    education: '教育背景',
    hard_requirements: '硬性要求',
    soft_skills: '软性技能',
    culture_fit: '文化契合',
    overall: '综合评分'
  }
  return labels[key] || key
}

// 导出报告为 PDF — 通过 API 获取 Blob 并触发浏览器下载
const exportPDF = async () => {
  const id = route.params.id as string
  try {
    const blob: Blob = await $fetch(`/api/reports/${id}/export?format=pdf`, {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `report-${id}.pdf`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('PDF 已导出')
  } catch {
    ElMessage.error('导出失败')
  }
}

// 页面初始化：根据路由参数加载报告数据
onMounted(async () => {
  const id = route.params.id as string
  loading.value = true
  try {
    const data: any = await $fetch(`/api/reports/${id}`)
    report.value = data
  } catch {
    ElMessage.error('获取报告失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.report-page {
  max-width: 1000px;
  margin: 0 auto;
}

.report-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.report-header-card {
  background: #fff;
  border-radius: 8px;
  padding: 32px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.report-title-section {
  flex: 1;
}

.report-title {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px 0;
}

.report-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.score-section {
  flex-shrink: 0;
  text-align: center;
}

.score-label {
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.flags-section {
  margin-bottom: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.report-content-card {
  border-radius: 8px;
  margin-bottom: 20px;
}

.markdown-content {
  line-height: 1.8;
  color: #303133;
  font-size: 14px;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  margin: 20px 0 12px;
  color: #303133;
}

.markdown-content :deep(p) {
  margin: 0 0 12px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 20px;
  margin-bottom: 12px;
}

.markdown-content :deep(li) {
  margin-bottom: 4px;
}

.markdown-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
  color: #f56c6c;
}

.markdown-content :deep(pre) {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding-left: 16px;
  color: #606266;
  margin: 12px 0;
}

.breakdown-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.breakdown-label {
  min-width: 80px;
  font-size: 13px;
  color: #606266;
  text-align: right;
}

.breakdown-item .el-progress {
  flex: 1;
}

/* 打印样式 */
@media print {
  .report-toolbar {
    display: none;
  }
  .report-page {
    max-width: 100%;
  }
  .report-header-card {
    box-shadow: none;
    border: 1px solid #e4e7ed;
  }
  .report-content-card {
    box-shadow: none;
    border: 1px solid #e4e7ed;
    break-inside: avoid;
  }
}
</style>
