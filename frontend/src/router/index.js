import { createRouter, createWebHashHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Recognize from '../views/Recognize.vue'
import Steles from '../views/Steles.vue'
import SteleDetail from '../views/SteleDetail.vue'
import TubiAnalysis from '../views/TubiAnalysis.vue'
import TubiRanking from '../views/TubiRanking.vue'
import CompositionAnalyze from '../modules/pantianshou-composition/pages/CompositionAnalyze.vue'
import CompositionKnowledge from '../modules/pantianshou-composition/pages/CompositionKnowledge.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/recognize',
    name: 'Recognize',
    component: Recognize
  },
  {
    path: '/steles',
    name: 'Steles',
    component: Steles
  },
  {
    path: '/steles/:id',
    name: 'SteleDetail',
    component: SteleDetail
  },
  {
    path: '/tubi',
    name: 'TubiAnalysis',
    component: TubiAnalysis
  },
  {
    path: '/tubi/ranking',
    name: 'TubiRanking',
    component: TubiRanking
  },
  {
    path: '/composition',
    name: 'CompositionAnalyze',
    component: CompositionAnalyze
  },
  {
    path: '/composition/knowledge',
    name: 'CompositionKnowledge',
    component: CompositionKnowledge
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
