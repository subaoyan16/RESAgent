<template>
  <!-- 匹配度分数徽标组件 — SVG 圆形进度显示 -->
  <div class="match-score-badge" :class="colorClass" :title="`匹配度: ${percentage}%`">
    <svg class="score-circle" :width="size" :height="size" viewBox="0 0 36 36">
      <!-- 背景圆环（灰色） -->
      <path
        class="circle-bg"
        d="M18 2.0845
          a 15.9155 15.9155 0 0 1 0 31.831
          a 15.9155 15.9155 0 0 1 0 -31.831"
        fill="none"
        stroke="#e4e7ed"
        :stroke-width="strokeWidth"
      />
      <!-- 前景圆环（根据分数着色，显示匹配百分比） -->
      <path
        class="circle-fill"
        d="M18 2.0845
          a 15.9155 15.9155 0 0 1 0 31.831
          a 15.9155 15.9155 0 0 1 0 -31.831"
        fill="none"
        :stroke="strokeColor"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
        :stroke-dasharray="`${percentage}, 100`"
      />
      <!-- 中央文字（百分比数值） -->
      <text x="18" y="20.5" class="score-text" text-anchor="middle" :font-size="fontSize" :fill="strokeColor">
        {{ percentage }}
      </text>
    </svg>
    <!-- 分数等级文字标签（如"优秀"、"良好"等） -->
    <span class="score-label" v-if="showLabel">{{ labelText }}</span>
  </div>
</template>

<script setup lang="ts">
/**
 * 匹配度分数徽标组件 MatchScoreBadge — SVG 环形进度显示
 *
 * 使用 SVG 绘制圆形进度条，直观展示候选人匹配度百分比。
 * 根据分数值自动切换颜色：
 *   >= 0.85 绿色（优秀） / >= 0.70 黄色（良好） / >= 0.50 红色（一般） / < 0.50 灰色（较低）
 *
 * @prop score - 匹配分数（0 ~ 1 之间的小数）
 * @prop size - SVG 尺寸（像素，默认 48）
 * @prop showLabel - 是否显示文字等级标签（默认 false）
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  score: number
  size?: number
  showLabel?: boolean
}>(), {
  size: 48,
  showLabel: false
})

// 将分数转换为百分比（四舍五入）
const percentage = computed(() => Math.round(Math.min(Math.max(props.score, 0), 1) * 100))

// 根据尺寸计算圆环宽度
const strokeWidth = computed(() => Math.max(2.5, props.size / 14))

// 根据尺寸计算中央字体大小
const fontSize = computed(() => Math.max(5, props.size / 8))

// CSS 颜色类名
const colorClass = computed(() => {
  if (props.score >= 0.85) return 'score-green'
  if (props.score >= 0.70) return 'score-yellow'
  if (props.score >= 0.50) return 'score-orange'
  return 'score-red'
})

// SVG 圆环前景色
const strokeColor = computed(() => {
  if (props.score >= 0.85) return '#67c23a'
  if (props.score >= 0.70) return '#e6a23c'
  if (props.score >= 0.50) return '#f56c6c'
  return '#909399'
})

// 分数等级中文标签
const labelText = computed(() => {
  if (props.score >= 0.85) return '优秀'
  if (props.score >= 0.70) return '良好'
  if (props.score >= 0.50) return '一般'
  return '较低'
})
</script>

<style scoped>
.match-score-badge {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.score-circle {
  display: block;
}

.circle-bg {
  opacity: 0.3;
}

.score-text {
  font-weight: 700;
  dominant-baseline: central;
}

.score-label {
  font-size: 11px;
  font-weight: 500;
}

.score-green .score-label { color: #67c23a; }
.score-yellow .score-label { color: #e6a23c; }
.score-orange .score-label { color: #f56c6c; }
.score-red .score-label { color: #909399; }
</style>
