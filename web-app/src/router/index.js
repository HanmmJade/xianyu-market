import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import ModelDetail from '../views/ModelDetail.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
  },
  {
    path: '/model/:name',
    name: 'ModelDetail',
    component: ModelDetail,
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
