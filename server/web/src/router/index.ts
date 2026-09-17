import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'login',
      component: () => import('@/views/Login.vue')
    },
    {
      path: '/login',
      redirect: '/'
    },
    {
      path: '/workbench',
      name: 'workbench',
      component: () => import('@/views/Workbench.vue')
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/History.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/api-keys',
      name: 'api-keys',
      component: () => import('@/views/ApiKeys.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/docs',
      name: 'docs',
      component: () => import('@/views/Docs.vue')
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/Admin.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    }
  ]
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // logged-in user visiting login → straight to workbench
  if (authStore.token && (to.name === 'login')) {
    next({ name: 'workbench' })
    return
  }

  if (to.meta.requiresAuth && !authStore.token) {
    next({ name: 'login' })
  } else if (to.meta.requiresAdmin && authStore.user?.role !== 'admin') {
    next({ name: 'workbench' })
  } else {
    next()
  }
})

export default router
