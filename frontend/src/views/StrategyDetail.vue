// StrategyDetail.vue — v0.2 策略详情：4 Tab（状态 / 动态 / 告警 / 配置），SSE 实时追加动态、告警与进程状态。
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NButton, NDropdown, useDialog, useMessage } from 'naive-ui';
import { KeyRound, Pause, Play, RefreshCw } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Alert, RunnerDetail, StrategyToken } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { ruleLabel } from '@/utils/catalog';
import { fmtDateTime, fmtNumber, fromNow } from '@/utils/format';
import EmptyState from '@/components/EmptyState.vue';
import EventTimeline from '@/components/EventTimeline.vue';
import NavChart from '@/components/NavChart.vue';
import PageHeader from '@/components/PageHeader.vue';
import ProcessTable from '@/components/ProcessTable.vue';
import SectionCard from '@/components/SectionCard.vue';
import StatusDot from '@/components/StatusDot.vue';
import StatusTag from '@/components/StatusTag.vue';
import StrategyTokenModal from '@/components/StrategyTokenModal.vue';
import TabBar from '@/components/TabBar.vue';
import type { TabItem } from '@/components/TabBar.vue';

const route = useRoute();
const dialog = useDialog();
const message = useMessage();
const settings = useSettingsStore();
const realtime = useRealtimeStore();

const runnerId = computed(() => String(route.params.id || ''));
const detail = ref<RunnerDetail | null>(null);
const tokens = ref<StrategyToken[]>([]);
const loading = ref(true);
const refreshing = ref(false);
const error = ref('');
const initialTab = String(route.query.tab || 'status');
const activeTab = ref(['status', 'events', 'alerts', 'config'].includes(initialTab) ? initialTab : 'status');
const actionLoading = ref(false);
const processBusy = ref('');
const tokenOpen = ref(false);
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

const runner = computed(() => detail.value?.runner ?? null);
const processes = computed(() => detail.value?.processes ?? []);
const events = computed(() => detail.value?.events ?? []);
const equityCurve = computed(() => detail.value?.equity_curve ?? []);
const alerts = computed(() => [...(detail.value?.alerts ?? [])].sort((a, b) => Date.parse(b.starts_at) - Date.parse(a.starts_at)));
const activeAlertCount = computed(() => alerts.value.filter((a) => a.status === 'firing').length);

const silenceOptions = [
  { label: '静默 1 小时', key: '1h' },
  { label: '静默 4 小时', key: '4h' },
  { label: '静默 24 小时', key: '24h' },
];

const tabs = computed<TabItem[]>(() => [
  { key: 'status', label: '状态' },
  { key: 'events', label: '动态', count: events.value.length },
  { key: 'alerts', label: '告警', count: alerts.value.length },
  { key: 'config', label: '配置' },
]);

/** 把 SSE 实时动态合并进当前详情（按 id 去重，最多保留 200 条） */
function mergeLiveEvents(): void {
  if (!detail.value) return;
  const existing = new Set(detail.value.events.map((e) => String(e.id)));
  const incoming = realtime.events.filter((e) => e.runner_id === runnerId.value && !existing.has(String(e.id)));
  if (!incoming.length) return;
  detail.value = { ...detail.value, events: [...incoming, ...detail.value.events].slice(0, 200) };
}

async function load(initial = false, silent = false): Promise<void> {
  if (initial) loading.value = true;
  else if (!silent) refreshing.value = true;
  error.value = '';
  try {
    const [detailRes, tokenRes] = await Promise.all([
      api.runner(runnerId.value),
      api.tokens({ runner_id: runnerId.value }).catch(() => ({ items: [] as StrategyToken[] })),
    ]);
    detail.value = detailRes;
    tokens.value = tokenRes.items || [];
  } catch (err) {
    if (!silent || !detail.value) error.value = err instanceof Error ? err.message : '策略详情加载失败';
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

function togglePause(): void {
  if (!runner.value) return;
  const paused = runner.value.status === 'paused';
  dialog.warning({
    title: paused ? '恢复监控' : '暂停监控',
    content: paused ? '恢复后按心跳与 loop 重新判断该策略组状态。' : '暂停后该策略组不再产生心跳/卡死告警；已上报的进程数据保留。',
    positiveText: paused ? '恢复' : '暂停',
    negativeText: '取消',
    onPositiveClick: async () => {
      actionLoading.value = true;
      try {
        if (paused) await api.resumeRunner(runnerId.value);
        else await api.pauseRunner(runnerId.value);
        message.success(paused ? '已恢复监控' : '已暂停监控');
        await load(false, true);
        settings.triggerRefresh();
      } catch (err) {
        message.error(err instanceof Error ? err.message : '操作失败');
      } finally {
        actionLoading.value = false;
      }
    },
  });
}

function toggleProcess(name: string, retired: boolean): void {
  dialog.warning({
    title: retired ? '恢复进程' : '停用进程',
    content: retired
      ? '恢复后该进程重新参与存活判定，并会由下一次上报自动刷新状态。'
      : '停用后该进程不再参与策略组存活判定，也不会产生心跳/卡死告警；历史数据保留，可随时恢复。',
    positiveText: retired ? '恢复' : '停用',
    negativeText: '取消',
    onPositiveClick: async () => {
      processBusy.value = name;
      try {
        if (retired) await api.activateProcess(runnerId.value, name);
        else await api.retireProcess(runnerId.value, name);
        message.success(retired ? '进程已恢复' : '进程已停用');
        await load(false, true);
        settings.triggerRefresh();
      } catch (err) {
        message.error(err instanceof Error ? err.message : '操作失败');
      } finally {
        processBusy.value = '';
      }
    },
  });
}

async function acknowledge(alert: Alert): Promise<void> {
  try {
    await api.ackAlert(alert.id);
    message.success('已确认告警：' + ruleLabel(alert.rule));
    await load(false, true);
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '确认失败');
  }
}

async function silence(alert: Alert, duration = '1h'): Promise<void> {
  try {
    await api.silenceAlert(alert.id, duration);
    const labels: Record<string, string> = { '1h': '1 小时', '4h': '4 小时', '24h': '24 小时' };
    message.success('已静默 ' + (labels[duration] ?? '1 小时'));
    await load(false, true);
    window.dispatchEvent(new CustomEvent('qwatch:alerts-changed'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '静默失败');
  }
}

watch(() => realtime.events, mergeLiveEvents);
watch(() => [realtime.lastAlertChangeAt, realtime.lastProcessChangeAt], scheduleReload);
watch(() => settings.refreshSeq, () => { void load(false, true); });
watch(() => route.params.id, () => { activeTab.value = 'status'; void load(true); });
watch(() => route.query.tab, (tab) => {
  const value = String(tab || '');
  if (['status', 'events', 'alerts', 'config'].includes(value)) activeTab.value = value;
});

onMounted(() => {
  void load(true);
  pollTimer = window.setInterval(() => {
    if (!document.hidden) void load(false, true);
  }, 15000);
});

onBeforeUnmount(() => {
  window.clearInterval(pollTimer);
  window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="page">
    <div v-if="loading && !detail" class="page">
      <div class="skel skel-line" style="width: 180px; height: 12px" />
      <div class="skel skel-line" style="width: 320px; height: 28px" />
      <div class="skel" style="height: 160px; border-radius: 12px" />
      <div class="skel" style="height: 260px; border-radius: 12px" />
    </div>

    <div v-else-if="error && !detail" class="card">
      <EmptyState title="策略详情加载失败" :description="error">
        <template #action>
          <div class="error-actions">
            <n-button size="small" @click="load(true)">重新加载</n-button>
            <n-button size="small" quaternary @click="$router.push('/strategies')">返回策略列表</n-button>
          </div>
        </template>
      </EmptyState>
    </div>

    <template v-else-if="detail && runner">
      <PageHeader
        :title="runner.name"
        :subtitle="(runner.description || '策略组') + ' · ' + (runner.last_seen ? '最后心跳 ' + fromNow(runner.last_seen) : '尚未上报')"
        back-to="/strategies"
        back-label="策略列表"
      >
        <template #extra>
          <StatusTag :status="runner.status" />
          <n-button size="small" :loading="actionLoading" @click="togglePause">
            <template #icon><component :is="runner.status === 'paused' ? Play : Pause" :size="13" /></template>
            {{ runner.status === 'paused' ? '恢复监控' : '暂停监控' }}
          </n-button>
          <n-button size="small" @click="tokenOpen = true">
            <template #icon><KeyRound :size="13" /></template>
            接入令牌
          </n-button>
          <n-button size="small" :loading="refreshing" @click="load(false)">
            <template #icon><RefreshCw :size="13" /></template>
            刷新
          </n-button>
        </template>
      </PageHeader>

      <div v-if="error" class="error-bar">
        <span class="dot" />{{ error }}
        <n-button text size="tiny" @click="load(true)">重试</n-button>
      </div>

      <section class="card tabs-card">
        <TabBar v-model="activeTab" :tabs="tabs" />

        <!-- 状态 -->
        <div v-show="activeTab === 'status'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">策略组状态</h2>
              <p class="panel-sub">一个策略组 = 一个 token；组内进程独立心跳、独立 loop 判定。</p>
            </div>
            <span class="live-hint" :class="{ live: realtime.live }">
              <StatusDot :status="realtime.live ? 'running' : 'warn'" :size="6" />
              {{ realtime.live ? '实时' : '轮询兜底' }}
            </span>
          </div>
          <div class="nav-hero">
            <div class="nav-hero-main">
              <span class="nav-hero-label">策略权益</span>
              <strong class="nav-hero-value mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</strong>
              <span class="nav-hero-meta">{{ runner.equity_updated_at ? '更新于 ' + fmtDateTime(runner.equity_updated_at) : '暂无权益上报' }}</span>
              <span class="nav-hero-note">权益由组内进程上报，同一 token 以最后一次为准；品种不单独计算权益。</span>
            </div>
            <NavChart :data="equityCurve" :height="160" />
          </div>

          <div class="status-grid">
            <div class="status-item"><span class="k">状态</span><span class="v"><StatusTag :status="runner.status" compact /></span></div>
            <div class="status-item"><span class="k">进程在线</span><span class="v mono">{{ runner.online_processes ?? 0 }} / {{ runner.process_count ?? 0 }}</span></div>
            <div class="status-item"><span class="k">策略权益</span><span class="v mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</span></div>
            <div class="status-item"><span class="k">最后心跳</span><span class="v mono">{{ runner.last_seen ? fmtDateTime(runner.last_seen) + '（' + fromNow(runner.last_seen) + '）' : '尚未上报' }}</span></div>
            <div class="status-item"><span class="k">最后消息</span><span class="v">{{ runner.last_msg || '—' }}</span></div>
            <div v-if="runner.status === 'paused'" class="status-item status-item--wide">
              <span class="k">监控状态</span>
              <span class="v">已暂停：不再产生心跳/卡死告警，点击右上角「恢复监控」重新纳入判定。</span>
            </div>
          </div>

          <div class="panel-head panel-head--sub">
            <div>
              <h3 class="sub-title">进程</h3>
              <p class="panel-sub">进程名来自策略上报的 instrument；停用后不参与存活判定。</p>
            </div>
          </div>
          <ProcessTable :processes="processes" :busy="processBusy" actionable @retire="(name) => toggleProcess(name, false)" @activate="(name) => toggleProcess(name, true)" />

          <div class="panel-head panel-head--sub">
            <div>
              <h3 class="sub-title">接入令牌</h3>
              <p class="panel-sub">组内所有进程共用；完整令牌仅生成时展示一次。</p>
            </div>
            <n-button size="tiny" @click="tokenOpen = true">管理令牌</n-button>
          </div>
          <div v-if="tokens.length" class="token-list">
            <div v-for="token in tokens" :key="token.id" class="token-row">
              <span class="mono prefix">{{ token.token_prefix }}</span>
              <span class="chip" :class="token.status === 'active' ? 'active' : 'revoked'">{{ token.status === 'active' ? '有效' : '已吊销' }}</span>
              <span class="token-meta">创建 {{ fmtDateTime(token.created_at) }}</span>
              <span v-if="token.last_used_at" class="token-meta">最近使用 {{ fmtDateTime(token.last_used_at) }}</span>
              <span class="token-meta">请求 {{ token.request_count }}</span>
            </div>
          </div>
          <EmptyState v-else compact title="还没有接入令牌" description="点击「管理令牌」生成后即可开始上报。" />
        </div>

        <!-- 动态 -->
        <div v-show="activeTab === 'events'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">动态</h2>
              <p class="panel-sub">消息 + 信号合并时间线；SSE 实时追加，轮询兜底。</p>
            </div>
          </div>
          <EventTimeline :events="events" empty-title="暂无动态" empty-desc="策略上报消息或交易信号后会实时出现在这里。" />
        </div>

        <!-- 告警 -->
        <div v-show="activeTab === 'alerts'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">告警</h2>
              <p class="panel-sub">本策略组的 P0 告警（含活跃与历史）· 按策略组汇总一条</p>
            </div>
            <router-link to="/alerts" class="link-more">告警中心 →</router-link>
          </div>
          <div v-if="alerts.length" class="alert-list">
            <article v-for="alert in alerts" :key="alert.id" class="alert-card" :class="alert.status">
              <div class="alert-head">
                <span class="rule-chip">{{ ruleLabel(alert.rule) }}</span>
                <span class="mono rule-key">{{ alert.rule }}</span>
                <span class="status-chip" :class="alert.status">{{ alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复' }}</span>
                <span class="spacer" />
                <span class="mono time">{{ fmtDateTime(alert.starts_at) }}</span>
              </div>
              <p class="alert-summary">{{ alert.summary }}</p>
              <div class="alert-actions">
                <span class="mono muted">开始 {{ fmtDateTime(alert.starts_at) }}</span>
                <span v-if="alert.ends_at" class="mono muted">结束 {{ fmtDateTime(alert.ends_at) }}</span>
                <span v-if="alert.labels && alert.labels.silenced_until" class="mono silenced">静默至 {{ fmtDateTime(alert.labels.silenced_until) }}</span>
                <span class="spacer" />
                <template v-if="alert.status !== 'resolved'">
                  <n-button v-if="alert.status === 'firing'" size="tiny" @click="acknowledge(alert)">确认</n-button>
                  <n-dropdown trigger="click" :options="silenceOptions" @select="(key) => silence(alert, String(key))">
                    <n-button size="tiny" quaternary>静默</n-button>
                  </n-dropdown>
                </template>
              </div>
            </article>
          </div>
          <EmptyState v-else compact title="暂无告警" description="该策略组近期没有触发心跳丢失 / 策略卡死。" />
        </div>

        <!-- 配置 -->
        <div v-show="activeTab === 'config'" class="tab-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">配置</h2>
              <p class="panel-sub">策略组简要信息与接入方式；不展示宿主/进程号等伪配置。</p>
            </div>
            <n-button size="small" @click="tokenOpen = true">
              <template #icon><KeyRound :size="13" /></template>
              接入令牌
            </n-button>
          </div>
          <div class="config-grid">
            <section class="config-block">
              <h3 class="config-title">策略信息</h3>
              <dl class="kv">
                <div class="kv-item"><dt>策略名称</dt><dd>{{ runner.name }}</dd></div>
                <div class="kv-item"><dt>策略 ID</dt><dd class="mono">{{ runner.id }}</dd></div>
                <div v-if="runner.created_at" class="kv-item"><dt>创建时间</dt><dd class="mono">{{ fmtDateTime(runner.created_at) }}</dd></div>
                <div class="kv-item"><dt>进程数</dt><dd class="mono">{{ runner.online_processes ?? 0 }} / {{ runner.process_count ?? 0 }} 在线</dd></div>
                <div class="kv-item kv-item--wide"><dt>简介</dt><dd>{{ runner.description || '—' }}</dd></div>
              </dl>
            </section>
            <section class="config-block">
              <h3 class="config-title">接入</h3>
              <dl class="kv">
                <div class="kv-item"><dt>上报地址</dt><dd class="mono">POST /api/v1/report</dd></div>
                <div class="kv-item"><dt>鉴权</dt><dd class="mono">Authorization: Bearer &lt;策略 token&gt;</dd></div>
                <div class="kv-item kv-item--wide"><dt>说明</dt><dd>每次上报必须携带 instrument（进程名）；消息/信号也走同一接口，任何成功上报都会刷新进程心跳。</dd></div>
              </dl>
              <div v-if="tokens.some((t) => t.status === 'active')" class="config-token">
                当前有效令牌：<span class="mono">{{ tokens.filter((t) => t.status === 'active').map((t) => t.token_prefix).join('、') }}</span>
              </div>
              <n-button size="small" style="margin-top: 10px" @click="tokenOpen = true">管理接入令牌</n-button>
            </section>
          </div>
        </div>
      </section>

      <StrategyTokenModal v-model:show="tokenOpen" :runner="runner" />
    </template>
  </div>
</template>

<style scoped>
.nav-hero {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.09), rgba(21, 28, 44, 0.4));
}
.nav-hero-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.nav-hero-label {
  font-size: 11px;
  color: var(--text-3);
}
.nav-hero-value {
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--text);
}
.nav-hero-meta {
  font-size: 11px;
  color: var(--text-2);
}
.detail-metric-tabs {
  display: inline-flex;
  align-self: flex-start;
  gap: 2px;
  margin-top: 6px;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
}
.detail-metric-tabs button {
  height: 22px;
  padding: 0 10px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-3);
  font-size: 11px;
  cursor: pointer;
}
.detail-metric-tabs button.active {
  background: var(--primary-soft);
  color: var(--text);
}
.nav-hero-note {
  margin-top: 4px;
  font-size: 10px;
  color: var(--text-3);
  line-height: 1.5;
}
@media (max-width: 700px) {
  .nav-hero {
    grid-template-columns: minmax(0, 1fr);
  }
}

.tabs-card {
  padding-top: 4px;
}
.tab-panel {
  padding: 16px 0 4px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.panel-head--sub {
  margin-top: 22px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.panel-sub {
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.6;
}
.sub-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.live-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-3);
}
.live-hint.live {
  color: #2ecc8f;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  font-size: 12px;
}
.status-item--wide {
  grid-column: 1 / -1;
}
.status-item .k {
  font-size: 10px;
  color: var(--text-3);
}
.status-item .v {
  color: var(--text);
  word-break: break-all;
}
.token-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.token-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  font-size: 11px;
}
.prefix {
  color: var(--text);
  font-size: 12px;
}
.token-meta {
  color: var(--text-3);
}
.chip {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  font-size: 10px;
}
.chip.active {
  color: #2ecc8f;
  border-color: rgba(46, 204, 143, 0.3);
  background: rgba(46, 204, 143, 0.08);
}
.chip.revoked {
  color: var(--text-3);
}
.link-more {
  font-size: 12px;
  color: var(--text-2);
}
.link-more:hover {
  color: var(--primary);
}
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-card {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(21, 28, 44, 0.45);
}
.alert-card.firing {
  border-color: rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.045);
}
.alert-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.rule-chip {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid rgba(240, 68, 56, 0.32);
  background: rgba(240, 68, 56, 0.1);
  color: #ff8f86;
  font-size: 10px;
}
.rule-key {
  font-size: 10px;
  color: var(--text-3);
}
.status-chip {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 10px;
  border: 1px solid transparent;
}
.status-chip.firing {
  color: #ff8f86;
  background: rgba(240, 68, 56, 0.12);
  border-color: rgba(240, 68, 56, 0.3);
}
.status-chip.acknowledged {
  color: #f5b64b;
  background: rgba(245, 165, 36, 0.1);
  border-color: rgba(245, 165, 36, 0.26);
}
.status-chip.resolved {
  color: var(--text-3);
  background: rgba(95, 109, 132, 0.12);
  border-color: rgba(95, 109, 132, 0.26);
}
.spacer {
  flex: 1;
}
.time {
  font-size: 10px;
  color: var(--text-3);
}
.alert-summary {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text);
}
.alert-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 10px;
}
.silenced {
  color: #f5b64b;
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
  color: var(--text-3);
  margin-bottom: 3px;
}
.kv-item dd {
  margin: 0;
  font-size: 12px;
  color: var(--text);
  line-height: 1.55;
  word-break: break-word;
}
.config-token {
  margin-top: 12px;
  font-size: 11px;
  color: var(--text-2);
}
.error-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}
@media (max-width: 1099px) {
  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 899px) {
  .config-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 639px) {
  .status-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .kv {
    grid-template-columns: minmax(0, 1fr);
  }
  .kv-item:last-child:nth-child(odd),
  .kv-item--wide {
    grid-column: auto;
  }
}
</style>