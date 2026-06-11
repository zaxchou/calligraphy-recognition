import { createRouter, createWebHashHistory } from 'vue-router'
import { siteConfig } from '../config'
import api from '@/api'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/auth/callback',
    name: 'AuthCallback',
    component: () => import('../views/AuthCallback.vue'),
    meta: { title: '登录中' }
  },
  // 画家百科
  {
    path: '/artists',
    name: 'ArtistList',
    component: () => import('../views/ArtistList.vue'),
    meta: { title: '艺术家百科' }
  },
  {
    path: '/artist/:name',
    name: 'ArtistOverview',
    component: () => import('../views/artist/ArtistOverview.vue'),
    meta: { title: '画家百科' }
  },
  {
    path: '/artist/:name/works',
    name: 'ArtistWorks',
    component: () => import('../views/artist/ArtistWorks.vue'),
    meta: { title: '画家作品' }
  },
  {
    path: '/artist/:name/seals',
    name: 'ArtistSeals',
    component: () => import('../views/artist/ArtistSeals.vue'),
    meta: { title: '画家印章' }
  },
  {
    path: '/artist/:name/literature',
    name: 'ArtistLiterature',
    component: () => import('../views/artist/ArtistLiterature.vue'),
    meta: { title: '画家文献' }
  },
  {
    path: '/artist/:name/analysis',
    name: 'ArtistAnalysis',
    component: () => import('../views/artist/ArtistAnalysisSlides.vue'),
    meta: { title: '画家数据分析' }
  },
  {
    path: '/artist/:name/analysis-legacy',
    name: 'ArtistAnalysisLegacy',
    component: () => import('../views/artist/ArtistAnalysis.vue'),
    meta: { title: '画家数据分析（旧版）' }
  },
  {
    path: '/recognize',
    name: 'Recognize',
    component: () => import('../views/Recognize.vue'),
    meta: { title: '书法识别' }
  },
  {
    path: '/steles',
    name: 'Steles',
    component: () => import('../views/Steles.vue'),
    meta: { title: '碑帖数据库' }
  },
  {
    path: '/steles/:id',
    name: 'SteleDetail',
    component: () => import('../views/SteleDetail.vue'),
    meta: { title: '碑帖详情' }
  },
  {
    path: '/tiba',
    name: 'TibaAnalysis',
    component: () => import('../views/TibaAnalysis.vue'),
    meta: { title: '题跋分析' }
  },
  {
    path: '/tiba/:id',
    name: 'TibaDetail',
    component: () => import('../views/TibaAnalysis.vue'),
    meta: { title: '题跋分析' }
  },
  {
    path: '/tiba/list',
    name: 'TibaList',
    component: () => import('../views/TibaList.vue'),
    meta: { title: '作品库' }
  },
  {
    path: '/tiba/dimensions',
    name: 'DimensionInput',
    component: () => import('../views/DimensionInput.vue'),
    meta: { title: '尺寸录入' }
  },
  {
    path: '/composition',
    name: 'CompositionAnalyze',
    component: () => import('../modules/pantianshou-composition/pages/CompositionAnalyze.vue'),
    meta: { title: '构图分析' }
  },
  {
    path: '/knowledge',
    name: 'KnowledgeSearch',
    component: () => import('../views/KnowledgeSearch.vue'),
    meta: { title: '知识库搜索' }
  },
  {
    path: '/composition/print/:taskId',
    name: 'CompositionPrint',
    component: () => import('../modules/pantianshou-composition/pages/CompositionPrint.vue'),
    meta: { title: '构图报告' }
  },
  {
    path: '/composition/arrow-demo',
    name: 'ArrowDemo',
    component: () => import('../modules/pantianshou-composition/pages/ArrowDemo.vue'),
    meta: { title: '箭头演示' }
  },
  {
    path: '/qczh',
    name: 'QczhAnalysis',
    component: () => import('../modules/pantianshou-composition/pages/ArrowDemo.vue'),
    meta: { title: '起承转合分析' }
  },
  {
    path: '/content-analysis',
    name: 'ContentAnalysis',
    component: () => import('../views/ContentAnalysis.vue'),
    meta: { title: '题跋大数据分析' }
  },
  // 管理后台（新布局：侧边栏 + 内容区）
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    meta: { title: '管理后台', requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Admin',
        component: () => import('../views/ContentVerify.vue'),
        meta: { title: '管理后台' },
      },
      {
        path: 'permissions',
        name: 'AdminPermissions',
        component: () => import('../views/admin/Permissions.vue'),
        meta: { title: '权限配置', requiresSuperAdmin: true },
      },
      {
        path: 'artist/:name/edit',
        name: 'ArtistEditor',
        component: () => import('../views/admin/ArtistEditor.vue'),
        meta: { title: '编辑画家', requiresAuth: true },
      },
      {
        path: 'travel-notes',
        name: 'AdminTravelNotes',
        component: () => import('../views/admin/ArtistTravelNotes.vue'),
        meta: { title: '行旅编辑', requiresAuth: true },
      },
      {
        path: 'settings',
        name: 'AdminSettings',
        component: () => import('../views/admin/SystemSettings.vue'),
        meta: { title: '系统设置', requiresAuth: true },
      },
      {
        path: 'emotion-engine',
        name: 'EmotionEngine',
        component: () => import('../views/EmotionEngine.vue'),
        meta: { title: '墨林情绪引擎', requiresAuth: true },
      },
      {
        path: 'emotion-logs',
        name: 'EmotionLogs',
        component: () => import('../views/admin/EmotionLogs.vue'),
        meta: { title: '情绪分析日志', requiresAuth: true },
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
    meta: { title: '题跋标注', requiresAuth: true, requiresEditor: true }
  },
  {
    path: '/artist/:name/map',
    name: 'ArtistMap',
    component: () => import('../views/MapMode.vue'),
    meta: { title: '翰墨行旅' }
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
    meta: { title: '我的知识库', requiresAuth: true }
  },
  {
    path: '/user/center',
    name: 'UserCenter',
    component: () => import('../views/UserCenter.vue'),
    meta: { title: '用户中心', requiresAuth: true }
  },
  {
    path: '/libraries',
    name: 'Libraries',
    component: () => import('../views/Libraries.vue'),
    meta: { title: '我的作品库', requiresAuth: true }
  },
  {
    path: '/libraries/public',
    name: 'PublicLibraries',
    component: () => import('../views/PublicLibraries.vue'),
    meta: { title: '公开作品库' }
  },
  {
    path: '/libraries/:id',
    name: 'LibraryDetail',
    component: () => import('../views/LibraryDetail.vue'),
    meta: { title: '作品库详情' }
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

router.beforeEach((to, _from, next) => {
  if (to.path === '/' && siteConfig.readonly === 'true') {
    const token = localStorage.getItem('auth_token')
    if (token) { next(); return }
    next('/tiba')
  } else {
    next()
  }
})

router.beforeResolve(async (to, _from) => {
  const artistRoutes = ['ArtistOverview', 'ArtistWorks', 'ArtistSeals', 'ArtistLiterature', 'ArtistAnalysis', 'ArtistAnalysisLegacy', 'ArtistMap']
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
  const pageTitle = to.meta?.title
  const name = to.params?.name
  // 画家相关路由 → 动态标题："李鱓 - 作品 - 墨林百科"
  if (name && ['ArtistOverview', 'ArtistWorks', 'ArtistSeals', 'ArtistLiterature', 'ArtistAnalysis', 'ArtistMap'].includes(to.name)) {
    const section = pageTitle?.replace('画家', '') || ''
    document.title = section ? `${name} - ${section} - ${siteConfig.fullTitle}` : `${name} - ${siteConfig.fullTitle}`
    return
  }
  document.title = pageTitle ? `${pageTitle} - ${siteConfig.fullTitle}` : siteConfig.fullTitle
})

router.beforeEach((to, _from, next) => {
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
    const userInfo = JSON.parse(localStorage.getItem('auth_user') || 'null')
    const role = userInfo?.role
    if (role !== 'editor' && role !== 'admin' && role !== 'super_admin') {
      next({ name: 'Home' })
      return
    }
  }
  // 需要管理员权限的路由
  if (to.meta?.requiresAdmin) {
    const userInfo = JSON.parse(localStorage.getItem('auth_user') || 'null')
    const role = userInfo?.role
    if (role !== 'admin' && role !== 'super_admin') {
      next({ name: 'Home' })
      return
    }
  }
  // 需要站长权限的路由
  if (to.meta?.requiresSuperAdmin) {
    const userInfo = JSON.parse(localStorage.getItem('auth_user') || 'null')
    if (userInfo?.role !== 'super_admin') {
      next({ name: 'Home' })
      return
    }
  }
  next()
})

export default router
