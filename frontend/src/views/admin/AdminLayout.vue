<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="admin-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <span v-if="!sidebarCollapsed" class="sidebar-title">管理后台</span>
        <button class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '▶' : '◀' }}
        </button>
      </div>

      <!-- 紧凑控制面板（作者 + 统计 + 操作） -->
      <div v-if="!sidebarCollapsed" class="sidebar-panel">
        <!-- 作者选择 -->
        <select class="sb-select" v-model="selectedArtist" @change="onArtistChange">
          <option value="all">全部作者</option>
          <option v-for="a in artistList" :key="a" :value="a">{{ a }}</option>
        </select>

        <!-- 统计（紧凑两列） -->
        <div class="sb-stats" v-if="stats.total > 0">
          <div class="sb-stat"><span class="sb-stat-num">{{ stats.verified }}</span><span class="sb-stat-lbl">已校对</span></div>
          <div class="sb-stat"><span class="sb-stat-num">{{ stats.translated }}</span><span class="sb-stat-lbl">已翻译</span></div>
          <div class="sb-stat"><span class="sb-stat-num">{{ stats.analyzed }}</span><span class="sb-stat-lbl">已分析</span></div>
          <div class="sb-stat"><span class="sb-stat-num">{{ stats.annotated }}</span><span class="sb-stat-lbl">已标注</span></div>
        </div>
        <div class="sb-stats sb-stats-total" v-if="stats.total > 0">
          <span class="sb-stat-total">共 {{ stats.total }} 幅</span>
        </div>

        <!-- 操作按钮 -->
        <div class="sb-actions">
          <button class="sb-btn" :disabled="batchState.translating" @click="triggerBatch('translate')">
            翻译题跋
          </button>
          <button class="sb-btn" :disabled="batchState.analyzing" @click="triggerBatch('reanalyze')">
            解析文字
          </button>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div v-if="!sidebarCollapsed" class="nav-expand-ctrl">
          <button class="expand-all-btn" @click="expandAll" title="全部展开">＋</button>
          <button class="expand-all-btn" @click="collapseAll" title="全部折叠">−</button>
        </div>
        <template v-for="group in menuGroups" :key="group.category">
          <div v-if="group.items.length > 0" class="nav-group">
            <button class="nav-group-title" @click="toggleGroup(group.category)">
              <span class="group-arrow" :class="{ open: expandedGroups.has(group.category) }">▾</span>
              <span v-if="!sidebarCollapsed" class="group-label">{{ group.category }}</span>
            </button>
            <div v-show="expandedGroups.has(group.category)" class="nav-group-items">
              <router-link
                v-for="item in group.items"
                :key="item.key"
                :to="item.link"
                class="nav-item"
                :class="{ active: isActive(item) }"
                :title="sidebarCollapsed ? item.label : ''"
              >
                <el-icon class="nav-item-icon"><component :is="iconMap[item.icon]" /></el-icon>
                <span v-if="!sidebarCollapsed" class="nav-item-label">{{ item.label }}</span>
              </router-link>
            </div>
          </div>
        </template>
      </nav>
    </aside>

    <!-- 内容区 -->
    <main class="admin-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide, reactive, inject, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'
import { adminApi } from '../../api/adminApi'
import {
  EditPen, Picture, Upload, ScaleToOriginal, Stamp, Notebook, List, PriceTag,
  User, Setting, Search, DataBoard, UserFilled, Key, InfoFilled,
} from '@element-plus/icons-vue'

// 图标名 → 组件映射（用于侧边栏动态渲染）
const iconMap = {
  EditPen, Picture, Upload, ScaleToOriginal, Stamp, Notebook, List, PriceTag,
  User, Setting, Search, DataBoard, UserFilled, Key, InfoFilled,
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 侧边栏折叠状态持久化（按用户）
const SB_COLLAPSED_KEY = computed(() => `admin_sb_collapsed_${authStore.user?.id || 'anon'}`)
const sidebarCollapsed = ref(
  localStorage.getItem(`admin_sb_collapsed_${authStore.user?.id || 'anon'}`) === '1'
)
watch(sidebarCollapsed, (v) => {
  localStorage.setItem(SB_COLLAPSED_KEY.value, v ? '1' : '0')
})
const ALL_CATEGORIES = ['内容管理', '元数据管理', '知识管理', '工具', '系统管理']
const expandedGroups = ref(new Set(ALL_CATEGORIES))
const userPermissions = ref([])

const activeTab = computed(() => route.query?.tab || 'verify')

// ── 共享控制面板状态（provide 给 ContentVerify） ──
const artistList = ref([])
const selectedArtist = ref(route.query.artist || '李鱓')
const stats = reactive({ verified: 0, total: 0, translated: 0, analyzed: 0, annotated: 0 })
const batchState = reactive({ translating: false, analyzing: false })
const batchTrigger = ref(null)  // ContentVerify 会 watch 这个来触发批量操作

provide('adminArtistList', artistList)
provide('adminSelectedArtist', selectedArtist)
provide('adminStats', stats)
provide('adminBatchState', batchState)
provide('adminBatchTrigger', batchTrigger)

// ── 菜单定义 ──
const MENU_DEF = [
  {
    category: '内容管理',
    items: [
      { key: 'verify', label: '题跋校对', icon: 'EditPen', link: '/admin?tab=verify', perm: 'content.verify' },
      { key: 'annotation', label: '标注图校对', icon: 'Picture', link: '/admin?tab=annotation', perm: 'content.annotate' },
      { key: 'upload', label: '作品上传', icon: 'Upload', link: '/admin?tab=upload', perm: 'content.upload' },
      { key: 'change-requests', label: '变更审核', icon: 'InfoFilled', link: '/admin?tab=change-requests', perm: 'system.config' },
    ],
  },
  {
    category: '元数据管理',
    items: [
      { key: 'dimensions', label: '尺寸录入', icon: 'ScaleToOriginal', link: '/admin?tab=dimensions', perm: 'metadata.dimensions' },
      { key: 'seal', label: '印章管理', icon: 'Stamp', link: '/admin?tab=seal', perm: 'metadata.seals' },
      { key: 'album', label: '册页管理', icon: 'Notebook', link: '/admin?tab=album', perm: 'metadata.albums' },
      { key: 'strip', label: '条屏管理', icon: 'List', link: '/admin?tab=strip', perm: 'metadata.strips' },
      { key: 'tag', label: '标签管理', icon: 'PriceTag', link: '/admin?tab=tag', perm: 'metadata.tags' },
    ],
  },
  {
    category: '知识管理',
    items: [
      { key: 'artist-info', label: '作者信息', icon: 'User', link: '/admin?tab=artist-info', perm: 'knowledge.artist_info' },
      { key: 'artist-rules', label: '画家规则', icon: 'Setting', link: '/admin?tab=artist-rules', perm: 'knowledge.artist_rules' },
    ],
  },
  {
    category: '工具',
    items: [
      { key: 'image-search', label: '作品查重', icon: 'Search', link: '/admin?tab=image-search', perm: 'tools.dedup' },
    ],
  },
  {
    category: '系统管理',
    items: [
      { key: 'dashboard', label: '系统概览', icon: 'DataBoard', link: '/admin?tab=dashboard', perm: 'system.dashboard' },
      { key: 'users', label: '用户管理', icon: 'UserFilled', link: '/admin?tab=users', perm: 'system.users' },
      { key: 'permissions', label: '权限配置', icon: 'Key', link: '/admin/permissions', perm: 'system.permissions' },
      { key: 'settings', label: '系统设置', icon: 'InfoFilled', link: '/admin/settings', perm: 'system.config' },
    ],
  },
]

// 根据用户权限过滤菜单
const menuGroups = computed(() => {
  return MENU_DEF.map(group => ({
    category: group.category,
    items: group.items.filter(item => userPermissions.value.includes(item.perm)),
  })).filter(group => group.items.length > 0)
})

function isActive(item) {
  if (item.link === '/admin/permissions') return route.path === '/admin/permissions'
  if (item.link === '/admin/settings') return route.path === '/admin/settings'
  return activeTab.value === item.key
}

function toggleGroup(category) {
  if (expandedGroups.value.has(category)) {
    expandedGroups.value.delete(category)
  } else {
    expandedGroups.value.add(category)
  }
  expandedGroups.value = new Set(expandedGroups.value)
}
function expandAll() {
  expandedGroups.value = new Set(ALL_CATEGORIES)
}
function collapseAll() {
  expandedGroups.value = new Set()
}

// ── 作者列表 ──
async function loadArtistList() {
  try {
    const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    const data = await res.json()
    artistList.value = data.artists || []
  } catch (e) { console.error('获取作者列表失败', e) }
}

function onArtistChange() {
  router.replace({ query: { ...route.query, artist: selectedArtist.value } })
}

// ── 批量操作触发 ──
function triggerBatch(type) {
  batchTrigger.value = type
}

// ── 权限 ──
async function loadPermissions() {
  try {
    const resp = await adminApi.getMyPermissions()
    userPermissions.value = resp.permissions || []
  } catch (e) {
    console.error('获取用户权限失败:', e)
    const role = authStore.role
    if (role === 'super_admin' || role === 'admin') {
      userPermissions.value = MENU_DEF.flatMap(g => g.items.map(i => i.perm))
    } else if (role === 'editor') {
      userPermissions.value = [
        'content.verify', 'content.annotate', 'content.upload',
        'metadata.dimensions', 'metadata.seals', 'metadata.albums',
        'metadata.strips', 'metadata.tags',
        'knowledge.artist_info', 'knowledge.artist_rules',
        'tools.dedup',
      ]
    }
  }
}

// 同步 URL artist → select
watch(() => route.query.artist, (a) => {
  const artist = Array.isArray(a) ? a[0] : a
  if (artist && artist !== selectedArtist.value) {
    selectedArtist.value = artist
  }
})

onMounted(() => {
  loadPermissions()
  loadArtistList()
  // 从 URL 恢复 artist
  const urlArtist = route.query.artist
  if (urlArtist) selectedArtist.value = Array.isArray(urlArtist) ? urlArtist[0] : urlArtist
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: calc(100vh - 56px);
}

/* ── 侧边栏（浅色主题） ── */
.admin-sidebar {
  width: 240px;
  min-width: 240px;
  background: #faf9f5;
  color: #5c5346;
  border-right: 1px solid #e8e4d8;
  display: flex;
  flex-direction: column;
  transition: width 0.2s, min-width 0.2s;
  overflow-y: auto;
  overflow-x: hidden;
}
.admin-sidebar.collapsed { width: 48px; min-width: 48px; }

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 12px;
  border-bottom: 1px solid #e8e4d8;
}
.sidebar-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 15px;
  color: #c45a3c;
  font-weight: 500;
  white-space: nowrap;
}
.sidebar-toggle {
  background: none; border: none;
  color: #b0a890; cursor: pointer;
  font-size: 11px; padding: 4px; flex-shrink: 0;
}
.sidebar-toggle:hover { color: #c45a3c; }

/* ── 控制面板 ── */
.sidebar-panel {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e4d8;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sb-select {
  width: 100%;
  padding: 5px 8px;
  font-size: 12px;
  border: 1px solid #d0ccc0;
  border-radius: 6px;
  background: #fff;
  color: #3a3222;
  outline: none;
  box-sizing: border-box;
}
.sb-select:focus { border-color: #c8a45c; }

.sb-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 8px;
}
.sb-stat {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}
.sb-stat-num {
  font-size: 13px;
  font-weight: 600;
  color: #3a3222;
}
.sb-stat-lbl {
  font-size: 10px;
  color: #b0a890;
}
.sb-stats-total {
  display: block;
  text-align: center;
}
.sb-stat-total {
  font-size: 10px;
  color: #b0a890;
}

.sb-actions {
  display: flex;
  gap: 6px;
}
.sb-btn {
  flex: 1;
  padding: 5px 0;
  border: 1px solid #c45a3c;
  border-radius: 6px;
  background: transparent;
  color: #c45a3c;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.sb-btn:hover { background: #c45a3c; color: #fff; }
.sb-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── 导航 ── */
.sidebar-nav { flex: 1; padding: 8px 0; }

.nav-expand-ctrl {
  display: flex; gap: 4px; justify-content: flex-end;
  padding: 0 14px 4px;
  margin-bottom: 2px;
}
.expand-all-btn {
  width: 20px; height: 20px; padding: 0;
  border: 1px solid #d0ccc0;
  border-radius: 4px;
  background: transparent;
  color: #8c7a5c; font-size: 12px; line-height: 18px;
  cursor: pointer; transition: all 0.15s;
  display: flex; align-items: center; justify-content: center;
}
.expand-all-btn:hover { border-color: #c45a3c; color: #c45a3c; }
.nav-group { margin-bottom: 2px; }

.nav-group-title {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 8px 14px;
  border: none; background: none;
  color: #b0a890; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
  cursor: pointer; text-align: left;
}
.nav-group-title:hover { color: #8c7a5c; }

.group-arrow { font-size: 8px; transition: transform 0.2s; flex-shrink: 0; }
.group-arrow.open { transform: rotate(-90deg); }
.group-label { white-space: nowrap; }

.nav-group-items { display: flex; flex-direction: column; }

.nav-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px 8px 26px;
  color: #5c5346; font-size: 13px;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.nav-item:hover { background: #f0ebe0; color: #3a3222; }
.nav-item.active {
  background: #c45a3c10; color: #c45a3c;
  border-right: 2px solid #c45a3c; font-weight: 500;
}
.nav-item-icon { font-size: 15px; flex-shrink: 0; display: inline-flex; align-items: center; }
.nav-item-label { overflow: hidden; text-overflow: ellipsis; }

/* collapsed 状态下导航项居中 */
.admin-sidebar.collapsed .nav-item {
  padding: 8px 0;
  justify-content: center;
}
.admin-sidebar.collapsed .nav-item.active {
  border-right: none;
}
.admin-sidebar.collapsed .nav-group-title {
  padding: 8px 0;
  justify-content: center;
}

/* ── 主内容区 ── */
.admin-main {
  flex: 1;
  overflow-x: hidden; overflow-y: auto;
  background: #f5f3ed;
}
</style>

<!-- 非 scoped 样式 -->
<style>
.admin-layout .admin-main .el-tabs__header {
  display: none !important;
}
.admin-layout .admin-main .content-verify .page-header {
  display: none !important;
}
.admin-layout .admin-main .content-verify {
  max-width: none; margin: 0;
  padding: 12px 20px 24px;
  min-height: auto; background: transparent;
}
</style>
