<template>
  <!-- 简历卡片组件 — 展示候选人摘要信息 -->
  <el-card
    shadow="hover"
    class="resume-card"
    @click="emit('select', candidate)"
  >
    <!-- 头部：头像占位 + 姓名 + 邮箱 -->
    <div class="card-top">
      <div class="avatar-placeholder">
        {{ initials }}
      </div>
      <div class="card-main">
        <div class="candidate-name">{{ candidate.name || '未知' }}</div>
        <div class="candidate-email" v-if="candidate.email">{{ candidate.email }}</div>
      </div>
    </div>

    <!-- 经验年数 -->
    <div class="card-stats" v-if="candidate.experience_years">
      <el-icon :size="14"><Clock /></el-icon>
      <span>{{ candidate.experience_years }} 年经验</span>
    </div>

    <!-- 技能标签行：最多显示 5 个，超出显示 +N -->
    <div class="skills-row" v-if="candidate.skills && candidate.skills.length > 0">
      <el-tag
        v-for="skill in topSkills"
        :key="skill"
        size="small"
        type="info"
        effect="plain"
        class="skill-tag"
      >
        {{ skill }}
      </el-tag>
      <span v-if="candidate.skills.length > 5" class="more-skills">
        +{{ candidate.skills.length - 5 }}
      </span>
    </div>

    <!-- 所在地 -->
    <div class="location-row" v-if="candidate.location">
      <el-icon :size="14"><Location /></el-icon>
      <span>{{ candidate.location }}</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
/**
 * 简历卡片组件 ResumeCard — 展示候选人关键信息摘要
 *
 * 显示候选人的头像首字母、姓名、邮箱、经验年数、技能标签和所在地。
 * 点击卡片触发 select 事件，父组件可据此跳转到详情报告页。
 *
 * @prop candidate - 候选人数据对象（含 name, email, experience_years, skills, location 等字段）
 * @emit select - 点击卡片时触发，传递候选人数据
 */
import { computed } from 'vue'
import { Clock, Location } from '@element-plus/icons-vue'

const props = defineProps<{
  candidate: {
    id?: string
    name?: string
    email?: string
    experience_years?: number
    skills?: string[]
    location?: string
    [key: string]: any
  }
}>()

const emit = defineEmits<{
  select: [candidate: any]
}>()

// 头像占位文字：取姓名前两个字
const initials = computed(() => {
  const name = props.candidate.name || '?'
  if (name.length >= 2) {
    return name.slice(0, 2)
  }
  return name
})

// 最多显示前 5 个技能标签
const topSkills = computed(() => {
  return (props.candidate.skills || []).slice(0, 5)
})
</script>

<style scoped>
.resume-card {
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.resume-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.12);
}

.card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.avatar-placeholder {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.card-main {
  flex: 1;
  min-width: 0;
}

.candidate-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.candidate-email {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-stats {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.skills-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
  align-items: center;
}

.skill-tag {
  font-size: 11px;
}

.more-skills {
  font-size: 11px;
  color: #909399;
  margin-left: 2px;
}

.location-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}
</style>
