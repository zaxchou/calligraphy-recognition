import { createRouter, createWebHashHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Recognize from '../views/Recognize.vue'
import Steles from '../views/Steles.vue'
import SteleDetail from '../views/SteleDetail.vue'
import TubiAnalysis from '../views/TubiAnalysis.vue'

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
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
