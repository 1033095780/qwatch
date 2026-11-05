// AppShell.vue — v0.6 侧栏（总览/策略/告警/设置）+ 顶栏（实时状态/刷新/告警/头像）+ 移动端抽屉。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { Component } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NDropdown, useMessage } from 'naive-ui';
import {
  Activity, Bell, LayoutDashboard, Menu, PanelLeftClose, PanelLeftOpen,
  RefreshCw, Settings as SettingsIcon,
} from 'lucide-vue-next';
import { api, apiMeta } from '@/api/client';
import { nowTick } from '@/utils/format';
import { streamMeta } from '@/api/stream';
import { useAuthStore } from '@/stores/auth';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import BrandMark from '@/components/BrandMark.vue';
import StatusControls from '@/components/StatusControls.vue';
import StatusDot from '@/components/StatusDot.vue';

interface NavItem { to: string; label: string; icon: Component; badge?: boolean }

const navItems: NavItem[] = [
  { to: '/overview', label: '总览', icon: LayoutDashboard },
  { to: '/strategies', label: '策略', icon: Activity },
  { to: '/alerts', label: '告警', icon: Bell, badge: true },
  { to: '/settings', label: '设置', icon: SettingsIcon },
];

const route = useRoute();
const router = useRouter();
const message = useMessage();
const auth = useAuthStore();
const realtime = useRealtimeStore();
const settings = useSettingsStore();

const isMobile = ref(false);
const drawerOpen = ref(false);
const alertCount = ref(0);
let alertTimer: number | undefined;
let clockTimer: number | undefined;
let mql: MediaQueryList | null = null;

const collapsed = computed(() => !isMobile.value && settings.collapsed);
const activePath = computed(() => route.path);
const breadcrumbParent = computed(() => route.meta.parent || null);

const streamChip = computed(() => {
  if (realtime.live) return { text: '实时', dot: 'running' as const, title: 'SSE 实时连接正常' };
  if (realtime.state === 'connecting') return { text: '实时连接中', dot: 'warn' as const, title: '正在建立 SSE 实时连接' };
  if (realtime.state === 'reconnecting') return { text: '实时重连中', dot: 'warn' as const, title: '实时连接中断，自动重连中；页面使用轮询兜底' };
  if (realtime.state === 'error') return { text: '轮询模式', dot: 'warn' as const, title: streamMeta.lastError || '实时连接不可用，已降级为轮询' };
  return { text: '轮询模式', dot: 'warn' as const, title: '实时连接不可用，页面使用轮询兜底' };
});

const userOptions = computed(() => [
  { key: 'account', label: auth.user?.name || 'Trader', disabled: true },
  { type: 'divider', key: 'd1' },
  { key: 'logout', label: '退出登录', icon: () => null },
]);


function isActive(to: string): boolean {
  return activePath.value === to || activePath.value.startsWith(to + '/');
}

async function loadAlertCount(): Promise<void> {
  try {
    const res = await api.alerts('active');
    alertCount.value = res.active_count;
  } catch {
    /* 未登录或网络问题：顶栏不阻塞 */
  }
}

function onRefresh(): void {
  settings.triggerRefresh();
  void loadAlertCount();
}

function onAlertsChanged(): void {
  void loadAlertCount();
}

function onMenuClick(): void {
  if (isMobile.value) drawerOpen.value = true;
  else settings.toggleCollapse();
}

function onUserSelect(key: string): void {
  if (key === 'logout') {
    drawerOpen.value = false;
    auth.logout().finally(() => {
      message.success('已退出登录');
      router.replace('/login');
    });
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') drawerOpen.value = false;
}

function applyViewport(): void {
  isMobile.value = window.innerWidth < 900;
  if (!isMobile.value) drawerOpen.value = false;
}

watch(() => realtime.lastAlertChangeAt, () => { void loadAlertCount(); });
watch(() => settings.refreshSeq, () => { void loadAlertCount(); });
watch(() => route.fullPath, () => { drawerOpen.value = false; });

onMounted(() => {
  applyViewport();
  mql = window.matchMedia('(max-width: 899px)');
  mql.addEventListener('change', applyViewport);
  window.addEventListener('keydown', onKeydown);
  window.addEventListener('qwatch:alerts-changed', onAlertsChanged);
  alertTimer = window.setInterval(loadAlertCount, 60000);
  clockTimer = window.setInterval(() => { nowTick.value = Date.now(); }, 1000);
  realtime.start();
  if (!auth.user) void auth.fetchMe();
  void loadAlertCount();
});

onBeforeUnmount(() => {
  mql?.removeEventListener('change', applyViewport);
  window.removeEventListener('keydown', onKeydown);
  window.removeEventListener('qwatch:alerts-changed', onAlertsChanged);
  if (alertTimer) window.clearInterval(alertTimer);
  if (clockTimer) window.clearInterval(clockTimer);
  realtime.stop();
});
</script>

<template>
  <div class="shell">
    <aside class="sidebar" :class="{ collapsed, 'drawer-open': isMobile && drawerOpen }">
      <div class="brand-row">
        <BrandMark :collapsed="collapsed" size="md" />
      </div>
      <nav class="nav" aria-label="主导航">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to), 'has-alert': item.to === '/alerts' && alertCount > 0 }"
          :title="collapsed ? item.label : undefined"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.7" class="nav-icon" />
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          <span v-if="!collapsed && item.badge && alertCount > 0" class="nav-badge">{{ alertCount }}</span>
          <span v-if="collapsed && item.badge && alertCount > 0" class="nav-alert-dot" />
        </router-link>
      </nav>
      <div class="sidebar-foot">
        <template v-if="!collapsed">
          <span class="env"><StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" /> v0.6.0</span>
          <span class="ver">qwatch · 可信看门狗</span>
        </template>
        <span v-else class="ver">0.5</span>
      </div>
    </aside>
    <div v-if="isMobile && drawerOpen" class="overlay" @click="drawerOpen = false" />

    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn" type="button" :aria-label="isMobile ? '打开菜单' : collapsed ? '展开侧栏' : '收起侧栏'" @click="onMenuClick">
            <component :is="isMobile ? Menu : collapsed ? PanelLeftOpen : PanelLeftClose" :size="17" />
          </button>
          <div class="crumbs">
            <template v-if="breadcrumbParent">
              <router-link :to="breadcrumbParent.to" class="crumb">{{ breadcrumbParent.title }}</router-link>
              <span class="sep">/</span>
            </template>
            <span class="current">{{ route.meta.title }}</span>
          </div>
        </div>
        <StatusControls />
      </header>
      <main class="content">
        <router-view v-slot="{ Component: ViewComponent }">
          <transition name="fade-slide" mode="out-in">
            <component :is="ViewComponent" :key="route.path" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}
.sidebar {
  z-index: 30;
  width: var(--sidebar-w);
  flex: none;
  display: flex;
  flex-direction: column;
  background: #0b1019;
  border-right: 1px solid var(--border);
  transition: width 180ms ease, transform 180ms ease;
}
.sidebar.collapsed {
  width: var(--sidebar-w-collapsed);
}
.brand-row {
  display: flex;
  align-items: center;
  height: var(--topbar-h);
  flex: none;
  padding: 0 16px;
  border-bottom: 1px solid var(--border);
}
.collapsed .brand-row {
  justify-content: center;
  padding: 0;
}
.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 8px;
  overflow-y: auto;
}
.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 38px;
  padding: 0 10px;
  border-radius: 8px;
  color: var(--text-2);
  font-size: 13px;
  transition: background-color 150ms ease, color 150ms ease;
  white-space: nowrap;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
}
.nav-item.active {
  background: var(--primary-soft);
  color: var(--primary);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 9px;
  bottom: 9px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--primary);
}
.collapsed .nav-item {
  justify-content: center;
  padding: 0;
}
.collapsed .nav-item.active::before {
  left: -8px;
}
.nav-icon {
  flex: none;
}
.nav-label {
  flex: 1;
}
.nav-badge {
  display: grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(240, 68, 56, 0.16);
  color: #ff8f86;
  font-family: var(--font-mono);
  font-size: 10px;
}
.nav-item.has-alert {
  background: rgba(240, 68, 56, 0.07);
}
.nav-item.has-alert .nav-icon {
  color: #ff8f86;
}
.nav-alert-dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #f04438;
  box-shadow: 0 0 0 3px rgba(240, 68, 56, 0.16);
}
.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 16px 14px;
  border-top: 1px solid var(--border);
}
.collapsed .sidebar-foot {
  align-items: center;
  padding: 12px 0 14px;
}
.env {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-2);
}
.ver {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-3);
}
.overlay {
  position: fixed;
  inset: 0;
  z-index: 29;
  background: rgba(4, 7, 12, 0.62);
  backdrop-filter: blur(2px);
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
.topbar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: var(--topbar-h);
  padding: 0 var(--pad-page);
  border-bottom: 1px solid var(--border);
  background: rgba(10, 14, 22, 0.88);
  backdrop-filter: blur(10px);
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stream-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 9px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-2);
  font-size: 11px;
  white-space: nowrap;
}
.freshness {
  font-size: 11px;
  color: var(--text-3);
  white-space: nowrap;
}
.icon-btn {
  position: relative;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
}
.icon-btn:hover {
  background: var(--surface-2);
  border-color: var(--border);
  color: var(--text);
}
.crumbs {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 16px;
  min-width: 0;
}
.crumb {
  color: var(--text-3);
}
.crumb:hover {
  color: var(--text-2);
}
.sep {
  color: var(--text-3);
  opacity: 0.6;
}
.current {
  color: var(--text);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: 50%;
  border: 1px solid rgba(91, 140, 255, 0.32);
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.bell.has-alerts {
  color: #ff8f86;
  background: rgba(240, 68, 56, 0.1);
  border-color: rgba(240, 68, 56, 0.28);
}
.bell-dot {
  position: absolute;
  top: -4px;
  right: -5px;
  display: grid;
  place-items: center;
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  border-radius: 8px;
  background: #f04438;
  border: 2px solid var(--bg);
  color: #fff;
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1;
}
.spinning {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--pad-page);
  scroll-behavior: smooth;
}
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 120ms ease, transform 120ms ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.fade-slide-leave-to {
  opacity: 0;
}
@media (max-width: 899px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: var(--sidebar-w);
    transform: translateX(-100%);
    box-shadow: none;
  }
  .sidebar.drawer-open {
    transform: none;
    box-shadow: var(--shadow-pop);
  }
  .content {
    -webkit-overflow-scrolling: touch;
  }
}
@media (min-width: 900px) {
  .overlay {
    display: none;
  }
}
@media (max-width: 639px) {
  .freshness,
  .stream-text {
    display: none;
  }
  .topbar {
    gap: 8px;
  }
  .topbar-right {
    gap: 4px;
  }
  .crumbs .crumb,
  .crumbs .sep {
    display: none;
  }
}
</style>