<script setup lang="ts">
// AppShell.vue — 桌面侧栏（232/64）+ 顶栏（市场状态/刷新/告警/头像）+ 移动端抽屉；全局刷新信号。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { Component } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NDropdown, useMessage } from 'naive-ui';
import {
  Activity, Bell, FileText, LayoutDashboard, LogOut, Menu, PanelLeftClose,
  PanelLeftOpen, Radio, RefreshCw, Settings as SettingsIcon, Wallet,
} from 'lucide-vue-next';
import { api, apiMeta } from '@/api/client';
import { useAuthStore } from '@/stores/auth';
import { useSettingsStore } from '@/stores/settings';
import { fmtSecondsAgo } from '@/utils/format';
import BrandMark from '@/components/BrandMark.vue';
import StatusDot from '@/components/StatusDot.vue';

interface NavItem { to: string; label: string; icon: Component; badge?: boolean }

const navItems: NavItem[] = [
  { to: '/overview', label: '总览', icon: LayoutDashboard },
  { to: '/strategies', label: '策略', icon: Activity },
  { to: '/accounts', label: '账户', icon: Wallet },
  { to: '/signals', label: '信号', icon: Radio },
  { to: '/alerts', label: '告警', icon: Bell, badge: true },
  { to: '/reports', label: '日报', icon: FileText },
  { to: '/settings', label: '设置', icon: SettingsIcon },
];

const route = useRoute();
const router = useRouter();
const message = useMessage();
const auth = useAuthStore();
const settings = useSettingsStore();

const isMobile = ref(false);
const drawerOpen = ref(false);
const alertCount = ref(0);
const now = ref(Date.now());
let clockTimer: number | undefined;
let alertTimer: number | undefined;
let mql: MediaQueryList | null = null;

const collapsed = computed(() => !isMobile.value && settings.collapsed);
const activePath = computed(() => route.path);

const userOptions = computed(() => [
  { key: 'account', label: auth.user?.name || 'Trader', disabled: true },
  { type: 'divider', key: 'd1' },
  { key: 'logout', label: '退出登录', icon: () => null },
]);

function isActive(to: string): boolean {
  return activePath.value === to || activePath.value.startsWith(to + '/');
}

function shanghaiMinutes(): number {
  const d = new Date(Date.now() + 8 * 3600 * 1000);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}

function inSessions(minutes: number, sessions: [number, number][]): boolean {
  return sessions.some(([start, end]) => minutes >= start && minutes < end);
}

const marketChips = computed(() => {
  // 依赖 now 触发每 30s 重算
  void now.value;
  const m = shanghaiMinutes();
  const weekday = new Date(Date.now() + 8 * 3600 * 1000).getUTCDay(); // 0=周日
  const weekend = weekday === 0 || weekday === 6;
  const aTrading = !weekend && inSessions(m, [[555, 690], [780, 900]]);
  const aLunch = !weekend && m >= 690 && m < 780;
  const aText = weekend ? '休市' : aTrading ? '交易中' : aLunch ? '午间休市' : m < 555 ? '未开盘' : '已收盘';
  const futNight = m >= 1260 || m < 150;
  const futDay = !weekend && inSessions(m, [[540, 615], [630, 690], [810, 900]]);
  const futLunch = !weekend && ((m >= 615 && m < 630) || (m >= 690 && m < 810));
  const futText = futNight ? '夜盘' : futDay ? '交易中' : futLunch ? '午间休市' : '休市';
  return [
    { label: 'A股', text: aText, active: aTrading },
    { label: '期货', text: futText, active: futNight || futDay },
  ];
});

const freshness = computed(() => {
  void now.value;
  return fmtSecondsAgo(apiMeta.lastResponseAt);
});

const breadcrumbParent = computed(() => route.meta.parent || null);

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
  loadAlertCount();
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

onMounted(() => {
  applyViewport();
  mql = window.matchMedia('(max-width: 899px)');
  mql.addEventListener('change', applyViewport);
  window.addEventListener('keydown', onKeydown);
  clockTimer = window.setInterval(() => { now.value = Date.now(); }, 5000);
  alertTimer = window.setInterval(loadAlertCount, 60000);
  if (!auth.user) auth.fetchMe();
  loadAlertCount();
});

onBeforeUnmount(() => {
  mql?.removeEventListener('change', applyViewport);
  window.removeEventListener('keydown', onKeydown);
  if (clockTimer) window.clearInterval(clockTimer);
  if (alertTimer) window.clearInterval(alertTimer);
});

watch(() => settings.refreshSeq, loadAlertCount);
watch(() => route.fullPath, () => { drawerOpen.value = false; });
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
          :class="{ active: isActive(item.to) }"
          :title="collapsed ? item.label : undefined"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.7" class="nav-icon" />
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          <span v-if="!collapsed && item.badge && alertCount > 0" class="nav-badge">{{ alertCount }}</span>
        </router-link>
      </nav>
      <div class="sidebar-foot">
        <template v-if="!collapsed">
          <span class="env"><StatusDot status="running" :size="6" /> v0.1.0</span>
          <span class="ver">qwatch v0.1.0</span>
        </template>
        <span v-else class="ver">0.1</span>
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
        <div class="topbar-right">
          <div class="market-chips">
            <span v-for="chip in marketChips" :key="chip.label" class="market-chip">
              <StatusDot :status="chip.active ? 'running' : 'off_hours'" :size="6" />
              {{ chip.label }} {{ chip.text }}
            </span>
          </div>
          <span class="freshness num" title="数据新鲜度">{{ freshness }}</span>
          <button class="icon-btn" type="button" aria-label="刷新" title="刷新当前页数据" @click="onRefresh">
            <RefreshCw :size="16" :class="{ spinning: apiMeta.pending > 0 }" />
          </button>
          <button class="icon-btn bell" type="button" aria-label="告警中心" title="告警中心" @click="router.push('/alerts')">
            <Bell :size="17" />
            <span v-if="alertCount > 0" class="bell-dot">{{ alertCount > 9 ? '9+' : alertCount }}</span>
          </button>
          <n-dropdown trigger="click" :options="userOptions" @select="onUserSelect">
            <button class="avatar" type="button" :aria-label="'账号：' + (auth.user?.name || 'Trader')">
              {{ (auth.user?.name || 'T').slice(0, 1).toUpperCase() }}
            </button>
          </n-dropdown>
        </div>
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
  gap: 6px;
  font-size: 13px;
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
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.market-chips {
  display: flex;
  align-items: center;
  gap: 6px;
}
.market-chip {
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
  font-size: 9px;
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

@media (max-width: 1099px) {
  .market-chips {
    display: none;
  }
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
  .freshness {
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
