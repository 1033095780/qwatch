<script setup lang="ts">
// StrategyDetail.vue — 策略详情：状态头、6 KPI、Tabs（净值/信号/持仓/心跳/告警/配置）。
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton } from 'naive-ui';
import { ArrowUpRight, KeyRound } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { RangeKey, RunnerDetail } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { MARKET_LABELS, SIGNAL_ACTION_LABELS } from '@/utils/catalog';
import {
  fmtDateTime, fmtDuration, fmtFullDateTime, fmtMoney, fmtPct, fmtUtc, fromNow, pnlClass,
} from '@/utils/format';
import DrawdownChart from '@/components/DrawdownChart.vue';
import EmptyState from '@/components/EmptyState.vue';
import EquityChart from '@/components/EquityChart.vue';
import HeartbeatBar from '@/components/HeartbeatBar.vue';
import MetricCard from '@/components/MetricCard.vue';
import PageHeader from '@/components/PageHeader.vue';
import RangeTabs from '@/components/RangeTabs.vue';
import SectionCard from '@/components/SectionCard.vue';
import SeverityTag from '@/components/SeverityTag.vue';
import SideTag from '@/components/SideTag.vue';
import SignalStatusTag from '@/components/SignalStatusTag.vue';
import StrategyTokenModal from '@/components/StrategyTokenModal.vue';
import StatusTag from '@/components/StatusTag.vue';
import MarketTag from '@/components/MarketTag.vue';
import TabBar from '@/components/TabBar.vue';
import type { TabItem } from '@/components/TabBar.vue';

const route = useRoute();
const settings = useSettingsStore();

const runnerId = computed(() => String(route.params.id || ''));
const detail = ref<RunnerDetail | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref('');
const range = ref<RangeKey>('all');
const activeTab = ref('equity');
const tokenOpen = ref(false);

const neverReported = computed(() => {
  const ts = detail.value ? Date.parse(detail.value.runner.last_heartbeat) : NaN;
  return !Number.isFinite(ts) || Date.now() - ts > 24 * 3600 * 1000;
});

const tabs = computed<TabItem[]>(() => [
  { key: 'equity', label: '净值' },
  { key: 'signals', label: '信号', count: detail.value?.signals.length ?? 0 },
  { key: 'heartbeat', label: '心跳' },
  { key: 'alerts', label: '告警', count: detail.value?.alerts.length ?? 0 },
  { key: 'config', label: '配置' },
]);

const periodReturn = computed(() => {
  const curve = detail.value?.equity ?? [];
  if (curve.length < 2) return null;
  const first = Number(curve[0].value);
  const last = Number(curve[curve.length - 1].value);
  return first > 0 ? ((last - first) / first) * 100 : null;
});

const runningOutage = computed(() => detail.value?.outages.find((o) => !o.end) ?? null);

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  else refreshing.value = true;
  error.value = '';
  try {
    detail.value = await api.runner(runnerId.value, range.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '策略详情加载失败';
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

watch(range, () => load());
watch(() => settings.refreshSeq, () => load());

onMounted(() => load(true));
</script>

<template>
  <div class="page">
    <div v-if="loading && !detail" class="page">
      <div class="skel skel-line" style="width: 180px; height: 12px" />
      <div class="skel skel-line" style="width: 320px; height: 28px" />
      <div class="stats-grid">
        <div v-for="i in 6" :key="i" class="skel" style="height: 104px; border-radius: 12px" />
      </div>
      <div class="skel" style="height: 420px; border-radius: 12px" />
    </div>

    <div v-else-if="error && !detail" class="card">
      <EmptyState title="策略详情加载失败" :description="error">
        <template #action>
          <n-button size="small" @click="load(true)">重新加载</n-button>
        </template>
      </EmptyState>
    </div>

    <template v-else-if="detail">
      <PageHeader
        :title="detail.runner.name"
        :subtitle="(detail.runner.description || '策略归因口径') + ' · ' + (neverReported ? '尚未接入，等待第一次心跳' : '最后心跳 ' + fromNow(detail.runner.last_heartbeat))"
        back-to="/strategies"
        back-label="策略列表"
      >
        <template #extra>
          <StatusTag :status="detail.runner.status" />
          <MarketTag :market="detail.runner.market" />
          <n-button size="small" @click="tokenOpen = true">
            <template #icon><KeyRound :size="13" /></template>
            接入令牌
          </n-button>
          <n-button size="small" tag="a" :href="'/signals?runner_id=' + detail.runner.id" @click.prevent="$router.push('/signals?runner_id=' + detail.runner.id)">
            <template #icon><ArrowUpRight :size="13" /></template>
            查看信号
          </n-button>
        </template>
      </PageHeader>

      <div v-if="error" class="error-bar">
        <span class="dot" />{{ error }}
        <n-button text size="tiny" @click="load(true)">重试</n-button>
      </div>

      <div class="stats-grid">
        <MetricCard label="总权益" :value="'¥' + fmtMoney(detail.runner.equity)" sub="策略归因口径" />
        <MetricCard label="今日盈亏" :value="'¥' + fmtMoney(detail.metrics.today_pnl)" :change="detail.metrics.today_pnl" :change-pct="detail.runner.today_pnl_pct" sub="今日" />
        <MetricCard label="累计收益" :value="fmtPct(detail.metrics.total_return_pct)" :change="detail.metrics.total_return_pct" :change-pct="null" sub="策略归因口径" />
        <MetricCard
          label="心跳"
          :value="neverReported ? '尚未上报' : fromNow(detail.runner.last_heartbeat)"
          :sub="neverReported ? '等待第一次心跳' : '间隔 ' + detail.config.heartbeat_interval_s + 's'"
        />
        <MetricCard label="夏普" :value="detail.metrics.sharpe" sub="近 180 个交易日 · 年化" />
        <MetricCard label="最大回撤" :value="fmtPct(detail.metrics.max_drawdown_pct, 2, false)" sub="峰值回落" />
        <MetricCard label="日胜率" :value="detail.metrics.win_rate_pct + '%'" sub="近 30 个交易日" />
        <MetricCard label="盈亏比" :value="detail.metrics.profit_factor" sub="总盈利 / 总亏损" />
      </div>

      <section class="card tabs-card">
        <TabBar v-model="activeTab" :tabs="tabs" />

        <div v-show="activeTab === 'equity'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">净值与回撤</h2>
              <p class="panel-sub">策略归因口径（非资金曲线）· Asia/Shanghai</p>
            </div>
            <RangeTabs v-model="range" />
          </div>
          <div :class="{ dimmed: refreshing }">
            <EquityChart :data="detail.equity" :height="300" value-label="策略净值" />
            <div class="dd-head">
              <span class="eyebrow">回撤</span>
              <span v-if="periodReturn !== null" class="muted">
                区间收益 <span class="num" :class="pnlClass(periodReturn)">{{ fmtPct(periodReturn) }}</span>
              </span>
              <span class="spacer" />
              <span class="muted mono">{{ range.toUpperCase() }}</span>
            </div>
            <DrawdownChart :data="detail.drawdown" :height="132" />
          </div>
        </div>

        <div v-show="activeTab === 'signals'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">最近信号</h2>
              <p class="panel-sub">仅展示最近 {{ detail.signals.length }} 条；完整信号流水请到交易信号</p>
            </div>
            <n-button size="small" @click="$router.push('/signals?runner_id=' + detail.runner.id)">全部信号</n-button>
          </div>
          <div v-if="detail.signals.length" class="tbl-wrap">
            <table class="tbl tbl--compact">
              <thead>
                <tr>
                  <th>时间</th><th>品种</th><th>方向</th><th>动作</th>
                  <th class="th-num">数量</th><th class="th-num">参考价</th><th class="th-num">金额</th><th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="signal in detail.signals" :key="signal.id">
                  <td class="mono nowrap">{{ fmtDateTime(signal.ts) }}</td>
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
          <EmptyState v-else compact title="暂无信号" description="该策略近 3 个交易日没有信号记录" />
        </div>

        <div v-show="activeTab === 'heartbeat'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">心跳与可用率</h2>
              <p class="panel-sub">近 24 小时 · 每段 30 分钟 · 非交易时段不判活</p>
            </div>
          </div>
          <HeartbeatBar :segments="detail.heartbeat_timeline" :height="30" />
          <div class="hb-stats">
            <div class="hb-stat"><span class="k">24h 可用率</span><span class="v mono">{{ detail.runner.uptime_24h }}%</span></div>
            <div class="hb-stat"><span class="k">30d 可用率</span><span class="v mono">{{ detail.metrics.uptime_30d }}%</span></div>
            <div class="hb-stat"><span class="k">最后心跳</span><span class="v mono">{{ fmtDateTime(detail.runner.last_heartbeat) }}（{{ fromNow(detail.runner.last_heartbeat) }}）</span></div>
            <div class="hb-stat"><span class="k">心跳间隔 / 软/硬阈值</span><span class="v mono">{{ detail.config.heartbeat_interval_s }}s / {{ detail.config.soft_timeout_s }}s / {{ detail.config.hard_timeout_s }}s</span></div>
            <div v-if="runningOutage" class="hb-stat">
              <span class="k">当前中断</span>
              <span class="v mono">始于 {{ fmtDateTime(runningOutage.start) }} · 持续 {{ fmtDuration(runningOutage.duration_s) }}</span>
            </div>
          </div>
          <h3 class="sub-title">断线记录</h3>
          <div v-if="detail.outages.length" class="tbl-wrap">
            <table class="tbl tbl--compact">
              <thead><tr><th>开始</th><th>结束</th><th class="th-num">时长</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="(outage, i) in detail.outages" :key="i">
                  <td class="mono">{{ fmtFullDateTime(outage.start) }}</td>
                  <td class="mono">{{ outage.end ? fmtFullDateTime(outage.end) : '—' }}</td>
                  <td class="td-num mono">{{ fmtDuration(outage.duration_s) }}</td>
                  <td>
                    <span v-if="!outage.end" class="ongoing">进行中</span>
                    <span v-else class="muted">已恢复</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <EmptyState v-else compact title="近 24 小时无断线" description="心跳稳定，无需处理" />
        </div>

        <div v-show="activeTab === 'alerts'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">告警历史</h2>
              <p class="panel-sub">该 Runner 的全部告警（活跃 + 历史）</p>
            </div>
            <n-button size="small" @click="$router.push('/alerts')">告警中心</n-button>
          </div>
          <div v-if="detail.alerts.length" class="alert-list">
            <div v-for="alert in detail.alerts" :key="alert.id" class="alert-row">
              <SeverityTag :severity="alert.severity" />
              <div class="alert-main">
                <p class="alert-summary">{{ alert.summary }}</p>
                <p class="alert-meta mono">
                  {{ alert.rule }} · 开始 {{ fmtDateTime(alert.starts_at) }}
                  <span v-if="alert.ends_at"> · 结束 {{ fmtDateTime(alert.ends_at) }}</span>
                </p>
              </div>
              <span class="alert-status" :class="alert.status">
                {{ alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复' }}
              </span>
            </div>
          </div>
          <EmptyState v-else compact title="暂无告警" description="该策略近期没有触发任何规则" />
        </div>

        <div v-show="activeTab === 'config'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">策略配置</h2>
              <p class="panel-sub">运行参数与接入信息</p>
            </div>
            <n-button size="small" @click="tokenOpen = true">接入令牌</n-button>
          </div>
          <div class="config-grid">
            <section class="config-block">
              <h3 class="config-title">策略信息</h3>
              <dl class="kv">
                <div class="kv-item"><dt>策略名称</dt><dd>{{ detail.runner.name }}</dd></div>
                <div class="kv-item"><dt>市场</dt><dd>{{ MARKET_LABELS[detail.runner.market] || detail.runner.market }}</dd></div>
                <div class="kv-item"><dt>量化平台</dt><dd>{{ detail.runner.platform_label || detail.runner.platform }}</dd></div>
                <div class="kv-item"><dt>策略类型</dt><dd>{{ detail.runner.strategy_type_label || '—' }}</dd></div>
                <div class="kv-item kv-item--wide"><dt>简介</dt><dd>{{ detail.runner.description || '—' }}</dd></div>
                <div class="kv-item"><dt>创建时间</dt><dd class="mono">{{ fmtFullDateTime(detail.config.started_at) }}</dd></div>
              </dl>
            </section>
            <section class="config-block">
              <h3 class="config-title">运行与接入</h3>
              <dl class="kv">
                <div class="kv-item"><dt>运行实例</dt><dd class="mono">{{ detail.runner.id }}</dd></div>
                <div class="kv-item"><dt>策略标识</dt><dd class="mono">{{ detail.config.strategy }}@{{ detail.config.version }}</dd></div>
                <div class="kv-item"><dt>交易日历</dt><dd class="mono">{{ detail.config.calendar_id }}</dd></div>
                <div class="kv-item"><dt>心跳间隔</dt><dd class="mono">{{ detail.config.heartbeat_interval_s }}s</dd></div>
                <div class="kv-item"><dt>软 / 硬阈值</dt><dd class="mono">{{ detail.config.soft_timeout_s }}s / {{ detail.config.hard_timeout_s }}s</dd></div>
                <div class="kv-item"><dt>最近上报</dt><dd class="mono">{{ fmtUtc(detail.runner.last_heartbeat) }}</dd></div>
              </dl>
            </section>
          </div>
        </div>
      </section>

      <StrategyTokenModal v-model:show="tokenOpen" :runner="detail.runner" />
    </template>
  </div>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: var(--gap);
}
.stats-grid :deep(.kpi-value) {
  font-size: 26px;
}
.tabs-card {
  padding-top: 4px;
}
.tab-panel {
  padding: 16px 0 4px;
}
.dimmed {
  opacity: 0.6;
  transition: opacity 160ms ease;
}
.dd-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 11px;
}
.dd-head .spacer {
  flex: 1;
}
.inst {
  display: block;
  font-size: 10px;
  color: var(--text-3);
  line-height: 1.2;
}
.hb-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0 8px;
}
.hb-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(21, 28, 44, 0.5);
}
.hb-stat .k {
  font-size: 10px;
  color: var(--text-3);
}
.hb-stat .v {
  font-size: 12px;
  color: var(--text);
}
.sub-title {
  margin: 18px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.ongoing {
  font-size: 11px;
  color: #ff8f86;
}
.alert-list {
  display: flex;
  flex-direction: column;
}
.alert-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 6px;
  border-bottom: 1px solid rgba(30, 38, 55, 0.65);
}
.alert-row:last-child {
  border-bottom: none;
}
.alert-main {
  flex: 1;
  min-width: 0;
}
.alert-summary {
  font-size: 12px;
  color: var(--text);
}
.alert-meta {
  margin-top: 3px;
  font-size: 10px;
  color: var(--text-3);
}
.alert-status {
  font-size: 11px;
  white-space: nowrap;
}
.alert-status.firing {
  color: #ff8f86;
}
.alert-status.acknowledged {
  color: #f5b64b;
}
.alert-status.resolved {
  color: var(--text-3);
}
.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--gap);
}
.config-block {
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
}
.config-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}
.kv {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 20px;
  margin: 0;
}
.kv-item {
  min-width: 0;
}
.kv-item:last-child:nth-child(odd),
.kv-item--wide {
  grid-column: span 2;
}
.kv-item dt {
  font-size: 10px;
  color: var(--text-2);
  margin-bottom: 3px;
}
.kv-item dd {
  margin: 0;
  font-size: 12px;
  color: var(--text);
  line-height: 1.5;
  word-break: break-word;
}
@media (max-width: 899px) {
  .config-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .hb-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 639px) {
  .kv {
    grid-template-columns: minmax(0, 1fr);
  }
  .kv-item:last-child:nth-child(odd),
  .kv-item--wide {
    grid-column: auto;
  }
  .hb-stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>