// Overview.vue — v0.5 总览：总权益/今日变动/策略在线/活跃告警；主区左侧权益曲线、右侧策略大卡片（同策略页，内部滚动）；底部动态/告警。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { NButton } from 'naive-ui';
import { Activity, Bell, ChevronRight, TrendingUp, Wallet } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, CurvePoint, Overview, RunnerEvent } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { fmtNumber, fromNow } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import GroupCard from '@/components/GroupCard.vue';
import NavChart from '@/components/NavChart.vue';
import NavSparkline from '@/components/NavSparkline.vue';
import PageHeader from '@/components/PageHeader.vue';
import SectionCard from '@/components/SectionCard.vue';
import StatusDot from '@/components/StatusDot.vue';

const settings = useSettingsStore();
const realtime = useRealtimeStore();
const router = useRouter();

const data = ref<Overview | null>(null);
const loading = ref(true);
const error = ref('');
const selectedAccount = ref<string>('all');
const range = ref<'1D' | '1W' | '1M' | '3M' | 'ALL'>('1D');
const accountCurve = ref<CurvePoint[]>([]);
const curveLoading = ref(false);
const curveCache = new Map<string, CurvePoint[]>();
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const ranges = [
  { key: '1D', label: '1日', days: 1 },
  { key: '1W', label: '1周', days: 7 },
  { key: '1M', label: '1月', days: 30 },
  { key: '3M', label: '3月', days: 90 },
  { key: 'ALL', label: '全部', days: 0 },
] as const;

const accounts = computed<Account[]>(() => data.value?.accounts ?? []);
const accountOptions = computed(() => [
  { id: 'all', label: '全部账户' },
  ...accounts.value.map((account) => ({ id: account.id, label: account.broker && account.broker !== account.name ? account.broker + ' · ' + account.name : account.name })),
]);

const summary = computed(() => {
  const ov = data.value;
  if (!ov) return null;
  return {
    total: ov.total ?? 0,
    running: ov.running ?? 0,
    activeAlerts: ov.active_alerts ?? 0,
    accountCount: ov.account_count ?? accounts.value.length,
    totalEquity: ov.total_equity ?? null,
    todayEquityChange: ov.today_equity_change ?? null,
  };
});
const equityChange = computed(() => {
  const raw = summary.value?.todayEquityChange;
  if (raw === null || raw === undefined || raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
});
const sourceCurve = computed<CurvePoint[]>(() => (selectedAccount.value === 'all'
  ? data.value?.equity_curve ?? []
  : accountCurve.value));
const equityCurve = computed<CurvePoint[]>(() => {
  const curve = sourceCurve.value;
  if (!curve.length) return [];
  const cfg = ranges.find((item) => item.key === range.value);
  if (!cfg || cfg.days === 0) return curve;
  const latest = Date.parse(curve[curve.length - 1].ts);
  const cutoff = latest - cfg.days * 86400000;
  const filtered = curve.filter((point) => Date.parse(point.ts) >= cutoff);
  return filtered.length > 1 ? filtered : curve.slice(-2);
});
const recentEvents = computed<RunnerEvent[]>(() => {
  const live = realtime.events;
  const initial = data.value?.recent_events || [];
  const ids = new Set(live.map((event) => String(event.id)));
  return [...live, ...initial.filter((event) => !ids.has(String(event.id)))].slice(0, 20);
});
const recentAlerts = computed(() => (data.value?.recent_alerts || []).slice(0, 4));
const statusOrder: Record<string, number> = { offline: 0, degraded: 1, paused: 2, running: 3 };
const sortedRunners = computed(() => [...(data.value?.runners || [])].sort((a, b) => {
  const order = (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9);
  return order || a.name.localeCompare(b.name, 'zh-CN');
}));

async function loadAccountCurve(id: string): Promise<void> {
  if (!id || id === 'all') { accountCurve.value = []; return; }
  const cached = curveCache.get(id);
  if (cached) { accountCurve.value = cached; return; }
  curveLoading.value = true;
  try {
    const curve = await api.accountEquityCurve(id);
    curveCache.set(id, curve);
    accountCurve.value = curve;
  } catch {
    accountCurve.value = [];
  } finally {
    curveLoading.value = false;
  }
}

async function load(initial = false, silent = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    data.value = await api.overview();
    if (selectedAccount.value !== 'all' && !(data.value.accounts || []).some((account) => account.id === selectedAccount.value)) {
      selectedAccount.value = 'all';
    }
    if (selectedAccount.value !== 'all') {
      curveCache.delete(selectedAccount.value);
      await loadAccountCurve(selectedAccount.value);
    }
  } catch (err) {
    if (!silent) error.value = err instanceof Error ? err.message : '总览加载失败';
  } finally {
    loading.value = false;
  }
}

function selectAccount(id: string): void {
  selectedAccount.value = id;
  void loadAccountCurve(id);
}

function openEvent(event: RunnerEvent): void {
  if (event.runner_id) void router.push('/strategies/' + event.runner_id);
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

watch(() => settings.refreshSeq, () => { void load(false, true); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastEventAt, realtime.lastAccountChangeAt, realtime.lastEquityChangeAt], scheduleReload);

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
  <div class="page overview-page">
    <PageHeader title="总览" />

    <div v-if="loading && !data" class="skeleton-page">
      <div class="summary-grid">
        <div v-for="i in 4" :key="i" class="skel skel-card" style="height: 104px" />
      </div>
      <div class="overview-main">
        <div class="skel skel-card" style="height: 420px; border-radius: var(--radius-lg)" />
        <div class="skel skel-card" style="height: 420px; border-radius: var(--radius-lg)" />
      </div>
    </div>
    <div v-else-if="error && !data" class="card">
      <EmptyState title="总览加载失败" :description="error">
        <template #action><n-button size="small" @click="load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else-if="data && summary">
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div class="summary-grid">
        <div class="ov-kpi">
          <div class="ov-kpi-top"><span class="ov-kpi-label">总权益</span><Wallet :size="15" /></div>
          <div class="ov-kpi-value">{{ summary.totalEquity !== null ? '¥' + fmtNumber(summary.totalEquity, 0) : '—' }}</div>
          <div class="ov-kpi-foot">{{ summary.accountCount }} 个账户 · {{ summary.total }} 个策略</div>
        </div>
        <div class="ov-kpi">
          <div class="ov-kpi-top"><span class="ov-kpi-label">今日盈利额</span><TrendingUp :size="15" /></div>
          <div class="ov-kpi-value" :class="equityChange === null ? '' : equityChange >= 0 ? 'up' : 'down'">
            {{ equityChange === null ? '—' : (equityChange >= 0 ? '+' : '') + fmtNumber(equityChange, 0) }}
          </div>
          <div class="ov-kpi-foot">按今日基线计算</div>
        </div>
        <div class="ov-kpi">
          <div class="ov-kpi-top"><span class="ov-kpi-label">策略在线</span><Activity :size="15" /></div>
          <div class="ov-kpi-value">{{ summary.running }}</div>
          <div class="ov-kpi-foot">共 {{ summary.total }} 个策略</div>
        </div>
        <router-link to="/alerts" class="ov-kpi link" :class="{ danger: summary.activeAlerts > 0 }">
          <div class="ov-kpi-top"><span class="ov-kpi-label">活跃告警</span><Bell :size="15" :class="{ danger: summary.activeAlerts > 0 }" /></div>
          <div class="ov-kpi-value" :class="{ danger: summary.activeAlerts > 0 }">{{ summary.activeAlerts }}</div>
          <div class="ov-kpi-foot">{{ summary.activeAlerts > 0 ? '需要处理' : '全部正常' }}</div>
        </router-link>
      </div>

      <div class="overview-main">
        <SectionCard title="权益曲线">
          <template #extra>
            <div class="chart-tools">
              <select :value="selectedAccount" class="chart-select" aria-label="选择账户" @change="selectAccount(($event.target as HTMLSelectElement).value)">
                <option v-for="option in accountOptions" :key="option.id" :value="option.id">{{ option.label }}</option>
              </select>
              <div class="range-tabs">
                <button v-for="item in ranges" :key="item.key" type="button" :class="{ active: range === item.key }" @click="range = item.key">{{ item.label }}</button>
              </div>
            </div>
          </template>
          <div class="chart-wrap" :class="{ dimmed: curveLoading }">
            <NavChart :data="equityCurve" fill />
          </div>
        </SectionCard>

        <SectionCard title="策略状态">
          <template #extra><router-link to="/strategies" class="link-more">全部策略 <ChevronRight :size="13" /></router-link></template>
          <div v-if="sortedRunners.length" class="strategy-column">
            <GroupCard v-for="runner in sortedRunners" :key="runner.id" :runner="runner" />
          </div>
          <EmptyState v-else compact title="还没有策略" description="前往「策略」页新建策略并生成接入令牌。" />
        </SectionCard>
      </div>

      <div class="overview-lower">
        <SectionCard title="动态">
          <template #extra><span class="live-hint" :class="{ live: realtime.live }"><StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" />{{ realtime.live ? '实时' : '轮询' }}</span></template>
          <div class="ov-activity-scroll">
            <button v-for="event in recentEvents" :key="event.id" type="button" class="ov-event" @click="openEvent(event)">
              <span class="ov-event-type" :class="event.type">{{ event.type === 'signal' ? '信号' : '消息' }}</span>
              <strong>{{ event.runner_name || event.instrument }}</strong>
              <span class="ov-event-text">{{ event.type === 'signal' ? event.symbol + ' ' + event.action + ' ' + event.qty : event.text }}</span>
              <time>{{ fromNow(event.ts) }}</time>
            </button>
          </div>
        </SectionCard>
        <SectionCard title="最近告警">
          <template #extra><router-link to="/alerts" class="link-more">告警中心 <ChevronRight :size="13" /></router-link></template>
          <div v-if="recentAlerts.length" class="ov-alert-scroll">
            <router-link v-for="alert in recentAlerts" :key="alert.id" to="/alerts" class="ov-alert">
              <span class="ov-alert-dot" :class="alert.status" />
              <div><strong>{{ alert.runner_name }}</strong><span>{{ alert.summary }}</span></div>
              <em>{{ alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复' }}</em>
            </router-link>
          </div>
          <div v-else class="alert-empty"><span class="ok" /><div><strong>暂无告警</strong><span>所有策略心跳与运行状态正常。</span></div></div>
        </SectionCard>
      </div>
    </template>
  </div>
</template>

<style scoped>
.overview-page { height: 100%; min-height: 0; overflow: hidden; gap: 14px; }
.overview-page > .summary-grid { flex: none; height: 96px; }
.skeleton-page { display: flex; flex-direction: column; gap: var(--gap); }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--gap); }
.ov-kpi { display: flex; flex-direction: column; align-items: flex-start; min-height: 0; padding: 11px 14px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: linear-gradient(145deg, rgba(29, 38, 58, 0.7), rgba(17, 23, 36, 0.7)); color: inherit; }
.ov-kpi-top { width: 100%; display: flex; align-items: center; justify-content: space-between; color: #ffffff; font-size: 12px; font-weight: 600; }
.ov-kpi-label { color: #ffffff; font-weight: 600; }
.ov-kpi-value { width: 100%; margin-top: 8px; font-family: var(--font-mono); font-size: 25px; font-weight: 700; letter-spacing: -0.04em; color: #ffffff; text-align: left; white-space: nowrap; line-height: 1.15; }
.ov-kpi-value.up { color: var(--up); }
.ov-kpi-value.down { color: var(--down); }
.ov-kpi-value.danger, .danger { color: var(--danger); }
.ov-kpi-foot { margin-top: auto; padding-top: 5px; color: #cbd5e5; font-size: 9px; }
.ov-kpi.link:hover { border-color: var(--border-strong); }
.up { color: var(--up) !important; }
.down { color: var(--down) !important; }

.overview-main { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(400px, 1fr); gap: var(--gap); align-items: stretch; }
.overview-main > :deep(.section-card) { height: 100%; min-height: 0; }
.overview-main :deep(.panel-head) { flex: none; }
.chart-wrap { flex: 1; min-height: 0; display: flex; }
.chart-wrap :deep(.nav-chart) { height: 100% !important; }
.chart-wrap { transition: opacity 160ms ease; }
.chart-wrap.dimmed { opacity: 0.55; }

.chart-tools { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chart-select { height: 27px; min-width: 150px; max-width: 220px; padding: 0 24px 0 9px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-2); font-size: 11px; outline: none; cursor: pointer; }
.range-tabs { display: inline-flex; padding: 2px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
.range-tabs button { height: 23px; padding: 0 8px; border: 0; border-radius: 4px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.range-tabs button.active { background: var(--primary-soft); color: var(--text); }

.strategy-column { display: flex; flex: 1; flex-direction: column; gap: 10px; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding-right: 4px; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.strategy-column :deep(.group-card) { flex: 0 0 auto; }
.strategy-column::-webkit-scrollbar { width: 5px; }
.strategy-column::-webkit-scrollbar-thumb { background: #2b3a55; border-radius: 999px; }
.strategy-column::-webkit-scrollbar-track { background: transparent; }
.link-more { display: inline-flex; align-items: center; gap: 1px; color: var(--text-3); font-size: 10px; }
.link-more:hover { color: var(--text-2); }

.overview-lower { flex: none; height: clamp(150px, 18vh, 230px); display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(280px, 1fr); gap: var(--gap); min-height: 0; }
.overview-lower > :deep(.section-card) { height: 100%; min-height: 0; }
.ov-activity-scroll { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.ov-activity-scroll::-webkit-scrollbar { width: 5px; }
.ov-activity-scroll::-webkit-scrollbar-thumb { background: #2b3a55; border-radius: 999px; }
.ov-event { display: grid; grid-template-columns: 32px 90px minmax(0, 1fr) auto; align-items: center; gap: 7px; width: 100%; min-height: 24px; padding: 3px 0; border: 0; border-bottom: 1px solid rgba(125, 139, 161, 0.09); background: transparent; color: inherit; text-align: left; cursor: pointer; }
.ov-event:last-child { border-bottom: 0; }
.ov-event:hover { background: rgba(255, 255, 255, 0.018); }
.ov-event-type { padding: 1px 4px; border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 3px; color: #38bdf8; font-size: 7px; text-align: center; }
.ov-event-type.message { border-color: rgba(125, 139, 161, 0.2); color: var(--text-3); }
.ov-event strong { color: var(--text-2); font-size: 8px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ov-event-text { color: var(--text-3); font-size: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ov-event time { color: var(--text-3); font: 7px var(--font-mono); white-space: nowrap; }
.ov-alert-scroll { flex: 1; min-height: 0; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.ov-alert { display: grid; grid-template-columns: 5px minmax(0, 1fr) auto; gap: 7px; align-items: start; padding: 5px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.09); color: inherit; }
.ov-alert:last-child { border-bottom: 0; }
.ov-alert-dot { width: 5px; height: 5px; margin-top: 4px; border-radius: 50%; background: #f25c5c; }
.ov-alert-dot.resolved { background: var(--down); }
.ov-alert div { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.ov-alert strong { color: var(--text-2); font-size: 8px; font-weight: 500; }
.ov-alert span { color: var(--text-3); font-size: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ov-alert em { color: #f47c74; font: 7px var(--font-mono); font-style: normal; white-space: nowrap; }
.alert-empty { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; gap: 8px; text-align: left; }
.alert-empty .ok { width: 6px; height: 6px; flex: none; border-radius: 50%; background: var(--down); box-shadow: 0 0 8px rgba(46, 204, 143, 0.5); }
.alert-empty div { display: flex; flex-direction: column; gap: 2px; }
.alert-empty strong { color: var(--text-2); font-size: 10px; font-weight: 500; }
.alert-empty span { color: var(--text-3); font-size: 8px; }
.live-hint { display: inline-flex; align-items: center; gap: 5px; color: var(--text-3); font-size: 9px; }
.live-hint.live { color: var(--down); }

@media (max-height: 820px) {
  .overview-page { gap: 12px; }
  .overview-page > .summary-grid { height: 80px; }
  .ov-kpi { padding: 8px 12px; }
  .ov-kpi-value { margin-top: 5px; font-size: 22px; }
  .ov-kpi-foot { font-size: 8px; }
  .overview-lower { height: 90px; }
  .overview-lower :deep(.section-card) { padding: 10px 13px; }
  .overview-lower :deep(.panel-head) { margin-bottom: 4px; }
  .ov-event { min-height: 21px; padding: 2px 0; }
  .ov-alert { padding: 4px 0; }
  .alert-empty strong { font-size: 10px; }
}
@media (max-width: 1100px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .overview-page { height: auto; overflow: visible; }
  .overview-main { flex: none; min-height: 560px; grid-template-columns: minmax(0, 1fr); }
  .overview-main > :deep(.section-card) { height: auto; }
  .strategy-column { max-height: 560px; }
  .overview-lower { height: 180px; grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ov-kpi { min-height: 92px; padding: 11px 12px; }
  .ov-kpi-value { font-size: 22px; }
  .chart-tools { align-items: flex-start; flex-direction: column; width: 100%; }
  .chart-select { width: 100%; max-width: none; }
  .range-tabs { align-self: stretch; justify-content: space-between; }
  .overview-lower { height: auto; grid-template-columns: 1fr; }
  .overview-lower > :deep(.section-card) { min-height: 180px; }
}
</style>