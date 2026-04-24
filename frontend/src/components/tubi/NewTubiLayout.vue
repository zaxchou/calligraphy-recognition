<template>
  <div class="new-tubi-layout">
    <!-- 侧边栏 -->
    <SidebarNavigation />
    
    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 顶部栏 -->
      <TopHeader
        v-model="searchKeyword"
        @search="handleSearch"
      >
        <template #left>
          <div class="page-filter">
            <el-dropdown trigger="click">
              <span class="filter-trigger">
                {{ selectedFilter }}
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="selectedFilter = '全部作品'">全部作品</el-dropdown-item>
                  <el-dropdown-item @click="selectedFilter = '李鱓'">李鱓</el-dropdown-item>
                  <el-dropdown-item @click="selectedFilter = '郑燮'">郑燮</el-dropdown-item>
                  <el-dropdown-item @click="selectedFilter = '金农'">金农</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </TopHeader>
      
      <!-- 页面内容 -->
      <div class="page-content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import SidebarNavigation from './SidebarNavigation.vue'
import TopHeader from './TopHeader.vue'

const emit = defineEmits(['search'])

const searchKeyword = ref('')
const selectedFilter = ref('全部作品')

function handleSearch(keyword) {
  emit('search', keyword)
}
</script>

<style scoped>
.new-tubi-layout {
  display: flex;
  min-height: 100vh;
  background: #f5f5f5;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  display: flex;
  flex-direction: column;
}

.page-content {
  flex: 1;
  padding: 24px;
  padding-top: 88px; /* 64px header + 24px padding */
  overflow-y: auto;
}

.page-filter {
  display: flex;
  align-items: center;
}

.filter-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 8px;
  transition: background 0.2s;
}

.filter-trigger:hover {
  background: #f0f0f0;
}
</style>
