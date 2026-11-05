<script setup lang="ts">
// StatusControls.vue — 顶栏状态控制组：实时/刷新/告警/账号；总览沉浸模式下复用。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { NDropdown, useMessage } from 'naive-ui';
import { Bell, RefreshCw } from 'lucide-vue-next';
import { api, apiMeta } from '@/api/client';
import { useAuthStore } from '@/stores/auth';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import StatusDot from './StatusDot.vue';

const router = useRouter();
const message = useMessage();
const auth = useAuthStore();
const realtime = useRealtimeStore();
const settings = useSettingsStore();
const alertCount = ref(0);
let timer: number | undefined;

const stream = computed(() => {
  if (realtime.live) return { text: '实时', dot: 'running' as const, title: 'SSE 实时连接正常' };
  if (realtime.state === 'connecting') return { text: '连接中', dot: 'warn' as const, title: '正在建立 SSE 实时连接' };
  if (realtime.state === 'reconnecting') return { text: '重连中', dot: 'warn' as const, title: '实时连接中断，自动重连中' };
  return { text: '轮询', dot: 'warn' as const, title: '实时连接不可用，使用轮询兜底' };
});
const userOptions = computed(() => [
  { key: 'account', label: auth.user?.name || 'Trader', disabled: true },
  { type: 'divider', key: 'd1' },
  { key: 'logout', label: '退出登录' },
]);

async function loadAlertCount(): Promise<void> {
  try { alertCount.value = (await api.alerts('active')).active_count; }
  catch { /* 顶栏不阻塞页面 */ }
}
function refresh(): void {
  settings.triggerRefresh();
  void loadAlertCount();
}
function onUserSelect(key: string): void {
  if (key !== 'logout') return;
  auth.logout().finally(() => {
    message.success('已退出登录');
    router.replace('/login');
  });
}
function onAlertsChanged(): void { void loadAlertCount(); }
watch(() => realtime.lastAlertChangeAt, () => { void loadAlertCount(); });
onMounted(() => {
  void loadAlertCount();
  timer = window.setInterval(loadAlertCount, 60000);
  window.addEventListener('qwatch:alerts-changed', onAlertsChanged);
});
onBeforeUnmount(() => {
  window.clearInterval(timer);
  window.removeEventListener('qwatch:alerts-changed', onAlertsChanged);
});
</script>

<template>
  <div class="status-controls">
    <span class="stream" :title="stream.title"><StatusDot :status="stream.dot" :size="6" />{{ stream.text }}</span>
    <button class="ctl" type="button" aria-label="刷新" title="刷新全部数据" @click="refresh">
      <RefreshCw :size="15" :class="{ spinning: apiMeta.pending > 0 }" />
    </button>
    <button class="ctl bell" :class="{ 'has-alerts': alertCount > 0 }" type="button" aria-label="告警中心" title="告警中心" @click="router.push('/alerts')">
      <Bell :size="16" />
      <span v-if="alertCount" class="dot">{{ alertCount > 9 ? '9+' : alertCount }}</span>
    </button>
    <n-dropdown trigger="click" :options="userOptions" @select="onUserSelect">
      <button class="avatar" type="button" :aria-label="'账号：' + (auth.user?.name || 'Trader')">{{ (auth.user?.name || 'T').slice(0, 1).toUpperCase() }}</button>
    </n-dropdown>
  </div>
</template>

<style scoped>
.status-controls { display: flex; align-items: center; gap: 6px; }
.stream { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 8px; border: 1px solid var(--border); border-radius: 6px; color: var(--text-2); font-size: 10px; white-space: nowrap; }
.ctl { position: relative; width: 28px; height: 28px; display: grid; place-items: center; border: 1px solid transparent; border-radius: 7px; background: transparent; color: var(--text-2); cursor: pointer; }
.ctl:hover { border-color: var(--border); background: var(--surface-2); color: var(--text); }
.ctl.has-alerts { color: #ff8f86; background: rgba(240,68,56,.08); border-color: rgba(240,68,56,.2); }
.dot { position: absolute; top: -4px; right: -5px; min-width: 15px; height: 15px; padding: 0 3px; display: grid; place-items: center; border-radius: 8px; border: 2px solid var(--bg); background: #f04438; color: #fff; font: 9px var(--font-mono); }
.avatar { width: 28px; height: 28px; border-radius: 50%; border: 1px solid rgba(91,140,255,.32); background: var(--primary-soft); color: var(--primary); font: 600 11px var(--font); cursor: pointer; }
.spinning { animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
