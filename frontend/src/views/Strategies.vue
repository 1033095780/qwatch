// Strategies.vue — v0.5 策略列表：按账户分组（账户头聚合权益/净值 + 策略卡片网格）；新建策略必须选/建账户。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { NButton, NInput, NSelect } from 'naive-ui';
import { Plus, Search } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Runner, RunnerStatus } from '@/api/types';
import { RUNNER_STATUS_LABELS } from '@/utils/catalog';
import { fmtNumber } from '@/utils/format';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import EmptyState from '@/components/EmptyState.vue';
import GroupCard from '@/components/GroupCard.vue';
import NavSparkline from '@/components/NavSparkline.vue';
import PageHeader from '@/components/PageHeader.vue';
import StrategyCreateModal from '@/components/StrategyCreateModal.vue';
import StrategyGrid from '@/components/StrategyGrid.vue';

const settings = useSettingsStore();
const realtime = useRealtimeStore();

const accounts = ref<Account[]>([]);
const runners = ref<Runner[]>([]);
const loading = ref(true);
const error = ref('');
const createOpen = ref(false);
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const keyword = ref('');
const statusFilter = ref<RunnerStatus | 'all'>('all');
const statusOptions = [{ label: '全部状态', value: 'all' }, ...Object.entries(RUNNER_STATUS_LABELS).map(([value, label]) => ({ value, label }))];
const hasFilter = computed(() => !!keyword.value || statusFilter.value !== 'all');

const matchedRunners = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  return runners.value.filter((runner) => {
    if (statusFilter.value !== 'all' && runner.status !== statusFilter.value) return false;
    if (q && !(runner.name + runner.id + runner.description + (runner.account_name || '')).toLowerCase().includes(q)) return false;
    return true;
  });
});

interface AccountGroup { account: Account; runners: Runner[]; online: number }

const groups = computed<AccountGroup[]>(() => {
  const byAccount = new Map<string, Runner[]>();
  matchedRunners.value.forEach((runner) => {
    const list = byAccount.get(runner.account_id) || [];
    list.push(runner);
    byAccount.set(runner.account_id, list);
  });
  const result: AccountGroup[] = accounts.value.map((account) => {
    const list = byAccount.get(account.id) || [];
    return {
      account,
      runners: list,
      online: list.filter((runner) => runner.status === 'running').length,
    };
  });
  // 数据异常兜底：runner 的 account 不在 accounts 列表时仍展示，避免策略被隐藏
  const known = new Set(accounts.value.map((account) => account.id));
  byAccount.forEach((list, accountId) => {
    if (known.has(accountId)) return;
    const first = list[0];
    result.push({
      account: {
        id: accountId,
        name: first.account_name || '未关联账户',
        broker: first.account_broker || '',
        equity: null,
        nav: null,
        strategy_count: list.length,
        online_strategies: list.filter((runner) => runner.status === 'running').length,
      },
      runners: list,
      online: list.filter((runner) => runner.status === 'running').length,
    });
  });
  if (hasFilter.value) return result.filter((group) => group.runners.length > 0);
  return result;
});

const totalOnline = computed(() => matchedRunners.value.filter((runner) => runner.status === 'running').length);

async function load(initial = false, silent = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [runnerRes, accountRes] = await Promise.all([
      api.runners(),
      api.accounts().catch(() => ({ items: [] as Account[] })),
    ]);
    runners.value = runnerRes.items;
    accounts.value = accountRes.items || [];
  } catch (err) {
    if (!silent) error.value = err instanceof Error ? err.message : '策略列表加载失败';
  } finally {
    loading.value = false;
  }
}

function resetFilters(): void {
  keyword.value = '';
  statusFilter.value = 'all';
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

watch(() => settings.refreshSeq, () => { void load(false, true); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastAccountChangeAt, realtime.lastEquityChangeAt], scheduleReload);

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
    <PageHeader title="策略">
      <template #extra>
        <n-button type="primary" size="small" @click="createOpen = true">
          <template #icon><Plus :size="14" /></template>
          新建策略
        </n-button>
      </template>
    </PageHeader>

    <section class="card toolbar">
      <div class="toolbar-left">
        <n-input v-model:value="keyword" clearable placeholder="搜索策略名 / 标识 / 账户" class="search" size="small">
          <template #prefix><Search :size="14" /></template>
        </n-input>
        <n-select v-model:value="statusFilter" :options="statusOptions" size="small" class="select" />
      </div>
      <div class="toolbar-right">
        <span class="result mono">{{ matchedRunners.length }} / {{ runners.length }}</span>
        <button v-if="hasFilter" type="button" class="reset" @click="resetFilters">重置筛选</button>
      </div>
    </section>

    <div v-if="error" class="error-bar">
      <span class="dot" />{{ error }}
      <n-button text size="tiny" @click="load(true)">重试</n-button>
    </div>

    <div v-if="loading" class="skeleton-groups">
      <div v-for="i in 2" :key="i" class="skel skel-card" style="height: 300px; border-radius: var(--radius-lg)" />
    </div>

    <EmptyState
      v-else-if="!groups.length"
      title="没有匹配的策略"
      :description="hasFilter ? '试着放宽筛选条件，或清空搜索关键词' : '还没有账户/策略，点击右上角「新建策略」，可在弹窗内先创建账户'"
    >
      <template #action>
        <n-button v-if="hasFilter" size="small" @click="resetFilters">重置筛选</n-button>
        <n-button v-else size="small" type="primary" @click="createOpen = true">新建策略</n-button>
      </template>
    </EmptyState>

    <div v-else class="account-groups">
      <section v-for="group in groups" :key="group.account.id" class="account-group">
        <router-link :to="'/accounts/' + group.account.id" class="account-header card">
          <div class="account-identity">
            <span class="account-name truncate" :title="group.account.name">{{ group.account.name }}</span>
            <span v-if="group.account.broker && group.account.broker !== group.account.name" class="broker">{{ group.account.broker }}</span>
            <span class="account-count"><strong class="mono">{{ group.runners.length }}</strong> 个策略 · <strong class="mono">{{ group.online }}</strong> 在线</span>
          </div>
          <div class="account-metrics">
            <div class="metric">
              <span class="metric-label">账户权益</span>
              <strong class="metric-value mono">{{ group.account.equity !== null && group.account.equity !== undefined && group.account.equity !== '' ? '¥' + fmtNumber(group.account.equity, 0) : '—' }}</strong>
            </div>
            <div class="metric">
              <span class="metric-label">账户净值</span>
              <strong class="metric-value mono">{{ group.account.nav !== null && group.account.nav !== undefined && group.account.nav !== '' ? fmtNumber(group.account.nav, 4) : '—' }}</strong>
            </div>
            <div class="account-spark">
              <NavSparkline v-if="group.account.equity_sparkline && group.account.equity_sparkline.length" :values="group.account.equity_sparkline" :width="260" :height="52" />
            </div>
            <span class="account-open">查看账户 →</span>
          </div>
        </router-link>

        <StrategyGrid v-if="group.runners.length">
          <GroupCard v-for="runner in group.runners" :key="runner.id" :runner="runner" />
        </StrategyGrid>
        <div v-else class="group-empty">该账户下暂无策略</div>
      </section>
    </div>

    <StrategyCreateModal v-model:show="createOpen" :accounts="accounts" @created="load(true)" />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 16px;
  flex-wrap: wrap;
}
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; min-width: 0; }
.search { width: 260px; }
.select { width: 140px; }
.toolbar-right { display: flex; align-items: center; gap: 10px; }
.result { font-size: 11px; color: var(--text-3); }
.reset { border: 0; background: transparent; color: var(--text-2); font-size: 12px; cursor: pointer; padding: 0; }
.reset:hover { color: var(--primary); }
.skeleton-groups { display: flex; flex-direction: column; gap: var(--gap); }
.account-groups { display: flex; flex-direction: column; gap: 18px; }
.account-group { display: flex; flex-direction: column; gap: 12px; }
.account-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  padding: 17px 20px;
  color: inherit;
  transition: border-color 160ms ease, background-color 160ms ease;
}
.account-header:hover { border-color: var(--border-strong); background: rgba(91, 140, 255, 0.045); }
.account-identity { display: flex; align-items: center; gap: 9px; min-width: 0; }
.broker { flex: none; padding: 2px 7px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-2); font-size: 10px; }
.account-name { font-size: 20px; font-weight: 650; color: #ffffff; letter-spacing: -0.02em; }
.account-metrics { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
.metric { display: flex; flex-direction: column; gap: 3px; }
.metric-label { font-size: 10px; color: var(--text-3); }
.metric-value { font-size: 21px; letter-spacing: -0.02em; color: #ffffff; white-space: nowrap; }
.account-spark { width: 290px; max-width: 100%; opacity: 0.95; }
.account-open { color: var(--primary); font-size: 11px; white-space: nowrap; }
.account-count { font-size: 10px; color: var(--text-3); white-space: nowrap; margin-left: 4px; }
.account-count .mono { color: var(--text); font-size: 12px; }
.group-empty { padding: 14px 16px; border: 1px dashed var(--border); border-radius: 8px; color: var(--text-3); font-size: 11px; }
@media (max-width: 899px) {
  .search { width: 100%; }
  .select { flex: 1; width: auto; min-width: 130px; }
  .account-header { align-items: flex-start; }
  .account-metrics { width: 100%; gap: 16px; }
  .account-spark { width: 100%; order: 4; }
  .account-open { display: none; }
}
</style>