<template>
  <!-- 偏见检测标识列表组件 — 展示所有检测到的偏见告警 -->
  <div class="bias-flags">
    <div
      v-for="(flag, index) in flags"
      :key="index"
      class="flag-item"
    >
      <el-alert
        :title="flagTitle(flag)"
        :type="severityType(flag.severity)"
        :closable="false"
        show-icon
        class="flag-alert"
      >
        <template #default>
          <div class="flag-body">
            <!-- 偏见详情描述 -->
            <p class="flag-detail" v-if="flag.detail || flag.description">
              {{ flag.detail || flag.description }}
            </p>
            <!-- 建议操作 -->
            <p class="flag-action" v-if="flag.suggested_action || flag.action">
              <strong>建议操作:</strong> {{ flag.suggested_action || flag.action }}
            </p>
          </div>
        </template>
      </el-alert>
    </div>

    <!-- 无偏见标识时的空状态 -->
    <el-empty v-if="!flags || flags.length === 0" description="未检测到偏见标识" :image-size="40" />
  </div>
</template>

<script setup lang="ts">
import type { AlertType } from 'element-plus'

/**
 * 偏见检测标识告警组件 BiasFlagAlert — 展示 AI 检测到的潜在偏见
 *
 * 以告警列表形式展示每个偏见的严重级别（高/中/低）、详细描述和建议操作。
 * 严重级别映射为 Element Plus Alert 类型：high -> error, medium -> warning, low -> info。
 *
 * @prop flags - 偏见标识数组，每个元素包含 title, severity, detail/description, suggested_action/action 等字段
 */
interface BiasFlag {
  title?: string
  severity?: 'low' | 'medium' | 'high'
  detail?: string
  description?: string
  suggested_action?: string
  action?: string
  [key: string]: any
}

withDefaults(defineProps<{
  flags: BiasFlag[]
}>(), {
  flags: () => []
})

// 将偏见严重级别映射为 Alert 组件类型
const severityType = (severity?: string): AlertType => {
  switch (severity) {
    case 'high':
      return 'error'
    case 'medium':
      return 'warning'
    case 'low':
      return 'info'
    default:
      return 'info'
  }
}

// 将后端返回的 type 字段映射为中文标题
const biasTypeLabels: Record<string, string> = {
  gender: '性别偏见',
  potential_gender_bias: '潜在性别偏见',
  age: '年龄偏见',
  potential_age_bias: '潜在年龄偏见',
  education: '院校偏见',
  potential_education_bias: '潜在院校偏见',
  geography: '地域偏见',
  geographic: '地域偏见',
  potential_geographic_bias: '潜在地域偏见',
  experience_description: '经验描述偏差',
}

const flagTitle = (flag: BiasFlag): string => {
  return flag.title || biasTypeLabels[flag.type] || flag.type || '偏见标识'
}
</script>

<style scoped>
.bias-flags {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flag-item {
  width: 100%;
}

.flag-alert {
  border-radius: 6px;
}

.flag-body {
  margin-top: 4px;
}

.flag-detail {
  margin: 0 0 6px 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.flag-action {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.flag-action strong {
  color: #303133;
}
</style>
