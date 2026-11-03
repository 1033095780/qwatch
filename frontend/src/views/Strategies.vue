<script setup lang="ts">
// Strategies.vue — 策略列表：搜索 + 状态/市场/平台/类型/标签/账户筛选 + 卡片网格 + 空状态。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NInput, NSelect } from 'naive-ui';
import { Plus, Search, SlidersHorizontal } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Runner, RunnerStatus } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import RunnerCard from '@/components/RunnerCard.vue';
import StrategyCreateModal from '@/components/StrategyCreateModal.vue';

const settings = useSettingsStore();

const runners = ref<Runner[]>([]);
const accounts = ref<Account[]>([]);
const loading = ref(true);
const error = ref('');
const createOpen = ref(false);

const keyword = ref('');
const statusFilter = ref<RunnerStatus | 'all'>('all');
const marketFilter = ref<'all' | 'CN_A' | 'CN_FUT'>('all');
const platformFilter = ref<string>('all');
const typeFilter = ref<string>('all');
const tagFilter = ref<string>('all');
const accountFilter = ref<string>('all');

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '降级', value: 'degraded' },
  { label: '离线', value: 'offline' },
  { label: '非交易时段', value: 'off_hours' },
];
const marketOptions = [
  { label: '全部市场', value: 'all' },
  { label: 'A股', value: 'CN_A' },
  { label: '期货', value: 'CN_FUT' },
];
const accountOptions = computed(() => [
  { label: '全部账户', value: 'all' },
  ...accounts.value.map((a) => ({ label: a.name, value: a.id })),
]);
const platformOptions = computed(() => {
  const seen = new Map<string, string>();
  runners.value.forEach((r) => { if (r.platform) seen.set(r.platform, r.platform_label); });
  return [{ label: '全部平台', value: 'all' }, ...[...seen].map(([value, label]) => ({ value, label }))];
});
const typeOptions = computed(() => {
  const seen = new Map<string, string>();
  runners.value.forEach((r) => { if (r.strategy_type) seen.set(r.strategy_type, r.strategy_type_label); });
  return [{ label: '全部类型', value: 'all' }, ...[...seen].map(([value, label]) => ({ value, label }))];
});
const tagOptions = computed(() => {
  const tags = new Set<string>();
  runners.value.forEach((r) => r.tags.forEach((tag) => tags.add(tag)));
  return [{ label: '全部标签', value: 'all' }, ...[...tags].sort().map((tag) => ({ value: tag, label: tag }))];
});

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  return runners.value.filter((runner) => {
    if (statusFilter.value !== 'all' && runner.status !== statusFilter.value) return false;
    if (marketFilter.value !== 'all' && runner.market !== marketFilter.value) return false;
    if (platformFilter.value !== 'all' && runner.platform !== platformFilter.value) return false;
    if (typeFilter.value !== 'all' && runner.strategy_type !== typeFilter.value) return false;
    if (tagFilter.value !== 'all' && !runner.tags.includes(tagFilter.value)) return false;
    if (accountFilter.value !== 'all' && !runner.accounts.some((a) => a.id === accountFilter.value)) return false;
    if (q && !(runner.name + runner.strategy + runner.id).toLowerCase().includes(q)) return false;
    return true;
  });
});

const hasFilter = computed(
  () => !!keyword.value || statusFilter.value !== 'all' || marketFilter.value !== 'all'
    || platformFilter.value !== 'all' || typeFilter.value !== 'all' || tagFilter.value !== 'all'
    || accountFilter.value !== 'all',
);

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [runnerRes, accountRes] = await Promise.all([api.runners(), api.accounts()]);
    runners.value = runnerRes.items;
    accounts.value = accountRes.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '策略列表加载失败';
  } finally {
    loading.value = false;
  }
}

function resetFilters(): void {
  keyword.value = '';
  statusFilter.value = 'all';
  marketFilter.value = 'all';
  platformFilter.value = 'all';
  typeFilter.value = 'all';
  tagFilter.value = 'all';
  accountFilter.value = 'all';
}

watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <PageHeader title="策略" :subtitle="'运行实例与状态 · 共 ' + runners.length + ' 个 · 告警与心跳按交易日历判定'">
      <template #extra>
        <n-button type="primary" size="small" @click="createOpen = true">
          <template #icon><Plus :size="14" /></template>
          新建策略
        </n-button>
      </template>
    </PageHeader>

    <section class="card toolbar">
      <div class="toolbar-left">
        <n-input v-model:value="keyword" clearable placeholder="搜索策略名 / 标识" class="search" size="small">
          <template #prefix><Search :size="14" /></template>
        </n-input>
        <n-select v-model:value="statusFilter" :options="statusOptions" size="small" class="select" />
        <n-select v-model:value="marketFilter" :options="marketOptions" size="small" class="select" />
        <n-select v-model:value="platformFilter" :options="platformOptions" size="small" class="select" />
        <n-select v-model:value="typeFilter" :options="typeOptions" size="small" class="select" />
        <n-select v-model:value="tagFilter" :options="tagOptions" size="small" class="select" />
        <n-select v-model:value="accountFilter" :options="accountOptions" size="small" class="select select-wide" />
      </div>
      <div class="toolbar-right">
        <span class="result mono">{{ filtered.length }} / {{ runners.length }}</span>
        <button v-if="hasFilter" type="button" class="reset" @click="resetFilters">重置筛选</button>
        <SlidersHorizontal :size="14" class="faint" />
      </div>
    </section>

    <div v-if="error" class="error-bar">
      <span class="dot" />{{ error }}
      <n-button text size="tiny" @click="load(true)">重试</n-button>
    </div>

    <div v-if="loading" class="grid grid-2">
      <div v-for="i in 4" :key="i" class="skel skel-card" style="height: 300px" />
    </div>

    <EmptyState
      v-else-if="!filtered.length"
      title="没有匹配的策略"
      :description="hasFilter ? '试着放宽筛选条件，或清空搜索关键词' : '还没有策略，点右上角「新建策略」开始接入'"
    >
      <template #action>
        <n-button v-if="hasFilter" size="small" @click="resetFilters">重置筛选</n-button>
      </template>
    </EmptyState>

    <div v-else class="grid grid-2">
      <RunnerCard v-for="runner in filtered" :key="runner.id" :runner="runner" />
    </div>

    <StrategyCreateModal v-model:show="createOpen" @created="load()" />
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
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}
.search {
  width: 220px;
}
.select {
  width: 120px;
}
.select-wide {
  width: 150px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
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
@media (max-width: 899px) {
  .search {
    width: 100%;
  }
  .select,
  .select-wide {
    flex: 1;
    width: auto;
    min-width: 110px;
  }
}
</style>
