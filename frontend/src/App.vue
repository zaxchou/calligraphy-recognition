<template>
  <div class="app">
    <!-- 顶部导航 -->
    <header class="main-header">
      <div class="header-content">
        <div class="logo" @click="$router.push('/')">
          <div class="logo-icon">
            <el-icon size="24"><Document /></el-icon>
          </div>
          <div class="logo-text">
            <span class="logo-main">书画</span>
            <span class="logo-sub">智能分析系统</span>
          </div>
          <span class="version-tag">v1.0.0</span>
        </div>
        
        <nav class="main-nav">
          <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
            <span class="nav-text">首页</span>
          </router-link>
          <router-link to="/tubi" class="nav-item" :class="{ active: $route.path === '/tubi' }">
            <span class="nav-text">题跋分析</span>
          </router-link>
          <router-link to="/recognize" class="nav-item" :class="{ active: $route.path === '/recognize' }">
            <span class="nav-text">字体识别</span>
          </router-link>
          <router-link to="/steles" class="nav-item" :class="{ active: $route.path === '/steles' }">
            <span class="nav-text">碑帖库</span>
          </router-link>
        </nav>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- 底部 -->
    <footer class="main-footer">
      <div class="footer-content">
        <div class="footer-divider">
          <span class="divider-line"></span>
          <span class="divider-seal">印</span>
          <span class="divider-line"></span>
        </div>
        <p class="footer-text">书画智能分析系统 &copy; 2026</p>
        <p class="footer-sub">作者 周豪 Zax</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
</script>

<style>
/* 全局字体设置 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;600;700&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: "Noto Serif SC", "Source Han Serif SC", "SimSun", serif;
  background: #f8f6f1;
  color: #3d3d3d;
}
</style>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 顶部导航 */
.main-header {
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid #e8e4dc;
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(10px);
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 70px;
  padding: 0 40px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: opacity 0.3s;
}

.logo:hover {
  opacity: 0.8;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #c45c48 0%, #a84838 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-main {
  font-size: 18px;
  font-weight: 600;
  color: #3d3d3d;
  letter-spacing: 0.1em;
}

.logo-sub {
  font-size: 12px;
  color: #8b7355;
  letter-spacing: 0.05em;
}

.version-tag {
  font-size: 10px;
  color: #999;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 8px;
  font-weight: 400;
  letter-spacing: 0.02em;
}

/* 导航菜单 */
.main-nav {
  display: flex;
  gap: 40px;
}

.nav-item {
  text-decoration: none;
  position: relative;
  padding: 8px 0;
}

.nav-text {
  font-size: 16px;
  color: #666;
  letter-spacing: 0.1em;
  transition: color 0.3s;
}

.nav-item:hover .nav-text,
.nav-item.active .nav-text {
  color: #c45c48;
}

.nav-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%) scaleX(0);
  width: 100%;
  height: 2px;
  background: #c45c48;
  transition: transform 0.3s;
}

.nav-item:hover::after,
.nav-item.active::after {
  transform: translateX(-50%) scaleX(1);
}

/* 主内容区 */
.main-content {
  flex: 1;
}

/* 底部 */
.main-footer {
  background: #3d3d3d;
  padding: 40px;
  text-align: center;
}

.footer-content {
  max-width: 800px;
  margin: 0 auto;
}

.footer-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  margin-bottom: 30px;
}

.divider-line {
  width: 100px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #8b7355, transparent);
}

.divider-seal {
  width: 36px;
  height: 36px;
  background: #c45c48;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: bold;
  border-radius: 4px;
  transform: rotate(-5deg);
}

.footer-text {
  font-size: 16px;
  color: #f0ebe3;
  letter-spacing: 0.2em;
  margin-bottom: 10px;
}

.footer-sub {
  font-size: 14px;
  color: #8b7355;
  letter-spacing: 0.1em;
}

/* 响应式 */
@media (max-width: 768px) {
  .header-content {
    padding: 0 20px;
  }

  .main-nav {
    gap: 20px;
  }

  .nav-text {
    font-size: 14px;
  }

  .logo-sub {
    display: none;
  }
}
</style>
