<script setup lang="ts">
// Accounts.vue — 账户列表：汇总 4 卡 + 账户卡片（venue/权益/今日盈亏/持仓数/sparkline）。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton } from 'naive-ui';
import { CreditCard, RefreshCw, Wallet, WalletCards } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtMoney } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import MarketTag from '@/components/MarketTag.vue';
import MetricCard from '@/components/MetricCard.vue';
import PageHeader from '@/components/PageHeader.vue';
import PnlText from '@/components/PnlText.vue';
import SectionCard from '@/components/SectionCard.vue';
import Sparkline from '@/components/Sparkline.vue';

const settings = useSettingsStore();

const items = ref<Account[]>([]);
const loading = ref(true);
const error = ref('');

const totalEquity = computed(() => items.value.reduce((sum, a) => sum + Number(a.equity), 0));
const totalTodayPnl = computed(() => items.value.reduce((sum, a) => sum + Number(a.today_pnl), 0));
const totalPositions = computed(() => items.value.reduce((sum, a) => sum + a.positions_count, 0));

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const res = await api.accounts();
    items.value = res.items;
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
    <PageHeader title="账户" :subtitle="'资金与持仓归属 · ' + items.length + ' 个账户 · 单位净值法展示'">
      <template #extra>
        <n-button size="small" :loading="loading" @click="load()">
          <template #icon><RefreshCw :size="14" /></template>
          刷新
        </n-button>
      </template>
    </PageHeader>

    <div v-if="loading && !items.length" class="grid grid-kpi">
      <div v-for="i in 4" :key="i" class="skel skel-card" style="min-height: 128px" />
    </div>

    <div v-else-if="error && !items.length" class="card">
      <EmptyState title="账户加载失败" :description="error">
        <template #action><n-button size="small" @click="load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else>
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div class="grid grid-kpi">
        <MetricCard label="账户总权益" :value="'¥' + fmtMoney(totalEquity)" sub="全部账户合并" :icon="Wallet" />
        <MetricCard label="今日盈亏" :value="'¥' + fmtMoney(totalTodayPnl)" sub="较昨日收盘" :icon="WalletCards" accent="warning" />
        <MetricCard label="账户数" :value="items.length + ' 个'" sub="券商 / 期货 / A股" :icon="CreditCard" />
        <MetricCard label="持仓标的" :value="totalPositions + ' 个'" sub="跨账户去重前统计" :icon="CreditCard" />
      </div>

      <div class="grid grid-3">
        <router-link
          v-for="account in items"
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
            <span class="chip">{{ account.positions_count }} 个持仓</span>
            <span class="chip">{{ account.currency }}</span>
            <span class="more">查看详情 →</span>
          </div>
        </router-link>
      </div>

      <SectionCard title="账户口径说明" subtitle="净值不受出入金影响">
        <p class="note">
          账户曲线使用单位净值法：出入金按份额增减处理，不扭曲收益率；跨策略共账户时，策略曲线为归因口径，不代表账户真实资金曲线。
          
        </p>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
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
}
.more {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-3);
}
.account-card:hover .more {
  color: var(--primary);
}
.note {
  font-size: 12px;
  line-height: 1.8;
  color: var(--text-2);
  max-width: 900px;
}
</style>
