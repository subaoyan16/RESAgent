<template>
  <!-- 岗位管理页面 — 岗位列表 + 新建/编辑弹窗 -->
  <div class="jobs-page">
    <!-- 页面顶部：标题 + 新建按钮 + 搜索框 -->
    <div class="page-header">
      <div class="page-title-row">
        <h2>岗位管理</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建岗位
        </el-button>
      </div>
      <!-- 搜索筛选栏 — 按岗位名称/公司关键词搜索 -->
      <div class="search-row">
        <el-input
          v-model="searchQuery"
          placeholder="搜索岗位名称、公司..."
          clearable
          :prefix-icon="Search"
          style="width: 360px"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        />
      </div>
    </div>

    <!-- 岗位列表表格：名称、公司、部门、状态、时间、操作 -->
    <el-card shadow="never" class="table-card">
      <el-table :data="jobs" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="title" label="岗位名称" min-width="160" />
        <el-table-column prop="company" label="公司" width="140" />
        <el-table-column prop="department" label="部门" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <!-- 操作列：详情 / 编辑 / 删除 -->
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewJob(row.id)">详情</el-button>
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确定删除此岗位？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页控件：显示总条数、每页条数切换、页码导航 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @change="fetchData"
        />
      </div>
    </el-card>

    <!-- 新建/编辑岗位弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="isEditing ? '编辑岗位' : '新建岗位'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        status-icon
      >
        <el-form-item label="岗位名称" prop="title">
          <el-input v-model="form.title" placeholder="请输入岗位名称" />
        </el-form-item>
        <el-form-item label="公司名称" prop="company">
          <el-input v-model="form.company" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="form.department" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="岗位描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="6"
            placeholder="请输入岗位描述、职责和要求..."
          />
        </el-form-item>
        <el-form-item label="硬性要求" prop="hard_requirements">
          <el-input
            v-model="form.hard_requirements"
            type="textarea"
            :rows="3"
            placeholder="每行一个，如：精通TypeScript"
          />
        </el-form-item>
        <el-form-item label="加分项" prop="nice_to_have">
          <el-input
            v-model="form.nice_to_have"
            type="textarea"
            :rows="3"
            placeholder="每行一个，可选加分条件"
          />
        </el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 提交 -->
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEditing ? '保存修改' : '创建岗位' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 岗位管理页面 — 岗位列表 + CRUD 操作
 *
 * 加载所有岗位的分页列表，支持按关键词搜索。
 * 用户可新建、编辑、删除岗位。
 * 编辑弹窗中可设置岗位名称、公司、描述、硬性要求、加分项等字段。
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'

const router = useRouter()
const formRef = ref<any>(null)

// 岗位列表数据及分页状态
const jobs = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchQuery = ref('')

// 弹窗控制
const showCreateDialog = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)

// 表单数据模型
const form = ref({
  title: '',
  company: '',
  department: '',
  description: '',
  hard_requirements: '',
  nice_to_have: ''
})

// 表单校验规则：岗位名称和公司为必填
const rules = {
  title: [{ required: true, message: '请输入岗位名称', trigger: 'blur' }],
  company: [{ required: true, message: '请输入公司名称', trigger: 'blur' }]
}

// 从 API 加载分页岗位列表
const fetchData = async () => {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    const res: any = await $fetch('/api/jobs/', { params })
    jobs.value = res.items || res || []
    total.value = res.total || jobs.value.length
  } catch (e: any) {
    ElMessage.error('获取岗位列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索时重置页码并重新加载
const handleSearch = () => {
  page.value = 1
  fetchData()
}

// 跳转到岗位详情页
const viewJob = (id: string) => {
  router.push(`/jobs/${id}`)
}

// 打开编辑弹窗 — 回填已有数据
const openEdit = (job: any) => {
  isEditing.value = true
  editingId.value = job.id
  const apiHard = job.requirements?.hard || []
  const apiNice = job.requirements?.nice_to_have || []
  form.value = {
    title: job.title || '',
    company: job.company || '',
    department: job.department || '',
    description: job.description || '',
    hard_requirements: apiHard.map((r: any) => r.skill || r).join('\n'),
    nice_to_have: apiNice.map((r: any) => r.skill || r).join('\n')
  }
  showCreateDialog.value = true
}

// 重置表单到空状态
const resetForm = () => {
  form.value = { title: '', company: '', department: '', description: '', hard_requirements: '', nice_to_have: '' }
  isEditing.value = false
  editingId.value = null
}

// 提交表单：创建或更新岗位
const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    // 构建请求载荷：将文本行转换为结构化需求数组
    const payload: any = {
      title: form.value.title,
      company: form.value.company,
      department: form.value.department,
      description: form.value.description,
      requirements: {
        hard: form.value.hard_requirements
          .split('\n')
          .filter(Boolean)
          .map((s: string) => ({ skill: s.trim(), min_years: 0, weight: 0.9, category: 'other' })),
        nice_to_have: form.value.nice_to_have
          .split('\n')
          .filter(Boolean)
          .map((s: string) => ({ skill: s.trim(), weight: 0.3, category: 'other' }))
      },
      scoring_weights: {
        skill_match: 0.45,
        experience_relevance: 0.25,
        education: 0.10,
        career_trajectory: 0.10,
        other: 0.10
      }
    }

    if (isEditing.value && editingId.value) {
      await $fetch(`/api/jobs/${editingId.value}`, {
        method: 'PUT',
        body: payload
      })
      ElMessage.success('岗位更新成功')
    } else {
      await $fetch('/api/jobs/', {
        method: 'POST',
        body: payload
      })
      ElMessage.success('岗位创建成功')
    }

    showCreateDialog.value = false
    resetForm()
    await fetchData()
  } catch (e: any) {
    ElMessage.error(isEditing.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除岗位（需要二次确认）
const handleDelete = async (id: string) => {
  try {
    await $fetch(`/api/jobs/${id}`, { method: 'DELETE' })
    ElMessage.success('岗位已删除')
    await fetchData()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.jobs-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-title-row h2 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.search-row {
  display: flex;
  gap: 12px;
}

.table-card {
  border-radius: 8px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
