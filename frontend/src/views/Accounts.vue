<script setup lang="ts">
// Accounts.vue — 账户列表：汇总 KPI + 市场/通道/币种筛选 + 账户卡片（关联策略数、权益、今日盈亏、持仓）。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NSelect } from 'naive-ui';
import { CreditCard, Wallet, WalletCards } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Runner } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { venueLabel } from '@/utils/catalog';
import { fmtMoney } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import MarketTag from '@/components/MarketTag.vue';
import MetricCard from '@/components/MetricCard.vue';
import PageHeader from '@/components/PageHeader.vue';
import PnlText from '@/components/PnlText.vue';
import Sparkline from '@/components/Sparkline.vue';

const settings = useSettingsStore();

const accounts = ref<Account[]>([]);
const runners = ref<Runner[]>([]);
const loading = ref(true);
const error = ref('');

const marketFilter = ref<'all' | 'CN_A' | 'CN_FUT'>('all');
const venueFilter = ref('all');
const currencyFilter = ref('all');

const marketOptions = [
  { label: '全部市场', value: 'all' },
  { label: 'A股', value: 'CN_A' },
  { label: '期货', value: 'CN_FUT' },
];
const venueOptions = computed(() => [
  { label: '全部通道', value: 'all' },
  ...Array.from(new Set(accounts.value.map((a) => a.venue))).map((v) => ({ label: venueLabel(v), value: v })),
]);
const currencyOptions = computed(() => [
  { label: '全部币种', value: 'all' },
  ...Array.from(new Set(accounts.value.map((a) => a.currency))).map((c) => ({ label: c, value: c })),
]);

const strategyCounts = computed(() => {
  const map: Record<string, number> = {};
  runners.value.forEach((r) => r.accounts.forEach((a) => {
    map[a.id] = (map[a.id] || 0) + 1;
  }));
  return map;
});

const filtered = computed(() =>
  accounts.value.filter((a) => {
    if (marketFilter.value !== 'all' && a.market !== marketFilter.value) return false;
    if (venueFilter.value !== 'all' && a.venue !== venueFilter.value) return false;
    if (currencyFilter.value !== 'all' && a.currency !== currencyFilter.value) return false;
    return true;
  }),
);

const totalEquity = computed(() => filtered.value.reduce((sum, a) => sum + Number(a.equity), 0));
const totalTodayPnl = computed(() => filtered.value.reduce((sum, a) => sum + Number(a.today_pnl), 0));
const totalPositions = computed(() => filtered.value.reduce((sum, a) => sum + a.positions_count, 0));
const hasFilter = computed(
  () => marketFilter.value !== 'all' || venueFilter.value !== 'all' || currencyFilter.value !== 'all',
);

function resetFilters(): void {
  marketFilter.value = 'all';
  venueFilter.value = 'all';
  currencyFilter.value = 'all';
}

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [accountRes, runnerRes] = await Promise.all([api.accounts(), api.runners()]);
    accounts.value = accountRes.items;
    runners.value = runnerRes.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '账户加载失败';
  } finally {
    loading.value = false;
  }
}

watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <PageHeader
      title="账户"
      :subtitle="'资金与持仓归属 · ' + accounts.length + ' 个账户 · 单位净值法（出入金不影响收益）'"
    />

    <div v-if="loading && !accounts.length" class="grid grid-kpi">
      <div v-for="i in 4" :key="i" class="skel skel-card" style="min-height: 128px" />
    </div>

    <div v-else-if="error && !accounts.length" class="card">
      <EmptyState title="账户加载失败" :description="error">
        <template #action><n-button size="small" @click="load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else>
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div class="grid grid-kpi">
        <MetricCard label="账户总权益" :value="'¥' + fmtMoney(totalEquity)" sub="当前筛选范围" :icon="Wallet" />
        <MetricCard label="今日盈亏" :value="'¥' + fmtMoney(totalTodayPnl)" sub="较昨日收盘" :icon="WalletCards" accent="warning" />
        <MetricCard label="账户数" :value="filtered.length + ' 个'" :sub="hasFilter ? '筛选结果' : '全部账户'" :icon="CreditCard" />
        <MetricCard label="持仓标的" :value="totalPositions + ' 个'" sub="跨账户去重前统计" :icon="CreditCard" />
      </div>

      <section class="card toolbar">
        <div class="toolbar-left">
          <n-select v-model:value="marketFilter" :options="marketOptions" size="small" class="select" />
          <n-select v-model:value="venueFilter" :options="venueOptions" size="small" class="select" />
          <n-select v-model:value="currencyFilter" :options="currencyOptions" size="small" class="select" />
          <button v-if="hasFilter" type="button" class="reset" @click="resetFilters">清空筛选</button>
        </div>
        <span class="result mono">{{ filtered.length }} / {{ accounts.length }} 个账户</span>
      </section>

      <div v-if="!filtered.length" class="card">
        <EmptyState title="没有匹配的账户" description="调整筛选条件后重试">
          <template #action><n-button size="small" @click="resetFilters">清空筛选</n-button></template>
        </EmptyState>
      </div>

      <div v-else class="grid grid-3">
        <router-link
          v-for="account in filtered"
          :key="account.id"
          :to="'/accounts/' + account.id"
          class="account-card card card-hover"
        >
          <div class="head">
            <div class="name-wrap">
              <span class="name">{{ account.name }}</span>
              <span class="id mono">{{ account.id }}</span>
            </div>
            <MarketTag :market="account.market" :venue="account.venue" />
          </div>
          <div class="mid">
            <div>
              <div class="eyebrow">权益</div>
              <div class="equity num">¥{{ fmtMoney(account.equity) }}</div>
            </div>
            <Sparkline :values="account.sparkline" :width="104" :height="34" />
          </div>
          <div class="pnl-row">
            <span class="muted">今日</span>
            <PnlText :value="account.today_pnl" :pct="account.today_pnl_pct" show-pct size="sm" bold />
          </div>
          <div class="foot">
            <span class="chip">{{ strategyCounts[account.id] || 0 }} 个策略</span>
            <span class="chip">{{ account.positions_count }} 个持仓</span>
            <span class="chip">{{ account.currency }}</span>
            <span class="more">查看详情 →</span>
          </div>
        </router-link>
      </div>
    </template>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.select {
  width: 132px;
}
.result {
  font-size: 11px;
  color: var(--text-3);
}
.reset {
  border: 0;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.reset:hover {
  color: var(--primary);
}
.account-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: inherit;
}
.account-card:hover {
  color: inherit;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.name-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.name {
  font-size: 14px;
  font-weight: 600;
}
.id {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
}
.mid {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}
.equity {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin-top: 2px;
}
.pnl-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}
.foot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.more {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-3);
}
.account-card:hover .more {
  color: var(--primary);
}
@media (max-width: 899px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .select {
    flex: 1 1 calc(50% - 4px);
    width: auto;
  }
  .result {
    width: 100%;
  }
}
</style>
