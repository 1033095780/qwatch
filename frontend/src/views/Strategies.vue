// Strategies.vue — v0.4 策略列表：按账户筛选 + 搜索/状态筛选 + 与总览一致的大卡片网格 + 新建策略（必选账户）。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton, NInput, NSelect } from 'naive-ui';
import { Plus, Search } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Runner, RunnerStatus } from '@/api/types';
import { RUNNER_STATUS_LABELS } from '@/utils/catalog';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import EmptyState from '@/components/EmptyState.vue';
import GroupCard from '@/components/GroupCard.vue';
import PageHeader from '@/components/PageHeader.vue';
import StrategyCreateModal from '@/components/StrategyCreateModal.vue';
import StrategyGrid from '@/components/StrategyGrid.vue';

const settings = useSettingsStore();
const realtime = useRealtimeStore();
const route = useRoute();

const runners = ref<Runner[]>([]);
const accounts = ref<Account[]>([]);
const loading = ref(true);
const error = ref('');
const createOpen = ref(false);
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const keyword = ref('');
const statusFilter = ref<RunnerStatus | 'all'>('all');
const accountFilter = ref<string>('all');

const statusOptions = [{ label: '全部状态', value: 'all' }, ...Object.entries(RUNNER_STATUS_LABELS).map(([value, label]) => ({ value, label }))];
const accountOptions = computed(() => [
  { label: '全部账户', value: 'all' },
  ...accounts.value.map((account) => ({ label: account.broker ? account.broker + ' · ' + account.name : account.name, value: account.id })),
]);
const accountMap = computed(() => new Map(accounts.value.map((account) => [account.id, account])));

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  return runners.value.filter((runner) => {
    if (accountFilter.value !== 'all' && runner.account_id !== accountFilter.value) return false;
    if (statusFilter.value !== 'all' && runner.status !== statusFilter.value) return false;
    if (q && !(runner.name + runner.id + runner.description + (runner.account_name || '')).toLowerCase().includes(q)) return false;
    return true;
  });
});
const hasFilter = computed(() => !!keyword.value || statusFilter.value !== 'all' || accountFilter.value !== 'all');

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
  accountFilter.value = 'all';
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

function applyAccountQuery(): void {
  const query = route.query.account_id;
  if (typeof query === 'string' && query) accountFilter.value = query;
}

watch(() => settings.refreshSeq, () => { void load(false, true); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastAccountChangeAt], scheduleReload);
watch(() => route.query.account_id, applyAccountQuery);

onMounted(() => {
  applyAccountQuery();
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
        <n-select v-model:value="accountFilter" :options="accountOptions" size="small" class="select" />
        <n-select v-model:value="statusFilter" :options="statusOptions" size="small" class="select" />
      </div>
      <div class="toolbar-right">
        <span class="result mono">{{ filtered.length }} / {{ runners.length }}</span>
        <button v-if="hasFilter" type="button" class="reset" @click="resetFilters">重置筛选</button>
      </div>
    </section>

    <div v-if="error" class="error-bar">
      <span class="dot" />{{ error }}
      <n-button text size="tiny" @click="load(true)">重试</n-button>
    </div>

    <div v-if="loading" class="strategy-grid">
      <div v-for="i in 3" :key="i" class="skel skel-card" style="height: 180px" />
    </div>

    <EmptyState
      v-else-if="!filtered.length"
      title="没有匹配的策略"
      :description="hasFilter ? '试着放宽筛选条件，或清空搜索关键词' : '还没有策略，点击右上角「新建策略」创建（需先有账户）'"
    >
      <template #action>
        <n-button v-if="hasFilter" size="small" @click="resetFilters">重置筛选</n-button>
      </template>
    </EmptyState>

    <StrategyGrid v-else>
      <GroupCard v-for="runner in filtered" :key="runner.id" :runner="runner" :account="accountMap.get(runner.account_id) || null" />
    </StrategyGrid>

    <StrategyCreateModal v-model:show="createOpen" :accounts="accounts" @created="load(true)" />
  </div>
</template>

<style scoped>
.strategy-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--gap);
}
@media (max-width: 1100px) {
  .strategy-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .strategy-grid { grid-template-columns: minmax(0, 1fr); }
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 16px;
  flex-wrap: wrap;
}
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; min-width: 0; }
.search { width: 240px; }
.select { width: 170px; }
.toolbar-right { display: flex; align-items: center; gap: 10px; }
.result { font-size: 11px; color: var(--text-3); }
.reset { border: 0; background: transparent; color: var(--text-2); font-size: 12px; cursor: pointer; padding: 0; }
.reset:hover { color: var(--primary); }
@media (max-width: 899px) {
  .search { width: 100%; }
  .select { flex: 1; width: auto; min-width: 130px; }
}
</style>
