<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="admin-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">管理</span>
      </div>

      <!-- 紧凑控制面板（作品库选择 + 统计 + 操作）→ 仅作品库权限可见 -->
      <div v-if="hasLibraryAccess" class="sidebar-panel">
        <!-- 作品库选择 -->
        <select class="sb-select" v-model="selectedLibraryId" @change="onLibraryChange">
          <option value="" disabled>作品库</option>
          <option v-for="lib in accessibleLibraries" :key="lib.id" :value="lib.id">
            {{ lib.name }}{{ lib.artist_name ? '-' + lib.artist_name : '' }}
          </option>
        </select>

        <!-- 统计 -->
        <div class="sb-stats" v-if="libStats.total > 0">
          <div class="sb-stat"><span class="sb-stat-num">{{ libStats.verified }}</span><span class="sb-stat-lbl">校对</span></div>
          <div class="sb-stat"><span class="sb-stat-num">{{ libStats.translated }}</span><span class="sb-stat-lbl">翻译</span></div>
          <div class="sb-stat"><span class="sb-stat-num">{{ libStats.analyzed }}</span><span class="sb-stat-lbl">分析</span></div>
          <div class="sb-stat"><span class="sb-stat-num">{{ libStats.annotated }}</span><span class="sb-stat-lbl">标注</span></div>
        </div>
        <div class="sb-total" v-if="libStats.total > 0">共 {{ libStats.total }} 幅</div>

        <!-- 操作按钮 -->
        <div class="sb-actions">
          <button class="sb-btn" :disabled="batchState.translating || !selectedLibraryId" @click="triggerBatch('translate')">
            翻译题跋
          </button>
          <button class="sb-btn" :disabled="batchState.analyzing || !selectedLibraryId" @click="triggerBatch('reanalyze')">
            解析文字
          </button>
        </div>
      </div>

      <nav class="sidebar-nav">
        <template v-for="group in menuGroups" :key="group.category">
          <div v-if="group.items.length > 0" class="nav-group">
            <button class="nav-group-title" @click="toggleGroup(group.category)">
              <span class="group-arrow" :class="{ open: expandedGroups.has(group.category) }">▾</span>
              <span class="group-label">{{ group.category }}</span>
            </button>
            <div v-show="expandedGroups.has(group.category)" class="nav-group-items">
              <router-link
                v-for="item in group.items"
                :key="item.key"
                :to="item.link"
                class="nav-item"
                :class="{ active: isActive(item) }"
              >
                <span class="nav-item-label">{{ item.label }}</span>
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
import { ref, computed, onMounted, provide, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'
import { adminApi } from '../../api/adminApi'


const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 作品库权限：admin/super_admin/editor 可见
const hasLibraryAccess = computed(() => {
  const role = authStore.role
  return role === 'super_admin' || role === 'admin' || role === 'editor'
})

const ALL_CATEGORIES = ['内容', '元数据', '知识', '工具', '系统']
const expandedGroups = ref(new Set(ALL_CATEGORIES))
const userPermissions = ref([])

const activeTab = computed(() => route.query?.tab || 'verify')

// ── 共享控制面板状态（provide 给 ContentVerify） ──
const accessibleLibraries = ref([])
const selectedLibraryId = ref(null)
const libStats = reactive({ verified: 0, total: 0, translated: 0, analyzed: 0, annotated: 0 })
const batchState = reactive({ translating: false, analyzing: false })
const batchTrigger = ref(null)  // ContentVerify 会 watch 这个来触发批量操作

provide('adminAccessibleLibraries', accessibleLibraries)
provide('adminSelectedLibraryId', selectedLibraryId)
provide('adminLibStats', libStats)
provide('adminBatchState', batchState)
provide('adminBatchTrigger', batchTrigger)

// ── 菜单定义 ──
const MENU_DEF = [
  {
    category: '内容',
    items: [
      { key: 'verify', label: '题跋校对', link: '/admin?tab=verify', perm: 'content.verify' },
      { key: 'annotation', label: '标注图', link: '/admin?tab=annotation', perm: 'content.annotate' },
      { key: 'upload', label: '作品上传', link: '/admin?tab=upload', perm: 'content.upload' },
      { key: 'change-requests', label: '变更审核', link: '/admin?tab=change-requests', perm: 'content.verify' },
      { key: 'libraries', label: '作品库', link: '/admin?tab=libraries', perm: 'content.upload' },
    ],
  },
  {
    category: '元数据',
    items: [
      { key: 'dimensions', label: '尺寸录入', link: '/admin?tab=dimensions', perm: 'metadata.dimensions' },
      { key: 'seal', label: '印章管理', link: '/admin?tab=seal', perm: 'metadata.seals' },
      { key: 'album', label: '册页管理', link: '/admin?tab=album', perm: 'metadata.albums' },
      { key: 'strip', label: '条屏管理', link: '/admin?tab=strip', perm: 'metadata.strips' },
      { key: 'tag', label: '标签管理', link: '/admin?tab=tag', perm: 'metadata.tags' },
    ],
  },
  {
    category: '知识',
    items: [
      { key: 'artist-info', label: '艺术家', link: '/admin?tab=artist-info', perm: 'knowledge.artist_info' },
      { key: 'artist-rules', label: '画家规则', link: '/admin?tab=artist-rules', perm: 'knowledge.artist_rules' },
    ],
  },
  {
    category: '工具',
    items: [
      { key: 'image-search', label: '作品查重', link: '/admin?tab=image-search', perm: 'tools.dedup' },
    ],
  },
  {
    category: '系统',
    items: [
      { key: 'dashboard', label: '系统概览', link: '/admin?tab=dashboard', perm: 'system.dashboard' },
      { key: 'users', label: '用户管理', link: '/admin?tab=users', perm: 'system.users' },
      { key: 'permissions', label: '权限配置', link: '/admin/permissions', perm: 'system.permissions' },
      { key: 'settings', label: '系统设置', link: '/admin/settings', perm: 'system.config' },
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

// ── 作品库列表 ──
async function loadAccessibleLibraries() {
  try {
    const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
    const token = localStorage.getItem('auth_token') || ''
    const res = await fetch(`${API_BASE}/libraries/accessible-libraries`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    accessibleLibraries.value = data.libraries || []
    // 自动选中第一个
    if (accessibleLibraries.value.length > 0 && !selectedLibraryId.value) {
      selectedLibraryId.value = accessibleLibraries.value[0].id
      loadLibStats()
    }
  } catch (e) { console.error('获取作品库列表失败', e) }
}

function onLibraryChange() {
  router.replace({ query: { ...route.query, lib_id: selectedLibraryId.value } })
  loadLibStats()
}

async function loadLibStats() {
  if (!selectedLibraryId.value) return
  try {
    const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
    const token = localStorage.getItem('auth_token') || ''
    const res = await fetch(`${API_BASE}/libraries/${selectedLibraryId.value}/stats`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    Object.assign(libStats, data)
  } catch (e) { console.error('获取作品库统计失败', e) }
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

onMounted(() => {
  loadPermissions()
  loadAccessibleLibraries()
  // 从 URL 恢复 lib_id
  const urlLibId = route.query.lib_id
  if (urlLibId) {
    selectedLibraryId.value = parseInt(urlLibId) || null
    loadLibStats()
  }
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: calc(100vh - 56px);
}

/* ── 侧边栏 ── */
.admin-sidebar {
  width: 120px;
  min-width: 120px;
  background: #faf9f5;
  color: #5c5346;
  border-right: 1px solid #e8e4d8;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 8px;
  border-bottom: 1px solid #e8e4d8;
}
.sidebar-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 14px;
  color: #c45a3c;
  font-weight: 500;
  white-space: nowrap;
}

/* ── 控制面板 ── */
.sidebar-panel {
  padding: 8px 8px;
  border-bottom: 1px solid #e8e4d8;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sb-select {
  width: 100%;
  padding: 4px 4px;
  font-size: 10px;
  border: 1px solid #d0ccc0;
  border-radius: 4px;
  background: #fff;
  color: #3a3222;
  outline: none;
  box-sizing: border-box;
}
.sb-select:focus { border-color: #c8a45c; }

.sb-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px 4px;
}
.sb-stat {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
}
.sb-stat-num {
  font-size: 10px;
  font-weight: 600;
  color: #3a3222;
}
.sb-stat-lbl {
  font-size: 9px;
  color: #b0a890;
}

.sb-total {
  text-align: center;
  font-size: 9px;
  color: #8c7a5c;
}

.sb-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sb-btn {
  padding: 4px 0;
  border: 1px solid #c45a3c;
  border-radius: 4px;
  background: transparent;
  color: #c45a3c;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}
.sb-btn:hover { background: #c45a3c; color: #fff; }
.sb-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── 导航 ── */
.sidebar-nav { flex: 1; padding: 4px 0; }
.nav-group { margin-bottom: 1px; }

.nav-group-title {
  display: flex; align-items: center; gap: 4px;
  width: 100%; padding: 6px 8px;
  border: none; background: none;
  color: #b0a890; font-size: 9px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
  cursor: pointer; text-align: left;
}
.nav-group-title:hover { color: #8c7a5c; }

.group-arrow { font-size: 7px; transition: transform 0.2s; flex-shrink: 0; }
.group-arrow.open { transform: rotate(-90deg); }
.group-label { white-space: nowrap; }

.nav-group-items { display: flex; flex-direction: column; }

.nav-item {
  display: flex; align-items: center;
  padding: 6px 8px 6px 16px;
  color: #5c5346; font-size: 11px;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.nav-item:hover { background: #f0ebe0; color: #3a3222; }
.nav-item.active {
  background: #c45a3c10; color: #c45a3c;
  border-right: 2px solid #c45a3c; font-weight: 500;
}
.nav-item-label { overflow: hidden; text-overflow: ellipsis; }

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
