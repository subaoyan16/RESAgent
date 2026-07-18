<template>
  <div class="screening-detail">
    <!-- 返回导航 -->
    <div class="back-row">
      <el-button text @click="router.push('/screening')">
        <el-icon><ArrowLeft /></el-icon>
        返回任务列表
      </el-button>
    </div>

    <template v-if="task">
      <!-- 任务状态卡片 -->
      <el-card shadow="never" class="detail-card">
        <div class="task-header">
          <div class="task-info">
            <h3>#{{ taskIndex }} {{ task.job_title || '筛选任务' }}</h3>
            <el-tag :type="statusType(task.status)" effect="dark" size="small">{{ statusLabel(task.status) }}</el-tag>
            <span class="task-meta">创建于 {{ formatTime(task.created_at) }}</span>
          </div>
          <!-- 进度条（运行中显示） -->
          <div v-if="task.status === 'running' || task.status === 'pending'" class="progress-wrap">
            <ScreeningProgress :status="task.status" :current-step="task.current_step || 0" />
          </div>
        </div>
      </el-card>

      <!-- 运行中：显示进度 -->
      <el-card v-if="task.status === 'running' || task.status === 'pending'" shadow="never" class="detail-card">
        <el-progress :percentage="progressPercent" :stroke-width="20" :text-inside="true" />
        <p class="progress-hint">AI Agent 正在分析中，请稍候...</p>
      </el-card>

      <!-- 失败 -->
      <el-result v-else-if="task.status === 'failed'" icon="error" title="筛选任务失败"
        :sub-title="task.error_message || '处理过程中出现错误'" />

      <!-- 已完成：显示结果 -->
      <template v-else-if="task.status === 'completed'">
        <!-- 偏见检测报告 -->
        <el-card v-if="biasReport" shadow="never" class="detail-card bias-card">
          <template #header>
            <span class="section-title">
              <el-icon color="#e6a23c"><WarningFilled /></el-icon>
              偏见检测报告
            </span>
          </template>
          <div class="bias-summary">
            <span class="bias-score-label">公平性评分：</span>
            <el-progress
              type="circle"
              :percentage="Math.round((biasReport.fairness_score || 0) * 100)"
              :width="80"
              :stroke-width="6"
              :color="biasReport.fairness_score >= 0.8 ? '#67c23a' : biasReport.fairness_score >= 0.6 ? '#e6a23c' : '#f56c6c'"
            />
          </div>
          <BiasFlagAlert v-if="biasReport.flags?.length" :flags="biasReport.flags" />
          <el-empty v-else description="未检测到偏见标识" :image-size="40" />
        </el-card>

        <!-- 候选人排名 -->
        <el-card shadow="never" class="detail-card">
          <template #header><span class="section-title">候选人排名</span></template>
          <div v-if="candidates.length === 0" style="text-align:center;padding:40px;color:#909399">
            <p v-if="task.processed_candidates === 0">暂无匹配结果，请确认待筛选简历中包含文本内容</p>
            <p v-else>加载中...</p>
            <el-button v-if="task.processed_candidates === 0" type="primary" @click="loadResults" :loading="loadingResults">刷新结果</el-button>
          </div>
          <div v-else class="candidate-list">
            <div v-for="(c, index) in candidates" :key="c.candidate_id" class="candidate-row"
              :class="{ expanded: expandedId === c.candidate_id }">
              <!-- 摘要行 -->
              <div class="candidate-summary" @click="toggleExpand(c.candidate_id)">
                <span class="rank-badge" :class="'rank-' + (index + 1)">{{ index + 1 }}</span>
                <div class="candidate-info">
                  <div class="candidate-name">{{ c.name }}</div>
                </div>
                <div class="candidate-score">
                  <MatchScoreBadge :score="c.overall_score || 0" />
                  <el-tag v-if="c.recommendation === 'strong_hire'" type="success" size="small">强烈推荐</el-tag>
                  <el-tag v-else-if="c.recommendation === 'recommend'" size="small">推荐</el-tag>
                  <el-tag v-else-if="c.recommendation === 'hold'" type="warning" size="small">待定</el-tag>
                  <el-tag v-else type="info" size="small">不推荐</el-tag>
                </div>
                <el-icon class="expand-icon"><ArrowDown v-if="expandedId !== c.candidate_id" /><ArrowUp v-else /></el-icon>
              </div>

              <!-- 展开：详细报告 -->
              <div v-if="expandedId === c.candidate_id" class="candidate-detail">
                <el-divider />

                <!-- 维度评分 -->
                <h4>各维度评分</h4>
                <div class="dim-scores">
                  <div v-for="(score, key) in c.dimension_scores" :key="key" class="dim-item">
                    <span class="dim-label">{{ dimLabel(key) }}</span>
                    <el-progress :percentage="Math.round(score * 100)" :stroke-width="14" :color="scoreColor(score)" />
                  </div>
                </div>

                <!-- 匹配技能 -->
                <h4 v-if="c.matched_skills?.length">匹配技能</h4>
                <div class="skill-list">
                  <div v-for="(s, i) in c.matched_skills" :key="i" class="skill-row">
                    <span class="skill-name">{{ s.skill || s.name || s }}</span>
                    <el-progress :percentage="Math.round((s.match || s.confidence || 0) * 100)" :stroke-width="8" :color="'#67c23a'" style="width:100px;flex-shrink:0" />
                  </div>
                </div>

                <!-- 技能差距 -->
                <h4 v-if="c.gaps?.length">技能差距</h4>
                <div class="gap-list">
                  <div v-for="(g, i) in c.gaps" :key="i" class="gap-item">
                    <span class="gap-name">{{ g.skill || g.name || g }}</span>
                    <span class="gap-tag" :class="g.gap_severity === 'high' || g.importance === 'hard' ? 'gap-high' : 'gap-low'">
                      {{ g.importance === 'hard' ? '硬性要求' : '加分项' }}
                    </span>
                  </div>
                </div>

                <!-- 可迁移技能 -->
                <h4 v-if="c.transferable_skills?.length">可迁移技能</h4>
                <div class="transfer-list">
                  <span v-for="(t, i) in c.transferable_skills" :key="i" class="transfer-item">
                    {{ t.candidate_skill || t }} → {{ t.mapped_to }} ({{ Math.round((t.similarity || 0) * 100) }}%)
                  </span>
                </div>

                <!-- 亮点 -->
                <h4 v-if="c.highlights?.length">候选人亮点</h4>
                <ul class="highlights">
                  <li v-for="(h, i) in c.highlights" :key="i">{{ h }}</li>
                </ul>

                <!-- 风险 -->
                <h4 v-if="c.risks?.length">风险提示</h4>
                <ul class="risks">
                  <li v-for="(r, i) in c.risks" :key="i">{{ r }}</li>
                </ul>

                <!-- 评估理由 -->
                <h4>评估理由</h4>
                <p class="rationale">{{ c.match_rationale || '暂无详细评估理由' }}</p>
              </div>
            </div>
          </div>
        </el-card>

      </template>
    </template>

    <el-empty v-else-if="!loading" description="任务不存在" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowDown, ArrowUp, WarningFilled } from '@element-plus/icons-vue'
import BiasFlagAlert from '~/components/BiasFlagAlert.vue'
import { useSSE } from '~/composables/useSSE'

const route = useRoute()
const router = useRouter()

const task = ref<any>(null)
const candidates = ref<any[]>([])
const biasReport = ref<any>(null)
const loading = ref(true)
const loadingResults = ref(false)
const expandedId = ref<string | null>(null)
const taskIndex = ref(0)

// ── SSE 实时进度 ──
const nodeToStep: Record<string, number> = {
  job_analyzer: 2, retriever: 3, matcher: 3, bias_detector: 4,
}
const { data: sseData, connect: sseConnect, disconnect: sseDisconnect } =
  useSSE(`/api/screening/${route.params.id as string}/stream`)

watch(sseData, (event) => {
  if (!event) return
  switch (event.event) {
    case 'node_update':
      if (event.status === 'completed' && task.value) {
        const step = nodeToStep[event.node] || 0
        if (step > (task.value.current_step || 0)) {
          task.value = { ...task.value, current_step: step, status: 'running' }
        }
      }
      break
    case 'workflow_complete':
      if (task.value) task.value = { ...task.value, status: 'completed', current_step: 5 }
      fetchTask().then(() => loadResults())
      break
    case 'workflow_error':
      if (task.value) task.value = { ...task.value, status: 'failed', error_message: event.error }
      fetchTask()
      break
  }
})

const progressPercent = computed(() => {
  if (!task.value) return 0
  const total = task.value.total_candidates || 1
  const done = task.value.processed_candidates || 0
  return Math.round((done / total) * 100)
})

const statusType = (s: string) => ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger' } as any)[s] || 'info'
const statusLabel = (s: string) => ({ pending: '待处理', running: '进行中', completed: '已完成', failed: '失败' } as any)[s] || s
const formatTime = (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-'

const dimLabel = (key: string) => ({
  skill_match: '技能匹配', experience_relevance: '经验相关性', education: '教育背景',
  career_trajectory: '职业轨迹', other: '其他因素'
} as any)[key] || key

const scoreColor = (score: number) => score >= 0.8 ? '#67c23a' : score >= 0.6 ? '#e6a23c' : '#f56c6c'
const levelLabel = (level: string) => ({ expert: '专家', intermediate: '熟练', beginner: '入门' } as any)[level] || level
const biasTypeLabel = (type: string) => ({
  potential_gender_bias: '潜在性别偏见', gender: '性别偏见',
  potential_age_bias: '潜在年龄偏见', age: '年龄偏见',
  potential_education_bias: '潜在院校偏见', education: '院校偏见',
  potential_geographic_bias: '潜在地域偏见', geography: '地域偏见',
} as any)[type] || type

const toggleExpand = (id: string) => {
  expandedId.value = expandedId.value === id ? null : id
}

// 加载任务详情
const fetchTask = async () => {
  const id = route.params.id as string
  try {
    task.value = await $fetch(`/api/screening/${id}`)
  } catch { ElMessage.error('获取任务详情失败') }
  finally { loading.value = false }
}

// 加载完整结果
const loadResults = async () => {
  loadingResults.value = true
  try {
    const id = route.params.id as string
    const data: any = await $fetch(`/api/screening/${id}/results`)
    candidates.value = (data.candidates || []).sort((a: any, b: any) => (b.overall_score || 0) - (a.overall_score || 0))
    biasReport.value = data.bias_report || null
    taskIndex.value = (data.task_id || '').length > 0 ? 1 : 0
  } catch { candidates.value = [];  }
  finally { loadingResults.value = false }
}

onMounted(async () => {
  await fetchTask()
  if (task.value?.status === 'completed') {
    await loadResults()
  } else if (task.value?.status === 'running' || task.value?.status === 'pending') {
    sseConnect()
  }
})
</script>

<style scoped>
.screening-detail { max-width: 1000px; margin: 0 auto; }
.back-row { margin-bottom: 16px; }
.detail-card { border-radius: 8px; margin-bottom: 20px; }
.task-header { display: flex; flex-direction: column; gap: 12px; }
.task-info { display: flex; align-items: center; gap: 12px; }
.task-info h3 { margin: 0; font-size: 18px; }
.task-meta { color: #909399; font-size: 13px; }
.section-title { font-weight: 600; font-size: 15px; }
.progress-wrap { max-width: 600px; }
.progress-hint { text-align: center; color: #909399; margin-top: 12px; }

/* 候选人列表 */
.candidate-list { display: flex; flex-direction: column; gap: 4px; }
.candidate-row { border: 1px solid #ebeef5; border-radius: 8px; overflow: hidden; }
.candidate-row.expanded { border-color: #409eff; }
.candidate-summary { display: flex; align-items: center; gap: 16px; padding: 16px; cursor: pointer; transition: background 0.2s; }
.candidate-summary:hover { background: #f5f7fa; }
.rank-badge { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; background: #909399; color: #fff; flex-shrink: 0; }
.rank-badge.rank-1 { background: #f56c6c; }
.rank-badge.rank-2 { background: #e6a23c; }
.rank-badge.rank-3 { background: #409eff; }
.candidate-info { flex: 1; }
.candidate-name { font-weight: 600; font-size: 15px; }
.candidate-sub { font-size: 13px; color: #909399; }
.candidate-score { display: flex; align-items: center; gap: 8px; }
.expand-icon { color: #909399; font-size: 16px; }

/* 详细报告 */
.candidate-detail { padding: 0 16px 20px; }
.candidate-detail h4 { font-size: 14px; margin: 16px 0 8px; color: #303133; }
.dim-scores { display: flex; flex-direction: column; gap: 8px; }
.dim-item { display: flex; align-items: center; gap: 12px; }
.dim-label { width: 80px; font-size: 13px; color: #606266; text-align: right; flex-shrink: 0; }
.dim-item :deep(.el-progress) { flex: 1; }
.skill-list { display: flex; flex-direction: column; gap: 6px; }
.skill-row { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.skill-name { font-weight: 500; min-width: 80px; }
.skill-level { color: #909399; font-size: 12px; min-width: 140px; }
.gap-list { display: flex; flex-direction: column; gap: 6px; }
.gap-item { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.gap-name { font-weight: 500; }
.gap-tag { font-size: 12px; padding: 1px 8px; border-radius: 4px; }
.gap-high { background: #fef0f0; color: #f56c6c; }
.gap-low { background: #fdf6ec; color: #e6a23c; }
.transfer-list { display: flex; flex-wrap: wrap; gap: 10px; }
.transfer-item { font-size: 13px; background: #f0f9eb; color: #67c23a; padding: 2px 8px; border-radius: 4px; }
.highlights li, .risks li { font-size: 13px; line-height: 1.8; }
.risks li { color: #e6a23c; }
.rationale { font-size: 13px; color: #606266; line-height: 1.8; white-space: pre-wrap; }

.bias-card { border-left: 4px solid #e6a23c; }
.bias-action { font-size: 13px; color: #606266; margin-top: 8px; line-height: 1.6; }
.dist-stats { margin-top: 16px; }
.dist-item { margin-bottom: 8px; font-size: 13px; }
.dist-tag { margin-left: 12px; }
</style>
