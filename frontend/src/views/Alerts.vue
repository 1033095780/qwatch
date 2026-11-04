// Alerts.vue — v0.2 告警中心：P0 实时告警（SSE + 轮询兜底），活跃/历史，确认与静默。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { NButton, NDropdown, useMessage } from 'naive-ui';
import { api } from '@/api/client';
import type { Alert } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { ruleLabel } from '@/utils/catalog';
import { fmtDateTime, fromNow } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import StatusDot from '@/components/StatusDot.vue';
import TabBar from '@/components/TabBar.vue';
import type { TabItem } from '@/components/TabBar.vue';

const settings = useSettingsStore();
const realtime = useRealtimeStore();
const message = useMessage();

const activeItems = ref<Alert[]>([]);
const historyItems = ref<Alert[]>([]);
const loading = ref(true);
const error = ref('');
const tab = ref('active');
const busyId = ref('');
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const silenceOptions = [
  { label: '静默 1 小时', key: '1h' },
  { label: '静默 4 小时', key: '4h' },
  { label: '静默 24 小时', key: '24h' },
];

const tabs = computed<TabItem[]>(() => [
  { key: 'active', label: '活跃', count: activeItems.value.length },
  { key: 'history', label: '历史', count: historyItems.value.length },
]);
const currentItems = computed(() => {
  const source = tab.value === 'active' ? activeItems.value : historyItems.value;
  return [...source].sort((a, b) => Date.parse(b.starts_at) - Date.parse(a.starts_at));
});

async function load(initial = false, silent = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [active, history] = await Promise.all([api.alerts('active'), api.alerts('history')]);
    activeItems.value = active.items;
    historyItems.value = history.items;
  } catch (err) {
    if (!silent || !activeItems.value.length) error.value = err instanceof Error ? err.message : '告警加载失败';
  } finally {
    loading.value = false;
  }
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

async function acknowledge(alert: Alert): Promise<void> {
  busyId.value = alert.id;
  try {
    await api.ackAlert(alert.id);
    message.success('已确认告警：' + ruleLabel(alert.rule));
    await load(false, true);
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '确认失败');
  } finally {
    busyId.value = '';
  }
}

async function silence(alert: Alert, duration = '1h'): Promise<void> {
  busyId.value = alert.id;
  try {
    await api.silenceAlert(alert.id, duration);
    const labels: Record<string, string> = { '1h': '1 小时', '4h': '4 小时', '24h': '24 小时' };
    message.success('已静默 ' + (labels[duration] ?? '1 小时'));
    await load(false, true);
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '静默失败');
  } finally {
    busyId.value = '';
  }
}

watch(() => realtime.lastAlertChangeAt, scheduleReload);
watch(() => settings.refreshSeq, () => { void load(false, true); });

onMounted(() => {
  void load(true);
  pollTimer = window.setInterval(() => {
    if (!document.hidden) void load(false, true);
  }, 20000);
});

onBeforeUnmount(() => {
  window.clearInterval(pollTimer);
  window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="page">
    <PageHeader title="告警">
      <template #extra>
        <span class="live-hint" :class="{ live: realtime.live }">
          <StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" />
          {{ realtime.live ? '实时' : '轮询' }}
        </span>
      </template>
    </PageHeader>

    <div v-if="error" class="error-bar">
      <span class="dot" />{{ error }}
      <n-button text size="tiny" @click="load(true)">重试</n-button>
    </div>

    <section class="card alerts-card">
      <TabBar v-model="tab" :tabs="tabs" />

      <div v-if="loading && !activeItems.length && !historyItems.length" class="loading-list">
        <div v-for="i in 3" :key="i" class="skel" style="height: 92px; border-radius: 10px" />
      </div>

      <div v-else-if="!currentItems.length" class="empty-wrap">
        <EmptyState
          :title="tab === 'active' ? '当前没有活跃告警' : '暂无历史告警'"
          :description="tab === 'active' ? '所有策略组心跳与 loop 判定正常。' : '告警确认或恢复后会归档到这里。'"
        />
      </div>

      <div v-else class="alert-list">
        <article v-for="alert in currentItems" :key="alert.id" class="alert-card" :class="alert.status">
          <div class="alert-head">
            <span class="rule-chip">{{ ruleLabel(alert.rule) }}</span>
            <span class="mono rule-key">{{ alert.rule }}</span>
            <span class="status-chip" :class="alert.status">{{ alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复' }}</span>
            <span class="spacer" />
            <span class="time mono" :title="fmtDateTime(alert.starts_at)">{{ fromNow(alert.starts_at) }}</span>
          </div>
          <p class="alert-summary">{{ alert.summary }}</p>
          <div class="alert-meta">
            <router-link :to="'/strategies/' + alert.runner_id" class="runner-link">{{ alert.runner_name }}</router-link>
            <span class="sep">·</span>
            <span class="mono">{{ alert.runner_id }}</span>
            <span v-if="alert.ends_at" class="chip chip--soft">持续至 {{ fmtDateTime(alert.ends_at) }}</span>
            <span v-if="alert.labels && alert.labels.silenced_until" class="silenced mono">静默至 {{ fmtDateTime(alert.labels.silenced_until) }}</span>
            <span class="spacer" />
            <div v-if="alert.status !== 'resolved'" class="actions">
              <n-button v-if="alert.status === 'firing'" size="tiny" :loading="busyId === alert.id" @click="acknowledge(alert)">确认</n-button>
              <n-dropdown trigger="click" :options="silenceOptions" @select="(key) => silence(alert, String(key))">
                <n-button size="tiny" quaternary :loading="busyId === alert.id">静默</n-button>
              </n-dropdown>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.live-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-3);
}
.live-hint.live {
  color: #2ecc8f;
}
.alerts-card {
  padding: 0 20px 16px;
}
.loading-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 0;
}
.empty-wrap {
  padding: 8px 0;
}
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
}
.alert-card {
  padding: 14px 16px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.45);
}
.alert-card.firing {
  border-color: rgba(240, 68, 56, 0.28);
  background: rgba(240, 68, 56, 0.045);
}
.alert-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.rule-chip {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.1);
  color: #ff8f86;
  font-size: 10px;
}
.rule-key {
  font-size: 10px;
  color: var(--text-3);
}
.status-chip {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 10px;
  border: 1px solid transparent;
}
.status-chip.firing {
  color: #ff8f86;
  background: rgba(240, 68, 56, 0.12);
  border-color: rgba(240, 68, 56, 0.3);
}
.status-chip.acknowledged {
  color: #f5b64b;
  background: rgba(245, 165, 36, 0.1);
  border-color: rgba(245, 165, 36, 0.26);
}
.status-chip.resolved {
  color: var(--text-3);
  background: rgba(95, 109, 132, 0.12);
  border-color: rgba(95, 109, 132, 0.26);
}
.spacer {
  flex: 1;
}
.time {
  font-size: 11px;
  color: var(--text-2);
}
.time-abs {
  font-size: 10px;
  color: var(--text-3);
}
.alert-summary {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text);
}
.alert-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-3);
}
.runner-link {
  color: var(--primary);
  font-size: 11px;
}
.sep {
  color: var(--text-3);
}
.silenced {
  color: #f5b64b;
  font-size: 10px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
@media (max-width: 639px) {
  .alerts-card {
    padding: 0 12px 12px;
  }
  .alert-card {
    padding: 12px 12px 10px;
  }
  .time-abs {
    display: none;
  }
}
</style>
