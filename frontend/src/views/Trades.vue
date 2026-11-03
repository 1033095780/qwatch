<script setup lang="ts">
// Trades.vue — 交易流水：多条件筛选 + 本地排序/分页（一次取全量 ≤200）+ CSV 导出。
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton, NDatePicker, NInput, NSelect, useMessage } from 'naive-ui';
import { ArrowDown, ArrowUp, Download, FilterX, RefreshCw, Search } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Fill, Runner } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDate, fmtDateTime, fmtMoney } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import SectionCard from '@/components/SectionCard.vue';

type SortKey = 'ts' | 'qty' | 'price' | 'amount' | 'fee';

const route = useRoute();
const message = useMessage();
const settings = useSettingsStore();

const HOUR = 3600 * 1000;
const DAY = 24 * HOUR;

const runners = ref<Runner[]>([]);
const accounts = ref<Account[]>([]);
const items = ref<Fill[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref('');
const page = ref(1);
const pageSize = ref(20);
const dateRange = ref<[number, number] | null>(null);
const sortKey = ref<SortKey>('ts');
const sortDir = ref<'asc' | 'desc'>('desc');

const filters = reactive({
  runnerId: '',
  accountId: '',
  market: '',
  instrument: '',
  side: '',
});

const runnerOptions = computed(() => [
  { label: '全部策略', value: '' },
  ...runners.value.map((r) => ({ label: r.name, value: r.id })),
]);
const accountOptions = computed(() => [
  { label: '全部账户', value: '' },
  ...accounts.value.map((a) => ({ label: a.name, value: a.id })),
]);
const marketOptions = [
  { label: '全部市场', value: '' },
  { label: 'A股', value: 'CN_A' },
  { label: '期货', value: 'CN_FUT' },
];
const sideOptions = [
  { label: '全部方向', value: '' },
  { label: '买入', value: 'buy' },
  { label: '卖出', value: 'sell' },
];

const hasFilter = computed(
  () => !!(filters.runnerId || filters.accountId || filters.market || filters.instrument || filters.side || dateRange.value),
);

const sortedItems = computed(() => {
  const dir = sortDir.value === 'asc' ? 1 : -1;
  return [...items.value].sort((a, b) => {
    if (sortKey.value === 'ts') return (Date.parse(a.ts) - Date.parse(b.ts)) * dir;
    return (Number(a[sortKey.value]) - Number(b[sortKey.value])) * dir;
  });
});
const pageCount = computed(() => Math.max(1, Math.ceil(sortedItems.value.length / pageSize.value)));
const pageRows = computed(() =>
  sortedItems.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value),
);
const sumAmount = computed(() => sortedItems.value.reduce((sum, f) => sum + Number(f.amount), 0));

function shanghaiDayStart(ms: number): number {
  const d = new Date(ms + 8 * HOUR);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - 8 * HOUR;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const query = {
      runner_id: filters.runnerId || undefined,
      account_id: filters.accountId || undefined,
      market: filters.market || undefined,
      instrument: filters.instrument.trim() || undefined,
      side: filters.side || undefined,
      from: dateRange.value ? new Date(shanghaiDayStart(dateRange.value[0])).toISOString() : undefined,
      to: dateRange.value ? new Date(shanghaiDayStart(dateRange.value[1]) + DAY - 1).toISOString() : undefined,
      limit: 200,
      cursor: 0,
    };
    const [fillsRes, runnersRes, accountsRes] = await Promise.all([
      api.fills(query),
      runners.value.length ? Promise.resolve({ items: runners.value }) : api.runners(),
      accounts.value.length ? Promise.resolve({ items: accounts.value }) : api.accounts(),
    ]);
    items.value = fillsRes.items;
    total.value = fillsRes.total;
    runners.value = runnersRes.items;
    accounts.value = accountsRes.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '成交加载失败';
  } finally {
    loading.value = false;
  }
}

let debounceTimer: number | undefined;
function scheduleLoad(): void {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => {
    page.value = 1;
    load();
  }, 260);
}

function toggleSort(key: SortKey): void {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc';
  } else {
    sortKey.value = key;
    sortDir.value = 'desc';
  }
  page.value = 1;
}

function sortIcon(key: SortKey): string {
  if (sortKey.value !== key) return '';
  return sortDir.value === 'desc' ? '↓' : '↑';
}

function resetFilters(): void {
  filters.runnerId = '';
  filters.accountId = '';
  filters.market = '';
  filters.instrument = '';
  filters.side = '';
  dateRange.value = null;
  page.value = 1;
  load();
}

function csvCell(value: string | number): string {
  const s = String(value ?? '');
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function exportCsv(): void {
  if (!sortedItems.value.length) {
    message.warning('当前筛选条件下没有可导出的成交');
    return;
  }
  const header = ['时间(Asia/Shanghai)', '成交ID', '策略', '账户', '品种', '品种名称', '方向', '开平', '数量', '价格', '金额', '手续费', '币种', '状态'];
  const rows = sortedItems.value.map((f) => [
    fmtDateTime(f.ts), f.id, f.runner_name, f.account_name, f.instrument, f.instrument_name,
    f.side === 'buy' ? '买入' : '卖出', f.position_effect === 'open' ? '开仓' : '平仓',
    f.qty, f.price, f.amount, f.fee, f.currency, f.status === 'filled' ? '已成交' : '部分成交',
  ]);
  const csv = '\uFEFF' + [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'qwatch-fills-' + fmtDate(new Date().toISOString()).replace(/-/g, '') + '.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  message.success('已导出 ' + rows.length + ' 笔成交（CSV）');
}

watch(
  () => [filters.runnerId, filters.accountId, filters.market, filters.side, filters.instrument, dateRange.value],
  scheduleLoad,
  { deep: true },
);
watch(pageSize, () => {
  page.value = 1;
});
watch(() => settings.refreshSeq, load);
watch(pageCount, () => {
  if (page.value > pageCount.value) page.value = pageCount.value;
});

onMounted(() => {
  const qRunner = route.query.runner_id;
  if (typeof qRunner === 'string') filters.runnerId = qRunner;
  const qAccount = route.query.account_id;
  if (typeof qAccount === 'string') filters.accountId = qAccount;
  load();
});

onBeforeUnmount(() => window.clearTimeout(debounceTimer));
</script>

<template>
  <div class="page">
    <PageHeader title="交易流水" subtitle="跨策略 / 账户 / 市场的成交事实 · 时间统一 Asia/Shanghai（tooltip 显示 UTC）">
      <template #extra>
        <n-button size="small" @click="exportCsv">
          <template #icon><Download :size="14" /></template>
          导出 CSV
        </n-button>
        <n-button size="small" :loading="loading" @click="load">
          <template #icon><RefreshCw :size="14" /></template>
          刷新
        </n-button>
      </template>
    </PageHeader>

    <section class="card filter-bar">
      <div class="filters">
        <n-select v-model:value="filters.runnerId" :options="runnerOptions" size="small" class="f-select" />
        <n-select v-model:value="filters.accountId" :options="accountOptions" size="small" class="f-select" />
        <n-select v-model:value="filters.market" :options="marketOptions" size="small" class="f-select-sm" />
        <n-select v-model:value="filters.side" :options="sideOptions" size="small" class="f-select-sm" />
        <n-input v-model:value="filters.instrument" clearable placeholder="品种代码，如 rb2601" size="small" class="f-input">
          <template #prefix><Search :size="13" /></template>
        </n-input>
        <n-date-picker v-model:value="dateRange" type="daterange" size="small" clearable class="f-date" />
        <button v-if="hasFilter" type="button" class="reset" @click="resetFilters">
          <FilterX :size="13" /> 清空
        </button>
      </div>
      <div class="summary">
        <span class="muted">命中 <span class="num">{{ total }}</span> 笔</span>
        <span class="muted">成交额 <span class="num">¥{{ fmtMoney(sumAmount) }}</span></span>
      </div>
    </section>

    <div v-if="error" class="error-bar">
      <span class="dot" />{{ error }}
      <n-button text size="tiny" @click="load">重试</n-button>
    </div>

    <SectionCard flush>
      <div v-if="loading && !items.length" class="loading-pad">
        <div v-for="i in 8" :key="i" class="skel skel-line" style="margin-bottom: 12px; height: 30px" />
      </div>
      <EmptyState
        v-else-if="!sortedItems.length && !loading"
        title="没有匹配的成交"
        :description="hasFilter ? '调整筛选条件或清空后重试' : '策略尚未上报成交事件'"
      >
        <template #action>
          <n-button v-if="hasFilter" size="small" @click="resetFilters">清空筛选</n-button>
        </template>
      </EmptyState>
      <div v-else class="tbl-wrap">
        <div class="swipe-hint">左右滑动查看完整列 →</div>
        <table class="tbl">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('ts')">时间 <span class="sort">{{ sortIcon('ts') }}</span></th>
              <th>策略</th>
              <th>账户</th>
              <th>品种</th>
              <th>方向</th>
              <th>开平</th>
              <th class="th-num sortable" @click="toggleSort('qty')">数量 <span class="sort">{{ sortIcon('qty') }}</span></th>
              <th class="th-num sortable" @click="toggleSort('price')">价格 <span class="sort">{{ sortIcon('price') }}</span></th>
              <th class="th-num sortable" @click="toggleSort('amount')">金额 <span class="sort">{{ sortIcon('amount') }}</span></th>
              <th class="th-num sortable" @click="toggleSort('fee')">手续费 <span class="sort">{{ sortIcon('fee') }}</span></th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fill in pageRows" :key="fill.id">
              <td class="mono nowrap" :title="fill.ts">{{ fmtDateTime(fill.ts) }}</td>
              <td class="truncate cell-strong">{{ fill.runner_name }}</td>
              <td class="truncate muted">{{ fill.account_name }}</td>
              <td>
                <span class="mono">{{ fill.instrument }}</span>
                <span class="inst">{{ fill.instrument_name }}</span>
              </td>
              <td><span class="side" :class="fill.side">{{ fill.side === 'buy' ? '买入' : '卖出' }}</span></td>
              <td class="muted">{{ fill.position_effect === 'open' ? '开仓' : '平仓' }}</td>
              <td class="td-num">{{ fill.qty }}</td>
              <td class="td-num">{{ fill.price }}</td>
              <td class="td-num">{{ fmtMoney(fill.amount) }}</td>
              <td class="td-num faint">{{ fmtMoney(fill.fee) }}</td>
              <td>
                <span class="fill-status" :class="fill.status">{{ fill.status === 'filled' ? '已成交' : '部分成交' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="sortedItems.length" class="pager">
        <span class="pager-info mono">
          {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, sortedItems.length) }} / {{ sortedItems.length }} 条
        </span>
        <div class="pager-controls">
          <n-select v-model:value="pageSize" :options="[{ label: '20 条/页', value: 20 }, { label: '50 条/页', value: 50 }, { label: '100 条/页', value: 100 }]" size="tiny" style="width: 104px" />
          <n-button size="tiny" :disabled="page <= 1" @click="page--">
            <template #icon><ArrowUp :size="13" style="transform: rotate(-90deg)" /></template>
            上一页
          </n-button>
          <span class="page-num mono">{{ page }} / {{ pageCount }}</span>
          <n-button size="tiny" :disabled="page >= pageCount" @click="page++">
            下一页
            <template #icon><ArrowDown :size="13" style="transform: rotate(-90deg)" /></template>
          </n-button>
        </div>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
}
.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}
.f-select {
  width: 150px;
}
.f-select-sm {
  width: 112px;
}
.f-input {
  width: 180px;
}
.f-date {
  width: 240px;
}
.reset {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
  padding: 0 2px;
}
.reset:hover {
  color: var(--primary);
}
.summary {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 11px;
  white-space: nowrap;
}
.loading-pad {
  padding: 20px;
}
.sort {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--primary);
  margin-left: 2px;
}
.inst {
  display: block;
  font-size: 10px;
  color: var(--text-3);
  line-height: 1.2;
}
.side {
  display: inline-flex;
  height: 19px;
  align-items: center;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
}
.side.buy {
  color: var(--up);
  background: color-mix(in srgb, var(--up) 12%, transparent);
}
.side.sell {
  color: var(--down);
  background: color-mix(in srgb, var(--down) 12%, transparent);
}
.fill-status {
  font-size: 11px;
}
.fill-status.filled {
  color: #2ecc8f;
}
.fill-status.partial {
  color: #f5a524;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.pager-info {
  font-size: 11px;
  color: var(--text-3);
}
.pager-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}
.page-num {
  font-size: 11px;
  color: var(--text-2);
  padding: 0 4px;
}
.swipe-hint {
  display: none;
  padding: 8px 12px 0;
  font-size: 11px;
  color: var(--text-3);
}
@media (max-width: 639px) {
  .swipe-hint {
    display: block;
  }
}
@media (max-width: 899px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .filters {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
    gap: 8px;
  }
  .f-select,
  .f-select-sm {
    width: 100%;
    min-width: 0;
  }
  .f-input,
  .f-date {
    grid-column: 1 / -1;
    width: 100%;
    min-width: 0;
  }
  .reset {
    justify-self: start;
  }
  .summary {
    justify-content: space-between;
    width: 100%;
  }
}
@media (max-width: 639px) {
  .filters {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
