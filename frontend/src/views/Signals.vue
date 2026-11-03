<script setup lang="ts">
// Signals.vue — 交易信号：多条件筛选 + 本地排序/分页（一次取全量 ≤200）+ CSV 导出。
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton, NDatePicker, NInput, NSelect, useMessage } from 'naive-ui';
import { ArrowDown, ArrowUp, Download, FilterX, Search } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Runner, Signal, SignalStatus } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { MARKET_LABELS, PLATFORM_OPTIONS, SIGNAL_ACTION_LABELS, STRATEGY_TYPE_OPTIONS } from '@/utils/catalog';
import { fmtDate, fmtDateTime, fmtMoney } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import SectionCard from '@/components/SectionCard.vue';
import SideTag from '@/components/SideTag.vue';
import SignalStatusTag from '@/components/SignalStatusTag.vue';

type SortKey = 'ts' | 'qty' | 'price' | 'amount';

const route = useRoute();
const message = useMessage();
const settings = useSettingsStore();

const HOUR = 3600 * 1000;
const DAY = 24 * HOUR;

const runners = ref<Runner[]>([]);
const items = ref<Signal[]>([]);
const total = ref(0);
const sumAmount = ref('0');
const loading = ref(true);
const error = ref('');
const page = ref(1);
const pageSize = ref(20);
const dateRange = ref<[number, number] | null>(null);
const sortKey = ref<SortKey>('ts');
const sortDir = ref<'asc' | 'desc'>('desc');

const filters = reactive({
  runnerId: '',
  platform: '',
  market: '',
  strategyType: '',
  side: '',
  status: '',
  tag: '',
  instrument: '',
});

const withAll = (label: string, options: { value: string; label: string }[]) => [{ label, value: '' }, ...options];

const runnerOptions = computed(() => withAll('全部策略', runners.value.map((r) => ({ label: r.name, value: r.id }))));
const platformOptions = withAll('全部平台', PLATFORM_OPTIONS);
const marketOptions = withAll('全部市场', (Object.keys(MARKET_LABELS) as (keyof typeof MARKET_LABELS)[])
  .filter((key) => key !== 'HK')
  .map((key) => ({ label: MARKET_LABELS[key], value: key })));
const strategyTypeOptions = withAll('全部类型', STRATEGY_TYPE_OPTIONS);
const sideOptions = withAll('全部方向', [{ label: '买入', value: 'buy' }, { label: '卖出', value: 'sell' }]);
const statusOptions: { label: string; value: '' | SignalStatus }[] = [
  { label: '全部状态', value: '' },
  { label: '已执行', value: 'filled' },
  { label: '待执行', value: 'pending' },
  { label: '已忽略', value: 'ignored' },
];
const tagOptions = computed(() => {
  const tags = new Set<string>();
  runners.value.forEach((r) => r.tags.forEach((tag) => tags.add(tag)));
  return withAll('全部标签', [...tags].sort().map((tag) => ({ label: tag, value: tag })));
});

const hasFilter = computed(
  () => !!(filters.runnerId || filters.platform || filters.market || filters.strategyType
    || filters.side || filters.status || filters.tag || filters.instrument || dateRange.value),
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
const sumQty = computed(() => sortedItems.value.reduce((sum, s) => sum + Number(s.qty), 0));

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
      platform: filters.platform || undefined,
      market: filters.market || undefined,
      strategy_type: filters.strategyType || undefined,
      side: filters.side || undefined,
      status: filters.status || undefined,
      tag: filters.tag || undefined,
      instrument: filters.instrument.trim() || undefined,
      from: dateRange.value ? new Date(shanghaiDayStart(dateRange.value[0])).toISOString() : undefined,
      to: dateRange.value ? new Date(shanghaiDayStart(dateRange.value[1]) + DAY - 1).toISOString() : undefined,
      limit: 200,
      cursor: 0,
    };
    const [signalsRes, runnersRes] = await Promise.all([
      api.signals(query),
      runners.value.length ? Promise.resolve({ items: runners.value }) : api.runners(),
    ]);
    items.value = signalsRes.items;
    total.value = signalsRes.total;
    sumAmount.value = signalsRes.sum_amount;
    runners.value = runnersRes.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '信号加载失败';
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
  filters.platform = '';
  filters.market = '';
  filters.strategyType = '';
  filters.side = '';
  filters.status = '';
  filters.tag = '';
  filters.instrument = '';
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
    message.warning('当前筛选条件下没有可导出的信号');
    return;
  }
  const header = ['时间(Asia/Shanghai)', '信号ID', '策略', '平台', '市场', '品种', '品种名称', '方向', '动作', '数量', '参考价', '金额', '状态', '标签'];
  const rows = sortedItems.value.map((s) => [
    fmtDateTime(s.ts), s.id, s.runner_name, s.platform_label, s.market_label, s.instrument, s.instrument_name,
    s.side === 'buy' ? '买入' : '卖出', SIGNAL_ACTION_LABELS[s.action],
    s.qty, s.price, s.amount,
    s.status === 'filled' ? '已执行' : s.status === 'pending' ? '待执行' : '已忽略',
    s.tags.join(' / '),
  ]);
  const csv = '\uFEFF' + [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'qwatch-signals-' + fmtDate(new Date().toISOString()).replace(/-/g, '') + '.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  message.success('已导出 ' + rows.length + ' 条信号（CSV）');
}

watch(
  () => [filters.runnerId, filters.platform, filters.market, filters.strategyType, filters.side, filters.status, filters.tag, filters.instrument, dateRange.value],
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
  load();
});

onBeforeUnmount(() => window.clearTimeout(debounceTimer));
</script>

<template>
  <div class="page">
    <PageHeader title="交易信号" subtitle="跨策略 / 平台 / 市场 / 类型 / 标签的信号流水 · Asia/Shanghai">
      <template #extra>
        <n-button size="small" @click="exportCsv">
          <template #icon><Download :size="14" /></template>
          导出 CSV
        </n-button>
      </template>
    </PageHeader>

    <section class="card filter-bar">
      <div class="filters">
        <n-select v-model:value="filters.runnerId" :options="runnerOptions" size="small" class="f-select" />
        <n-select v-model:value="filters.platform" :options="platformOptions" size="small" class="f-select-sm" />
        <n-select v-model:value="filters.market" :options="marketOptions" size="small" class="f-select-sm" />
        <n-select v-model:value="filters.strategyType" :options="strategyTypeOptions" size="small" class="f-select-sm" />
        <n-select v-model:value="filters.side" :options="sideOptions" size="small" class="f-select-xs" />
        <n-select v-model:value="filters.status" :options="statusOptions" size="small" class="f-select-xs" />
        <n-select v-model:value="filters.tag" :options="tagOptions" size="small" class="f-select-sm" />
        <n-input v-model:value="filters.instrument" clearable placeholder="品种代码，如 rb2601" size="small" class="f-input">
          <template #prefix><Search :size="13" /></template>
        </n-input>
        <n-date-picker v-model:value="dateRange" type="daterange" size="small" clearable class="f-date" />
        <button v-if="hasFilter" type="button" class="reset" @click="resetFilters">
          <FilterX :size="13" /> 清空
        </button>
      </div>
      <div class="summary">
        <span class="muted">命中 <span class="num">{{ total }}</span> 条</span>
        <span class="muted">数量合计 <span class="num">{{ sumQty }}</span></span>
        <span class="muted">金额合计 <span class="num">¥{{ fmtMoney(sumAmount) }}</span></span>
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
        title="没有匹配的信号"
        :description="hasFilter ? '调整筛选条件或清空后重试' : '策略上报交易信号后会出现在这里'"
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
              <th>平台</th>
              <th>市场</th>
              <th>品种</th>
              <th>方向</th>
              <th>动作</th>
              <th class="th-num sortable" @click="toggleSort('price')">参考价 <span class="sort">{{ sortIcon('price') }}</span></th>
              <th class="th-num sortable" @click="toggleSort('qty')">数量 <span class="sort">{{ sortIcon('qty') }}</span></th>
              <th class="th-num sortable" @click="toggleSort('amount')">金额 <span class="sort">{{ sortIcon('amount') }}</span></th>
              <th>状态</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="signal in pageRows" :key="signal.id" :class="{ 'row-ignored': signal.status === 'ignored' }">
              <td class="mono nowrap" :title="signal.ts">{{ fmtDateTime(signal.ts) }}</td>
              <td class="truncate cell-strong"><router-link :to="'/strategies/' + signal.runner_id" class="cell-link">{{ signal.runner_name }}</router-link></td>
              <td class="muted nowrap">{{ signal.platform_label || '—' }}</td>
              <td class="muted nowrap">{{ signal.market_label }}</td>
              <td>
                <span class="mono">{{ signal.instrument }}</span>
                <span class="inst">{{ signal.instrument_name }}</span>
              </td>
              <td><SideTag :side="signal.side" /></td>
              <td class="muted nowrap">{{ SIGNAL_ACTION_LABELS[signal.action] }}</td>
              <td class="td-num">{{ signal.price }}</td>
              <td class="td-num">{{ signal.qty }}</td>
              <td class="td-num">{{ fmtMoney(signal.amount) }}</td>
              <td><SignalStatusTag :status="signal.status" /></td>
              <td class="truncate muted" :title="signal.msg || ''">{{ signal.msg || '—' }}</td>
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
  width: 140px;
}
.f-select-sm {
  width: 108px;
}
.f-select-xs {
  width: 96px;
}
.f-input {
  width: 170px;
}
.f-date {
  width: 230px;
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
.cell-link {
  color: var(--text);
}
.cell-link:hover {
  color: var(--primary);
}
.row-ignored td {
  opacity: 0.62;
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
  .f-select-sm,
  .f-select-xs {
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
    flex-wrap: wrap;
  }
}
@media (max-width: 639px) {
  .filters {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
