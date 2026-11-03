<script setup lang="ts">
// AccountDetail.vue — 账户详情：KPI、净值曲线、持仓表、出入金、当日信号。
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton } from 'naive-ui';
import { ArrowUpRight } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { AccountDetail, Runner } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { SIGNAL_ACTION_LABELS } from '@/utils/catalog';
import { fmtDateTime, fmtMoney, fmtPct } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import EquityChart from '@/components/EquityChart.vue';
import MarketTag from '@/components/MarketTag.vue';
import MetricCard from '@/components/MetricCard.vue';
import PageHeader from '@/components/PageHeader.vue';
import PnlText from '@/components/PnlText.vue';
import SectionCard from '@/components/SectionCard.vue';
import SideTag from '@/components/SideTag.vue';
import StatusDot from '@/components/StatusDot.vue';
import SignalStatusTag from '@/components/SignalStatusTag.vue';

const route = useRoute();
const settings = useSettingsStore();

const accountId = computed(() => String(route.params.id || ''));
const detail = ref<AccountDetail | null>(null);
const runners = ref<Runner[]>([]);
const loading = ref(true);
const error = ref('');

const relatedStrategies = computed(() =>
  runners.value.filter((r) => r.accounts.some((a) => a.id === detail.value?.account.id)),
);

const positionValue = computed(() =>
  (detail.value?.positions ?? []).reduce((sum, p) => sum + Number(p.market_value), 0),
);

const periodReturn = computed(() => {
  const curve = detail.value?.equity ?? [];
  if (curve.length < 2) return null;
  const first = Number(curve[0].value);
  const last = Number(curve[curve.length - 1].value);
  return first > 0 ? ((last - first) / first) * 100 : null;
});

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [account, runnerRes] = await Promise.all([api.account(accountId.value), api.runners()]);
    detail.value = account;
    runners.value = runnerRes.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '账户详情加载失败';
  } finally {
    loading.value = false;
  }
}

watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <div v-if="loading && !detail" class="page">
      <div class="skel skel-line" style="width: 200px; height: 26px" />
      <div class="grid grid-kpi">
        <div v-for="i in 4" :key="i" class="skel skel-card" />
      </div>
      <div class="skel" style="height: 360px; border-radius: 12px" />
    </div>

    <div v-else-if="error && !detail" class="card">
      <EmptyState title="账户详情加载失败" :description="error">
        <template #action><n-button size="small" @click="load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else-if="detail">
      <PageHeader
        :title="detail.account.name"
        :subtitle="detail.account.id + ' · ' + detail.account.venue + ' · ' + detail.account.currency + ' · 初始权益 ¥' + fmtMoney(detail.account.initial_equity)"
        back-to="/accounts"
        back-label="账户列表"
      >
        <template #extra>
          <MarketTag :market="detail.account.market" :venue="detail.account.venue" />
          <n-button size="small" @click="$router.push('/signals?account_id=' + detail.account.id)">
            <template #icon><ArrowUpRight :size="13" /></template>
            查看信号
          </n-button>
        </template>
      </PageHeader>

      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div class="grid grid-kpi">
        <MetricCard label="账户权益" :value="'¥' + fmtMoney(detail.account.equity)" sub="单位净值法" />
        <MetricCard
          label="今日盈亏"
          :value="'¥' + fmtMoney(detail.account.today_pnl)"
          :change="detail.account.today_pnl"
          :change-pct="detail.account.today_pnl_pct"
          sub="较昨日收盘"
        />
        <MetricCard label="累计收益" :value="fmtPct(detail.total_return_pct)" :change="detail.total_return_pct" :change-pct="null" sub="相对初始权益" />
        <MetricCard label="持仓市值" :value="'¥' + fmtMoney(positionValue)" :sub="detail.positions.length + ' 个标的 · 期货按名义市值'" />
      </div>

      <SectionCard title="净值曲线" subtitle="出入金按份额处理，不影响收益率">
        <template #extra>
          <span v-if="periodReturn !== null" class="muted" style="font-size: 11px">
            区间收益 <span class="num" :class="Number(periodReturn) >= 0 ? 'pos' : 'neg'">{{ fmtPct(periodReturn) }}</span>
          </span>
        </template>
        <EquityChart :data="detail.equity" :height="280" value-label="账户净值" />
        <div class="chart-foot">
          <span class="muted">初始权益 <span class="num">¥{{ fmtMoney(detail.account.initial_equity) }}</span></span>
          <span class="spacer" />
          <span class="muted mono">近 {{ detail.equity.length }} 个交易日</span>
        </div>
      </SectionCard>

      <SectionCard title="关联策略" :subtitle="relatedStrategies.length + ' 个策略使用该账户'">
        <div v-if="relatedStrategies.length" class="related-list">
          <router-link
            v-for="runner in relatedStrategies"
            :key="runner.id"
            :to="'/strategies/' + runner.id"
            class="related-item"
          >
            <StatusDot :status="runner.status" :size="6" />
            <span class="related-name">{{ runner.name }}</span>
            <span class="mono related-id">{{ runner.strategy }}</span>
            <span class="chip">{{ runner.platform_label }}</span>
            <span class="related-more">查看策略 →</span>
          </router-link>
        </div>
        <EmptyState v-else compact title="暂无关联策略" description="策略 Runner 绑定该账户后会出现在这里" />
      </SectionCard>

      <div class="grid grid-main">
        <SectionCard title="持仓" :subtitle="detail.positions.length + ' 个标的'">
          <div v-if="detail.positions.length" class="tbl-wrap">
            <table class="tbl tbl--compact">
              <thead>
                <tr><th>品种</th><th>市场</th><th class="th-num">数量</th><th class="th-num">均价</th><th class="th-num">最新价</th><th class="th-num">市值</th><th class="th-num">浮动盈亏</th></tr>
              </thead>
              <tbody>
                <tr v-for="pos in detail.positions" :key="pos.instrument">
                  <td><span class="mono">{{ pos.instrument }}</span><span class="inst">{{ pos.instrument_name }}</span></td>
                  <td class="muted">{{ pos.market === 'CN_A' ? 'A股' : '期货' }}</td>
                  <td class="td-num">{{ pos.qty }}</td>
                  <td class="td-num">{{ pos.avg_price }}</td>
                  <td class="td-num">{{ pos.last_price }}</td>
                  <td class="td-num">{{ fmtMoney(pos.market_value) }}</td>
                  <td class="td-num"><PnlText :value="pos.pnl" :pct="pos.pnl_pct" show-pct size="sm" /></td>
                </tr>
              </tbody>
            </table>
          </div>
          <EmptyState v-else compact title="无持仓" description="账户当前为空仓状态" />
        </SectionCard>

        <SectionCard title="出入金" :subtitle="detail.cash_flows.length + ' 笔记录'">
          <div v-if="detail.cash_flows.length" class="flows">
            <div v-for="flow in detail.cash_flows" :key="flow.id" class="flow-row">
              <div class="flow-main">
                <span class="flow-kind" :class="flow.kind">{{ flow.kind === 'deposit' ? '入金' : '出金' }}</span>
                <span class="flow-note">{{ flow.note }}</span>
              </div>
              <div class="flow-right">
                <span class="num" :class="flow.kind === 'deposit' ? 'pos' : 'neg'">
                  {{ flow.kind === 'deposit' ? '+' : '-' }}{{ fmtMoney(flow.amount) }}
                </span>
                <span class="mono flow-time">{{ fmtDateTime(flow.ts) }}</span>
              </div>
            </div>
          </div>
          <EmptyState v-else compact title="暂无出入金" />
        </SectionCard>
      </div>

      <SectionCard title="当日信号" :subtitle="'共 ' + detail.signals.length + ' 条 · Asia/Shanghai'">
        <template #extra>
          <router-link :to="'/signals?account_id=' + detail.account.id" class="link-more">全部信号 →</router-link>
        </template>
        <div v-if="detail.signals.length" class="tbl-wrap">
          <table class="tbl tbl--compact">
            <thead>
              <tr><th>时间</th><th>策略</th><th>品种</th><th>方向</th><th>动作</th><th class="th-num">数量</th><th class="th-num">参考价</th><th class="th-num">金额</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="signal in detail.signals" :key="signal.id">
                <td class="mono nowrap">{{ fmtDateTime(signal.ts) }}</td>
                <td class="truncate">{{ signal.runner_name }}</td>
                <td><span class="mono">{{ signal.instrument }}</span><span class="inst">{{ signal.instrument_name }}</span></td>
                <td><SideTag :side="signal.side" /></td>
                <td class="muted">{{ SIGNAL_ACTION_LABELS[signal.action] }}</td>
                <td class="td-num">{{ signal.qty }}</td>
                <td class="td-num">{{ signal.price }}</td>
                <td class="td-num">{{ fmtMoney(signal.amount) }}</td>
                <td><SignalStatusTag :status="signal.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else compact title="今日暂无信号" description="交易日收盘后统计" />
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.pos {
  color: var(--up);
}
.neg {
  color: var(--down);
}
.chart-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 11px;
}
.chart-foot .spacer {
  flex: 1;
}
.inst {
  display: block;
  font-size: 10px;
  color: var(--text-3);
  line-height: 1.2;
}
.link-more {
  font-size: 12px;
  color: var(--text-2);
  white-space: nowrap;
}
.link-more:hover {
  color: var(--primary);
}
.flows {
  display: flex;
  flex-direction: column;
}
.flow-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 2px;
  border-bottom: 1px solid rgba(30, 38, 55, 0.65);
}
.flow-row:last-child {
  border-bottom: none;
}
.flow-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.flow-kind {
  display: inline-flex;
  height: 19px;
  align-items: center;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 10px;
  flex: none;
}
.flow-kind.deposit {
  color: var(--up);
  background: color-mix(in srgb, var(--up) 12%, transparent);
}
.flow-kind.withdraw {
  color: var(--down);
  background: color-mix(in srgb, var(--down) 12%, transparent);
}
.flow-note {
  font-size: 12px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.flow-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  flex: none;
}
.flow-time {
  font-size: 10px;
  color: var(--text-3);
}
.related-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.related-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 6px;
  border-bottom: 1px solid rgba(30, 38, 55, 0.65);
  color: var(--text);
  border-radius: 6px;
}
.related-item:last-child {
  border-bottom: none;
}
.related-item:hover {
  background: rgba(21, 28, 44, 0.7);
  color: var(--text);
}
.related-name {
  font-size: 13px;
  font-weight: 500;
}
.related-id {
  font-size: 11px;
  color: var(--text-3);
}
.related-more {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-3);
}
.related-item:hover .related-more {
  color: var(--primary);
}
</style>
