<template>
  <aside class="sidebar">
    <!-- Logo区域 -->
    <div class="sidebar-logo">
      <div class="logo-icon">
        <el-icon size="24"><Collection /></el-icon>
      </div>
      <div class="logo-text">
        <div class="logo-title">{{ siteConfig.title }}</div>
        <div class="logo-subtitle">{{ siteConfig.subtitle }}</div>
      </div>
    </div>

    <!-- 主导航 -->
    <nav class="sidebar-nav">
      <div class="nav-section">
        <div
          class="nav-item"
          :class="{ active: currentRoute === 'tubi' }"
          @click="navigateTo('tubi')"
        >
          <el-icon size="18"><HomeFilled /></el-icon>
          <span class="nav-label">概览</span>
        </div>
        <div class="nav-item" @click="showComingSoon">
          <el-icon size="18"><Picture /></el-icon>
          <span class="nav-label">作品分析</span>
        </div>
        <div class="nav-item" @click="showComingSoon">
          <el-icon size="18"><Edit /></el-icon>
          <span class="nav-label">字体识别</span>
        </div>
        <div class="nav-item" @click="showComingSoon">
          <el-icon size="18"><Document /></el-icon>
          <span class="nav-label">主题识别</span>
        </div>
        <div
          class="nav-item"
          :class="{ active: currentRoute === 'tubi-detail' }"
          @click="navigateTo('tubi-detail')"
        >
          <el-icon size="18"><ChatDotSquare /></el-icon>
          <span class="nav-label">题跋识别</span>
        </div>
        <div class="nav-item" @click="navigateToQCZH">
          <el-icon size="18"><Refresh /></el-icon>
          <span class="nav-label">起承转合</span>
        </div>
        <div class="nav-item" @click="navigateToContentAnalysis">
          <el-icon size="18"><DataAnalysis /></el-icon>
          <span class="nav-label">大数据分析</span>
        </div>
      </div>

      <div class="nav-section">
        <div class="nav-section-title">收藏</div>
        <div class="nav-item" @click="showComingSoon">
          <el-icon size="18"><FolderOpened /></el-icon>
          <span class="nav-label">作品库</span>
        </div>
        <div class="nav-item" @click="showComingSoon">
          <el-icon size="18"><Switch /></el-icon>
          <span class="nav-label">对比分析</span>
        </div>
        <div class="nav-item" @click="showComingSoon">
          <el-icon size="18"><Star /></el-icon>
          <span class="nav-label">我的收藏</span>
        </div>
      </div>
    </nav>

    <!-- 升级按钮 -->
    <div class="sidebar-upgrade">
      <div class="upgrade-card">
        <div class="upgrade-icon">+</div>
        <div class="upgrade-text">
          <div class="upgrade-title">升级专业版</div>
          <div class="upgrade-desc">解锁高级分析功能与更多创作工具。</div>
        </div>
        <el-button type="primary" size="small" class="upgrade-btn">
          立即升级
        </el-button>
      </div>
    </div>

    <!-- 用户信息 -->
    <div class="sidebar-user">
      <div class="user-avatar">
        <img v-if="userAvatar" :src="userAvatar" alt="avatar" />
        <el-icon v-else size="20"><User /></el-icon>
      </div>
      <div class="user-info">
        <div class="user-name">{{ userName }}</div>
        <div class="user-role">专业版</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Collection, HomeFilled, Picture, Edit, Document,
  ChatDotSquare, Refresh, DataAnalysis, FolderOpened,
  Switch, Star, User
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { siteConfig } from '../../config'

const route = useRoute()
const router = useRouter()

const currentRoute = computed(() => {
  if (route.path === '/tubi' || route.path === '/') return 'tubi'
  if (route.path.startsWith('/tubi/')) return 'tubi-detail'
  return ''
})

const userName = computed(() => {
  // 可以从 localStorage 或 store 获取
  return 'Zax'
})

const userAvatar = computed(() => {
  // 可以从 localStorage 或 store 获取
  return null
})

function navigateTo(path) {
  if (path === 'tubi') {
    router.push('/tubi')
  } else if (path === 'tubi-detail') {
    // 需要有当前作品才能进入详情页
    ElMessage.info('请先选择一幅作品查看详情')
  }
}

function navigateToQCZH() {
  router.push('/qczh')
}

function navigateToContentAnalysis() {
  router.push('/content-analysis')
}

function showComingSoon() {
  ElMessage.info('功能开发中，敬请期待')
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  height: 100vh;
  background: #f8f9fa;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
}

/* Logo区域 */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid #e8e8e8;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: #1a1a1a;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.logo-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.logo-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  font-family: 'Noto Serif SC', serif;
}

.logo-subtitle {
  font-size: 11px;
  color: #888;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.nav-section {
  margin-bottom: 24px;
}

.nav-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0 12px;
  margin-bottom: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #555;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: #e8e8e8;
  color: #1a1a1a;
}

.nav-item.active {
  background: #e8e8e8;
  color: #1a1a1a;
  font-weight: 500;
}

.nav-label {
  font-size: 13px;
}

/* 升级按钮 */
.sidebar-upgrade {
  padding: 0 12px 16px;
}

.upgrade-card {
  background: linear-gradient(135deg, #f0f0f0 0%, #e8e8e8 100%);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}

.upgrade-icon {
  width: 32px;
  height: 32px;
  background: #1a1a1a;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  margin: 0 auto 12px;
}

.upgrade-title {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.upgrade-desc {
  font-size: 11px;
  color: #888;
  margin-bottom: 12px;
  line-height: 1.4;
}

.upgrade-btn {
  width: 100%;
  background: #1a1a1a;
  border-color: #1a1a1a;
}

.upgrade-btn:hover {
  background: #333;
  border-color: #333;
}

/* 用户信息 */
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #e8e8e8;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: #1a1a1a;
}

.user-role {
  font-size: 11px;
  color: #888;
}
</style>
