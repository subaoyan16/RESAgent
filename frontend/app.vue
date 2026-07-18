<template>
  <!-- 整体应用布局 — 左侧导航 + 右侧主内容区 -->
  <el-container class="app-container">
    <!-- 左侧导航栏：应用 Logo + 菜单 -->
    <el-aside width="220px" class="app-aside">
      <!-- 顶部品牌标识区 -->
      <div class="aside-header">
        <el-icon :size="28" color="#409eff"><Monitor /></el-icon>
        <span class="aside-title">RESAgent</span>
      </div>
      <!-- 主导航菜单：首页 / 岗位管理 / 筛选任务 -->
      <div class="aside-menu">
        <NuxtLink to="/" class="menu-item" :class="{ active: route.path === '/' }">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </NuxtLink>
        <NuxtLink to="/jobs" class="menu-item" :class="{ active: route.path.startsWith('/jobs') }">
          <el-icon><Briefcase /></el-icon>
          <span>岗位管理</span>
        </NuxtLink>
        <NuxtLink to="/screening" class="menu-item" :class="{ active: route.path.startsWith('/screening') }">
          <el-icon><DataAnalysis /></el-icon>
          <span>筛选任务</span>
        </NuxtLink>
      </div>
    </el-aside>

    <!-- 右侧主容器：顶栏 + 页面内容 -->
    <el-container class="main-container">
      <!-- 顶部导航栏：面包屑 + 标题 -->
      <el-header class="app-header" height="56px">
        <div class="header-left">
          <!-- 面包屑导航：动态显示当前所在层级 -->
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="breadcrumb.length > 0">{{ breadcrumb }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <span class="header-title">ResAgent — 智能简历筛选</span>
        </div>
      </el-header>
      <!-- 主页面内容区：通过 NuxtPage 渲染子路由页面 -->
      <el-main class="app-main">
        <NuxtPage />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
/**
 * 应用根组件 App.vue — 整体布局框架
 *
 * 提供左侧固定导航栏和右侧主内容区的布局结构。
 * 根据当前路由路径高亮左侧菜单项、显示面包屑导航。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Monitor,
  HomeFilled,
  Briefcase,
  DataAnalysis
} from '@element-plus/icons-vue'

const route = useRoute()

// 当前激活的菜单项 — 根据路由前缀匹配
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/jobs')) return '/jobs'
  if (path.startsWith('/screening')) return '/screening'
  if (path.startsWith('/reports')) return '/screening'
  return '/'
})

// 当前页面面包屑文本 — 根据路由前缀生成中文名称
const breadcrumb = computed(() => {
  const path = route.path
  if (path === '/') return ''
  if (path.startsWith('/jobs')) return '岗位管理'
  if (path.startsWith('/screening')) return '筛选任务'
  if (path.startsWith('/reports')) return '候选人报告'
  return ''
})
</script>

<style>
html, body, #__nuxt {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  background-color: #f0f2f5;
}
</style>

<style scoped>
.app-container {
  height: 100vh;
  overflow: hidden;
}

.app-aside {
  background-color: #1d1e1f;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.aside-header {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.aside-title {
  font-size: 18px;
  font-weight: 700;
  color: #e6e9ed;
  letter-spacing: 1px;
}

.aside-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
}

.aside-menu .el-menu-item {
  font-size: 14px;
  margin: 2px 8px;
  border-radius: 6px;
}

.aside-menu .menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 14px;
  color: #bfcbd9;
  text-decoration: none;
  border-radius: 6px;
  margin: 2px 8px;
}
.aside-menu .menu-item:hover {
  background-color: rgba(255, 255, 255, 0.06);
}
.aside-menu .menu-item.active {
  background-color: rgba(64, 158, 255, 0.15);
  color: #409eff;
}

.main-container {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-title {
  font-size: 13px;
  color: #909399;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}
</style>
