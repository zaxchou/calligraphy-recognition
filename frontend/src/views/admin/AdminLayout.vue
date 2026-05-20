<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="admin-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">管理</span>
      </div>

      <nav class="sidebar-nav">
        <template v-for="group in menuGroups" :key="group.category">
          <div v-if="group.items.length > 0" class="nav-group">
            <button class="nav-group-title" @click="toggleGroup(group.category)">
              <span class="group-arrow" :class="{ open: expandedGroups.has(group.category) }">▾</span>
              <span class="group-label">{{ group.category }}</span>
            </button>
            <div v-show="expandedGroups.has(group.category)" class="nav-group-items">
              <template v-if="group.category === '作品库'">
                <!-- 搜索框 -->
                <div class="nav-search">
                  <input v-model="librarySearch" class="nav-search-input" placeholder="搜索作品库..." @click.stop />
                  <span v-if="librarySearch" class="nav-search-clear" @click.stop="librarySearch = ''">×</span>
                </div>
                <!-- 全部作品库 -->
                <router-link
                  v-for="item in group.items"
                  :key="item.key"
                  :to="item.link"
                  class="nav-item"
                  :class="{ active: isActive(item) }"
                >
                  <span class="nav-item-label">{{ item.label }}</span>
                </router-link>
                <!-- 作品库列表 + 子菜单 -->
                <div v-for="lib in filteredLibraries" :key="'lib-'+lib.id" class="nav-library">
                  <div class="nav-lib-row">
                    <span class="nav-lib-arrow" :class="{ open: expandedLibraries.has(lib.id) }" @click.stop="toggleLibrary(lib.id)">▸</span>
                    <router-link
                      :to="`/admin?tab=libraries&detail_id=${lib.id}`"
                      class="nav-lib-link"
                      :class="{ active: activeTab === 'libraries' && route.query.detail_id == lib.id && !route.query.panel }"
                    >
                      {{ lib.name }}
                    </router-link>
                  </div>
                  <div v-show="expandedLibraries.has(lib.id)" class="nav-lib-items">
                    <router-link :to="`/admin?tab=libraries&detail_id=${lib.id}`" class="nav-item-sub" :class="{ active: activeTab === 'libraries' && route.query.detail_id == lib.id && !route.query.panel }">作品列表</router-link>
                    <router-link v-if="lib.artist_name" :to="{ name: 'ArtistEditor', params: { name: lib.artist_name } }" class="nav-item-sub" :class="{ active: route.name === 'ArtistEditor' && route.params.name === lib.artist_name }">艺术家信息</router-link>
                    <template v-for="sub in LIBRARY_TAB_SUB_MENUS" :key="'tab-'+sub.key">
                      <router-link v-if="userPermissions.includes(sub.perm)" :to="`/admin?tab=${sub.key}&artist=${encodeURIComponent(lib.artist_name || '')}&lib_id=${lib.id}`" class="nav-item-sub" :class="{ active: activeTab === sub.key && route.query.artist === lib.artist_name }">{{ sub.label }}</router-link>
                    </template>
                    <router-link v-for="sub in LIBRARY_PANEL_SUB_MENUS" :key="sub.key" :to="`/admin?tab=libraries&detail_id=${lib.id}&panel=${sub.key}`" class="nav-item-sub" :class="{ active: activeTab === 'libraries' && route.query.detail_id == lib.id && route.query.panel === sub.key }">{{ sub.label }}</router-link>
                  </div>
                </div>
              </template>
              <template v-else>
                <router-link
                  v-for="item in group.items"
                  :key="item.key"
                  :to="item.link"
                  class="nav-item"
                  :class="{ active: isActive(item) }"
                >
                  <span class="nav-item-label">{{ item.label }}</span>
                </router-link>
              </template>
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
import { ref, computed, onMounted, provide, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'
import { adminApi } from '../../api/adminApi'


const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()


const ALL_CATEGORIES = ['作品库', '工具', '批量操作', '系统']
const expandedGroups = ref(new Set(ALL_CATEGORIES))
const expandedLibraries = ref(new Set())
const librarySearch = ref('')
const userPermissions = ref([])

const filteredLibraries = computed(() => {
  if (!librarySearch.value) return accessibleLibraries.value
  const q = librarySearch.value.toLowerCase()
  return accessibleLibraries.value.filter(lib =>
    lib.name.toLowerCase().includes(q) ||
    (lib.artist_name && lib.artist_name.toLowerCase().includes(q))
  )
})

// 作品库子菜单（panel嵌入型）
const LIBRARY_PANEL_SUB_MENUS = [
  { key: 'dimensions', label: '尺寸录入' },
  { key: 'seal', label: '印章管理' },
  { key: 'album', label: '册页管理' },
  { key: 'strip', label: '条屏管理' },
  { key: 'tag', label: '标签管理' },
]

// 作品库子菜单中指向tab视图的项
const LIBRARY_TAB_SUB_MENUS = [
  { key: 'verify', label: '题跋校对', perm: 'content.verify' },
  { key: 'annotation', label: '标注图', perm: 'content.annotate' },
  { key: 'artist-rules', label: '画家规则', perm: 'knowledge.artist_rules' },
]

const activeTab = computed(() => route.query?.tab || 'verify')

// ── 共享控制面板状态（provide 给 ContentVerify） ──
const accessibleLibraries = ref([])
const selectedLibraryId = ref(null)
const libStats = reactive({ verified: 0, total: 0, translated: 0, analyzed: 0, annotated: 0 })

provide('adminAccessibleLibraries', accessibleLibraries)
provide('adminSelectedLibraryId', selectedLibraryId)
provide('adminLibStats', libStats)

// ── 菜单定义 ──
const MENU_DEF = [
  {
    category: '作品库',
    items: [
      { key: 'all-libraries', label: '全部作品库', link: '/admin?tab=libraries', perm: 'content.upload' },
    ],
  },
  {
    category: '工具',
    items: [
      { key: 'image-search', label: '作品查重', link: '/admin?tab=image-search', perm: 'tools.dedup' },
    ],
  },
  {
    category: '批量操作',
    items: [
      { key: 'batch-translate', label: '翻译', link: '/admin?tab=libraries&batch=translate', perm: 'system.dashboard' },
      { key: 'batch-analyze', label: '文字分析', link: '/admin?tab=libraries&batch=analyze', perm: 'system.dashboard' },
      { key: 'batch-ai', label: 'AI识图', link: '/admin?tab=libraries&batch=ai', perm: 'system.dashboard' },
    ],
  },
  {
    category: '系统',
    items: [
      { key: 'change-requests', label: '变更审核', link: '/admin?tab=change-requests', perm: 'content.verify' },
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
  if (item.key === 'all-libraries') return activeTab.value === 'libraries' && !route.query.detail_id
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

function toggleLibrary(libId) {
  if (expandedLibraries.value.has(libId)) {
    expandedLibraries.value.delete(libId)
  } else {
    expandedLibraries.value.add(libId)
  }
  expandedLibraries.value = new Set(expandedLibraries.value)
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
  // 作品库加载完成后，检查当前路由是否在 ArtistEditor
  if (route.name === 'ArtistEditor' && accessibleLibraries.value.length > 0) {
    const lib = accessibleLibraries.value.find(l => l.artist_name === route.params.name)
    if (lib) {
      expandedLibraries.value.add(lib.id)
      expandedLibraries.value = new Set(expandedLibraries.value)
    }
  }
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

// 路由变化时同步展开状态
watch(() => route.query.detail_id, () => {
  const id = route.query.detail_id
  if (id) {
    expandedLibraries.value.add(parseInt(id))
    expandedLibraries.value = new Set(expandedLibraries.value)
  }
})
watch(() => route.name, () => {
  if (route.name === 'ArtistEditor' && accessibleLibraries.value.length > 0) {
    const artistName = route.params.name
    const lib = accessibleLibraries.value.find(l => l.artist_name === artistName)
    if (lib) {
      expandedLibraries.value.add(lib.id)
      expandedLibraries.value = new Set(expandedLibraries.value)
    }
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
  width: 180px;
  min-width: 180px;
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

/* ── 导航 ── */
.sidebar-nav { flex: 1; padding: 4px 0; }
.nav-group { margin-bottom: 1px; }

.nav-group-title {
  display: flex; align-items: center; gap: 4px;
  width: 100%; padding: 6px 8px;
  border: none; background: none;
  color: #b0a890; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
  cursor: pointer; text-align: left;
}
.nav-group-title:hover { color: #8c7a5c; }

.group-arrow { font-size: 9px; transition: transform 0.2s; flex-shrink: 0; }
.group-arrow.open { transform: rotate(-90deg); }
.group-label { white-space: nowrap; }

.nav-group-items { display: flex; flex-direction: column; }

.nav-item {
  display: flex; align-items: center;
  padding: 6px 8px 6px 16px;
  color: #5c5346; font-size: 12px;
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

/* ── 搜索框 ── */
.nav-search {
  position: relative;
  padding: 6px 8px;
}
.nav-search-input {
  width: 100%; padding: 4px 20px 4px 6px;
  border: 1px solid #e0dccf;
  border-radius: 4px;
  font-size: 11px; color: #5c5346;
  background: #fff; outline: none;
}
.nav-search-input::placeholder { color: #c0b898; }
.nav-search-input:focus { border-color: #c8a45c; }
.nav-search-clear {
  position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
  font-size: 14px; color: #b0a890; cursor: pointer; line-height: 1;
}
.nav-search-clear:hover { color: #c45a3c; }

/* ── 作品库树形菜单 ── */
.nav-library { display: flex; flex-direction: column; }

.nav-lib-row {
  display: flex; align-items: center; gap: 2px;
  padding: 2px 8px 2px 8px;
  transition: background 0.12s;
  border-radius: 4px;
}
.nav-lib-row:hover { background: #f0ebe0; }

.nav-lib-arrow {
  font-size: 10px; color: #c0b898; cursor: pointer;
  flex-shrink: 0; width: 14px; text-align: center;
  line-height: 24px; transition: transform 0.2s, color 0.15s;
  user-select: none;
}
.nav-lib-arrow:hover { color: #c45a3c; }
.nav-lib-arrow.open { transform: rotate(90deg); }

.nav-lib-link {
  flex: 1; display: flex; align-items: center;
  padding: 4px 0; color: #4a4438; font-size: 12px; font-weight: 500;
  text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  transition: color 0.15s;
}
.nav-lib-link:hover { color: #c45a3c; }
.nav-lib-link.active { color: #c45a3c; font-weight: 600; }

.nav-lib-items {
  display: flex; flex-direction: column;
  margin-left: 10px; padding-left: 8px;
  border-left: 1px solid #e8e4d8;
  margin-bottom: 2px;
}

.nav-item-sub {
  display: flex; align-items: center;
  padding: 4px 6px 4px 4px;
  color: #6b6356; font-size: 12px; text-decoration: none;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  border-radius: 3px; transition: background 0.12s, color 0.12s;
  margin: 1px 0;
}
.nav-item-sub:hover { background: #f0ebe0; color: #3a3222; }
.nav-item-sub.active { background: #c45a3c10; color: #c45a3c; font-weight: 500; }

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
