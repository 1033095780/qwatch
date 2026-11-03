<script setup lang="ts">
// Alerts.vue — 告警中心：心跳丢失 / 策略卡死（统一 P0 红色）· 活跃/历史 Tabs · 确认与静默。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NDropdown, useMessage } from 'naive-ui';
import { AlertTriangle, BellOff, Check } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Alert } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDateTime, fmtDuration, fromNow } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import SeverityTag from '@/components/SeverityTag.vue';
import TabBar from '@/components/TabBar.vue';
import type { TabItem } from '@/components/TabBar.vue';

const settings = useSettingsStore();
const message = useMessage();

const activeItems = ref<Alert[]>([]);
const historyItems = ref<Alert[]>([]);
const loading = ref(true);
const error = ref('');
const tab = ref('active');
const busyId = ref('');
const ackAllBusy = ref(false);

const silenceOptions = [
  { label: '静默 1 小时', key: '1h' },
  { label: '静默 4 小时', key: '4h' },
  { label: '静默 24 小时', key: '24h' },
];

/** 告警规则展示名：后端只产出心跳丢失 / 策略卡死两类，统一按 P0 红色展示 */
const RULE_LABEL: Record<string, string> = {
  heartbeat_lost: '心跳丢失',
  runner_stalled: '策略卡死',
};

const STATUS_LABEL: Record<Alert['status'], string> = {
  firing: '触发中',
  acknowledged: '已确认',
  resolved: '已恢复',
};

const firingCount = computed(() => activeItems.value.filter((a) => a.status === 'firing').length);
const ackedCount = computed(() => activeItems.value.filter((a) => a.status === 'acknowledged').length);

const tabs = computed<TabItem[]>(() => [
  { key: 'active', label: '活跃', count: activeItems.value.length },
  { key: 'history', label: '历史', count: historyItems.value.length },
]);

const currentItems = computed(() => {
  const source = tab.value === 'active' ? activeItems.value : historyItems.value;
  return [...source].sort((a, b) => Date.parse(b.starts_at) - Date.parse(a.starts_at));
});

function durationOf(alert: Alert): string {
  if (!alert.ends_at) return '';
  return fmtDuration((Date.parse(alert.ends_at) - Date.parse(alert.starts_at)) / 1000);
}

/** 展示用 label：静默时间单独展示，不重复塞进 label 列表 */
function visibleLabels(alert: Alert): [string, string][] {
  return Object.entries(alert.labels).filter(([key]) => key !== 'silenced_until');
}

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [active, history] = await Promise.all([api.alerts('active'), api.alerts('history')]);
    activeItems.value = active.items;
    historyItems.value = history.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '告警加载失败';
  } finally {
    loading.value = false;
  }
}

async function acknowledge(alert: Alert): Promise<void> {
  busyId.value = alert.id;
  try {
    await api.ackAlert(alert.id);
    message.success('已确认告警：' + (RULE_LABEL[alert.rule] ?? alert.rule));
    await load();
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '确认失败');
  } finally {
    busyId.value = '';
  }
}

async function acknowledgeAll(): Promise<void> {
  const firing = activeItems.value.filter((item) => item.status === 'firing');
  if (!firing.length) return;
  ackAllBusy.value = true;
  try {
    await Promise.all(firing.map((item) => api.ackAlert(item.id)));
    message.success('已确认 ' + firing.length + ' 条 P0 告警');
    await load();
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '批量确认失败');
  } finally {
    ackAllBusy.value = false;
  }
}

async function silence(alert: Alert, duration = '1h'): Promise<void> {
  busyId.value = alert.id;
  try {
    await api.silenceAlert(alert.id, duration);
    const labels: Record<string, string> = { '1h': '1 小时', '4h': '4 小时', '24h': '24 小时' };
    message.success('已静默 ' + (labels[duration] ?? '1 小时'));
    await load();
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '静默失败');
  } finally {
    busyId.value = '';
  }
}

watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <PageHeader
      title="告警中心"
      :subtitle="firingCount + ' 条触发中 · ' + ackedCount + ' 条已确认 · 心跳丢失 / 策略卡死统一 P0 红色告警 · 时间 Asia/Shanghai'"
    >
      <template #extra>
        <span class="chip">确认 / 静默立即生效</span>
      </template>
    </PageHeader>

    <div v-if="firingCount > 0" class="alert-banner">
      <div class="banner-main">
        <span class="banner-icon"><AlertTriangle :size="18" /></span>
        <div class="banner-text">
          <strong>{{ firingCount }} 条 P0 告警待处理</strong>
          <span>心跳丢失 / 策略卡死 · 建议立即确认并检查策略进程</span>
        </div>
      </div>
      <n-button size="small" type="error" secondary :loading="ackAllBusy" @click="acknowledgeAll">
        全部确认
      </n-button>
    </div>

    <section class="card alerts-card">
      <TabBar v-model="tab" :tabs="tabs" />

      <div v-if="error" class="error-bar" style="margin-top: 14px">
        <span class="dot" />{{ error }}
        <n-button text size="tiny" @click="load(true)">重试</n-button>
      </div>

      <div v-if="loading && !activeItems.length && !historyItems.length" class="loading-list">
        <div v-for="i in 3" :key="i" class="skel" style="height: 92px; border-radius: 10px" />
      </div>

      <div v-else-if="!currentItems.length" class="empty-wrap">
        <EmptyState
          :title="tab === 'active' ? '当前没有活跃告警' : '暂无历史告警'"
          :description="tab === 'active' ? '所有策略心跳与运行状态均正常' : '告警恢复后会归档到这里'"
        />
      </div>

      <div v-else class="alert-list">
        <article v-for="alert in currentItems" :key="alert.id" class="alert-card P0">
          <div class="alert-head">
            <div class="head-left">
              <SeverityTag severity="P0" />
              <span class="rule">{{ RULE_LABEL[alert.rule] ?? alert.rule }}</span>
              <span class="rule-key mono">{{ alert.rule }}</span>
              <span class="status-chip" :class="alert.status">{{ STATUS_LABEL[alert.status] }}</span>
            </div>
            <div class="head-right">
              <span class="time mono" :title="alert.starts_at">{{ fromNow(alert.starts_at) }}</span>
              <span class="time-abs mono">{{ fmtDateTime(alert.starts_at) }}</span>
            </div>
          </div>
          <p class="summary">{{ alert.summary }}</p>
          <div class="alert-meta">
            <router-link :to="'/strategies/' + alert.runner_id" class="runner-link">{{ alert.runner_name }}</router-link>
            <span class="sep">·</span>
            <span class="mono">{{ alert.runner_id }}</span>
            <template v-for="entry in visibleLabels(alert)" :key="entry[0]">
              <span class="label-chip mono">{{ entry[0] }}={{ entry[1] }}</span>
            </template>
            <span v-if="alert.ends_at" class="chip chip--soft">持续 {{ durationOf(alert) }}</span>
            <span v-if="alert.labels.silenced_until" class="silenced mono">静默至 {{ fmtDateTime(alert.labels.silenced_until) }}</span>
            <span class="spacer" />
            <div v-if="alert.status !== 'resolved'" class="actions">
              <n-button
                v-if="alert.status === 'firing'"
                size="tiny"
                :loading="busyId === alert.id"
                @click="acknowledge(alert)"
              >
                <template #icon><Check :size="12" /></template>
                确认
              </n-button>
              <n-dropdown trigger="click" :options="silenceOptions" @select="(key) => silence(alert, String(key))">
                <n-button size="tiny" quaternary :loading="busyId === alert.id">
                  <template #icon><BellOff :size="12" /></template>
                  静默
                </n-button>
              </n-dropdown>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.alert-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  padding: 14px 18px;
  border: 1px solid rgba(240, 68, 56, 0.35);
  border-radius: 12px;
  background: linear-gradient(90deg, rgba(240, 68, 56, 0.16), rgba(240, 68, 56, 0.06));
}
.banner-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.banner-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 9px;
  background: rgba(240, 68, 56, 0.2);
  color: #ff8f86;
  animation: bannerPulse 2s ease-in-out infinite;
}
@keyframes bannerPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(240, 68, 56, 0.25); }
  50% { box-shadow: 0 0 0 6px rgba(240, 68, 56, 0.08); }
}
.banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.banner-text strong {
  color: #ffb4ad;
  font-size: 13px;
  font-weight: 600;
}
.banner-text span {
  color: var(--text-2);
  font-size: 11px;
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
  position: relative;
  padding: 14px 16px 12px;
  border-radius: 10px;
  border: 1px solid rgba(240, 68, 56, 0.2);
  background: rgba(240, 68, 56, 0.045);
  overflow: hidden;
  transition: border-color 150ms ease, background-color 150ms ease;
}
.alert-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
}
.alert-card.P0::before { background: #f04438; }
.alert-card:hover {
  border-color: var(--border-strong);
  background: rgba(21, 28, 44, 0.8);
}
.alert-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.head-right {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.rule {
  font-size: 13px;
  font-weight: 500;
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
.time {
  font-size: 11px;
  color: var(--text-2);
}
.time-abs {
  font-size: 10px;
  color: var(--text-3);
}
.summary {
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
.label-chip {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  color: var(--text-3);
  font-size: 10px;
}
.silenced {
  color: #f5b64b;
  font-size: 10px;
}
.spacer {
  flex: 1;
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
