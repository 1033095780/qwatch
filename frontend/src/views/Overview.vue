<script setup lang="ts">
// Overview.vue — 总览：KPI 四卡、组合净值/回撤、组合指标、策略状态、最新信号、告警动态。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, useMessage } from 'naive-ui';
import { Activity, ArrowRight, Bell, ChevronDown, ChevronRight, ChevronUp, Wallet } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Overview, RangeKey, RunnerDetail } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDateTime, fmtMoney, fmtPct, fromNow, pnlClass } from '@/utils/format';
import { MARKET_LABELS, SIGNAL_ACTION_LABELS } from '@/utils/catalog';
import DrawdownChart from '@/components/DrawdownChart.vue';
import EquityChart from '@/components/EquityChart.vue';
import EmptyState from '@/components/EmptyState.vue';
import HeartbeatMini from '@/components/HeartbeatMini.vue';
import PageHeader from '@/components/PageHeader.vue';
import PnlText from '@/components/PnlText.vue';
import RangeTabs from '@/components/RangeTabs.vue';
import SectionCard from '@/components/SectionCard.vue';
import SeverityTag from '@/components/SeverityTag.vue';
import SideTag from '@/components/SideTag.vue';
import StatusDot from '@/components/StatusDot.vue';

const settings = useSettingsStore();
const message = useMessage();

const data = ref<Overview | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref('');
const range = ref<RangeKey>('all');
const scope = ref<string>('portfolio');
const metricsOpen = ref(true);
const runnerDetail = ref<RunnerDetail | null>(null);
const scopeLoading = ref(false);

const isPortfolio = computed(() => scope.value === 'portfolio');
const activeRunner = computed(() => (isPortfolio.value ? null : data.value?.runners.find((r) => r.id === scope.value) ?? null));
const chartPoints = computed(() => (isPortfolio.value ? data.value?.equity_curve ?? [] : runnerDetail.value?.equity ?? []));
const lastNav = computed(() => {
  const points = runnerDetail.value?.equity ?? [];
  return points.length ? Number(points[points.length - 1].nav ?? 0).toFixed(4) : null;
});

const activeAlertCount = computed(() => data.value?.active_alerts ?? 0);

const periodReturn = computed(() => {
  const curve = chartPoints.value;
  if (curve.length < 2) return null;
  const first = Number(curve[0].value);
  const last = Number(curve[curve.length - 1].value);
  return first > 0 ? ((last - first) / first) * 100 : null;
});

/** 最大回撤统一带负号展示：后端返回绝对值百分比 */
function fmtDrawdownPct(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return (n > 0 ? '-' : '') + fmtPct(n, 2, false);
}

const currentMetrics = computed(() => (isPortfolio.value ? data.value?.metrics ?? null : runnerDetail.value?.metrics ?? null));
const drawdownPoints = computed(() =>
  isPortfolio.value ? data.value?.drawdown_curve ?? [] : runnerDetail.value?.drawdown ?? [],
);
const metricsSubtitle = computed(() =>
  isPortfolio.value ? '全部策略合并 · 当前净值区间口径' : (activeRunner.value?.name || '策略') + ' · 策略口径',
);
const metricItems = computed(() => {
  const metrics = currentMetrics.value;
  if (!metrics) return [];
  return [
    { label: '年化收益', value: fmtPct(metrics.annualized_return_pct), tone: pnlClass(metrics.annualized_return_pct) },
    { label: '最大回撤', value: fmtDrawdownPct(metrics.max_drawdown_pct), tone: 'is-flat' },
    { label: '夏普', value: metrics.sharpe || '—', tone: 'is-flat' },
    { label: '卡玛', value: metrics.calmar || '—', tone: 'is-flat' },
    { label: '波动率', value: fmtPct(metrics.volatility, 2, false), tone: 'is-flat' },
    { label: '盈亏比', value: metrics.profit_factor || '—', tone: 'is-flat' },
  ];
});

async function loadRunner(): Promise<void> {
  if (isPortfolio.value) return;
  scopeLoading.value = true;
  try {
    runnerDetail.value = await api.runner(scope.value, range.value);
  } catch {
    runnerDetail.value = null;
  } finally {
    scopeLoading.value = false;
  }
}

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  else refreshing.value = true;
  error.value = '';
  try {
    data.value = await api.overview(range.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '总览加载失败';
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

function retry(): void {
  load(true);
}

function viewAllAlerts(): void {
  message.info('告警中心已列出全部告警');
}

watch(range, () => (isPortfolio.value ? load() : loadRunner()));
watch(scope, (value) => {
  if (value !== 'portfolio') loadRunner();
});
watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <PageHeader title="总览" :subtitle="'组合实时状态 · 数据时间 ' + (data ? fmtDateTime(data.as_of) : '—') + ' CST'">
      <template #extra>
        <span class="chip mono">Asia/Shanghai</span>
      </template>
    </PageHeader>

    <div v-if="loading && !data" class="page">
      <div class="grid grid-kpi">
        <div v-for="i in 4" :key="i" class="skel skel-card" style="min-height: 128px" />
      </div>

      <div class="grid grid-main">
        <div class="skel" style="height: 380px; border-radius: 12px" />
        <div class="skel" style="height: 380px; border-radius: 12px" />
      </div>
      <div class="grid grid-3">
        <div v-for="i in 3" :key="i" class="skel skel-card" />
      </div>
    </div>

    <div v-else-if="error && !data" class="card">
      <EmptyState title="总览数据加载失败" :description="error">
        <template #action><n-button size="small" @click="retry">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else-if="data">
      <div v-if="error" class="error-bar">
        <span class="dot" />{{ error }}
        <n-button text size="tiny" @click="retry">重试</n-button>
      </div>

      <section class="card overview-board">
        <div class="board-head">
          <div class="board-title-wrap">
            <h2 class="board-title">组合概览</h2>
            <p class="board-sub">{{ metricsSubtitle }}</p>
          </div>
          <button type="button" class="board-toggle" @click="metricsOpen = !metricsOpen">
            <span>{{ metricsOpen ? '收起指标' : '展开指标' }}</span>
            <ChevronUp v-if="metricsOpen" :size="14" />
            <ChevronDown v-else :size="14" />
          </button>
        </div>

        <div class="board-kpis">
          <div class="board-kpi">
            <div class="board-kpi-top">
              <span class="kpi-label">总权益</span>
              <span class="kpi-icon"><Wallet :size="15" /></span>
            </div>
            <div class="kpi-value">¥{{ fmtMoney(data.total_equity) }}</div>
            <div class="board-kpi-foot">
              <PnlText :value="data.today_pnl" :pct="data.today_pnl_pct" show-pct size="sm" />
              <span class="board-kpi-sub">较昨日收盘</span>
            </div>
          </div>

          <div class="board-kpi">
            <div class="board-kpi-top">
              <span class="kpi-label">今日盈亏</span>
              <span class="kpi-icon"><Activity :size="15" /></span>
            </div>
            <div class="kpi-value">¥{{ fmtMoney(data.today_pnl) }}</div>
            <div class="board-kpi-foot">
              <PnlText :value="data.today_pnl" :pct="data.today_pnl_pct" show-pct size="sm" />
              <span class="board-kpi-sub">今日收益率</span>
            </div>
          </div>

          <router-link to="/strategies" class="board-kpi board-kpi--link">
            <div class="board-kpi-top">
              <span class="kpi-label">策略运行</span>
              <span class="kpi-icon"><Activity :size="15" /></span>
            </div>
            <div class="kpi-value">{{ data.running }} <span class="kpi-dim">/ {{ data.total }}</span></div>
            <div class="board-kpi-foot"><span class="board-kpi-sub">运行中 / 全部策略</span></div>
          </router-link>

          <router-link
            to="/alerts"
            class="board-kpi board-kpi--link"
            :class="{ 'board-kpi--danger': activeAlertCount > 0 }"
          >
            <div class="board-kpi-top">
              <span class="kpi-label">活跃告警</span>
              <span class="kpi-icon" :class="{ danger: activeAlertCount > 0 }"><Bell :size="15" /></span>
            </div>
            <div class="kpi-value" :class="{ danger: activeAlertCount > 0 }">{{ data.active_alerts }} <span class="kpi-unit">条</span></div>
            <div class="board-kpi-foot">
              <span class="board-kpi-sub">{{ activeAlertCount > 0 ? '心跳丢失 / 策略卡死 · 点击处理' : '全部正常' }}</span>
            </div>
          </router-link>
        </div>

        <div v-show="metricsOpen" class="board-risks">
          <div v-for="item in metricItems" :key="item.label" class="risk-cell">
            <span class="risk-label">{{ item.label }}</span>
            <span class="risk-value mono" :class="item.tone">{{ item.value }}</span>
          </div>
          <template v-if="!metricItems.length">
            <div v-for="i in 6" :key="i" class="risk-cell">
              <span class="skel skel-line" style="width: 42px; height: 10px" />
              <span class="skel skel-line" style="width: 64px; height: 18px; margin-top: 6px" />
            </div>
          </template>
        </div>
      </section>

      <div class="grid grid-main">
        <SectionCard
          :title="isPortfolio ? '组合净值' : activeRunner?.name || '策略净值'"
          :subtitle="isPortfolio ? '全部策略合并 · 策略归因口径' : (activeRunner?.description || MARKET_LABELS[activeRunner?.market || 'CN_A']) + ' · 策略归因口径'"
        >
          <template #extra>
            <RangeTabs v-model="range" />
          </template>

          <div class="scope-switch">
            <button type="button" class="scope-item" :class="{ active: isPortfolio }" @click="scope = 'portfolio'">组合</button>
            <button
              v-for="runner in data.runners"
              :key="runner.id"
              type="button"
              class="scope-item"
              :class="{ active: scope === runner.id }"
              @click="scope = runner.id"
            >
              <StatusDot :status="runner.status" :size="6" />
              {{ runner.name }}
            </button>
          </div>

          <div class="chart-wrap" :class="{ refreshing: refreshing || scopeLoading }">
            <EquityChart
              :data="chartPoints"
              :height="300"
              :value-label="isPortfolio ? '组合权益' : '策略权益'"
            />
            <div class="chart-foot">
              <span class="legend-item"><i class="legend-line eq" />{{ isPortfolio ? '组合' : activeRunner?.name }}</span>
              <span v-if="periodReturn !== null">
                区间收益 <PnlText :value="periodReturn" :pct="null" :money="false" :digits="2" size="sm" />
              </span>
              <span v-if="isPortfolio" class="muted">最新权益 <span class="num">¥{{ fmtMoney(data.total_equity) }}</span></span>
              <span v-else-if="lastNav" class="muted">最新净值 <span class="num mono">{{ lastNav }}</span></span>
              <span class="spacer" />
              <span class="muted mono">{{ range.toUpperCase() }} · {{ chartPoints.length }} 点</span>
            </div>
            <div class="dd-head">
              <span class="eyebrow">回撤</span>
              <span class="muted">{{ isPortfolio ? '组合峰值回落' : '策略峰值回落' }}</span>
              <span class="spacer" />
              <span class="muted mono">{{ drawdownPoints.length }} 点</span>
            </div>
            <DrawdownChart :data="drawdownPoints" :height="132" />
          </div>
        </SectionCard>

        <SectionCard title="策略状态" subtitle="按状态与今日盈亏排序">
          <template #extra>
            <router-link to="/strategies" class="link-more">全部策略 <ChevronRight :size="13" /></router-link>
          </template>
          <div class="status-list">
            <router-link
              v-for="runner in data.runners"
              :key="runner.id"
              :to="'/strategies/' + runner.id"
              class="status-row"
            >
              <StatusDot :status="runner.status" :size="7" :pulse="runner.status === 'running'" />
              <div class="status-main">
                <span class="status-name truncate">{{ runner.name }}</span>
                <span class="status-meta">{{ runner.description || MARKET_LABELS[runner.market] || runner.market }}</span>
                <HeartbeatMini :bars="runner.heartbeat_bars" />
              </div>
              <div class="status-right">
                <PnlText :value="runner.today_pnl" :pct="runner.today_pnl_pct" show-pct size="sm" />
                <span class="status-hb mono">{{ fromNow(runner.last_heartbeat) }}</span>
              </div>
            </router-link>
          </div>
        </SectionCard>
      </div>


      <div class="grid grid-main">
        <SectionCard title="最新信号" subtitle="最近 8 条">
          <template #extra>
            <router-link to="/signals" class="link-more">全部信号 <ChevronRight :size="13" /></router-link>
          </template>
          <div v-if="data.recent_signals.length" class="tbl-wrap">
            <table class="tbl tbl--compact">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>策略</th>
                  <th>品种</th>
                  <th>方向</th>
                  <th>动作</th>
                  <th class="th-num">数量</th>
                  <th class="th-num">参考价</th>
                  <th class="th-num">金额</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="signal in data.recent_signals" :key="signal.id">
                  <td class="mono nowrap">{{ fmtDateTime(signal.ts) }}</td>
                  <td class="truncate">{{ signal.runner_name }}</td>
                  <td>
                    <span class="mono">{{ signal.instrument }}</span>
                    <span class="inst-name">{{ signal.instrument_name }}</span>
                  </td>
                  <td><SideTag :side="signal.side" /></td>
                  <td class="muted">{{ SIGNAL_ACTION_LABELS[signal.action] }}</td>
                  <td class="td-num">{{ signal.qty }}</td>
                  <td class="td-num">{{ signal.price }}</td>
                  <td class="td-num">{{ fmtMoney(signal.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <EmptyState v-else compact title="暂无信号" description="策略上报交易信号后会出现在这里" />
        </SectionCard>

        <SectionCard title="告警动态" subtitle="活跃告警优先">
          <template #extra>
            <router-link to="/alerts" class="link-more">告警中心 <ChevronRight :size="13" /></router-link>
          </template>
          <div v-if="data.alerts.length" class="alert-feed">
            <button
              v-for="alert in data.alerts"
              :key="alert.id"
              type="button"
              class="alert-item"
              @click="$router.push('/alerts')"
            >
              <SeverityTag :severity="alert.severity" size="sm" />
              <div class="alert-body">
                <p class="alert-summary">{{ alert.summary }}</p>
                <p class="alert-meta">
                  <span class="mono">{{ alert.runner_name }}</span>
                  <span class="dot-sep">·</span>
                  <span class="mono">{{ fromNow(alert.starts_at) }}</span>
                </p>
              </div>
            </button>
          </div>
          <EmptyState v-else compact title="没有活跃告警" description="所有策略心跳正常" />
          <router-link to="/alerts" class="alert-all">
            查看全部告警 <ArrowRight :size="13" />
          </router-link>
        </SectionCard>
      </div>
    </template>
  </div>
</template>

<style scoped>
.scope-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -2px 0 10px;
  padding-bottom: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}
.scope-switch::-webkit-scrollbar {
  display: none;
}
.scope-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
  height: 26px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text-2);
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 150ms ease;
}
.scope-item:hover {
  border-color: var(--border-strong);
  color: var(--text);
}
.scope-item.active {
  border-color: var(--primary);
  background: var(--primary-soft);
  color: var(--text);
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
.chart-wrap {
  transition: opacity 160ms ease;
}
.chart-wrap.refreshing {
  opacity: 0.55;
}
.chart-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-2);
}
.chart-foot .spacer {
  flex: 1;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-3);
}
.legend-line {
  display: inline-block;
  width: 14px;
  height: 2px;
  border-radius: 1px;
}
.legend-line.eq {
  background: var(--primary);
}
.dd-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 11px;
}
.dd-head .spacer {
  flex: 1;
}
.overview-board {
  padding: 18px 20px 16px;
}
.board-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.board-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}
.board-sub {
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-2);
}
.board-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
  transition: all 150ms ease;
}
.board-toggle:hover {
  border-color: var(--border-strong);
  color: var(--text);
}
.board-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.board-kpi {
  position: relative;
  min-width: 0;
  padding: 0 20px;
  border-left: 1px solid var(--border);
  color: inherit;
}
.board-kpi:first-child {
  padding-left: 0;
  border-left: none;
}
.board-kpi--link {
  border-radius: 8px;
  transition: background-color 150ms ease;
}
.board-kpi--link:hover {
  background: rgba(21, 28, 44, 0.55);
}
.board-kpi--danger {
  background: rgba(240, 68, 56, 0.055);
}
.board-kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.kpi-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex: none;
  border-radius: 8px;
  color: #a9c2ff;
  border: 1px solid rgba(91, 140, 255, 0.22);
  background: rgba(91, 140, 255, 0.1);
}
.kpi-icon.danger {
  color: #ff8f86;
  border-color: rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.12);
}
.board-kpi .kpi-value {
  margin-top: 6px;
}
.kpi-value.danger {
  color: #ff8f86;
}
.kpi-dim {
  color: var(--text-2);
  font-size: 22px;
}
.kpi-unit {
  color: var(--text-2);
  font-family: var(--font-sans);
  font-size: 18px;
}
.board-kpi-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 18px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.board-kpi-sub {
  font-size: 11px;
  color: var(--text-2);
}
.board-risks {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}
.risk-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 2px 16px;
  border-left: 1px solid var(--border);
}
.risk-cell:first-child {
  padding-left: 0;
  border-left: none;
}
.risk-label {
  font-size: 11px;
  color: var(--text-2);
}
.risk-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
}
.risk-value.is-up {
  color: var(--up);
}
.risk-value.is-down {
  color: var(--down);
}
.status-list {
  display: flex;
  flex-direction: column;
  margin: -4px 0;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 6px;
  border-bottom: 1px solid rgba(30, 38, 55, 0.65);
  color: var(--text);
  border-radius: 6px;
  transition: background-color 150ms ease;
}
.status-row:last-child {
  border-bottom: none;
}
.status-row:hover {
  background: rgba(21, 28, 44, 0.7);
  color: var(--text);
}
.status-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.status-name {
  font-size: 13px;
}
.status-meta {
  font-size: 10px;
  color: var(--text-3);
}
.status-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}
.status-hb {
  font-size: 10px;
  color: var(--text-3);
}
.inst-name {
  display: block;
  font-size: 10px;
  color: var(--text-3);
  line-height: 1.2;
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
  width: 100%;
  padding: 10px 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 150ms ease;
  border-bottom: 1px solid rgba(30, 38, 55, 0.6);
}
.alert-item:last-of-type {
  border-bottom: none;
}
.alert-item:hover {
  background: rgba(21, 28, 44, 0.7);
}
.alert-body {
  min-width: 0;
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
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  font-size: 10px;
  color: var(--text-3);
}
.dot-sep {
  opacity: 0.6;
}
.alert-all {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-2);
}
.alert-all:hover {
  color: var(--primary);
}
@media (max-width: 1279px) {
  .board-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .board-kpi {
    padding: 14px 0;
    border-left: none;
    border-top: 1px solid var(--border);
  }
  .board-kpi:nth-child(-n + 2) {
    padding-top: 0;
    border-top: none;
  }
  .board-kpi:nth-child(even) {
    padding-left: 16px;
    border-left: 1px solid var(--border);
  }
  .board-risks {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: 12px;
  }
  .risk-cell:nth-child(3n + 1) {
    padding-left: 0;
    border-left: none;
  }
}
@media (max-width: 639px) {
  .overview-board {
    padding: 16px;
  }
  .board-kpi {
    padding-left: 0;
    padding-right: 0;
  }
  .board-kpi:nth-child(even) {
    padding-left: 12px;
  }
  .board-risks {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .risk-cell:nth-child(3n + 1) {
    padding-left: 16px;
    border-left: 1px solid var(--border);
  }
  .risk-cell:nth-child(odd) {
    padding-left: 0;
    border-left: none;
  }
}
</style>