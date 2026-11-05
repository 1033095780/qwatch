<script setup lang="ts">
// AccountDetail.vue — 点击策略页账户头进入：账户综合权益/净值 + 策略卡片。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { api } from '@/api/client';
import type { Account, CurvePoint, Runner } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { fmtNumber } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import GroupCard from '@/components/GroupCard.vue';
import NavChart from '@/components/NavChart.vue';
import PageHeader from '@/components/PageHeader.vue';
import StrategyGrid from '@/components/StrategyGrid.vue';

const route = useRoute();
const realtime = useRealtimeStore();
const settings = useSettingsStore();
const account = ref<Account | null>(null);
const strategies = ref<Runner[]>([]);
const curve = ref<CurvePoint[]>([]);
const rangeKey = ref('all');
const customStart = ref('');
const customEnd = ref('');
const rangeOptions = [
  { value: 'all', label: '全部历史' }, { value: '1m', label: '近 1 个月' }, { value: '3m', label: '近 3 个月' },
  { value: '6m', label: '近 6 个月' }, { value: '1y', label: '近 1 年' }, { value: '3y', label: '近 3 年' },
  { value: '5y', label: '近 5 年' }, { value: 'custom', label: '自定义' },
];
const loading = ref(true);
const error = ref('');
let timer: number | undefined;
let reloadTimer: number | undefined;

const todayPnl = computed(() => {
  const n = Number(account.value?.today_pnl);
  return account.value?.today_pnl !== null && account.value?.today_pnl !== undefined && Number.isFinite(n) ? n : null;
});
const chartData = computed(() => {
  const daily = curve.value;
  if (!daily.length || rangeKey.value === 'all') return daily;
  if (rangeKey.value === 'custom') {
    const start = customStart.value ? Date.parse(customStart.value) : -Infinity;
    const end = customEnd.value ? Date.parse(customEnd.value) + 86399000 : Infinity;
    return daily.filter((point) => { const ts = Date.parse(point.ts); return ts >= start && ts <= end; });
  }
  const latest = Date.parse(daily[daily.length - 1].ts);
  const months = ({ '1m': 1, '3m': 3, '6m': 6, '1y': 12, '3y': 36, '5y': 60 } as Record<string, number>)[rangeKey.value] || 0;
  const cutoff = new Date(latest);
  cutoff.setMonth(cutoff.getMonth() - months);
  return daily.filter((point) => Date.parse(point.ts) >= cutoff.getTime());
});
async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [detail, points] = await Promise.all([
      api.account(String(route.params.id)),
      api.equityCurve('account', String(route.params.id)),
    ]);
    account.value = detail.account;
    strategies.value = detail.strategies;
    curve.value = points.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '账户加载失败';
  } finally {
    loading.value = false;
  }
}
function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false); }, 700);
}
watch(() => settings.refreshSeq, () => { void load(false); });
watch(() => [realtime.lastAccountChangeAt, realtime.lastProcessChangeAt], scheduleReload);
onMounted(() => {
  void load(true);
  timer = window.setInterval(() => { if (!document.hidden) void load(false); }, 20000);
});
onBeforeUnmount(() => {
  window.clearInterval(timer);
  window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="page">
    <PageHeader title="账户详情" back-to="/strategies" back-label="策略列表" />

    <div v-if="loading && !account" class="skel skel-card" style="height: 320px" />
    <div v-else-if="error && !account" class="card">
      <EmptyState title="账户加载失败" :description="error" />
    </div>

    <template v-else-if="account">
      <section class="account-hero">
        <div class="hero-main">
          <div class="account-title">
            <h2>{{ account.name }}</h2>
            <span v-if="account.broker && account.broker !== account.name" class="broker">{{ account.broker }}</span>
          </div>
          <span class="equity-label">账户权益</span>
          <strong class="equity-value mono">{{ account.equity ? '¥' + fmtNumber(account.equity, 0) : '—' }}</strong>
          <div class="hero-meta">
            <span>今日盈利额 <strong class="mono" :class="todayPnl === null ? '' : todayPnl >= 0 ? 'up' : 'down'">{{ todayPnl === null ? '—' : (todayPnl >= 0 ? '+' : '') + fmtNumber(todayPnl, 0) }}</strong></span>
            <span>{{ account.strategy_count }} 个策略 · {{ account.online_strategies }} 在线</span>
          </div>
        </div>
        <div class="detail-range">
          <select v-model="rangeKey" class="range-select" aria-label="选择时间范围">
            <option v-for="item in rangeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <template v-if="rangeKey === 'custom'">
            <input v-model="customStart" type="date" class="date-input" aria-label="开始日期" />
            <span class="date-sep">—</span>
            <input v-model="customEnd" type="date" class="date-input" aria-label="结束日期" />
          </template>
          <span class="chart-window">日粒度</span>
        </div>
      </section>

      <section class="card chart-card">
        <NavChart :data="chartData" :height="260" date-only />
      </section>

      <section class="strategies-section">
        <div class="section-head">
          <h3>策略</h3>
          <span class="count">{{ strategies.length }} 个</span>
        </div>
        <StrategyGrid v-if="strategies.length">
          <GroupCard v-for="runner in strategies" :key="runner.id" :runner="runner" />
        </StrategyGrid>
        <EmptyState v-else compact title="账户下还没有策略" description="在策略页新建策略并选择这个账户。" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail-range { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.range-select { height: 28px; padding: 0 22px 0 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-2); font-size: 11px; }
.date-input { height: 28px; padding: 0 7px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-2); font-size: 10px; }
.date-sep { color: var(--text-3); font-size: 10px; }
.chart-window { color: var(--text-3); font-size: 10px; white-space: nowrap; }
.account-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; padding: 4px 2px 0; }
.account-title { display: flex; align-items: center; gap: 8px; }
.account-title h2 { font-size: 22px; font-weight: 650; color: #ffffff; letter-spacing: -0.02em; }
.broker { padding: 2px 7px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-2); font-size: 10px; }
.equity-label { display: block; margin-top: 14px; font-size: 11px; color: var(--text-3); }
.equity-value { display: block; margin-top: 2px; font-size: 34px; line-height: 1.1; letter-spacing: -0.04em; color: #ffffff; }
.hero-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 8px; color: var(--text-3); font-size: 10px; }
.hero-meta strong { color: var(--text); }
.hero-meta strong.up { color: var(--up); }
.hero-meta strong.down { color: var(--down); }
.source { padding: 1px 6px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-2); }
.range-tabs { display: inline-flex; padding: 2px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
.range-tabs button { height: 24px; padding: 0 9px; border: 0; border-radius: 4px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.range-tabs button.active { background: var(--primary-soft); color: var(--text); }
.chart-card { padding: 12px 18px 14px; }
.strategies-section { display: flex; flex-direction: column; gap: 10px; }
.section-head { display: flex; align-items: baseline; gap: 8px; }
.section-head h3 { font-size: 15px; color: #ffffff; }
.count { color: var(--text-3); font-size: 10px; }
@media (max-width: 760px) {
  .account-hero { align-items: flex-start; flex-direction: column; }
  .range-tabs { align-self: flex-end; }
  .equity-value { font-size: 28px; }
}
</style>