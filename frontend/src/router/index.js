import { createRouter, createWebHashHistory } from 'vue-router'
import { siteConfig } from '../config'

const SITE_NAME = siteConfig.fullTitle

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
    ],
  },
  // 旧路由重定向
  {
    path: '/content-verify',
    redirect: to => ({ path: '/admin', query: to.query }),
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

router.beforeEach((to, _from, next) => {
  // 需要登录的路由
  if (to.meta?.requiresAuth) {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
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
