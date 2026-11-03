<script setup lang="ts">
// Reports.vue — 日报：7 天列表 + 抽屉详情（摘要 + 策略明细）。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NDrawer, NDrawerContent, useMessage } from 'naive-ui';
import { ChevronRight, FileText, RefreshCw } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Report, ReportSummary } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDate, fmtDateTime, fmtMoney, fmtPct } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import PnlText from '@/components/PnlText.vue';
import SectionCard from '@/components/SectionCard.vue';
import StatusDot from '@/components/StatusDot.vue';

const settings = useSettingsStore();
const message = useMessage();

const reports = ref<ReportSummary[]>([]);
const loading = ref(true);
const error = ref('');
const drawerOpen = ref(false);
const detail = ref<Report | null>(null);
const detailLoading = ref(false);
const detailError = ref('');

const totalPnl = computed(() => reports.value.reduce((sum, r) => sum + Number(r.today_pnl), 0));
const avgTrades = computed(() => (reports.value.length ? Math.round(reports.value.reduce((sum, r) => sum + r.trades, 0) / reports.value.length) : 0));
const totalAlerts = computed(() => reports.value.reduce((sum, r) => sum + r.alerts, 0));
const okCount = computed(() => reports.value.filter((r) => r.status === 'ok').length);

const drawerWidth = computed(() => (typeof window !== 'undefined' && window.innerWidth < 640 ? '92vw' : 'min(560px, 92vw)'));

function weekday(ts: string): string {
  const days = ['日', '一', '二', '三', '四', '五', '六'];
  return '周' + days[new Date(ts + 'T00:00:00+08:00').getDay()];
}

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const res = await api.reports();
    reports.value = res.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '日报加载失败';
  } finally {
    loading.value = false;
  }
}

async function openReport(summary: ReportSummary): Promise<void> {
  drawerOpen.value = true;
  detail.value = null;
  detailError.value = '';
  detailLoading.value = true;
  try {
    detail.value = await api.report(summary.date);
  } catch (err) {
    detailError.value = err instanceof Error ? err.message : '日报详情加载失败';
  } finally {
    detailLoading.value = false;
  }
}

function copySummary(): void {
  if (!detail.value) return;
  const report = detail.value;
  const lines = [
    'qwatch 日报 ' + report.date,
    '总权益 ¥' + fmtMoney(report.total_equity) + ' · 当日盈亏 ' + fmtPct(report.today_pnl_pct) + '（¥' + fmtMoney(report.today_pnl) + '）',
    '成交 ' + report.trades + ' 笔 · 告警 ' + report.alerts + ' 条',
    '— 策略明细 —',
    ...report.strategies.map((s) => s.name + '：' + fmtPct(s.pct) + ' · 成交 ' + s.trades + ' 笔 · 回撤 ' + s.drawdown + '%'),
  ].join('\n');
  navigator.clipboard.writeText(lines)
    .then(() => message.success('日报摘要已复制'))
    .catch(() => message.error('复制失败'));
}

watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <PageHeader title="日报" :subtitle="'收盘复盘 · 最近 7 个交易日 · 生成时间按 Asia/Shanghai'">
      <template #extra>
        <span class="chip"><FileText :size="12" /> 每日 15:30 生成</span>
        <n-button size="small" :loading="loading" @click="load()">
          <template #icon><RefreshCw :size="14" /></template>
          刷新
        </n-button>
      </template>
    </PageHeader>

    <div v-if="loading && !reports.length" class="page">
      <div class="grid grid-kpi">
        <div v-for="i in 4" :key="i" class="skel skel-card" style="min-height: 120px" />
      </div>
      <div class="skel" style="height: 380px; border-radius: 12px" />
    </div>

    <div v-else-if="error && !reports.length" class="card">
      <EmptyState title="日报加载失败" :description="error">
        <template #action><n-button size="small" @click="load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else>
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div class="grid grid-kpi">
        <div class="card stat">
          <span class="kpi-label">7 日盈亏</span>
          <PnlText :value="totalPnl" size="lg" bold />
          <span class="faint">最近 7 个交易日累计</span>
        </div>
        <div class="card stat">
          <span class="kpi-label">日均成交</span>
          <span class="stat-value num">{{ avgTrades }} 笔</span>
          <span class="faint">按日报口径统计</span>
        </div>
        <div class="card stat">
          <span class="kpi-label">告警总数</span>
          <span class="stat-value num">{{ totalAlerts }} 条</span>
          <span class="faint">含已恢复告警</span>
        </div>
        <div class="card stat">
          <span class="kpi-label">日报状态</span>
          <span class="stat-value num">{{ okCount }} / {{ reports.length }}</span>
          <span class="faint">正常生成天数</span>
        </div>
      </div>

      <SectionCard title="日报列表" subtitle="点击查看当日摘要与策略明细" flush>
        <div class="report-list">
          <button
            v-for="report in reports"
            :key="report.date"
            type="button"
            class="report-row"
            @click="openReport(report)"
          >
            <div class="date-block">
              <span class="date mono">{{ fmtDate(report.date) }}</span>
              <span class="weekday">{{ weekday(report.date) }}</span>
            </div>
            <div class="status-block">
              <StatusDot :status="report.status === 'ok' ? 'ok' : 'warn'" :size="7" />
              <span class="status-text">{{ report.status === 'ok' ? '正常' : '有告警' }}</span>
            </div>
            <div class="pnl-block">
              <PnlText :value="report.today_pnl" :pct="report.today_pnl_pct" show-pct size="sm" bold />
            </div>
            <div class="equity-block">
              <span class="k">权益</span>
              <span class="v num">¥{{ fmtMoney(report.total_equity) }}</span>
            </div>
            <div class="counts">
              <span class="chip">{{ report.trades }} 笔成交</span>
              <span class="chip" :class="{ warn: report.alerts > 0 }">{{ report.alerts }} 条告警</span>
            </div>
            <ChevronRight :size="15" class="chev" />
          </button>
          <EmptyState v-if="!reports.length" compact title="暂无日报" description="收盘后会自动生成当日日报" />
        </div>
      </SectionCard>
    </template>

    <n-drawer v-model:show="drawerOpen" placement="right" :width="drawerWidth">
      <n-drawer-content closable>
        <template #header>
          <div class="drawer-title">
            日报 <span class="mono">{{ detail ? detail.date : '…' }}</span>
          </div>
        </template>
        <div v-if="detailLoading" class="drawer-loading">
          <div v-for="i in 5" :key="i" class="skel skel-line" style="height: 28px; margin-bottom: 12px" />
        </div>
        <div v-else-if="detailError" class="error-bar">
          <span class="dot" />{{ detailError }}
        </div>
        <template v-else-if="detail">
          <div class="drawer-kpis">
            <div class="dk"><span class="k">总权益</span><span class="v num">¥{{ fmtMoney(detail.total_equity) }}</span></div>
            <div class="dk">
              <span class="k">当日盈亏</span>
              <PnlText :value="detail.today_pnl" :pct="detail.today_pnl_pct" show-pct size="md" bold />
            </div>
            <div class="dk"><span class="k">成交笔数</span><span class="v num">{{ detail.trades }}</span></div>
            <div class="dk"><span class="k">告警</span><span class="v num">{{ detail.alerts }}</span></div>
          </div>
          <div class="drawer-actions">
            <n-button size="small" @click="copySummary">复制摘要</n-button>
            <span class="faint mono">生成于 {{ fmtDateTime(detail.date + 'T15:30:00+08:00') }} CST</span>
          </div>
          <h3 class="drawer-sub">策略明细</h3>
          <div class="tbl-wrap">
            <table class="tbl tbl--compact">
              <thead>
                <tr><th>策略</th><th class="th-num">盈亏</th><th class="th-num">收益率</th><th class="th-num">成交</th><th class="th-num">回撤</th></tr>
              </thead>
              <tbody>
                <tr v-for="s in detail.strategies" :key="s.runner_id">
                  <td class="truncate">{{ s.name }}</td>
                  <td class="td-num"><PnlText :value="s.pnl" size="sm" /></td>
                  <td class="td-num"><PnlText :value="s.pct" :money="false" size="sm" /></td>
                  <td class="td-num">{{ s.trades }}</td>
                  <td class="td-num faint">{{ s.drawdown }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="drawer-note">
            日报由后端在收盘后生成，经钉钉推送，并支持按策略/账户归因。
          </p>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.stat {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-height: 120px;
}
.stat-value {
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
}
.report-list {
  display: flex;
  flex-direction: column;
}
.report-row {
  display: flex;
  align-items: center;
  gap: 18px;
  width: 100%;
  padding: 14px 20px;
  border: 0;
  border-bottom: 1px solid rgba(30, 38, 55, 0.65);
  background: transparent;
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: background-color 150ms ease;
}
.report-row:last-of-type {
  border-bottom: none;
}
.report-row:hover {
  background: rgba(21, 28, 44, 0.7);
}
.date-block {
  display: flex;
  flex-direction: column;
  min-width: 104px;
}
.date {
  font-size: 13px;
  font-weight: 500;
}
.weekday {
  font-size: 10px;
  color: var(--text-3);
}
.status-block {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 72px;
}
.status-text {
  font-size: 11px;
  color: var(--text-2);
}
.pnl-block {
  min-width: 150px;
}
.equity-block {
  display: flex;
  flex-direction: column;
  min-width: 130px;
}
.equity-block .k {
  font-size: 10px;
  color: var(--text-3);
}
.equity-block .v {
  font-size: 12px;
  color: var(--text-2);
}
.counts {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.counts .chip.warn {
  color: #f5b64b;
  border-color: rgba(245, 165, 36, 0.26);
}
.chev {
  color: var(--text-3);
  flex: none;
}
.report-row:hover .chev {
  color: var(--primary);
}
.drawer-title {
  font-size: 15px;
}
.drawer-loading {
  padding: 8px 0;
}
.drawer-kpis {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.dk {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(21, 28, 44, 0.5);
}
.dk .k {
  font-size: 10px;
  color: var(--text-3);
}
.dk .v {
  font-size: 16px;
  font-weight: 600;
}
.drawer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0 6px;
  flex-wrap: wrap;
}
.drawer-sub {
  margin: 14px 0 8px;
  font-size: 13px;
  font-weight: 600;
}
.drawer-note {
  margin-top: 18px;
  font-size: 11px;
  line-height: 1.75;
  color: var(--text-3);
}
@media (max-width: 1023px) {
  .report-row {
    gap: 12px;
    flex-wrap: wrap;
    padding: 14px 16px;
  }
  .counts {
    margin-left: 0;
  }
}
@media (max-width: 639px) {
  .equity-block {
    min-width: 0;
  }
  .pnl-block {
    min-width: 0;
  }
}
</style>
