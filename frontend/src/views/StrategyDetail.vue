// StrategyDetail.vue — v0.5 策略详情：无 Tab；顶部策略权益曲线 + 所属账户/券商；下方左侧进程+告警、右侧动态（搜索/筛选/滚动）。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton, useDialog, useMessage } from 'naive-ui';
import { AlertTriangle, KeyRound, Pause, Play, Search } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Alert, CurvePoint, Runner, RunnerDetail, RunnerEvent } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import ActivityFeed from '@/components/ActivityFeed.vue';
import EmptyState from '@/components/EmptyState.vue';
import NavChart from '@/components/NavChart.vue';
import PageHeader from '@/components/PageHeader.vue';
import ProcessTable from '@/components/ProcessTable.vue';
import StatusDot from '@/components/StatusDot.vue';
import StatusTag from '@/components/StatusTag.vue';
import StrategyTokenModal from '@/components/StrategyTokenModal.vue';
import { fmtNumber, fromNow } from '@/utils/format';
import { ruleLabel } from '@/utils/catalog';

const route = useRoute();
const dialog = useDialog();
const message = useMessage();
const realtime = useRealtimeStore();
const settings = useSettingsStore();

const detail = ref<RunnerDetail | null>(null);
const dailyCurve = ref<CurvePoint[]>([]);
const rangeKey = ref('all');
const customStart = ref('');
const customEnd = ref('');
const rangeOptions = [
  { value: 'all', label: '全部历史' }, { value: '1m', label: '近 1 个月' }, { value: '3m', label: '近 3 个月' },
  { value: '6m', label: '近 6 个月' }, { value: '1y', label: '近 1 年' }, { value: '3y', label: '近 3 年' },
  { value: '5y', label: '近 5 年' }, { value: 'custom', label: '自定义' },
];
const loading = ref(true);
const error = ref('');
const pauseBusy = ref(false);
const processBusy = ref('');
const tokenOpen = ref(false);
const eventType = ref<'all' | 'message' | 'signal'>('all');
const eventQuery = ref('');
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const runner = computed<Runner | null>(() => detail.value?.runner ?? null);
const account = computed(() => detail.value?.account ?? null);
const accountName = computed(() => runner.value?.account_name || account.value?.name || '未关联账户');
const accountBroker = computed(() => runner.value?.account_broker || account.value?.broker || '');
const strategyEquity = computed(() => runner.value?.equity ?? null);
const processes = computed(() => detail.value?.processes ?? []);
const events = computed(() => detail.value?.events ?? []);
const alerts = computed(() => detail.value?.alerts ?? []);
const firingAlerts = computed(() => alerts.value.filter((alert) => alert.status === 'firing'));
const alertTab = ref<'active' | 'history'>('active');
const activeAlerts = computed(() => alerts.value.filter((alert) => alert.status !== 'resolved'));
const historyAlerts = computed(() => alerts.value.filter((alert) => alert.status === 'resolved'));
const currentAlerts = computed(() => (alertTab.value === 'active' ? activeAlerts.value : historyAlerts.value));
const filteredEvents = computed<RunnerEvent[]>(() => {
  const keyword = eventQuery.value.trim().toLowerCase();
  return events.value.filter((event) => {
    if (eventType.value !== 'all' && event.type !== eventType.value) return false;
    if (!keyword) return true;
    return [event.text, event.symbol, event.instrument, event.runner_name]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword));
  });
});
const equityCurve = computed<CurvePoint[]>(() => {
  const daily = dailyCurve.value;
  if (!daily.length || rangeKey.value === 'all') return daily;
  if (rangeKey.value === 'custom') {
    const start = customStart.value ? Date.parse(customStart.value) : -Infinity;
    const end = customEnd.value ? Date.parse(customEnd.value) + 86399000 : Infinity;
    return daily.filter((point) => { const ts = Date.parse(point.ts); return ts >= start && ts <= end; });
  }
  const latest = Date.parse(daily[daily.length - 1].ts);
  const months = ({ '1m': 1, '3m': 3, '6m': 6, '1y': 12, '3y': 36, '5y': 60 } as Record<string, number>)[rangeKey.value] || 0;
  const cutoff = new Date(latest);
  cutoff.setMonth(cutoff.getMonth() - months);
  return daily.filter((point) => Date.parse(point.ts) >= cutoff.getTime());
});

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    const [runnerDetail, curve] = await Promise.all([
      api.runner(String(route.params.id)),
      api.equityCurve('runner', String(route.params.id)),
    ]);
    detail.value = runnerDetail;
    dailyCurve.value = curve.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '策略加载失败';
  } finally {
    loading.value = false;
  }
}
function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false); }, 500);
}
function togglePause(): void {
  if (!runner.value) return;
  const paused = runner.value.status === 'paused';
  dialog.warning({
    title: paused ? '恢复监控' : '暂停监控',
    content: paused ? '恢复后重新纳入心跳与 loop 告警判定。' : '暂停后该策略不再产生心跳/卡死告警。',
    positiveText: paused ? '恢复' : '暂停',
    negativeText: '取消',
    onPositiveClick: async () => {
      pauseBusy.value = true;
      try {
        if (paused) await api.resumeRunner(runner.value!.id);
        else await api.pauseRunner(runner.value!.id);
        message.success(paused ? '已恢复监控' : '已暂停监控');
        await load(false);
      } catch (err) {
        message.error(err instanceof Error ? err.message : '操作失败');
      } finally {
        pauseBusy.value = false;
      }
    },
  });
}
function toggleProcess(name: string, activate: boolean): void {
  if (!runner.value) return;
  dialog.warning({
    title: activate ? '恢复进程' : '停用进程',
    content: activate ? '恢复后重新参与存活判定。' : '停用后该进程不再参与存活判定与告警。',
    positiveText: activate ? '恢复' : '停用',
    negativeText: '取消',
    onPositiveClick: async () => {
      processBusy.value = name;
      try {
        if (activate) await api.activateProcess(runner.value!.id, name);
        else await api.retireProcess(runner.value!.id, name);
        await load(false);
      } catch (err) {
        message.error(err instanceof Error ? err.message : '操作失败');
      } finally {
        processBusy.value = '';
      }
    },
  });
}
function alertStatusText(alert: Alert): string {
  return alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复';
}

watch(() => settings.refreshSeq, () => { void load(false); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastEventAt, realtime.lastAccountChangeAt, realtime.lastEquityChangeAt], scheduleReload);
onMounted(() => {
  void load(true);
  pollTimer = window.setInterval(() => { if (!document.hidden) void load(false); }, 15000);
});
onBeforeUnmount(() => {
  window.clearInterval(pollTimer);
  window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="page">
    <PageHeader :title="runner?.name || '策略详情'" back-to="/strategies" back-label="策略列表">
      <template v-if="runner" #extra>
        <StatusTag :status="runner.status" />
        <n-button size="small" :loading="pauseBusy" @click="togglePause">
          <template #icon><component :is="runner.status === 'paused' ? Play : Pause" :size="13" /></template>
          {{ runner.status === 'paused' ? '恢复监控' : '暂停监控' }}
        </n-button>
        <n-button size="small" @click="tokenOpen = true">
          <template #icon><KeyRound :size="13" /></template>
          接入令牌
        </n-button>
      </template>
    </PageHeader>

    <div v-if="loading && !detail" class="skel skel-card" style="height: 300px" />
    <div v-else-if="error && !detail" class="card">
      <EmptyState title="策略加载失败" :description="error">
        <template #action>
          <div class="error-actions">
            <n-button size="small" @click="load(true)">重新加载</n-button>
            <n-button size="small" quaternary @click="$router.push('/strategies')">返回策略列表</n-button>
          </div>
        </template>
      </EmptyState>
    </div>

    <template v-else-if="detail && runner">
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div v-if="firingAlerts.length" class="alert-banner">
        <AlertTriangle :size="15" />
        <span>{{ firingAlerts.length }} 条 P0 告警：{{ firingAlerts[0].summary }}</span>
        <router-link to="/activity" class="banner-link">去处理</router-link>
      </div>

      <section class="hero-break">
        <div class="hero-copy">
          <span class="hero-label">策略权益</span>
          <strong class="hero-equity mono">{{ strategyEquity !== null ? '¥' + fmtNumber(strategyEquity, 0) : '—' }}</strong>
          <div class="hero-meta">
            <router-link :to="{ path: '/strategies', query: { account_id: runner.account_id } }" class="account-link">
              <span v-if="accountBroker && accountBroker !== accountName" class="broker-chip">{{ accountBroker }}</span>
              <span>{{ accountName }}</span>
            </router-link>
            <span class="meta-item"><StatusDot :status="runner.status" :size="6" />{{ runner.status === 'running' ? '运行中' : runner.status === 'paused' ? '已暂停' : runner.status === 'degraded' ? '部分异常' : '离线' }}</span>
            <span class="meta-item">{{ runner.process_count > 1 ? runner.process_count + ' 个进程' : '单进程' }}</span>
            <span class="meta-item">{{ runner.last_seen ? '最后心跳 ' + fromNow(runner.last_seen) : '尚未上报' }}</span>
          </div>
        </div>
        <div class="detail-range">
          <select v-model="rangeKey" class="range-select" aria-label="选择时间范围">
            <option v-for="item in rangeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <template v-if="rangeKey === 'custom'">
            <input v-model="customStart" type="date" class="date-input" aria-label="开始日期" />
            <span class="date-sep">—</span>
            <input v-model="customEnd" type="date" class="date-input" aria-label="结束日期" />
          </template>
          <span class="chart-window">日粒度</span>
        </div>
      </section>

      <section class="card chart-card">
        <NavChart :data="equityCurve" :height="220" date-only />
      </section>

      <section class="detail-grid">
        <div class="left-column">
          <section class="card block-card">
            <div class="block-head">
              <div><h3>进程</h3><span class="block-sub">{{ runner.online_processes }}/{{ runner.process_count }} 在线 · 停用后不参与存活判定</span></div>
            </div>
            <ProcessTable
              :processes="processes"
              :busy="processBusy"
              actionable
              empty-text="进程首次上报后会自动出现。"
              @retire="(name) => toggleProcess(name, false)"
              @activate="(name) => toggleProcess(name, true)"
            />
          </section>

          <section class="card block-card">
            <div class="block-head">
              <div><h3>告警</h3><span class="block-sub">{{ activeAlerts.length }} 活跃 · {{ historyAlerts.length }} 历史</span></div>
              <router-link :to="{ path: '/activity', query: { runner_id: route.params.id } }" class="inline-link">告警中心</router-link>
            </div>
            <div class="alert-tabs">
              <button type="button" :class="{ active: alertTab === 'active' }" @click="alertTab = 'active'">最近 <b>{{ activeAlerts.length }}</b></button>
              <button type="button" :class="{ active: alertTab === 'history' }" @click="alertTab = 'history'">历史 <b>{{ historyAlerts.length }}</b></button>
            </div>
            <div class="alert-scroll">
              <template v-if="currentAlerts.length">
                <router-link v-for="alert in currentAlerts" :key="alert.id" to="/activity" class="alert-line">
                  <span class="rule-chip">{{ ruleLabel(alert.rule) }}</span>
                  <span class="alert-text">{{ alert.summary }}</span>
                  <span class="alert-status" :class="alert.status">{{ alertStatusText(alert) }}</span>
                </router-link>
              </template>
              <div v-else class="alert-empty-hint">{{ alertTab === 'active' ? '当前没有活跃告警 · 策略心跳与 loop 正常' : '暂无历史告警' }}</div>
            </div>
          </section>
        </div>

        <section class="card activity-card">
          <div class="block-head activity-title">
            <div><h3>动态</h3><span class="block-sub">{{ filteredEvents.length }} 条</span></div>
          </div>
          <div class="activity-tools">
            <div class="event-search">
              <Search :size="13" />
              <input v-model="eventQuery" type="search" placeholder="搜索消息 / 合约 / 品种" />
            </div>
            <div class="event-filter">
              <button v-for="item in [{ k: 'all', l: '全部' }, { k: 'message', l: '消息' }, { k: 'signal', l: '信号' }]" :key="item.k" type="button" :class="{ active: eventType === item.k }" @click="eventType = item.k as 'all' | 'message' | 'signal'">{{ item.l }}</button>
            </div>
          </div>
          <div class="activity-scroll">
            <ActivityFeed :events="filteredEvents" empty-title="暂无动态" empty-desc="策略发送消息或信号后会出现在这里。" />
          </div>
        </section>
      </section>
    </template>

    <StrategyTokenModal v-model:show="tokenOpen" :runner="runner" />
  </div>
</template>

<style scoped>
.error-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
.alert-banner { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid rgba(240, 68, 56, 0.28); border-radius: 8px; background: rgba(240, 68, 56, 0.06); color: #f47c74; font-size: 11px; }
.banner-link { margin-left: auto; color: #f47c74; text-decoration: underline; white-space: nowrap; }
.hero-break { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding: 4px 2px 0; }
.hero-label { font-size: 11px; color: var(--text-3); }
.hero-equity { display: block; margin-top: 2px; font-size: 32px; font-weight: 600; letter-spacing: -0.04em; line-height: 1.15; color: var(--text); }
.hero-meta { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; color: var(--text-3); font-size: 10px; }
.meta-item { display: inline-flex; align-items: center; gap: 5px; }
.account-link { display: inline-flex; align-items: center; gap: 6px; color: var(--text-2); font-size: 10px; }
.account-link:hover { color: var(--primary); }
.broker-chip { padding: 1px 6px; border: 1px solid var(--border); border-radius: 4px; }
.detail-range { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.range-select { height: 28px; padding: 0 22px 0 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-2); font-size: 11px; }
.date-input { height: 28px; padding: 0 7px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-2); font-size: 10px; }
.date-sep { color: var(--text-3); font-size: 10px; }
.chart-window { color: var(--text-3); font-size: 10px; white-space: nowrap; }
.detail-range { display: inline-flex; padding: 2px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
.detail-range button { height: 23px; padding: 0 9px; border: 0; border-radius: 4px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.detail-range button.active { background: var(--primary-soft); color: var(--text); }
.chart-card { padding: 10px 18px 12px; }
.detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); gap: var(--gap); align-items: start; }
.left-column { display: flex; flex-direction: column; gap: var(--gap); }
.block-card { padding: 16px 18px; }
.block-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 11px; }
.block-head h3 { font-size: 14px; font-weight: 600; color: #ffffff; }
.block-sub { display: block; margin-top: 2px; color: var(--text-3); font-size: 10px; }
.inline-link { color: var(--text-3); font-size: 10px; }
.alert-line { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--border); color: inherit; }
.alert-line:last-child { border-bottom: 0; }
.rule-chip { flex: 0 0 auto; padding: 2px 5px; border: 1px solid rgba(240, 68, 56, 0.25); border-radius: 4px; color: #f47c74; font-size: 10px; }
.alert-text { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-2); font-size: 10px; }
.alert-status { font-size: 10px; color: var(--text-3); white-space: nowrap; }
.alert-tabs { display: flex; gap: 2px; margin: -2px 0 4px; }
.alert-tabs button { height: 24px; padding: 0 9px; border: 0; border-radius: 5px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.alert-tabs button b { margin-left: 3px; color: var(--text-2); font: 9px var(--font-mono); font-weight: 500; }
.alert-tabs button.active { background: var(--primary-soft); color: var(--text); }
.alert-scroll { max-height: 190px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.alert-empty-hint { padding: 12px 0 4px; color: var(--text-3); font-size: 11px; }
.live-hint { display: inline-flex; align-items: center; gap: 5px; color: var(--text-3); font-size: 10px; }
.live-hint.live { color: var(--down); }
.activity-card { display: flex; flex-direction: column; min-height: 430px; padding: 16px 18px; }
.activity-title { margin-bottom: 10px; }
.activity-tools { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.event-search { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 150px; height: 29px; padding: 0 9px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text-3); }
.event-search input { flex: 1; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text); font-size: 11px; }
.event-filter { display: inline-flex; padding: 2px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
.event-filter button { height: 23px; padding: 0 9px; border: 0; border-radius: 4px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.event-filter button.active { background: var(--primary-soft); color: var(--text); }
.activity-scroll { flex: 1; min-height: 0; max-height: 470px; overflow-y: auto; overscroll-behavior: contain; padding-right: 4px; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.activity-scroll::-webkit-scrollbar { width: 5px; }
.activity-scroll::-webkit-scrollbar-thumb { background: #2b3a55; border-radius: 999px; }
.activity-scroll::-webkit-scrollbar-track { background: transparent; }
@media (max-width: 900px) {
  .detail-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 640px) {
  .hero-break { align-items: flex-start; flex-direction: column; }
  .hero-equity { font-size: 26px; }
  .detail-range { align-self: flex-end; }
  .activity-card { min-height: 360px; }
}
</style>