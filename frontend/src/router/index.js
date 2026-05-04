import { createRouter, createWebHashHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Recognize from '../views/Recognize.vue'
import Steles from '../views/Steles.vue'
import SteleDetail from '../views/SteleDetail.vue'
import TubiAnalysis from '../views/TubiAnalysis.vue'
import TubiList from '../views/TubiList.vue'
import DimensionInput from '../views/DimensionInput.vue'
import CompositionAnalyze from '../modules/pantianshou-composition/pages/CompositionAnalyze.vue'
import CompositionPrint from '../modules/pantianshou-composition/pages/CompositionPrint.vue'
import ArrowDemo from '../modules/pantianshou-composition/pages/ArrowDemo.vue'
import KnowledgeSearch from '../views/KnowledgeSearch.vue'
import ContentAnalysis from '../views/ContentAnalysis.vue'
import ContentVerify from '../views/ContentVerify.vue'
import InscriptionAnnotator from '../views/InscriptionAnnotator.vue'
import AlbumManager from '../views/AlbumManager.vue'
import TagManager from '../views/TagManager.vue'

const SITE_NAME = '中国画与书法AI综合分析系统'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: '首页' }
  },
  {
    path: '/recognize',
    name: 'Recognize',
    component: Recognize,
    meta: { title: '书法识别' }
  },
  {
    path: '/steles',
    name: 'Steles',
    component: Steles,
    meta: { title: '碑帖数据库' }
  },
  {
    path: '/steles/:id',
    name: 'SteleDetail',
    component: SteleDetail,
    meta: { title: '碑帖详情' }
  },
  {
    path: '/tubi',
    name: 'TubiAnalysis',
    component: TubiAnalysis,
    meta: { title: '题跋分析' }
  },
  {
    path: '/tubi/:id',
    name: 'TubiDetail',
    component: TubiAnalysis,
    meta: { title: '题跋分析' }
  },
  {
    path: '/tubi/list',
    name: 'TubiList',
    component: TubiList,
    meta: { title: '数据排行' }
  },
  {
    path: '/tubi/dimensions',
    name: 'DimensionInput',
    component: DimensionInput,
    meta: { title: '尺寸录入' }
  },
  {
    path: '/composition',
    name: 'CompositionAnalyze',
    component: CompositionAnalyze,
    meta: { title: '构图分析' }
  },
  {
    path: '/knowledge',
    name: 'KnowledgeSearch',
    component: KnowledgeSearch,
    meta: { title: '知识库搜索' }
  },
  {
    path: '/composition/print/:taskId',
    name: 'CompositionPrint',
    component: CompositionPrint,
    meta: { title: '构图报告' }
  },
  {
    path: '/composition/arrow-demo',
    name: 'ArrowDemo',
    component: ArrowDemo,
    meta: { title: '箭头演示' }
  },
  {
    path: '/qczh',
    name: 'QczhAnalysis',
    component: ArrowDemo,
    meta: { title: '起承转合分析' }
  },
  {
    path: '/content-analysis',
    name: 'ContentAnalysis',
    component: ContentAnalysis,
    meta: { title: '题跋大数据分析' }
  },
  {
    path: '/content-verify',
    name: 'ContentVerify',
    component: ContentVerify,
    meta: { title: '管理后台' }
  },
  {
    path: '/annotate/:id',
    name: 'InscriptionAnnotator',
    component: InscriptionAnnotator,
    meta: { title: '题跋标注' }
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
const ADMIN_ROUTES = ['ContentVerify', 'AlbumManager', 'TagManager', 'ArtistInfoManager', 'ArtistRulesManager']
router.beforeEach((to, _from, next) => {
  if (ADMIN_ROUTES.includes(to.name)) {
    const auth = localStorage.getItem('admin_auth')
    if (!auth || Date.now() > parseInt(auth, 10)) {
      next({ name: 'Home' })
      return
    }
  }
  next()
})

export default router
