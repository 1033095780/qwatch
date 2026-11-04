<script setup lang="ts">
// Overview.vue — v0.3 总览：总权益/权益曲线 + 策略状态（可展开进程、异常可见）+ 实时动态/告警。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Bell, ChevronDown, ChevronRight, TrendingUp, Wallet, Waves } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Overview, Runner, RunnerDetail, RunnerEvent } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { fmtNumber, fromNow } from '@/utils/format';
import { ruleLabel } from '@/utils/catalog';
import ActivityFeed from '@/components/ActivityFeed.vue';
import EmptyState from '@/components/EmptyState.vue';
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
const error = ref('');
const selectedStrategy = ref('all');
const range = ref<'1D' | '1W' | '1M' | '3M' | 'ALL'>('1D');
const selectedDetail = ref<RunnerDetail | null>(null);
const selectedLoading = ref(false);
const expandedId = ref('');
const expandedDetail = ref<RunnerDetail | null>(null);
const expandedLoading = ref(false);
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const ranges = [
  { key: '1D', label: '1日', days: 1 },
  { key: '1W', label: '1周', days: 7 },
  { key: '1M', label: '1月', days: 30 },
  { key: '3M', label: '3月', days: 90 },
  { key: 'ALL', label: '全部', days: 0 },
] as const;

const summary = computed(() => {
  const ov = data.value;
  if (!ov) return null;
  return {
    total: ov.total ?? 0,
    running: ov.running ?? 0,
    activeAlerts: ov.active_alerts ?? 0,
    processesTotal: ov.processes_total ?? 0,
    processesOnline: ov.processes_online ?? 0,
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
const recentEvents = computed(() => {
  const live = realtime.events;
  const initial = data.value?.recent_events || [];
  const ids = new Set(live.map((event) => String(event.id)));
  return [...live, ...initial.filter((event) => !ids.has(String(event.id)))].slice(0, 6);
});
const recentAlerts = computed(() => (data.value?.recent_alerts || []).slice(0, 4));
const sourceCurve = computed(() => (selectedStrategy.value === 'all'
  ? data.value?.equity_curve || []
  : selectedDetail.value?.equity_curve || []));
const equityCurve = computed(() => {
  const curve = sourceCurve.value;
  if (!curve.length) return [];
  const cfg = ranges.find((item) => item.key === range.value);
  if (!cfg || cfg.days === 0) return curve;
  const latest = Date.parse(curve[curve.length - 1].ts);
  const cutoff = latest - cfg.days * 86400000;
  const filtered = curve.filter((point) => Date.parse(point.ts) >= cutoff);
  return filtered.length > 1 ? filtered : curve.slice(-2);
});
const strategyOptions = computed(() => [
  { id: 'all', name: '全部策略' },
  ...((data.value?.runners || []).map((runner) => ({ id: runner.id, name: runner.name }))),
]);

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false); }, 700);
}
async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    data.value = await api.overview();
    if (selectedStrategy.value !== 'all') {
      if (!data.value.runners.some((runner) => runner.id === selectedStrategy.value)) selectedStrategy.value = 'all';
      else await loadSelected(selectedStrategy.value);
    }
    if (expandedId.value) {
      if (!data.value.runners.some((runner) => runner.id === expandedId.value)) closeExpanded();
      else await loadExpanded(expandedId.value);
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '总览加载失败';
  } finally {
    loading.value = false;
  }
}
async function loadSelected(id: string): Promise<void> {
  if (id === 'all') { selectedDetail.value = null; return; }
  selectedLoading.value = true;
  try { selectedDetail.value = await api.runner(id); }
  catch { selectedDetail.value = null; }
  finally { selectedLoading.value = false; }
}
function selectStrategy(id: string): void {
  selectedStrategy.value = id;
  void loadSelected(id);
}
async function loadExpanded(id: string): Promise<void> {
  expandedLoading.value = true;
  try { expandedDetail.value = await api.runner(id); }
  catch { expandedDetail.value = null; }
  finally { expandedLoading.value = false; }
}
async function toggleRunner(runner: Runner): Promise<void> {
  if (runner.process_count <= 1) { void router.push('/strategies/' + runner.id); return; }
  if (expandedId.value === runner.id) { closeExpanded(); return; }
  expandedId.value = runner.id;
  expandedDetail.value = null;
  await loadExpanded(runner.id);
}
function closeExpanded(): void {
  expandedId.value = '';
  expandedDetail.value = null;
}
function openEvent(event: RunnerEvent): void {
  if (event.runner_id) void router.push('/strategies/' + event.runner_id + '?tab=events');
}
function issueCount(runner: Runner): number {
  return Math.max(0, (runner.process_count || 0) - (runner.online_processes || 0));
}
watch(() => settings.refreshSeq, () => { void load(false); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastEventAt], scheduleReload);
onMounted(() => {
  void load(true);
  pollTimer = window.setInterval(() => { if (!document.hidden) void load(false); }, 20000);
});
onBeforeUnmount(() => {
  window.clearInterval(pollTimer);
  window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="page">
    <PageHeader title="总览" />

    <div v-if="loading && !data" class="summary-grid">
      <div v-for="i in 4" :key="i" class="skel skel-card" style="height: 96px" />
    </div>
    <div v-else-if="error && !data" class="card"><EmptyState title="总览加载失败" :description="error" /></div>

    <template v-else-if="data && summary">
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div class="summary-grid">
        <div class="ov-kpi">
          <div class="ov-kpi-top"><span>总权益</span><Wallet :size="15" /></div>
          <div class="ov-kpi-value equity">{{ summary.totalEquity !== null ? '¥' + fmtNumber(summary.totalEquity, 2) : '—' }}</div>
          <div class="ov-kpi-foot">运行中 {{ summary.running }} / {{ summary.total }} 个策略组</div>
        </div>
        <div class="ov-kpi">
          <div class="ov-kpi-top"><span>今日权益变动</span><TrendingUp :size="15" /></div>
          <div class="ov-kpi-value" :class="equityChange === null ? '' : equityChange >= 0 ? 'up' : 'down'">
            {{ equityChange === null ? '—' : (equityChange >= 0 ? '+' : '') + fmtNumber(equityChange, 2) }}
          </div>
          <div class="ov-kpi-foot">较今日基线</div>
        </div>
        <div class="ov-kpi">
          <div class="ov-kpi-top"><span>进程在线</span><Waves :size="15" /></div>
          <div class="ov-kpi-value">{{ summary.processesOnline }}<span class="dim"> / {{ summary.processesTotal }}</span></div>
          <div class="ov-kpi-foot">全部策略组进程</div>
        </div>
        <router-link to="/alerts" class="ov-kpi link" :class="{ danger: summary.activeAlerts > 0 }">
          <div class="ov-kpi-top"><span>活跃告警</span><Bell :size="15" :class="{ danger: summary.activeAlerts > 0 }" /></div>
          <div class="ov-kpi-value" :class="{ danger: summary.activeAlerts > 0 }">{{ summary.activeAlerts }} <span class="unit">条</span></div>
          <div class="ov-kpi-foot">{{ summary.activeAlerts > 0 ? '需要处理' : '全部正常' }}</div>
        </router-link>
      </div>

      <div class="overview-main">
        <SectionCard title="权益曲线">
          <div class="chart-toolbar">
            <select :value="selectedStrategy" class="chart-select" aria-label="选择策略" @change="selectStrategy(($event.target as HTMLSelectElement).value)">
              <option v-for="option in strategyOptions" :key="option.id" :value="option.id">{{ option.name }}</option>
            </select>
            <div class="range-tabs">
              <button v-for="item in ranges" :key="item.key" type="button" :class="{ active: range === item.key }" @click="range = item.key">{{ item.label }}</button>
            </div>
          </div>
          <div class="chart-wrap" :class="{ dimmed: selectedLoading }"><NavChart :data="equityCurve" :height="292" /></div>
        </SectionCard>

        <SectionCard title="策略状态">
          <template #extra><router-link to="/strategies" class="link-more">全部策略 <ChevronRight :size="13" /></router-link></template>
          <div v-if="data.runners.length" class="status-list">
            <div v-for="runner in data.runners" :key="runner.id" class="status-block" :class="{ expanded: expandedId === runner.id }">
              <div class="status-row" role="button" tabindex="0" @click="toggleRunner(runner)" @keydown.enter="toggleRunner(runner)">
                <div class="status-row-top">
                  <span class="status-name"><StatusDot :status="runner.status" :size="7" /><span class="truncate">{{ runner.name }}</span><StatusTag :status="runner.status" compact /></span>
                  <span class="status-right">
                    <span v-if="issueCount(runner) && runner.status !== 'paused'" class="issue">{{ issueCount(runner) }} 个进程异常</span>
                    <span v-else-if="runner.process_count > 1" class="proc-count">{{ runner.process_count }} 个进程</span>
                    <ChevronDown v-if="runner.process_count > 1" :size="13" class="chevron" :class="{ open: expandedId === runner.id }" />
                  </span>
                </div>
                <div class="status-row-mid">
                  <HeartbeatGrid :status="runner.status" :last-seen="runner.last_seen" />
                  <span class="equity mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</span>
                  <span class="last-seen">{{ runner.last_seen ? fromNow(runner.last_seen) : '从未上报' }}</span>
                </div>
                <p class="status-msg truncate">{{ runner.last_msg || runner.description || '暂无消息' }}</p>
              </div>
              <div v-if="expandedId === runner.id" class="process-pop">
                <div v-if="expandedLoading" class="pop-loading">加载进程…</div>
                <template v-else-if="expandedDetail">
                  <div v-for="process in expandedDetail.processes" :key="process.name" class="process-line">
                    <span class="process-name mono">{{ process.name }}</span>
                    <StatusTag :status="process.retired ? 'retired' : process.status" compact />
                    <HeartbeatGrid :status="process.status" :retired="process.retired" :last-seen="process.last_seen" />
                    <span class="process-time">{{ process.last_seen ? fromNow(process.last_seen) : '从未上报' }}</span>
                  </div>
                  <router-link :to="'/strategies/' + runner.id" class="pop-detail">查看策略详情 <ChevronRight :size="12" /></router-link>
                </template>
              </div>
            </div>
          </div>
          <EmptyState v-else compact title="还没有策略组" description="前往「策略」页创建策略并生成接入令牌。" />
        </SectionCard>
      </div>

      <div class="grid grid-2">
        <SectionCard title="实时动态">
          <template #extra><span class="live-hint" :class="{ live: realtime.live }"><StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" />{{ realtime.live ? '实时' : '轮询' }}</span></template>
          <ActivityFeed :events="recentEvents" show-runner clickable empty-title="暂无动态" empty-desc="策略上报消息或信号后会出现在这里。" @select="openEvent" />
        </SectionCard>
        <SectionCard title="最近告警">
          <template #extra><router-link to="/alerts" class="link-more">告警中心 <ChevronRight :size="13" /></router-link></template>
          <div v-if="recentAlerts.length" class="alert-feed">
            <router-link v-for="alert in recentAlerts" :key="alert.id" to="/alerts" class="alert-item">
              <span class="rule-chip">{{ ruleLabel(alert.rule) }}</span>
              <div class="alert-body"><p class="alert-summary">{{ alert.summary }}</p><p class="alert-meta mono">{{ alert.runner_name }} · {{ fromNow(alert.starts_at) }}</p></div>
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
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--gap); }
.ov-kpi { display: flex; flex-direction: column; min-height: 104px; padding: 14px 16px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: linear-gradient(145deg, rgba(29, 38, 58, 0.7), rgba(17, 23, 36, 0.7)); color: inherit; }
.ov-kpi-top { display: flex; align-items: center; justify-content: space-between; color: var(--text-3); font-size: 11px; }
.ov-kpi-value { margin-top: 10px; font-family: var(--font-mono); font-size: 26px; font-weight: 600; letter-spacing: -0.04em; color: var(--text); white-space: nowrap; }
.ov-kpi-value.equity { font-size: 23px; }
.ov-kpi-value.up { color: var(--up); }
.ov-kpi-value.down { color: var(--down); }
.ov-kpi-value.danger, .danger { color: var(--danger); }
.ov-kpi-value .dim { color: var(--text-3); font-size: 16px; font-weight: 400; }
.ov-kpi-value .unit { color: var(--text-3); font-size: 13px; font-weight: 400; }
.ov-kpi-foot { margin-top: auto; padding-top: 6px; color: var(--text-3); font-size: 10px; }
.ov-kpi.link:hover { border-color: var(--border-strong); }
.overview-main { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(320px, 1fr); gap: var(--gap); align-items: start; }
.chart-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.chart-select { height: 27px; min-width: 132px; padding: 0 24px 0 9px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-2); font-size: 11px; outline: none; cursor: pointer; }
.range-tabs { display: inline-flex; padding: 2px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
.range-tabs button { height: 23px; padding: 0 8px; border: 0; border-radius: 4px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.range-tabs button.active { background: var(--primary-soft); color: var(--text); }
.chart-wrap { transition: opacity 160ms ease; }
.chart-wrap.dimmed { opacity: 0.55; }
.status-list { display: flex; flex-direction: column; gap: 8px; }
.status-block { border: 1px solid var(--border); border-radius: 9px; background: rgba(21, 28, 44, 0.45); overflow: hidden; }
.status-block.expanded { border-color: rgba(91, 140, 255, 0.34); }
.status-row { padding: 11px 12px; cursor: pointer; transition: background-color 150ms ease; }
.status-row:hover { background: rgba(91, 140, 255, 0.055); }
.status-row-top, .status-row-mid { display: flex; align-items: center; gap: 8px; }
.status-row-top { justify-content: space-between; }
.status-name { display: inline-flex; align-items: center; gap: 7px; min-width: 0; font-size: 13px; font-weight: 600; }
.status-right { display: inline-flex; align-items: center; gap: 7px; }
.issue { color: #f5b64b; font-size: 10px; }
.proc-count { color: var(--text-3); font-size: 10px; }
.chevron { color: var(--text-3); transition: transform 160ms ease; }
.chevron.open { transform: rotate(180deg); }
.status-row-mid { margin-top: 9px; }
.equity { margin-left: auto; font-size: 12px; color: var(--text-2); }
.last-seen { font-size: 10px; color: var(--text-3); }
.status-msg { margin-top: 6px; font-size: 10px; color: var(--text-3); }
.process-pop { padding: 0 12px 11px; border-top: 1px solid var(--border); }
.pop-loading { padding: 10px 0; color: var(--text-3); font-size: 10px; }
.process-line { display: flex; align-items: center; gap: 9px; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 11px; }
.process-line:last-of-type { border-bottom: 0; }
.process-name { width: 52px; color: var(--text); }
.process-time { margin-left: auto; color: var(--text-3); font-size: 10px; }
.pop-detail { display: inline-flex; align-items: center; gap: 2px; margin-top: 7px; color: var(--primary); font-size: 10px; }
.live-hint { display: inline-flex; align-items: center; gap: 5px; color: var(--text-3); font-size: 10px; }
.live-hint.live { color: var(--down); }
.alert-feed { display: flex; flex-direction: column; }
.alert-item { display: flex; align-items: flex-start; gap: 9px; padding: 9px 0; border-bottom: 1px solid var(--border); color: inherit; }
.alert-item:last-child { border-bottom: 0; }
.rule-chip { flex: 0 0 auto; padding: 2px 5px; border: 1px solid rgba(240, 68, 56, 0.25); border-radius: 4px; color: #f47c74; font-size: 9px; }
.alert-body { min-width: 0; flex: 1; }
.alert-summary { font-size: 11px; line-height: 1.5; color: var(--text-2); }
.alert-meta { margin-top: 2px; font-size: 9px; color: var(--text-3); }
.alert-status { font-size: 9px; color: var(--text-3); white-space: nowrap; }
.link-more { display: inline-flex; align-items: center; gap: 1px; color: var(--text-3); font-size: 10px; }
.link-more:hover { color: var(--text-2); }
@media (max-width: 1100px) { .overview-main { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ov-kpi { min-height: 92px; padding: 11px 12px; }
  .ov-kpi-value { font-size: 20px; }
  .ov-kpi-value.equity { font-size: 18px; }
  .chart-toolbar { align-items: flex-start; flex-direction: column; }
  .range-tabs { align-self: flex-end; }
  .last-seen { display: none; }
}
</style>
