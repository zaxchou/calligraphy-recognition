<template>
  <div class="app">
    <!-- 顶部导航（annotate 和全屏页面隐藏：分析/行旅 tab） -->
    <header v-if="!$route.path.startsWith('/annotate') && !($route.path.startsWith('/artist/') && ($route.name === 'ArtistAnalysis' || $route.name === 'ArtistAnalysisLegacy' || $route.name === 'ArtistMap' || $route.name === 'ArtistLiteratureReader'))" class="main-header" :class="{ 'home-header': $route.path === '/' }">
      <div class="header-content">
        <router-link to="/" class="logo">
          <img src="/logo.png" alt="墨" class="logo-img">
          <div class="logo-text">
            <span class="logo-main">{{ displayTitle }}</span>
            <span class="logo-sub">{{ displaySubtitle }}</span>
          </div>
        </router-link>
        <nav class="main-nav">
          <router-link to="/" class="nav-item" active-class="active" exact-active-class="active"><span class="nav-text">首页</span></router-link>
          <router-link to="/knowledge" class="nav-item" active-class="active"><span class="nav-text">写意知识库</span></router-link>
          <router-link to="/artists" class="nav-item" active-class="active"><span class="nav-text">艺术家百科</span></router-link>
          <router-link to="/tiba" class="nav-item" :class="{ active: $route.path.startsWith('/tiba') }" @click="handleTibaNav"><span class="nav-text">题跋分析</span></router-link>
          <router-link v-if="siteConfig.readonly !== 'true'" to="/composition" class="nav-item" :class="{ active: $route.path.startsWith('/composition') }"><span class="nav-text">潘天寿教你构图</span></router-link>
          <router-link v-if="siteConfig.readonly !== 'true'" to="/qczh" class="nav-item" active-class="active"><span class="nav-text">起承转合</span></router-link>
        </nav>
        <div class="user-area" v-if="siteConfig.readonly !== 'true'">
          <button class="lang-switch" @click="toggleLang" :title="$t('lang.switch')">
            {{ locale === 'zh' ? 'EN' : '中' }}
          </button>
          <template v-if="authStore.isLoggedIn">
            <NotificationBell />
            <div class="user-menu-wrap" @mouseenter="showUserMenu" @mouseleave="hideUserMenu">
              <span class="user-nickname user-dropdown-trigger">
                <img v-if="authStore.avatarUrl" :src="authStore.avatarUrl" class="user-avatar-mini" />
                <span v-else class="user-avatar-mini-placeholder">{{ authStore.nickname?.charAt(0) || '用' }}</span>
                {{ authStore.nickname }} <span class="user-arrow" :class="{ open: userMenuOpen }">▾</span>
              </span>
              <div class="user-dropdown" v-show="userMenuOpen" @mouseenter="showUserMenu" @mouseleave="hideUserMenu">
                <div v-if="authStore.isEditor" class="user-dropdown-item" @click="go('/admin')">📂 管理后台</div>
                <div class="user-dropdown-item" @click="go('/user/center')">👤 用户中心</div>
                <div class="user-dropdown-item" @click="go('/my/knowledge')">📁 我的知识库</div>
                <div class="user-dropdown-item" @click="go('/content-analysis?my=1')">🎨 我的分析历史</div>
                <div class="user-dropdown-item user-dropdown-divider" @click="handleLogout()">退出登录</div>
              </div>
            </div>
          </template>
          <router-link v-else to="/login" class="user-login-link">
            <span class="nav-text">登录</span>
          </router-link>
        </div>
        <!-- 移动端汉堡菜单按钮 -->
        <button class="mobile-menu-toggle" @click="toggleMobileMenu" aria-label="打开菜单">
          <el-icon :size="22"><Menu /></el-icon>
        </button>
      </div>
    </header>

    <!-- 移动端菜单遮罩层 -->
    <transition name="drawer-fade">
      <div v-if="mobileMenuOpen" class="mobile-overlay" @click="closeMobileMenu"></div>
    </transition>

    <!-- 移动端菜单抽屉 -->
    <transition name="drawer-slide">
      <div v-if="mobileMenuOpen" class="mobile-drawer">
        <div class="drawer-header">
          <div class="drawer-logo">
            <img src="/logo.png" alt="墨" class="drawer-logo-img">
            <div class="drawer-logo-text">
              <span class="drawer-logo-main">{{ displayTitle }}</span>
            </div>
          </div>
          <button class="drawer-close" @click="closeMobileMenu" aria-label="关闭菜单">
            <el-icon :size="20"><Close /></el-icon>
          </button>
        </div>
        <nav class="drawer-nav">
          <a class="drawer-nav-item" @click.prevent="drawerNavigate('/')">
            <span class="nav-text">首页</span>
          </a>
          <a class="drawer-nav-item" @click.prevent="drawerNavigate('/knowledge')">
            <span class="nav-text">写意知识库</span>
          </a>
          <a class="drawer-nav-item" @click.prevent="drawerNavigate('/artists')">
            <span class="nav-text">艺术家百科</span>
          </a>
          <a class="drawer-nav-item" @click.prevent="drawerNavigate('/tiba')">
            <span class="nav-text">题跋分析</span>
          </a>
          <a v-if="siteConfig.readonly !== 'true'" class="drawer-nav-item" @click.prevent="drawerNavigate('/composition')">
            <span class="nav-text">潘天寿教你构图</span>
          </a>
          <a v-if="siteConfig.readonly !== 'true'" class="drawer-nav-item" @click.prevent="drawerNavigate('/qczh')">
            <span class="nav-text">起承转合</span>
          </a>
          <template v-if="authStore.isLoggedIn && siteConfig.readonly !== 'true'">
            <div class="drawer-section-label">个人中心</div>
            <a v-if="authStore.isEditor" class="drawer-nav-item" @click.prevent="drawerNavigate('/admin')">
              <span class="nav-text">📂 管理后台</span>
            </a>
            <a class="drawer-nav-item" @click.prevent="drawerNavigate('/user/center')">
              <span class="nav-text">👤 用户中心</span>
            </a>
            <a class="drawer-nav-item" @click.prevent="drawerNavigate('/my/knowledge')">
              <span class="nav-text">📁 我的知识库</span>
            </a>
            <a class="drawer-nav-item" @click.prevent="drawerNavigate('/content-analysis')">
              <span class="nav-text">🎨 我的分析历史</span>
            </a>
            <div class="drawer-nav-item drawer-logout-item" @click="handleLogout(); closeMobileMenu()">
              <span class="nav-text">退出登录</span>
            </div>
          </template>
          <a v-else-if="siteConfig.readonly !== 'true'" class="drawer-nav-item" @click.prevent="drawerNavigate('/login')">
            <span class="nav-text">登录</span>
          </a>
        </nav>
      </div>
    </transition>

    <!-- 宣纸背景纹理 -->
    <div class="grain-overlay"></div>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- 全局浮动聊天窗（所有画家页面隐藏，已在子页面各自挂载 ChatFloat） -->
    <ChatFloat v-if="siteConfig.readonly !== 'true' && !$route.path.startsWith('/knowledge') && !$route.path.startsWith('/artist/')" />

    <!-- 底部（annotate 页面隐藏） -->
    <footer v-if="!$route.path.startsWith('/annotate')" class="main-footer">
      <div class="footer-content">
        <div class="footer-divider">
          <span class="divider-line"></span>
          <img src="/logo.png" alt="墨" class="divider-seal-img">
          <span class="divider-line"></span>
        </div>
        <p class="footer-text">{{ siteConfig.footer }}</p>
        <p class="footer-sub" v-if="siteConfig.author">作者 {{ siteConfig.author }}</p>
        <p class="footer-sub"><a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;">沪ICP备2026019654号-2</a></p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Menu, Close, ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from './stores/authStore'
import { useI18n } from 'vue-i18n'
import NotificationBell from './components/NotificationBell.vue'
import ChatFloat from './components/ChatFloat.vue'
import { siteConfig } from './config'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { locale } = useI18n()
const mobileMenuOpen = ref(false)
const userMenuOpen = ref(false)

const displayTitle = computed(() => locale.value === 'en' ? 'Molin' : siteConfig.title)
const displaySubtitle = computed(() => locale.value === 'en' ? 'Chinese Painting & Calligraphy Intelligence' : siteConfig.subtitle)

function drawerNavigate(path) {
  mobileMenuOpen.value = false
  router.push(path)
}
let closeTimer = null
function showUserMenu() { clearTimeout(closeTimer); userMenuOpen.value = true }
function hideUserMenu() { closeTimer = setTimeout(() => { userMenuOpen.value = false }, 200) }

// 启动时刷新用户信息，确保 role 与数据库同步
onMounted(() => {
  if (authStore.isLoggedIn) authStore.refreshProfile()
})

function toggleMobileMenu() { mobileMenuOpen.value = !mobileMenuOpen.value }
function closeMobileMenu() { mobileMenuOpen.value = false }
function navigateAndClose() {
  mobileMenuOpen.value = false
}
function handleLogout() { authStore.logout(); router.push('/'); userMenuOpen.value = false }
function handleTibaNav(e) {
  // 如果已经在题跋详情页，强制返回首页（Vue Router 不会自动触发）
  if (route.path.startsWith('/tiba/') && route.params.id) {
    e.preventDefault()
    router.push('/tiba')
  }
}
function toggleLang() {
  locale.value = locale.value === 'zh' ? 'en' : 'zh'
  localStorage.setItem('lang', locale.value)
}
function go(path) { router.push(path); userMenuOpen.value = false }
</script>

<style>
/* === 全局样式 — Claude 风格 === */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-sans);
  background: var(--parchment);
  color: var(--near-black);
  line-height: var(--leading-relaxed);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 标题全局使用衬线体 */
h1, h2, h3, h4, h5, h6 {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-weight: 500;
  line-height: var(--leading-snug);
  color: var(--near-black);
}

/* Element Plus 覆盖 — 输入框暖色边框 */
.el-input__wrapper {
  box-shadow: none !important;
  border: 1px solid var(--border-warm);
  background-color: var(--pure-white);
  border-radius: var(--radius-lg);
  transition: border-color var(--transition-fast);
}

.el-input__wrapper:hover {
  border-color: var(--ring-warm);
}

.el-input__wrapper.is-focus {
  border-color: var(--focus-blue);
}

.el-input__inner {
  box-shadow: none !important;
  border: none !important;
  outline: none !important;
  font-family: var(--font-sans);
}

/* Element Plus 按钮暖色调 */
.el-button--primary {
  --el-button-bg-color: var(--cinnabar) !important;
  --el-button-border-color: var(--cinnabar) !important;
  --el-button-hover-bg-color: var(--cinnabar-light) !important;
  --el-button-hover-border-color: var(--cinnabar-light) !important;
  border-radius: var(--radius-md) !important;
}

/* Element Plus 消息暖色 */
.el-message-box {
  border-radius: var(--radius-lg) !important;
}

/* ── ElMessage 轻提示覆盖 ──────────────────────── */
.el-message {
  --el-message-bg-color: transparent !important;
  --el-message-border-color: transparent !important;
  background: rgba(255,252,245,0.92) !important;
  border: none !important;
  border-radius: 20px !important;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important;
  padding: 6px 16px !important;
  backdrop-filter: blur(8px);
  pointer-events: auto;
  z-index: 9999;
  max-width: 320px;
}
.el-message .el-message__icon {
  margin-right: 4px;
}
.el-message .el-message__icon svg {
  width: 14px;
  height: 14px;
}
.el-message .el-message__content {
  font-size: 12px;
  color: #5a5347;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.el-message .el-message__closeBtn {
  font-size: 12px;
  color: #bbb;
  right: 8px;
}
/* 不同类型的左侧色条 */
.el-message.el-message--success {
  border-left: 3px solid #3cb88b !important;
  border-radius: 4px 20px 20px 4px !important;
}
.el-message.el-message--error {
  border-left: 3px solid #e07a5f !important;
  border-radius: 4px 20px 20px 4px !important;
}
.el-message.el-message--warning {
  border-left: 3px solid #d4a843 !important;
  border-radius: 4px 20px 20px 4px !important;
}
.el-message.el-message--info {
  border-left: 3px solid #909399 !important;
  border-radius: 4px 20px 20px 4px !important;
}

/* 选中文字色 */
::selection {
  background: var(--cinnabar);
  color: var(--pure-white);
}

/* ─── 内容区过渡动画 ─── */
.page-slide-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.page-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}


/* 滚动条 — 暖色 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--parchment);
}

::-webkit-scrollbar-thumb {
  background: var(--ring-warm);
  border-radius: var(--radius-full);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--ring-deep);
}
</style>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--parchment);
}

/* === 顶部导航 — Claude 风格 === */
.main-header {
  background: var(--ivory);
  border-bottom: 1px solid var(--border-cream);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(18px);
  background: rgba(250, 249, 245, 0.85);
}

.header-content {
  max-width: var(--container-wide);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--space-2xl);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  transition: opacity var(--transition-normal);
  text-decoration: none;
}

.logo:hover {
  opacity: 0.85;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  object-fit: contain;
  transition: opacity var(--transition-normal);
  flex-shrink: 0;
}

.logo:hover .logo-img {
  opacity: 0.8;
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-main {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 16px;
  font-weight: 500;
  color: var(--near-black);
  letter-spacing: 0.08em;
  line-height: 1.2;
}

.logo-sub {
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--stone-gray);
  letter-spacing: 0.04em;
  line-height: 1.3;
}

/* === 导航菜单 — Claude 风格 === */
.main-nav {
  display: flex;
  gap: var(--space-2xl);
}

.nav-item {
  text-decoration: none;
  position: relative;
  padding: var(--space-sm) 0;
}

.nav-text {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  font-weight: 500;
  color: var(--olive-gray);
  letter-spacing: 0.06em;
  transition: color var(--transition-fast);
}

.nav-item:hover .nav-text,
.nav-item.active .nav-text {
  color: var(--near-black);
}

/* 下划线 — 极细暖色线 */
.nav-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%) scaleX(0);
  width: 100%;
  height: 1px;
  background: var(--cinnabar);
  transition: transform var(--transition-normal);
}

.nav-item:hover::after,
.nav-item.active::after {
  transform: translateX(-50%) scaleX(1);
}

/* === 移动端汉堡按钮（PC 隐藏） === */
.mobile-menu-toggle {
  display: none;
}

/* === 主内容区 === */
.main-content {
  flex: 1;
}

/* === 底部 — Claude 暗色区 === */
.main-footer {
  background: var(--deep-dark);
  padding: var(--space-4xl) var(--space-2xl);
  text-align: center;
}

.footer-content {
  max-width: 700px;
  margin: 0 auto;
}

.footer-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-lg);
  margin-bottom: var(--space-2xl);
}

.divider-line {
  width: 80px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}

.divider-seal-img {
  width: 28px;
  height: 28px;
  object-fit: contain;
  border-radius: 4px;
  opacity: 0.9;
}

.footer-text {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-caption);
  color: var(--warm-silver);
  letter-spacing: 0.15em;
  margin-bottom: var(--space-sm);
}

.footer-sub {
  font-family: var(--font-sans);
  font-size: var(--text-label);
  color: var(--gold);
  letter-spacing: 0.08em;
}

/* === 用户区域 === */
.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lang-switch {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border: 1px solid #d0c8b8;
  border-radius: 4px;
  background: transparent;
  color: #8a7a5e;
  cursor: pointer;
  transition: all 0.2s;
}
.lang-switch:hover {
  background: #f5f0e8;
  border-color: #b8a47e;
  color: #5d4e37;
}

.admin-nav-link {
  font-family: var(--font-sans);
  font-size: var(--text-label);
  color: var(--cinnabar);
  text-decoration: none;
  border: 1px solid var(--cinnabar);
  border-radius: var(--radius-md);
  padding: 4px 10px;
  transition: all var(--transition-fast);
  font-weight: 500;
}

.admin-nav-link:hover {
  background: var(--cinnabar);
  color: var(--pure-white);
}

/* 首页暗色主题下的管理后台链接 */
.home-header .admin-nav-link {
  color: var(--gold);
  border-color: var(--gold);
}

.home-header .admin-nav-link:hover {
  background: var(--gold);
  color: var(--near-black);
}

.user-nickname {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  color: var(--olive-gray);
  font-weight: 500;
}

.user-dropdown-trigger {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  user-select: none;
}

.user-avatar-mini {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid #e8e4d8;
  flex-shrink: 0;
}

.user-avatar-mini-placeholder {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f5f0e8;
  border: 1px solid #e8e4d8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #c8a45c;
  flex-shrink: 0;
}

.user-dropdown-trigger:hover {
  color: var(--gold);
  background: rgba(200, 164, 92, 0.06);
}

.user-arrow {
  font-size: 10px;
  transition: transform 0.2s;
  display: inline-block;
}
.user-arrow.open {
  transform: rotate(180deg);
}

/* 原生下拉菜单 */
.user-menu-wrap {
  position: relative;
  display: inline-flex;
}

.user-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0;
  padding-top: 8px;
  background: #fff;
  border: 1px solid #e8e4d8;
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.12);
  min-width: 180px;
  z-index: 10001;
  overflow: hidden;
}
/* 透明桥接区防止鼠标移动时菜单消失 */
.user-dropdown::before {
  content: '';
  position: absolute;
  top: -8px;
  left: 0;
  right: 0;
  height: 8px;
}

.user-dropdown-item {
  padding: 10px 16px;
  font-size: 14px;
  color: #2c2416;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.user-dropdown-item:hover {
  background: #f8f5f0;
  color: #c8a45c;
}

.user-dropdown-divider {
  border-top: 1px solid #f0ebe0;
  margin-top: 0;
}

.drawer-section-label {
  font-size: var(--text-label);
  color: var(--stone-gray);
  padding: 12px 24px 4px;
  margin-top: 8px;
  border-top: 1px solid var(--border-warm);
}

.drawer-logout-item {
  cursor: pointer;
  color: var(--cinnabar) !important;
  border-top: 1px solid var(--border-warm);
  margin-top: 8px;
}

.user-logout-btn {
  font-family: var(--font-sans);
  font-size: var(--text-label);
  color: var(--stone-gray);
  background: none;
  border: 1px solid var(--border-warm);
  border-radius: var(--radius-md);
  padding: 4px 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.user-logout-btn:hover {
  color: var(--cinnabar);
  border-color: var(--cinnabar);
}

.user-login-link {
  text-decoration: none;
}


/* === 响应式 === */
@media (max-width: 768px) {
  .header-content {
    padding: 0 var(--space-lg);
  }

  .main-nav {
    display: none;
  }

  .user-area {
    display: none;
  }

  .mobile-menu-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--olive-gray);
    padding: 4px;
    border-radius: 6px;
    transition: background var(--transition-fast);
  }

  .mobile-menu-toggle:active {
    background: rgba(0, 0, 0, 0.05);
  }

  .nav-text {
    font-size: var(--text-label);
  }

  .logo-sub {
    display: none;
  }
  
  .logo-img {
    width: 26px;
    height: 26px;
  }
}

/* === 移动端菜单遮罩层 === */
.mobile-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 200;
}

/* === 移动端菜单抽屉 === */
.mobile-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 280px;
  height: 100vh;
  height: 100dvh;
  background: var(--ivory);
  z-index: 201;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-cream);
}

.drawer-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drawer-logo-img {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  object-fit: contain;
  flex-shrink: 0;
}

.drawer-logo-main {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 15px;
  font-weight: 500;
  color: var(--near-black);
  letter-spacing: 0.08em;
}

.drawer-close {
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--stone-gray);
  padding: 6px;
  border-radius: 6px;
  transition: background var(--transition-fast);
}

.drawer-close:active {
  background: rgba(0, 0, 0, 0.05);
}

.drawer-nav {
  display: flex;
  flex-direction: column;
  padding: 12px 0;
}

.drawer-nav-item {
  display: flex;
  align-items: center;
  text-decoration: none;
  padding: 14px 20px;
  position: relative;
  transition: background var(--transition-fast);
}

.drawer-nav-item:active {
  background: rgba(0, 0, 0, 0.03);
}

.drawer-nav-item .nav-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--olive-gray);
  letter-spacing: 0.06em;
  transition: color var(--transition-fast);
}

.drawer-nav-item:hover .nav-text,
.drawer-nav-item.active .nav-text {
  color: var(--near-black);
}

/* 抽屉导航下划线 */
.drawer-nav-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 20px;
  right: 20px;
  height: 1px;
  background: var(--border-cream);
}

.drawer-nav-item:last-child::after {
  display: none;
}

.drawer-nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--cinnabar);
  border-radius: 0 3px 3px 0;
}

/* 管理后台抽屉链接 */
.admin-drawer-link .nav-text {
  color: var(--cinnabar) !important;
  font-weight: 600 !important;
}

.admin-drawer-link.active .nav-text {
  color: var(--near-black) !important;
}

.admin-drawer-link.active::before {
  background: var(--cinnabar);
}

/* 首页深色主题适配 */
.home-header .mobile-menu-toggle {
  color: rgba(255, 255, 255, 0.65);
}

.home-header .mobile-drawer {
  background: rgba(20, 20, 19, 0.98);
}

.home-header .drawer-header {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.home-header .drawer-logo-main {
  color: var(--pure-white);
}

.home-header .drawer-close {
  color: rgba(255, 255, 255, 0.55);
}

.home-header .drawer-nav-item .nav-text {
  color: rgba(255, 255, 255, 0.65);
}

.home-header .drawer-nav-item:hover .nav-text,
.home-header .drawer-nav-item.active .nav-text {
  color: var(--pure-white);
}

.home-header .drawer-nav-item::after {
  background: rgba(255, 255, 255, 0.06);
}

.home-header .drawer-nav-item.active::before {
  background: var(--gold);
}

.home-header .admin-drawer-link .nav-text {
  color: var(--gold) !important;
}

.home-header .admin-drawer-link.active .nav-text {
  color: var(--pure-white) !important;
}

.home-header .admin-drawer-link.active::before {
  background: var(--gold);
}

/* === 过渡动画 === */
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.25s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}

/* === 首页专属 — 黑底白字 Header === */
.home-header {
  background: rgba(20, 20, 19, 0.92) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.home-header .logo-main {
  color: var(--pure-white);
}

.home-header .logo-sub {
  color: rgba(255, 255, 255, 0.55);
}

.home-header .nav-text {
  color: rgba(255, 255, 255, 0.65);
}

.home-header .nav-item:hover .nav-text,
.home-header .nav-item.active .nav-text {
  color: var(--pure-white);
}

.home-header .nav-item::after {
  background: var(--gold);
}

.home-header .user-nickname {
  color: rgba(255, 255, 255, 0.75);
}

.home-header .user-logout-btn {
  color: rgba(255, 255, 255, 0.55);
  border-color: rgba(255, 255, 255, 0.2);
}

.home-header .user-logout-btn:hover {
  color: var(--gold);
  border-color: var(--gold);
}

.home-header .user-login-link .nav-text {
  color: rgba(255, 255, 255, 0.65);
}

.home-header .user-login-link:hover .nav-text {
  color: var(--pure-white);
}
</style>
