<template>
  <aside class="app-sidebar">
    <nav class="side-nav">
      <router-link
        v-for="item in visibleItems"
        :key="item.to"
        :to="item.to"
        class="side-item"
        :class="{ active: route.path === item.to }"
      >
        <span class="side-icon" v-html="item.icon"></span>
        <span class="side-label">{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="sidebar-foot" v-if="authStore.quota">
      <div class="foot-label">运行配额</div>
      <div class="foot-row"><span>我的任务</span><strong>{{ authStore.quota.running }}/{{ authStore.quota.limit }}</strong></div>
      <div class="foot-row"><span>全站运行</span><strong>{{ authStore.quota.global_running }}/{{ authStore.quota.global_limit }}</strong></div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()

const items: Array<{ to: string; label: string; auth: boolean; adminOnly?: boolean; icon: string }> = [
  {
    to: '/workbench', label: '工作台', auth: false,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="14" rx="3"/><path d="M10.5 9.5v5l4-2.5z"/></svg>',
  },
  {
    to: '/history', label: '历史', auth: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
  },
  {
    to: '/api-keys', label: 'API 密钥', auth: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15.5" r="4"/><path d="M11 12.5L20 3.5M15.5 7l2 2M17.5 9l2 2"/></svg>',
  },
  {
    to: '/docs', label: '文档', auth: false,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5a2 2 0 012-2h12v16H7a2 2 0 00-2 2z"/><path d="M9 8h7M9 12h7"/></svg>',
  },
  {
    to: '/admin', label: '后台管理', auth: true, adminOnly: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18v4H3z"/><path d="M5 9v10h14V9"/><path d="M9 13h6"/></svg>',
  },
]

const visibleItems = computed(() => items.filter((i) => (!i.auth || !authStore.isGuest) && (!i.adminOnly || authStore.isAdmin)))
</script>

<style scoped>
.app-sidebar {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 228px;
  flex-shrink: 0;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-strong);
  padding: 20px 14px;
}
.side-nav { display: flex; flex-direction: column; gap: 4px; }
.side-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; border-radius: 10px;
  font-size: 0.97rem; font-weight: 500; color: var(--text-muted);
  text-decoration: none; transition: all 0.18s ease;
}
.side-item:hover { background: var(--bg-hover); color: var(--text-main); }
.side-item.active { background: var(--emerald-soft); color: var(--emerald-deep); font-weight: 700; box-shadow: inset 3px 0 0 var(--emerald-primary) }
.side-icon { display: flex; align-items: center; width: 22px; height: 22px; }
.side-icon :deep(svg) { width: 22px; height: 22px; }
.sidebar-foot {
  margin-top: 20px; padding: 14px; border-radius: 12px;
  background: var(--bg-subtle); border: 1px solid var(--border-strong);
}
.foot-label { font-size: 0.74rem; font-weight: 700; color: var(--emerald-deep); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 10px; }
.foot-row { display: flex; justify-content: space-between; align-items: center; font-size: 0.88rem; color: var(--text-muted); padding: 4px 0; }
.foot-row strong { color: var(--emerald-deep); font-weight: 700; }
</style>
