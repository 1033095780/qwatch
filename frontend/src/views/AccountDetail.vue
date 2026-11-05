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
const loading = ref(true);
const error = ref('');
const range = ref<'1D' | '1W' | '1M' | '3M' | 'ALL'>('1D');
let timer: number | undefined;
let reloadTimer: number | undefined;

const ranges = [
  { key: '1D', label: '1日', days: 1 },
  { key: '1W', label: '1周', days: 7 },
  { key: '1M', label: '1月', days: 30 },
  { key: '3M', label: '3月', days: 90 },
  { key: 'ALL', label: '全部', days: 0 },
] as const;

const chartData = computed(() => {
  if (!curve.value.length) return [];
  const cfg = ranges.find((item) => item.key === range.value);
  if (!cfg || cfg.days === 0) return curve.value;
  const latest = Date.parse(curve.value[curve.value.length - 1].ts);
  const cutoff = latest - cfg.days * 86400000;
  const filtered = curve.value.filter((point) => Date.parse(point.ts) >= cutoff);
  return filtered.length > 1 ? filtered : curve.value.slice(-2);
});
const navSourceLabel = computed(() => {
  if (!account.value?.nav) return '';
  return account.value.nav_source === 'account' ? '账户上报' : '策略汇总';
});

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [detail, points] = await Promise.all([
      api.account(String(route.params.id)),
      api.accountEquityCurve(String(route.params.id)),
    ]);
    account.value = detail.account;
    strategies.value = detail.strategies;
    curve.value = points;
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
            <span>账户净值 <strong class="mono">{{ account.nav ? fmtNumber(account.nav, 4) : '—' }}</strong></span>
            <span v-if="navSourceLabel" class="source">{{ navSourceLabel }}</span>
            <span>{{ account.strategy_count }} 个策略 · {{ account.online_strategies }} 在线</span>
          </div>
        </div>
        <div class="range-tabs">
          <button v-for="item in ranges" :key="item.key" type="button" :class="{ active: range === item.key }" @click="range = item.key">{{ item.label }}</button>
        </div>
      </section>

      <section class="card chart-card">
        <NavChart :data="chartData" :height="260" />
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
.account-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; padding: 4px 2px 0; }
.account-title { display: flex; align-items: center; gap: 8px; }
.account-title h2 { font-size: 22px; font-weight: 650; color: #ffffff; letter-spacing: -0.02em; }
.broker { padding: 2px 7px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-2); font-size: 10px; }
.equity-label { display: block; margin-top: 14px; font-size: 11px; color: var(--text-3); }
.equity-value { display: block; margin-top: 2px; font-size: 34px; line-height: 1.1; letter-spacing: -0.04em; color: #ffffff; }
.hero-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 8px; color: var(--text-3); font-size: 10px; }
.hero-meta strong { color: var(--text); }
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
