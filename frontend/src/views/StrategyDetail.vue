<script setup lang="ts">
// StrategyDetail.vue — 策略详情：一页运行概览 + 动态，配置收进令牌弹窗，减少 Tab 层级。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NButton, useDialog, useMessage } from 'naive-ui';
import { AlertTriangle, KeyRound, Pause, Play } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Alert, Runner, RunnerDetail } from '@/api/types';
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
import TabBar from '@/components/TabBar.vue';
import type { TabItem } from '@/components/TabBar.vue';
import { fmtNumber, fromNow } from '@/utils/format';
import { ruleLabel } from '@/utils/catalog';

const route = useRoute();
const router = useRouter();
const dialog = useDialog();
const message = useMessage();
const realtime = useRealtimeStore();
const settings = useSettingsStore();

const detail = ref<RunnerDetail | null>(null);
const loading = ref(true);
const error = ref('');
const pauseBusy = ref(false);
const processBusy = ref('');
const tokenOpen = ref(false);
const range = ref<'1D' | '1W' | '1M' | '3M' | 'ALL'>('1D');
const activeTab = ref<'overview' | 'events'>('overview');
const initialTab = String(route.query.tab || '');
if (initialTab === 'events' || initialTab === 'dynamic') activeTab.value = 'events';
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const ranges = [
  { key: '1D', label: '1日', days: 1 },
  { key: '1W', label: '1周', days: 7 },
  { key: '1M', label: '1月', days: 30 },
  { key: '3M', label: '3月', days: 90 },
  { key: 'ALL', label: '全部', days: 0 },
] as const;

const runner = computed<Runner | null>(() => detail.value?.runner ?? null);
const processes = computed(() => detail.value?.processes ?? []);
const events = computed(() => detail.value?.events ?? []);
const alerts = computed(() => detail.value?.alerts ?? []);
const firingAlerts = computed(() => alerts.value.filter((alert) => alert.status === 'firing'));
const tabs = computed<TabItem[]>(() => [
  { key: 'overview', label: '概览' },
  { key: 'events', label: '动态', count: events.value.length },
]);
const equityCurve = computed(() => {
  const curve = detail.value?.equity_curve ?? [];
  if (!curve.length) return [];
  const cfg = ranges.find((item) => item.key === range.value);
  if (!cfg || cfg.days === 0) return curve;
  const latest = Date.parse(curve[curve.length - 1].ts);
  const cutoff = latest - cfg.days * 86400000;
  const filtered = curve.filter((point) => Date.parse(point.ts) >= cutoff);
  return filtered.length > 1 ? filtered : curve.slice(-2);
});

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    detail.value = await api.runner(String(route.params.id));
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
    content: paused ? '恢复后重新纳入心跳与 loop 告警判定。' : '暂停后该策略组不再产生心跳/卡死告警。',
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
function openEvent(event: { runner_id?: string }): void {
  if (event.runner_id) void router.push('/strategies/' + event.runner_id + '?tab=events');
}
function alertStatusText(alert: Alert): string {
  return alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复';
}

watch(() => route.query.tab, (tab) => {
  if (String(tab) === 'events' || String(tab) === 'dynamic') activeTab.value = 'events';
});
watch(() => settings.refreshSeq, () => { void load(false); });
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt, realtime.lastEventAt], scheduleReload);
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
      <EmptyState title="策略加载失败" :description="error" />
      <n-button size="small" @click="load(true)">重试</n-button>
    </div>

    <template v-else-if="detail && runner">
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <div v-if="firingAlerts.length" class="alert-banner">
        <AlertTriangle :size="15" />
        <span>{{ firingAlerts.length }} 条 P0 告警：{{ firingAlerts[0].summary }}</span>
        <router-link to="/alerts" class="banner-link">去处理</router-link>
      </div>

      <section class="hero-break">
        <div class="hero-copy">
          <span class="hero-label">策略权益</span>
          <strong class="hero-equity mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</strong>
          <div class="hero-meta">
            <span class="meta-item"><StatusDot :status="runner.status" :size="6" />{{ runner.status === 'running' ? '运行中' : runner.status === 'paused' ? '已暂停' : runner.status === 'degraded' ? '部分异常' : '离线' }}</span>
            <span class="meta-item">{{ runner.process_count > 1 ? runner.process_count + ' 个进程' : '单进程' }}</span>
            <span class="meta-item">{{ runner.last_seen ? '最后心跳 ' + fromNow(runner.last_seen) : '尚未上报' }}</span>
          </div>
        </div>
        <div class="detail-range">
          <button v-for="item in ranges" :key="item.key" type="button" :class="{ active: range === item.key }" @click="range = item.key">{{ item.label }}</button>
        </div>
      </section>

      <section class="card chart-card">
        <NavChart :data="equityCurve" :height="220" />
      </section>

      <section class="detail-body card">
        <TabBar v-model="activeTab" :tabs="tabs" />

        <div v-if="activeTab === 'overview'" class="overview-panel">
          <div class="section-line">
            <div><h3>进程</h3><p>{{ runner.process_count > 1 ? runner.online_processes + ' / ' + runner.process_count + ' 在线' : '单进程运行' }}</p></div>
            <span class="live-hint" :class="{ live: realtime.live }"><StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" />{{ realtime.live ? '实时' : '轮询' }}</span>
          </div>
          <ProcessTable
            :processes="processes"
            :busy="processBusy"
            actionable
            empty-text="进程首次上报后会自动出现。"
            @retire="(name) => toggleProcess(name, false)"
            @activate="(name) => toggleProcess(name, true)"
          />

          <div v-if="alerts.length" class="recent-alerts">
            <div class="section-line"><h3>最近告警</h3><router-link to="/alerts" class="inline-link">告警中心</router-link></div>
            <router-link v-for="alert in alerts.slice(0, 3)" :key="alert.id" to="/alerts" class="alert-line">
              <span class="rule-chip">{{ ruleLabel(alert.rule) }}</span>
              <span class="alert-text">{{ alert.summary }}</span>
              <span class="alert-status" :class="alert.status">{{ alertStatusText(alert) }}</span>
            </router-link>
          </div>
        </div>

        <div v-else class="events-panel">
          <ActivityFeed :events="events" empty-title="暂无动态" empty-desc="策略发送消息或信号后会出现在这里。" />
        </div>
      </section>
    </template>

    <StrategyTokenModal v-model:show="tokenOpen" :runner="runner" />
  </div>
</template>

<style scoped>
.alert-banner { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid rgba(240, 68, 56, 0.28); border-radius: 8px; background: rgba(240, 68, 56, 0.06); color: #f47c74; font-size: 11px; }
.banner-link { margin-left: auto; color: #f47c74; text-decoration: underline; white-space: nowrap; }
.hero-break { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding: 4px 2px 0; }
.hero-label { font-size: 11px; color: var(--text-3); }
.hero-equity { display: block; margin-top: 2px; font-size: 32px; font-weight: 600; letter-spacing: -0.04em; line-height: 1.15; color: var(--text); }
.hero-meta { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; color: var(--text-3); font-size: 10px; }
.meta-item { display: inline-flex; align-items: center; gap: 5px; }
.detail-range { display: inline-flex; padding: 2px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
.detail-range button { height: 23px; padding: 0 9px; border: 0; border-radius: 4px; background: transparent; color: var(--text-3); font-size: 10px; cursor: pointer; }
.detail-range button.active { background: var(--primary-soft); color: var(--text); }
.chart-card { padding: 10px 18px 12px; }
.detail-body { padding-top: 4px; }
.overview-panel { padding: 14px 0 4px; }
.section-line { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; margin: 18px 0 10px; }
.section-line:first-child { margin-top: 0; }
.section-line h3 { font-size: 13px; color: var(--text); }
.section-line p { margin-top: 2px; color: var(--text-3); font-size: 10px; }
.inline-link { color: var(--text-3); font-size: 10px; }
.recent-alerts { margin-top: 20px; }
.alert-line { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--border); color: inherit; }
.alert-line:last-child { border-bottom: 0; }
.rule-chip { flex: 0 0 auto; padding: 2px 5px; border: 1px solid rgba(240, 68, 56, 0.25); border-radius: 4px; color: #f47c74; font-size: 9px; }
.alert-text { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-2); font-size: 10px; }
.alert-status { font-size: 9px; color: var(--text-3); white-space: nowrap; }
.live-hint { display: inline-flex; align-items: center; gap: 5px; color: var(--text-3); font-size: 10px; }
.live-hint.live { color: var(--down); }
.events-panel { padding-top: 12px; }
@media (max-width: 640px) {
  .hero-break { align-items: flex-start; flex-direction: column; }
  .hero-equity { font-size: 26px; }
  .detail-range { align-self: flex-end; }
}
</style>
