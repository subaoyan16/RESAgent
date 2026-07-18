<template>
  <!-- 筛选进度步骤条组件 — 展示筛选处理的五个阶段 -->
  <div class="screening-progress">
    <el-steps :active="activeStep" align-center finish-status="success" process-status="process">
      <el-step
        v-for="(step, index) in steps"
        :key="index"
        :title="step.label"
        :description="step.desc"
        :status="getStepStatus(index)"
      />
    </el-steps>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'

/**
 * 筛选进度步骤条组件 ScreeningProgress — 展示 AI 筛选处理流程的五个阶段
 *
 * 通过 Element Plus 的 Steps 组件展示当前任务所处的处理阶段。
 * 五个阶段依次为：简历解析 -> 岗位分析 -> 语义匹配 -> 偏见检测 -> 报告生成。
 *
 * @prop status - 任务状态（pending / running / completed / failed）
 * @prop currentStep - 当前完成的步骤序号（从 1 开始，默认 0）
 */
const props = withDefaults(defineProps<{
  status: string
  currentStep?: number
}>(), {
  currentStep: 0
})

// 定义筛选流程的五个步骤及其描述
const steps = [
  { label: '简历解析', desc: '上传并解析简历内容' },
  { label: '岗位分析', desc: 'Agent 分析岗位需求与权重' },
  { label: '语义匹配', desc: '混合检索 + Agent 深度匹配' },
  { label: '偏见检测', desc: 'Agent 五维度公平性审计' },
  { label: '报告生成', desc: 'Agent 生成评估报告' }
]

// 当前激活的步骤索引（从 0 开始）
const activeStep = computed(() => {
  if (props.status === 'completed') return steps.length // 已完成：所有步骤都完成
  if (props.status === 'failed') return Math.max(0, (props.currentStep || 1) - 1) // 失败：停在当前步骤
  return Math.max(0, (props.currentStep || 1) - 1) // 进行中：currentStep - 1
})

// 返回每个步骤的状态：wait / process / success / error
const getStepStatus = (index: number): 'wait' | 'process' | 'success' | 'error' => {
  if (props.status === 'failed' && index === activeStep.value) {
    return 'error' // 失败状态：当前步骤显示错误
  }
  if (index < activeStep.value || props.status === 'completed') {
    return 'success' // 已完成或已通过的步骤
  }
  if (index === activeStep.value && props.status === 'running') {
    return 'process' // 当前正在进行的步骤
  }
  return 'wait' // 等待中的步骤
}
</script>

<style scoped>
.screening-progress {
  padding: 16px 0;
}

.screening-progress :deep(.el-step__title) {
  font-size: 13px;
}

.screening-progress :deep(.el-step__description) {
  font-size: 11px;
  color: #909399;
}
</style>
