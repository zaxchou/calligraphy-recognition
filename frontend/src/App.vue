<template>
  <div class="app">
    <!-- 顶部导航（annotate 页面隐藏） -->
    <header v-if="!$route.path.startsWith('/annotate')" class="main-header" :class="{ 'home-header': $route.path === '/' }">
      <div class="header-content">
        <div class="logo">
          <img src="/logo.png" alt="墨" class="logo-img">
          <div class="logo-text">
            <span class="logo-main">中国画与书法</span>
            <span class="logo-sub">AI 综合分析系统</span>
          </div>
        </div>
        <nav class="main-nav">
          <router-link to="/" class="nav-item" active-class="active" exact-active-class="active"><span class="nav-text">首页</span></router-link>
          <router-link to="/knowledge" class="nav-item" active-class="active"><span class="nav-text">写意知识库</span></router-link>
          <router-link to="/tubi" class="nav-item" :class="{ active: $route.path.startsWith('/tubi') }"><span class="nav-text">题跋分析</span></router-link>
          <router-link to="/recognize" class="nav-item" active-class="active"><span class="nav-text">字体识别</span></router-link>
          <router-link to="/composition" class="nav-item" :class="{ active: $route.path.startsWith('/composition') }"><span class="nav-text">潘天寿教你构图</span></router-link>
          <router-link to="/qczh" class="nav-item" active-class="active"><span class="nav-text">起承转合</span></router-link>
          <router-link to="/content-analysis" class="nav-item" active-class="active"><span class="nav-text">大数据分析</span></router-link>
        </nav>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- 底部（annotate 页面隐藏） -->
    <footer v-if="!$route.path.startsWith('/annotate')" class="main-footer">
      <div class="footer-content">
        <div class="footer-divider">
          <span class="divider-line"></span>
          <img src="/logo.png" alt="墨" class="divider-seal-img">
          <span class="divider-line"></span>
        </div>
        <p class="footer-text">中国画与书法 AI 综合分析系统 © 2026</p>
        <p class="footer-sub">作者 周豪 Zax</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
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

/* 选中文字色 */
::selection {
  background: var(--cinnabar);
  color: var(--pure-white);
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

/* === 响应式 === */
@media (max-width: 768px) {
  .header-content {
    padding: 0 var(--space-lg);
  }

  .main-nav {
    gap: var(--space-lg);
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
</style>
