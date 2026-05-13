import { createRouter, createWebHashHistory } from 'vue-router'

const SITE_NAME = '中国画与书法AI综合分析系统'

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
    path: '/tubi',
    name: 'TubiAnalysis',
    component: () => import('../views/TubiAnalysis.vue'),
    meta: { title: '题跋分析' }
  },
  {
    path: '/tubi/:id',
    name: 'TubiDetail',
    component: () => import('../views/TubiAnalysis.vue'),
    meta: { title: '题跋分析' }
  },
  {
    path: '/tubi/list',
    name: 'TubiList',
    component: () => import('../views/TubiList.vue'),
    meta: { title: '作品库' }
  },
  {
    path: '/tubi/dimensions',
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
  {
    path: '/content-verify',
    name: 'ContentVerify',
    component: () => import('../views/ContentVerify.vue'),
    meta: { title: '管理后台' }
  },
  {
    path: '/annotate/:id',
    name: 'InscriptionAnnotator',
    component: () => import('../views/InscriptionAnnotator.vue'),
    meta: { title: '题跋标注' }
  },
  {
    path: '/map',
    name: 'MapMode',
    component: () => import('../views/MapMode.vue'),
    meta: { title: '翰墨行旅' }
  },
  // Phase 2: 作品库产品线
  {
    path: '/libraries',
    name: 'Libraries',
    component: () => import('../views/Libraries.vue'),
    meta: { title: '我的作品库' }
  },
  // 管理后台
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: () => import('../views/admin/Dashboard.vue'),
    meta: { title: '管理后台', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('../views/admin/Users.vue'),
    meta: { title: '用户管理', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/settings',
    name: 'AdminSettings',
    component: () => import('../views/admin/Settings.vue'),
    meta: { title: '系统配置', requiresAuth: true, requiresAdmin: true }
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
  routes
})

// 全局路由守卫：自动设置页面标题
router.afterEach((to) => {
  const pageTitle = to.meta?.title
  document.title = pageTitle ? `${pageTitle} - ${SITE_NAME}` : SITE_NAME
})

// 管理后台路由保护
// 旧版（密码鉴权）
const ADMIN_ROUTES = ['ContentVerify', 'AlbumManager', 'TagManager', 'ArtistInfoManager', 'ArtistRulesManager']
// 新版（JWT + admin 角色）
const NEW_ADMIN_NAMES = ['AdminDashboard', 'AdminUsers', 'AdminSettings']

router.beforeEach((to, _from, next) => {
  // 旧版管理路由：密码鉴权
  if (ADMIN_ROUTES.includes(to.name)) {
    const auth = localStorage.getItem('admin_auth')
    if (!auth || Date.now() > parseInt(auth, 10)) {
      next({ name: 'Home' })
      return
    }
  }
  // 新版管理路由：JWT 登录 + admin 角色
  if (NEW_ADMIN_NAMES.includes(to.name) || to.path.startsWith('/admin')) {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
    let userInfo = null
    try {
      userInfo = JSON.parse(localStorage.getItem('auth_user') || 'null')
    } catch (e) { /* ignore */ }
    if (!userInfo || userInfo.role !== 'admin') {
      next({ name: 'Home' })
      return
    }
  }
  next()
})

export default router
