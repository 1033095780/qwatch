<script setup lang="ts">
// Overview.vue — 总览：KPI 四卡、组合净值（区间/基准）、策略状态、策略卡片、最新成交、告警动态。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NSwitch, useMessage } from 'naive-ui';
import { Activity, ArrowRight, Bell, ChevronRight, Wallet } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Overview, RangeKey, RunnerDetail } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDateTime, fmtMoney, fmtPct, fmtSignedMoney, fromNow, pnlClass } from '@/utils/format';
import EquityChart from '@/components/EquityChart.vue';
import EmptyState from '@/components/EmptyState.vue';
import MetricCard from '@/components/MetricCard.vue';
import PageHeader from '@/components/PageHeader.vue';
import PnlText from '@/components/PnlText.vue';
import RangeTabs from '@/components/RangeTabs.vue';
import RunnerCard from '@/components/RunnerCard.vue';
import SectionCard from '@/components/SectionCard.vue';
import SeverityTag from '@/components/SeverityTag.vue';
import StatusDot from '@/components/StatusDot.vue';

const settings = useSettingsStore();
const message = useMessage();

const data = ref<Overview | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref('');
const range = ref<RangeKey>('all');
const showBenchmark = ref(true);
const scope = ref<string>('portfolio');
const runnerDetail = ref<RunnerDetail | null>(null);
const scopeLoading = ref(false);

const isPortfolio = computed(() => scope.value === 'portfolio');
const activeRunner = computed(() => (isPortfolio.value ? null : data.value?.runners.find((r) => r.id === scope.value) ?? null));
const chartPoints = computed(() => (isPortfolio.value ? data.value?.equity_curve ?? [] : runnerDetail.value?.equity ?? []));
const chartBenchmark = computed(() => (isPortfolio.value ? data.value?.benchmark ?? [] : []));
const lastNav = computed(() => {
  const points = runnerDetail.value?.equity ?? [];
  return points.length ? Number(points[points.length - 1].nav ?? 0).toFixed(4) : null;
});

const statusCounts = computed(() => {
  const runners = data.value?.runners ?? [];
  return {
    running: runners.filter((r) => r.status === 'running').length,
    degraded: runners.filter((r) => r.status === 'degraded').length,
    offline: runners.filter((r) => r.status === 'offline').length,
    offHours: runners.filter((r) => r.status === 'off_hours').length,
  };
});

const activeAlertLevels = computed(() => {
  const alerts = data.value?.alerts ?? [];
  return {
    p0: alerts.filter((a) => a.severity === 'P0').length,
    p1: alerts.filter((a) => a.severity === 'P1').length,
    p2: alerts.filter((a) => a.severity === 'P2').length,
  };
});

const periodReturn = computed(() => {
  const curve = chartPoints.value;
  if (curve.length < 2) return null;
  const first = Number(curve[0].value);
  const last = Number(curve[curve.length - 1].value);
  return first > 0 ? ((last - first) / first) * 100 : null;
});

const benchmarkReturn = computed(() => {
  const curve = data.value?.benchmark ?? [];
  if (curve.length < 2) return null;
  const first = Number(curve[0].value);
  const last = Number(curve[curve.length - 1].value);
  return first > 0 ? ((last - first) / first) * 100 : null;
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

      <div class="grid grid-kpi">
        <MetricCard
          label="总权益"
          :value="'¥' + fmtMoney(data.total_equity)"
          :change="data.today_pnl"
          :change-pct="data.today_pnl_pct"
          sub="较昨日收盘"
          :icon="Wallet"
        />
        <MetricCard
          label="今日盈亏"
          :value="'¥' + fmtMoney(data.today_pnl)"
          :change="data.today_pnl_pct"
          :change-pct="null"
          sub="今日收益率"
          :icon="Activity"
          accent="warning"
        />
        <MetricCard
          label="策略运行"
          :value="data.running + ' / ' + data.total"
          :sub="statusCounts.degraded + ' 降级 · ' + statusCounts.offline + ' 离线 · ' + statusCounts.offHours + ' 非交易'"
          :icon="Activity"
          accent="primary"
        />
        <MetricCard
          label="活跃告警"
          :value="data.active_alerts + ' 条'"
          :sub="'P0 ' + activeAlertLevels.p0 + ' · P1 ' + activeAlertLevels.p1 + ' · P2 ' + activeAlertLevels.p2"
          :icon="Bell"
          :accent="activeAlertLevels.p0 > 0 ? 'danger' : activeAlertLevels.p1 > 0 ? 'warning' : 'primary'"
        />
      </div>

      <div class="grid grid-main">
        <SectionCard
          :title="isPortfolio ? '组合净值' : activeRunner?.name || '策略净值'"
          :subtitle="isPortfolio ? '全部账户合并 · 单位净值法' : (activeRunner?.strategy || '') + ' · 策略归因口径'"
        >
          <template #extra>
            <RangeTabs v-model="range" />
            <label v-if="isPortfolio" class="bench-toggle">
              <n-switch v-model:value="showBenchmark" size="small" />
              <span>基准</span>
            </label>
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
              :benchmark="chartBenchmark"
              :show-benchmark="showBenchmark && isPortfolio"
              :height="300"
              :value-label="isPortfolio ? '组合权益' : '策略权益'"
            />
          </div>
          <div class="chart-foot">
            <span class="legend-item"><i class="legend-line eq" />{{ isPortfolio ? '组合' : activeRunner?.name }}</span>
            <span v-if="showBenchmark && isPortfolio" class="legend-item"><i class="legend-line bm" />基准</span>
            <span v-if="periodReturn !== null">
              区间收益 <PnlText :value="periodReturn" :pct="null" :money="false" :digits="2" size="sm" />
            </span>
            <span v-if="showBenchmark && isPortfolio && benchmarkReturn !== null" class="muted">
              基准 <span class="num" :class="pnlClass(benchmarkReturn)">{{ fmtPct(benchmarkReturn) }}</span>
            </span>
            <span v-if="isPortfolio" class="muted">最新权益 <span class="num">¥{{ fmtMoney(data.total_equity) }}</span></span>
            <span v-else-if="lastNav" class="muted">最新净值 <span class="num mono">{{ lastNav }}</span></span>
            <span class="spacer" />
            <span class="muted mono">{{ range.toUpperCase() }} · {{ chartPoints.length }} 点</span>
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
                <span class="status-meta mono">{{ runner.strategy }}</span>
              </div>
              <div class="status-right">
                <PnlText :value="runner.today_pnl" :pct="runner.today_pnl_pct" show-pct size="sm" />
                <span class="status-hb mono">{{ fromNow(runner.last_heartbeat) }}</span>
              </div>
            </router-link>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="策略卡片" :subtitle="data.total + ' 个运行实例 · 覆盖 A股 / 商品期货 / 金融期货'">
        <template #extra>
          <router-link to="/strategies" class="link-more">筛选与搜索 <ChevronRight :size="13" /></router-link>
        </template>
        <div class="grid grid-3">
          <RunnerCard v-for="runner in data.runners" :key="runner.id" :runner="runner" />
        </div>
      </SectionCard>

      <div class="grid grid-main">
        <SectionCard title="最新成交" subtitle="最近 8 笔">
          <template #extra>
            <router-link to="/trades" class="link-more">全部流水 <ChevronRight :size="13" /></router-link>
          </template>
          <div v-if="data.recent_fills.length" class="tbl-wrap">
            <table class="tbl tbl--compact">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>策略</th>
                  <th>品种</th>
                  <th>方向</th>
                  <th class="th-num">数量</th>
                  <th class="th-num">价格</th>
                  <th class="th-num">金额</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="fill in data.recent_fills" :key="fill.id">
                  <td class="mono nowrap">{{ fmtDateTime(fill.ts) }}</td>
                  <td class="truncate">{{ fill.runner_name }}</td>
                  <td>
                    <span class="mono">{{ fill.instrument }}</span>
                    <span class="inst-name">{{ fill.instrument_name }}</span>
                  </td>
                  <td>
                    <span class="side-tag" :class="fill.side">
                      {{ fill.side === 'buy' ? '买入' : '卖出' }}
                    </span>
                  </td>
                  <td class="td-num">{{ fill.qty }}</td>
                  <td class="td-num">{{ fill.price }}</td>
                  <td class="td-num">{{ fmtMoney(fill.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <EmptyState v-else compact title="暂无成交" description="策略产生成交后会出现在这里" />
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
          <EmptyState v-else compact title="没有活跃告警" description="所有策略心跳与回撤均在阈值内" />
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
.bench-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-2);
  cursor: pointer;
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
.legend-line.bm {
  background: #5f6d84;
  background-image: linear-gradient(90deg, #5f6d84 60%, transparent 60%);
  background-size: 4px 2px;
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
.side-tag {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
}
.side-tag.buy {
  color: var(--up);
  background: color-mix(in srgb, var(--up) 12%, transparent);
}
.side-tag.sell {
  color: var(--down);
  background: color-mix(in srgb, var(--down) 12%, transparent);
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
</style>
