import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/utils/api'


export interface User {
  id: number
  email: string
  tier: string
  role?: string
}

export interface Quota {
  tier: string
  running: number
  limit: number
  global_running: number
  global_limit: number
}

export type HealthStatus = 'checking' | 'ready' | 'unavailable'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('access_token') || '')
  const user = ref<User | null>(null)
  const quota = ref<Quota | null>(null)
  const workerCount = ref(2)
  const healthStatus = ref<HealthStatus>('checking')
  let healthRequestId = 0
  const isGuest = computed(() => !user.value)
  const isAdmin = computed(() => (user.value?.role || "user") === "admin")

  async function refreshMe() {
    const requestId = ++healthRequestId
    healthStatus.value = 'checking'
    try {
      if (!token.value) throw new Error('No token')
      user.value = await api<User>('/api/v1/auth/me')
    } catch {
      user.value = null
      token.value = ''
      localStorage.removeItem('access_token')
    }
    
    // Always fetch health to update quota (even for guest)
    try {
      const h = await api<any>('/api/v1/health')
      if (requestId !== healthRequestId) return
      healthStatus.value = 'ready'
      if (h.quota) {
        quota.value = h.quota
      }
      if (Number.isFinite(h.worker_count)) {
        workerCount.value = h.worker_count
      }
    } catch (e) {
      if (requestId !== healthRequestId) return
      healthStatus.value = 'unavailable'
      console.error('Failed to fetch health/quota', e)
    }
  }

  function login(newToken: string) {
    token.value = newToken
    localStorage.setItem('access_token', newToken)
    return refreshMe()
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    refreshMe()
  }

  // Handle global 401 events dispatched from api.ts
  window.addEventListener('auth:401', () => {
    token.value = ''
    user.value = null
  })

  return {
    token,
    user,
    quota,
    workerCount,
    healthStatus,
    isGuest,
    isAdmin,
    refreshMe,
    login,
    logout
  }
})
