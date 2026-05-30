<template>
  <header class="top-header">
    <!-- 左侧：返回/标题或下拉 -->
    <div class="header-left">
      <template v-if="showBack">
        <div class="back-section">
          <el-button text class="back-btn" @click="$emit('back')">
            <el-icon><ArrowLeft /></el-icon>
            <span>返回作品列表</span>
          </el-button>
        </div>
      </template>
      <template v-else>
        <div class="filter-section">
          <span class="filter-label">全部作品</span>
          <el-icon class="filter-icon"><ArrowDown /></el-icon>
        </div>
      </template>
    </div>

    <!-- 中间：搜索框 -->
    <div class="header-center">
      <div class="search-box">
        <el-icon size="16" class="search-icon"><Search /></el-icon>
        <input
          v-model="searchValue"
          type="text"
          placeholder="搜索作品、作者、关键词..."
          @keyup.enter="handleSearch"
        />
        <span class="search-shortcut">⌘ K</span>
      </div>
    </div>

    <!-- 右侧：操作按钮 -->
    <div class="header-right">
      <template v-if="showAnalyze">
        <el-button type="primary" class="analyze-btn" @click="$emit('analyze')">
          <el-icon><Plus /></el-icon>
          <span>分析新作品</span>
        </el-button>
      </template>
      <div class="action-group">
        <el-button circle text class="action-btn" @click="toggleFullscreen">
          <el-icon size="18"><FullScreen /></el-icon>
        </el-button>
        <el-button circle text class="action-btn">
          <el-icon size="18"><Bell /></el-icon>
          <span v-if="notificationCount > 0" class="notification-dot"></span>
        </el-button>
      </div>
      <div class="user-avatar" @click="$emit('user-click')">
        <img v-if="userAvatar" :src="userAvatar" alt="avatar" />
        <el-icon v-else size="18"><User /></el-icon>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Search, Bell, User, ArrowLeft, ArrowDown, Plus, FullScreen } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  showBack: { type: Boolean, default: false },
  showAnalyze: { type: Boolean, default: false },
  userAvatar: { type: String, default: '' },
  notificationCount: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'search', 'back', 'analyze', 'user-click'])

const searchValue = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  searchValue.value = val
})

watch(searchValue, (val) => {
  emit('update:modelValue', val)
})

function handleSearch() {
  emit('search', searchValue.value)
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}
</script>

<style scoped>
.top-header {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: fixed;
  top: 0;
  left: 240px;
  right: 0;
  z-index: 99;
}

/* 左侧 */
.header-left {
  display: flex;
  align-items: center;
  min-width: 140px;
}

.back-section {
  display: flex;
  align-items: center;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #666;
  font-size: 14px;
  padding: 8px 12px;
}

.back-btn:hover {
  color: #333;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.2s;
}

.filter-section:hover {
  background: #f5f5f5;
}

.filter-label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.filter-icon {
  font-size: 12px;
  color: #999;
}

/* 中间搜索 */
.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 480px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 10px 14px;
  width: 100%;
  transition: all 0.2s;
}

.search-box:focus-within {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}

.search-icon {
  color: #999;
  flex-shrink: 0;
}

.search-box input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 14px;
  width: 100%;
  color: #333;
}

.search-box input::placeholder {
  color: #aaa;
}

.search-shortcut {
  font-size: 11px;
  color: #999;
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* 右侧 */
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 140px;
  justify-content: flex-end;
}

.analyze-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #6366f1;
  border-color: #6366f1;
  font-size: 14px;
  padding: 8px 16px;
  border-radius: 8px;
}

.analyze-btn:hover {
  background: #5558e0;
  border-color: #5558e0;
}

.action-group {
  display: flex;
  gap: 4px;
}

.action-btn {
  position: relative;
  color: #666;
}

.action-btn:hover {
  background: #f5f5f5;
  color: #333;
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
  border: 2px solid #fff;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  color: #666;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar:hover {
  background: #e8e8e8;
}
</style>
