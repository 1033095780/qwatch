// Overview.vue — v0.3 总览：总权益/权益曲线 + 策略状态/心跳 + 实时动态/告警。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { NButton } from 'naive-ui';
import { Bell, ChevronRight, RefreshCw, TrendingUp, Wallet, Waves } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Overview } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { fmtDateTime, fmtNumber, fromNow } from '@/utils/format';
import { ruleLabel } from '@/utils/catalog';
import EmptyState from '@/components/EmptyState.vue';
import EventTimeline from '@/components/EventTimeline.vue';
import HeartbeatGrid from '@/components/HeartbeatGrid.vue';
import NavChart from '@/components/NavChart.vue';
import PageHeader from '@/components/PageHeader.vue';
import SectionCard from '@/components/SectionCard.vue';
import StatusDot from '@/components/StatusDot.vue';
import StatusTag from '@/components/StatusTag.vue';

const settings = useSettingsStore();
const realtime = useRealtimeStore();
const router = useRouter();

const data = ref<Overview | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref('');
const lastLoadedAt = ref(Date.now());
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const summary = computed(() => {
  const ov = data.value;
  if (!ov) return null;
  const total = ov.total ?? 0;
  const running = ov.running ?? 0;
  const processesTotal = ov.processes_total ?? (ov.runners || []).reduce((sum, r) => sum + (r.process_count || 0), 0);
  const processesOnline = ov.processes_online ?? (ov.runners || []).reduce((sum, r) => sum + (r.online_processes || 0), 0);
  return {
    total,
    running,
    abnormal: Math.max(0, total - running),
    activeAlerts: ov.active_alerts ?? 0,
    processesTotal,
    processesOnline,
    totalEquity: ov.total_equity ?? null,
    todayEquityChange: ov.today_equity_change ?? null,
    equityAsOf: ov.equity_as_of ?? null,
  };
});

const recentEvents = computed(() => {
  const live = realtime.events;
  const initial = data.value?.recent_events || [];
  const ids = new Set(live.map((event) => String(event.id)));
  return [...live, ...initial.filter((event) => !ids.has(String(event.id)))].slice(0, 8);
});
const recentAlerts = computed(() => (data.value?.recent_alerts || []).slice(0, 6));
const equityCurve = computed(() => data.value?.equity_curve ?? []);
const equityChange = computed(() => {
  const raw = data.value?.today_equity_change;
  if (raw === null || raw === undefined || raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
});

async function load(initial = false, silent = false): Promise<void> {
  if (initial) loading.value = true;
  else if (!silent) refreshing.value = true;
  error.value = '';
  try {
    data.value = await api.overview();
    lastLoadedAt.value = Date.now();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '总览加载失败';
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

function openEvent(event: { runner_id?: string }): void {
  if (!event.runner_id) return;
  void router.push('/strategies/' + event.runner_id + '?tab=events');
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

watch(() => settings.refreshSeq, () => { void load(false, true); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastEventAt], scheduleReload);

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
    <PageHeader title="总览" :subtitle="'策略存活与实时告警 · 更新于 ' + fmtDateTime(new Date(lastLoadedAt).toISOString()) + ' CST'">
      <template #extra>
        <n-button size="small" :loading="refreshing" @click="load(false)">
          <template #icon><RefreshCw :size="14" /></template>
          刷新
        </n-button>
      </template>
    </PageHeader>

    <div v-if="loading && !data" class="page">
      <div class="summary-grid">
        <div v-for="i in 4" :key="i" class="skel skel-card" style="height: 96px" />
      </div>
      <div class="grid grid-2">
        <div v-for="i in 2" :key="i" class="skel" style="height: 220px; border-radius: 12px" />
      </div>
    </div>

    <div v-else-if="error && !data" class="card">
      <EmptyState title="总览加载失败" :description="error">
        <template #action><n-button size="small" @click="load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else-if="data && summary">
      <div v-if="error" class="error-bar">
        <span class="dot" />{{ error }}
        <n-button text size="tiny" @click="load(true)">重试</n-button>
      </div>

      <div class="summary-grid">
        <div class="ov-kpi">
          <div class="ov-kpi-top">
            <span class="ov-kpi-label">总权益</span>
            <span class="ov-kpi-icon"><Wallet :size="15" /></span>
          </div>
          <div class="ov-kpi-value equity">{{ summary.totalEquity !== null ? '¥' + fmtNumber(summary.totalEquity, 2) : '—' }}</div>
          <div class="ov-kpi-foot">运行中 {{ summary.running }} / 共 {{ summary.total }} 个策略组</div>
        </div>
        <div class="ov-kpi">
          <div class="ov-kpi-top">
            <span class="ov-kpi-label">今日权益变动</span>
            <span class="ov-kpi-icon"><TrendingUp :size="15" /></span>
          </div>
          <div class="ov-kpi-value" :class="equityChange === null ? '' : equityChange >= 0 ? 'up' : 'down'">
            {{ equityChange === null ? '—' : (equityChange >= 0 ? '+' : '') + fmtNumber(equityChange, 2) }}
          </div>
          <div class="ov-kpi-foot">{{ summary.equityAsOf ? '更新于 ' + fmtDateTime(summary.equityAsOf) : '暂无权益上报' }}</div>
        </div>
        <div class="ov-kpi">
          <div class="ov-kpi-top">
            <span class="ov-kpi-label">进程在线</span>
            <span class="ov-kpi-icon"><Waves :size="15" /></span>
          </div>
          <div class="ov-kpi-value">{{ summary.processesOnline }}<span class="ov-kpi-dim"> / {{ summary.processesTotal }}</span></div>
          <div class="ov-kpi-foot">在线 / 全部进程</div>
        </div>
        <router-link to="/alerts" class="ov-kpi ov-kpi--link" :class="{ 'ov-kpi--danger': summary.activeAlerts > 0 }">
          <div class="ov-kpi-top">
            <span class="ov-kpi-label">活跃告警</span>
            <span class="ov-kpi-icon" :class="{ danger: summary.activeAlerts > 0 }"><Bell :size="15" /></span>
          </div>
          <div class="ov-kpi-value" :class="{ danger: summary.activeAlerts > 0 }">{{ summary.activeAlerts }} <span class="ov-kpi-unit">条</span></div>
          <div class="ov-kpi-foot">{{ summary.activeAlerts > 0 ? 'P0 告警待处理 · 点击查看' : '全部正常' }}</div>
        </router-link>
      </div>

      <div class="overview-main">
        <SectionCard title="组合权益" subtitle="各策略组最新权益合计；曲线按组内进程上报的权益点合并">
          <div class="nav-panel">
            <div class="nav-panel-head">
              <div>
                <span class="nav-panel-label">组合总权益</span>
                <strong class="nav-panel-value mono">{{ summary.totalEquity !== null ? '¥' + fmtNumber(summary.totalEquity, 2) : '—' }}</strong>
              </div>
              <span class="nav-panel-meta">{{ summary.equityAsOf ? '更新于 ' + fmtDateTime(summary.equityAsOf) : '暂无权益上报' }}</span>
            </div>
            <NavChart :data="equityCurve" :height="260" />
          </div>
        </SectionCard>

        <SectionCard title="策略状态" subtitle="心跳 / 权益 / 最后消息">
          <template #extra>
            <router-link to="/strategies" class="link-more">全部策略 <ChevronRight :size="13" /></router-link>
          </template>
          <div v-if="data.runners.length" class="status-list">
            <router-link v-for="runner in data.runners" :key="runner.id" :to="'/strategies/' + runner.id" class="status-row">
              <div class="status-row-top">
                <span class="status-name"><StatusDot :status="runner.status" :size="7" /><span class="truncate">{{ runner.name }}</span></span>
                <StatusTag :status="runner.status" compact />
              </div>
              <div class="status-row-mid">
                <HeartbeatGrid :status="runner.status" :last-seen="runner.last_seen" />
                <span class="status-proc mono">{{ runner.online_processes }}/{{ runner.process_count }} 进程</span>
                <span class="status-equity mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</span>
              </div>
              <p class="status-msg truncate">{{ runner.last_msg || runner.description || '暂无消息' }}</p>
            </router-link>
          </div>
          <EmptyState v-else compact title="还没有策略组" description="前往「策略」页创建策略并生成接入令牌。" />
        </SectionCard>
      </div>

      <div class="grid grid-2">
        <SectionCard title="最近动态" subtitle="消息 / 信号合并 · SSE 实时追加">
          <template #extra>
            <span class="live-hint" :class="{ live: realtime.live }">
              <StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" />
              {{ realtime.live ? '实时' : '轮询兜底' }}
            </span>
          </template>
          <EventTimeline :events="recentEvents" show-runner clickable empty-title="暂无动态" empty-desc="策略上报消息或信号后会出现在这里。" @select="openEvent" />
        </SectionCard>

        <SectionCard title="最近告警" subtitle="P0 · 心跳丢失 / 策略卡死">
          <template #extra>
            <router-link to="/alerts" class="link-more">告警中心 <ChevronRight :size="13" /></router-link>
          </template>
          <div v-if="recentAlerts.length" class="alert-feed">
            <router-link v-for="alert in recentAlerts" :key="alert.id" to="/alerts" class="alert-item">
              <span class="rule-chip">{{ ruleLabel(alert.rule) }}</span>
              <div class="alert-body">
                <p class="alert-summary">{{ alert.summary }}</p>
                <p class="alert-meta mono">{{ alert.runner_name }} · {{ fromNow(alert.starts_at) }}</p>
              </div>
              <span class="alert-status" :class="alert.status">{{ alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复' }}</span>
            </router-link>
          </div>
          <EmptyState v-else compact title="暂无告警" description="所有策略组心跳与运行状态正常。" />
        </SectionCard>
      </div>
    </template>
  </div>
</template>

<style scoped>
.overview-main {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 1fr);
  gap: var(--gap);
  align-items: start;
}
.status-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.status-row {
  display: block;
  padding: 11px 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: rgba(21, 28, 44, 0.45);
  color: inherit;
  transition: border-color 150ms ease, background-color 150ms ease;
}
.status-row:hover {
  border-color: var(--border-strong);
  background: rgba(91, 140, 255, 0.06);
}
.status-row-top,
.status-row-mid {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-row-top {
  justify-content: space-between;
}
.status-name {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
}
.status-row-mid {
  margin-top: 9px;
}
.status-proc {
  font-size: 10px;
  color: var(--text-3);
}
.status-equity {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-2);
}
.status-msg {
  margin-top: 7px;
  font-size: 11px;
  color: var(--text-3);
}
@media (max-width: 1100px) {
  .overview-main { grid-template-columns: minmax(0, 1fr); }
}

.metric-tabs {
  display: inline-flex;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
}
.metric-tabs button {
  height: 22px;
  padding: 0 10px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-3);
  font-size: 11px;
  cursor: pointer;
}
.metric-tabs button.active {
  background: var(--primary-soft);
  color: var(--text);
}
.nav-panel-side {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ov-kpi-value.up { color: var(--up); }
.ov-kpi-value.down { color: var(--down); }
.ov-kpi-value.equity { font-size: 22px; letter-spacing: -0.02em; }

.nav-group-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}
.nav-group-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 25px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-2);
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
}
.nav-group-tabs button.active {
  border-color: var(--primary);
  background: var(--primary-soft);
  color: var(--text);
}
.nav-panel {
  padding: 12px 14px 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.07), rgba(21, 28, 44, 0.25));
  transition: opacity 160ms ease;
}
.nav-panel.dimmed {
  opacity: 0.6;
}
.nav-panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}
.nav-panel-label {
  display: block;
  font-size: 10px;
  color: var(--text-3);
}
.nav-panel-value {
  display: block;
  margin-top: 1px;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--text);
}
.nav-panel-meta {
  font-size: 10px;
  color: var(--text-3);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--gap);
}
.ov-kpi {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface);
  color: inherit;
}
.ov-kpi--link {
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease;
}
.ov-kpi--link:hover {
  background: var(--surface-2);
  border-color: var(--border-strong);
}
.ov-kpi--danger {
  border-color: rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.055);
}
.ov-kpi--warn {
  border-color: rgba(245, 165, 36, 0.28);
}
.ov-kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ov-kpi-label {
  font-size: 12px;
  color: var(--text-2);
}
.ov-kpi-icon {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex: none;
  border-radius: 8px;
  color: #a9c2ff;
  border: 1px solid rgba(91, 140, 255, 0.22);
  background: rgba(91, 140, 255, 0.1);
}
.ov-kpi-icon.warn {
  color: #f5b64b;
  border-color: rgba(245, 165, 36, 0.32);
  background: rgba(245, 165, 36, 0.1);
}
.ov-kpi-icon.danger {
  color: #ff8f86;
  border-color: rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.12);
}
.ov-kpi-value {
  margin-top: 4px;
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.2;
}
.ov-kpi-value.warn {
  color: #f5b64b;
}
.ov-kpi-value.danger {
  color: #ff8f86;
}
.ov-kpi-unit {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 400;
  color: var(--text-2);
}
.ov-kpi-dim {
  color: var(--text-2);
  font-size: 18px;
}
.ov-kpi-foot {
  font-size: 11px;
  color: var(--text-3);
}
.link-more {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: var(--text-2);
  white-space: nowrap;
}
.link-more:hover {
  color: var(--primary);
}
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
.alert-feed {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 8px;
  color: inherit;
  border-bottom: 1px solid rgba(30, 38, 55, 0.6);
  transition: background-color 150ms ease;
}
.alert-item:last-of-type {
  border-bottom: none;
}
.alert-item:hover {
  background: rgba(21, 28, 44, 0.7);
}
.rule-chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.1);
  color: #ff8f86;
  font-size: 10px;
  white-space: nowrap;
}
.alert-body {
  min-width: 0;
  flex: 1;
}
.alert-summary {
  font-size: 12px;
  color: var(--text);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.alert-meta {
  margin-top: 3px;
  font-size: 10px;
  color: var(--text-3);
}
.alert-status {
  flex: none;
  font-size: 10px;
  white-space: nowrap;
}
.alert-status.firing {
  color: #ff8f86;
}
.alert-status.acknowledged {
  color: #f5b64b;
}
.alert-status.resolved {
  color: var(--text-3);
}
@media (max-width: 1279px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 639px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .ov-kpi {
    padding: 12px;
  }
  .ov-kpi-value {
    font-size: 22px;
  }
}
</style>