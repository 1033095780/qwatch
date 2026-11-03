<script setup lang="ts">
// Alerts.vue — 告警中心：活跃/历史 Tabs、级别/时间排序、确认与静默。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NDropdown, useMessage } from 'naive-ui';
import { BellOff, Check } from 'lucide-vue-next';
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
const sortBy = ref<'time' | 'severity'>('time');
const busyId = ref('');

const silenceOptions = [
  { label: '静默 1 小时', key: '1h' },
  { label: '静默 4 小时', key: '4h' },
  { label: '静默 24 小时', key: '24h' },
];

const RULE_LABEL: Record<string, string> = {
  heartbeat_lost: '心跳丢失',
  runner_stalled: '策略卡死',
  market_data_stale: '行情断流',
  drawdown_breach: '回撤超阈值',
  daily_loss_limit: '日亏损超限',
  fill_burst: '成交突发',
  risk_limit: '风控触发',
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
  const severityRank: Record<string, number> = { P0: 0, P1: 1, P2: 2 };
  return [...source].sort((a, b) => {
    if (sortBy.value === 'severity') {
      const diff = (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9);
      if (diff !== 0) return diff;
    }
    return Date.parse(b.starts_at) - Date.parse(a.starts_at);
  });
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
    await load();
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
      :subtitle="firingCount + ' 条触发中 · ' + ackedCount + ' 条已确认 · P0 立即通知，P1 合并，P2 可静默 · 时间 Asia/Shanghai'"
    >
      <template #extra>
        <span class="chip">确认 / 静默立即生效</span>
      </template>
    </PageHeader>

    <section class="card alerts-card">
      <div class="head-row">
        <TabBar v-model="tab" :tabs="tabs" />
        <div class="sort-wrap">
          <span class="faint">排序</span>
          <div class="seg">
            <button type="button" :class="{ active: sortBy === 'time' }" @click="sortBy = 'time'">时间</button>
            <button type="button" :class="{ active: sortBy === 'severity' }" @click="sortBy = 'severity'">级别</button>
          </div>
        </div>
      </div>

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
          :description="tab === 'active' ? '所有策略心跳、行情与回撤均在阈值内' : '告警恢复后会归档到这里'"
        />
      </div>

      <div v-else class="alert-list">
        <article v-for="alert in currentItems" :key="alert.id" class="alert-card" :class="alert.severity">
          <div class="alert-head">
            <div class="head-left">
              <SeverityTag :severity="alert.severity" />
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
.alerts-card {
  padding: 0 20px 16px;
}
.head-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.sort-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  padding-bottom: 6px;
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
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.5);
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
.alert-card.P1::before { background: #f5a524; }
.alert-card.P2::before { background: #38bdf8; }
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
