import { createRouter, createWebHashHistory } from 'vue-router'
import { siteConfig } from '../config'
import { getStorageJson } from '../utils/storage'
import { translate } from '@/locales'
import api from '@/api'

const routes = [
  {
    path: '/',
    name: 'KnowledgeSearch',
    component: () => import('../views/KnowledgeSearch.vue'),
    meta: { title: 'title.k7' }
  },
  { path: '/knowledge', redirect: '/' },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: 'title.k20' }
  },
  // 画家百科
  {
    path: '/artists',
    name: 'ArtistList',
    component: () => import('../views/ArtistList.vue'),
    meta: { title: 'title.k27' }
  },
  // 画家百科 — 嵌套路由
  {
    path: '/artist/:name',
    component: () => import('../components/artist/ArtistPageLayout.vue'),
    meta: { title: 'title.k19' },
    children: [
      { path: '', name: 'ArtistOverview', component: () => import('../views/artist/ArtistOverview.vue') },
      { path: 'works', name: 'ArtistWorks', component: () => import('../views/artist/ArtistWorks.vue'), meta: { title: 'title.k1' } },
      { path: 'seals', name: 'ArtistSeals', component: () => import('../views/artist/ArtistSeals.vue'), meta: { title: 'title.k5' } },
      { path: 'literature', name: 'ArtistLiterature', component: () => import('../views/artist/ArtistLiterature.vue'), meta: { title: 'title.k13' } },
      { path: 'literature/:bookId', name: 'ArtistLiteratureReader', component: () => import('../views/artist/ArtistLiteratureReader.vue'), meta: { title: 'title.k14' } },
      { path: 'analysis', name: 'ArtistAnalysis', component: () => import('../views/artist/ArtistAnalysisSlides.vue'), meta: { title: 'title.k12' } },
      { path: 'map', name: 'ArtistMap', component: () => import('../views/MapMode.vue'), meta: { title: 'title.k28' } },
    ],
  },
  {
    path: '/recognize',
    name: 'Recognize',
    component: () => import('../views/Recognize.vue'),
    meta: { title: 'title.k0' }
  },
  {
    path: '/steles',
    name: 'Steles',
    component: () => import('../views/Steles.vue'),
    meta: { title: 'title.k21' }
  },
  {
    path: '/steles/:id',
    name: 'SteleDetail',
    component: () => import('../views/SteleDetail.vue'),
    meta: { title: 'title.k22' }
  },
  {
    path: '/tiba',
    name: 'TibaAnalysis',
    component: () => import('../views/TibaAnalysis.vue'),
    meta: { title: 'title.k31' }
  },
  {
    path: '/tiba/:id',
    name: 'TibaDetail',
    component: () => import('../views/TibaDetailPage.vue'),
    meta: { title: 'title.k31' }
  },
  {
    path: '/tiba/list',
    name: 'TibaList',
    component: () => import('../views/TibaList.vue'),
    meta: { title: 'title.k2' }
  },
  {
    path: '/tiba/dimensions',
    name: 'DimensionInput',
    component: () => import('../views/DimensionInput.vue'),
    meta: { title: 'title.k8' }
  },
  {
    path: '/composition',
    name: 'CompositionAnalyze',
    component: () => import('../modules/pantianshou-composition/pages/CompositionAnalyze.vue'),
    meta: { title: 'title.k16' }
  },
  {
    path: '/composition/print/:taskId',
    name: 'CompositionPrint',
    component: () => import('../modules/pantianshou-composition/pages/CompositionPrint.vue'),
    meta: { title: 'title.k17' }
  },
  {
    path: '/composition/arrow-demo',
    name: 'ArrowDemo',
    component: () => import('../modules/pantianshou-composition/pages/ArrowDemo.vue'),
    meta: { title: 'title.k24' }
  },
  {
    path: '/qczh',
    name: 'QczhAnalysis',
    component: () => import('../modules/pantianshou-composition/pages/ArrowDemo.vue'),
    meta: { title: 'title.k30' }
  },
  {
    path: '/content-analysis',
    name: 'ContentAnalysis',
    component: () => import('../views/ContentAnalysis.vue'),
    meta: { title: 'title.k32' }
  },
  // 管理后台（新布局：侧边栏 + 内容区）
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    meta: { title: 'title.k23', requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: '',
        name: 'Admin',
        component: () => import('../views/ContentVerify.vue'),
        meta: { title: 'title.k23' },
      },
      {
        path: 'permissions',
        name: 'AdminPermissions',
        component: () => import('../views/admin/Permissions.vue'),
        meta: { title: 'title.k15', requiresSuperAdmin: true },
      },
      {
        path: 'artist/:name/edit',
        name: 'ArtistEditor',
        component: () => import('../views/admin/ArtistEditor.vue'),
        meta: { title: 'title.k26', requiresAuth: true },
      },
      {
        path: 'travel-notes',
        name: 'AdminTravelNotes',
        component: () => import('../views/admin/ArtistTravelNotes.vue'),
        meta: { title: 'title.k29', requiresAuth: true },
      },
      {
        path: 'settings',
        name: 'AdminSettings',
        component: () => import('../views/admin/SystemSettings.vue'),
        meta: { title: 'title.k25', requiresAuth: true },
      },
      {
        path: 'emotion-engine',
        name: 'EmotionEngine',
        component: () => import('../views/EmotionEngine.vue'),
        meta: { title: 'title.k6', requiresAuth: true },
      },
      {
        path: 'emotion-logs',
        name: 'EmotionLogs',
        component: () => import('../views/admin/EmotionLogs.vue'),
        meta: { title: 'title.k9', requiresAuth: true },
      },
    ],
  },
  // 旧路由重定向
  {
    path: '/content-verify',
    redirect: to => ({ path: '/admin', query: to.query }),
  },
  { path: '/tubi', redirect: '/tiba' },
  { path: '/tubi/list', redirect: '/tiba/list' },
  { path: '/tubi/dimensions', redirect: '/tiba/dimensions' },
  { path: '/tubi/:id', redirect: to => ({ path: `/tiba/${to.params.id}` }) },
  {
    path: '/annotate/:id',
    name: 'InscriptionAnnotator',
    component: () => import('../views/InscriptionAnnotator.vue'),
    meta: { title: 'title.k33', requiresAuth: true, requiresEditor: true }
  },
  // 旧 route 重定向
  {
    path: '/map',
    redirect: '/artist/李鱓/map'
  },
  // Phase 3: 个人中心独立页面 (简化)
  {
    path: '/my/knowledge',
    name: 'MyKnowledge',
    component: () => import('../views/MyKnowledge.vue'),
    meta: { title: 'title.k11', requiresAuth: true }
  },
  {
    path: '/user/center',
    name: 'UserCenter',
    component: () => import('../views/UserCenter.vue'),
    meta: { title: 'title.k18', requiresAuth: true }
  },
  {
    path: '/libraries',
    name: 'Libraries',
    component: () => import('../views/Libraries.vue'),
    meta: { title: 'title.k10', requiresAuth: true }
  },
  {
    path: '/libraries/public',
    name: 'PublicLibraries',
    component: () => import('../views/PublicLibraries.vue'),
    meta: { title: 'title.k4' }
  },
  {
    path: '/libraries/:id',
    name: 'LibraryDetail',
    component: () => import('../views/LibraryDetail.vue'),
    meta: { title: 'title.k3' }
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  }
})

const nameCache = new Map()

router.beforeResolve(async (to, _from) => {
  const artistRoutes = ['ArtistOverview', 'ArtistWorks', 'ArtistSeals', 'ArtistLiterature', 'ArtistLiteratureReader', 'ArtistAnalysis', 'ArtistMap']
  if (artistRoutes.includes(to.name) && to.params.name) {
    const raw = to.params.name
    // 已缓存的 canonical 名 → 直接返回，不发起网络请求
    if (nameCache.has(raw)) {
      const canonical = nameCache.get(raw)
      if (canonical && canonical !== raw) {
        return { name: to.name, params: { ...to.params, name: canonical } }
      }
      return true
    }
    // 未命中 → 请求后端 canonical 解析（复用 api 实例，自动携带 auth）
    try {
      const data = await api.get(`/artists/by-name/${encodeURIComponent(raw)}`)
      const canonical = data.canonical_name || raw
      nameCache.set(raw, canonical)
      if (canonical !== raw) {
        nameCache.set(canonical, canonical)
        return { name: to.name, params: { ...to.params, name: canonical } }
      }
    } catch (e) {
      // 网络错误或名称不存在——允许导航继续，页面组件自行处理 404
      // 不缓存 null 结果，允许后续重试
    }
  }
  return true
})

// 全局路由守卫：自动设置页面标题
router.afterEach((to) => {
  const pageTitle = to.meta?.title ? translate(to.meta.title) : ''
  const name = to.params?.name
  // 画家相关路由 → 动态标题："李鱓 - 作品 - 墨林百科"
  if (name && ['ArtistOverview', 'ArtistWorks', 'ArtistSeals', 'ArtistLiterature', 'ArtistLiteratureReader', 'ArtistAnalysis', 'ArtistMap'].includes(to.name)) {
    document.title = pageTitle ? `${name} - ${pageTitle} - ${siteConfig.fullTitle}` : `${name} - ${siteConfig.fullTitle}`
    return
  }
  document.title = pageTitle ? `${pageTitle} - ${siteConfig.fullTitle}` : siteConfig.fullTitle
})

router.beforeEach((to, _from, next) => {
  // 读取本地用户角色（容错：localStorage 数据损坏时按未登录处理，避免导航白屏）
  const readRole = () => {
    // 兼容旧格式（裸 JSON）与新格式（storage 层版本包裹）
    const info = getStorageJson('auth_user')
    return (info && typeof info === 'object' ? info.role : null) || null
  }
  // 需要登录的路由
  if (to.meta?.requiresAuth) {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
  }
  // 需要编者权限的路由
  if (to.meta?.requiresEditor) {
    const role = readRole()
    if (role !== 'editor' && role !== 'admin' && role !== 'super_admin') {
      next({ name: 'KnowledgeSearch' })
      return
    }
  }
  // 需要管理员权限的路由
  if (to.meta?.requiresAdmin) {
    const role = readRole()
    if (role !== 'admin' && role !== 'super_admin') {
      next({ name: 'KnowledgeSearch' })
      return
    }
  }
  // 需要站长权限的路由
  if (to.meta?.requiresSuperAdmin) {
    if (readRole() !== 'super_admin') {
      next({ name: 'KnowledgeSearch' })
      return
    }
  }
  next()
})

export default router
