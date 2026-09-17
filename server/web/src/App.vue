<template>
  <n-config-provider :theme="appTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <div class="app-layout">
          <header class="navbar">
            <div class="navbar-left">
              <button class="menu-btn" @click="sidebarOpen = !sidebarOpen" aria-label="打开菜单" :aria-expanded="sidebarOpen">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
              </button>
              <div class="brand" @click="$router.push('/workbench')">
                <div class="logo-icon">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M15 10L20 7V17L15 14M4 6H13A2 2 0 0115 8V16A2 2 0 0113 18H4A2 2 0 012 16V8A2 2 0 014 6Z" stroke="url(#lux-logo-grad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><defs><linearGradient id="lux-logo-grad" x1="2" y1="6" x2="20" y2="18"><stop stop-color="#0e9f6e"/><stop offset="1" stop-color="#0b7a52"/></linearGradient></defs></svg>
                </div>
                <span class="brand-text">Video<span class="gold-gradient-text">Mind</span></span>
              </div>
              <nav class="nav-links">
                <template v-if="isCompactGuestNav">
                  <router-link to="/docs" class="nav-item" :class="{ active: $route.name === 'docs' }">文档</router-link>
                </template>
                <template v-else>
                  <router-link to="/workbench" class="nav-item" :class="{ active: $route.name === 'workbench' }">工作台</router-link>
                  <router-link v-if="!authStore.isGuest" to="/history" class="nav-item" :class="{ active: $route.name === 'history' }">历史</router-link>
                  <router-link v-if="!authStore.isGuest" to="/api-keys" class="nav-item" :class="{ active: $route.name === 'api-keys' }">API Keys</router-link>
                  <router-link to="/docs" class="nav-item" :class="{ active: $route.name === 'docs' }">文档</router-link>
                </template>
              </nav>
            </div>
            <div class="navbar-right">
              <div class="server-status" :class="`status-${authStore.healthStatus}`" role="status" aria-live="polite"><span class="pulse-dot"></span><span class="status-text">{{ engineStatusText }}</span></div>
              <div class="quota-badge" v-if="authStore.quota">
                <span class="label">我的任务</span><span class="val">{{ authStore.quota.running }}/{{ authStore.quota.limit }}</span>
                <span class="divider">|</span>
                <span class="label">全站运行</span><span class="val">{{ authStore.quota.global_running }}/{{ authStore.quota.global_limit }}</span>
                <span class="divider">|</span>
                <span class="label">执行槽</span><span class="val">{{ authStore.workerCount }}</span>
              </div>
              <div class="user-control">
                <template v-if="!authStore.isGuest">
                  <n-tag :type="authStore.user?.tier === 'vip' ? 'warning' : 'success'" round size="small">{{ authStore.user?.email }}</n-tag>
                  <n-button size="small" secondary type="default" @click="handleLogout">退出</n-button>
                </template>
                <template v-else>
                  <n-button size="small" type="primary" @click="$router.push('/')">登录 / 注册</n-button>
                </template>
              </div>
            </div>
          </header>

          <div class="app-body">
            <AppSidebar v-if="!isLoginPage" class="sidebar" :class="{ open: sidebarOpen }" />
            <main class="content" :class="{ 'content-full': isLoginPage }">
              <router-view v-slot="{ Component }">
                <transition name="page-fade" mode="out-in">
                  <component :is="Component" :key="$route.path" />
                </transition>
              </router-view>
            </main>
          </div>

          <footer class="app-footer"><div class="footer-content"><span>VideoMind &copy; 2026</span><span class="divider">&bull;</span><span class="gold-text">把每一段视频，解码成你的知识</span></div></footer>
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { lightTheme as appTheme } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const sidebarOpen = ref(false)
const isCompactGuestNav = computed(() => authStore.isGuest && route.name === 'login')
const isLoginPage = computed(() => route.name === 'login')
const engineStatusText = computed(() => {
  if (authStore.healthStatus === 'ready') return '引擎就绪'
  if (authStore.healthStatus === 'unavailable') return '引擎不可用'
  return '引擎检测中'
})

const themeOverrides: GlobalThemeOverrides = {
  common: { primaryColor: '#0e9f6e', primaryColorHover: '#0b8a5f', primaryColorPressed: '#0b7a52', primaryColorSuppl: '#0e9f6e', warningColor: '#d97706', borderRadius: '8px', textColorBase: '#1f2937' }
}

onMounted(() => authStore.refreshMe())

const handleLogout = () => { authStore.logout(); router.push('/') }
</script>

<style scoped>
.app-layout { min-height: 100vh; display: flex; flex-direction: column }
.navbar { display: flex; justify-content: space-between; align-items: center; padding: 0 28px; height: 64px; background: var(--bg-card); border-bottom: 1px solid var(--border-strong); position: sticky; top: 0; z-index: 100 }
.navbar-left, .navbar-right { display: flex; align-items: center; gap: 16px; min-width: 0 }
.brand { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none }
.logo-icon { display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 10px; background: var(--emerald-soft); border: 1px solid rgba(14,159,110,0.35); box-shadow: 0 1px 6px rgba(14,159,110,0.15) }
.brand-text { font-size: 1.3rem; font-weight: 800; letter-spacing: 0.02em; color: var(--text-main) }
.gold-gradient-text { background: var(--brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text }
.menu-btn { display: none; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--bg-card); color: var(--text-muted); cursor: pointer }
.menu-btn svg { width: 18px; height: 18px }
.nav-links { display: none; gap: 4px }
.nav-item { display: flex; align-items: center; gap: 8px; padding: 7px 12px; border-radius: 8px; font-size: 0.9rem; font-weight: 500; color: var(--text-muted); text-decoration: none; transition: all 0.18s ease }
.nav-item:hover { background: var(--bg-hover); color: var(--text-main) }
.nav-item.active { background: var(--emerald-soft); color: var(--emerald-deep); font-weight: 600 }
.server-status { display: flex; align-items: center; gap: 7px; font-size: 0.8rem; color: var(--text-muted); padding: 4px 10px; border-radius: 99px; background: var(--bg-subtle); border: 1px solid var(--border-soft) }
.server-status.status-checking { color: var(--warning); background: var(--warning-soft); border-color: rgba(217,119,6,0.3) }
.server-status.status-unavailable { color: var(--danger); background: var(--danger-soft); border-color: rgba(220,38,38,0.3) }
.server-status.status-unavailable .pulse-dot { background-color: var(--danger); box-shadow: 0 0 8px var(--danger); animation: none }
.server-status.status-checking .pulse-dot { background-color: var(--warning); box-shadow: 0 0 8px var(--warning); animation: none }
.pulse-dot { width: 7px; height: 7px; border-radius: 50%; background-color: var(--emerald-primary); box-shadow: 0 0 8px var(--emerald-primary); animation: pulse 2s infinite }
@keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(14,159,110,0.6) } 70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(14,159,110,0) } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(14,159,110,0) } }
.quota-badge { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; background: var(--bg-subtle); border: 1px solid var(--border-soft); padding: 4px 12px; border-radius: 99px }
.quota-badge .label { color: var(--text-muted) }
.quota-badge .val { color: var(--emerald-deep); font-weight: 700 }
.quota-badge .divider { color: var(--text-dim) }
.user-control { display: flex; align-items: center; gap: 10px }
.app-body { display: flex; flex: 1; align-items: stretch; min-height: 0 }
.sidebar { position: sticky; top: 64px; height: calc(100vh - 64px) }
.content { flex: 1; min-width: 0; max-width: 1380px; padding: 32px 36px 72px; margin: 0 auto; width: 100% }
.content-full { max-width: none; padding: 0 }
.app-footer { border-top: 1px solid var(--border-strong); padding: 16px 0; text-align: center; font-size: 0.82rem; color: var(--text-muted); background: var(--bg-card) }
.footer-content { display: flex; justify-content: center; align-items: center; gap: 12px }
.gold-text { color: var(--emerald-deep) }

@media (max-width: 1180px) {
  .quota-badge { display: none }
}
@media (max-width: 760px) {
  .navbar { height: auto; min-height: 64px; flex-wrap: wrap; align-items: stretch; gap: 8px; padding: 10px 14px; overflow: hidden }
  .navbar-left { width: 100%; min-width: 0; flex-wrap: wrap; gap: 10px }
  .navbar-right { width: 100%; min-width: 0; justify-content: space-between; gap: 8px }
  .brand { min-width: 0; flex: 1 }
  .menu-btn { display: flex }
  .nav-links { order: 2; display: flex; width: 100%; max-width: 100%; gap: 4px; overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch }
  .nav-links::-webkit-scrollbar { display: none }
  .nav-item { flex: 0 0 auto; padding: 7px 12px; white-space: nowrap }
  .server-status { flex: 0 0 auto; padding: 4px 10px; font-size: 0.75rem }
  .user-control { min-width: 0; gap: 8px }
  .user-control :deep(.n-tag) { max-width: min(50vw, 260px) }
  .user-control :deep(.n-tag__content) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
  .sidebar { position: fixed; left: 0; top: 64px; bottom: 0; z-index: 90; height: auto; transform: translateX(-100%); transition: transform 0.25s ease; box-shadow: 8px 0 24px rgba(15,23,42,0.08) }
  .sidebar.open { transform: translateX(0) }
  .content { padding: 20px 14px 48px }
  .footer-content { flex-wrap: wrap; padding: 0 16px }
}
</style>
