<script setup lang="ts">
// Activity.vue — 动态中心：左侧全局事件流，右侧活跃/历史告警。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, NInput, NSelect, useMessage } from 'naive-ui';
import { Check, Search } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, ActivityEvent, Alert } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import { fmtTime, fromNow } from '@/utils/format';
import { ruleLabel } from '@/utils/catalog';

const router = useRouter();
const message = useMessage();
const realtime = useRealtimeStore();
const settings = useSettingsStore();

const events = ref<ActivityEvent[]>([]);
const hasMore = ref(false);
const nextBefore = ref<number | null>(null);
const feedLoading = ref(false);
const feedLoadingMore = ref(false);
const feedError = ref('');
const keyword = ref('');
const typeFilter = ref<'all' | 'message' | 'signal'>('all');
const accountFilter = ref('all');
const daysFilter = ref(7);
const accounts = ref<Account[]>([]);

const activeAlerts = ref<Alert[]>([]);
const historyAlerts = ref<Alert[]>([]);
const alertTab = ref<'active' | 'history'>('active');
const alertsLoading = ref(false);
const acking = ref('');
const alertsError = ref('');
const feedScroll = ref<HTMLElement | null>(null);
let searchTimer: number | undefined;
let refreshTimer: number | undefined;
let alertTimer: number | undefined;

const typeOptions = [
  { label: '全部类型', value: 'all' },
  { label: '消息', value: 'message' },
  { label: '信号', value: 'signal' },
];
const rangeOptions = [
  { label: '今天', value: 1 },
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '全部', value: 0 },
];
const accountOptions = computed(() => [
  { label: '全部账户', value: 'all' },
  ...accounts.value.map((a) => ({ label: a.name, value: a.id })),
]);
const currentAlerts = computed(() => (alertTab.value === 'active' ? activeAlerts.value : historyAlerts.value));
const eventCount = computed(() => events.value.length);
const eventGroups = computed(() => {
  const groups: { key: string; label: string; items: ActivityEvent[] }[] = [];
  const today = dateKey(new Date());
  const yesterday = dateKey(new Date(Date.now() - 86400000));
  for (const event of events.value) {
    const key = dateKey(new Date(event.ts));
    let group = groups[groups.length - 1];
    if (!group || group.key !== key) {
      const label = key === today ? '今天' : key === yesterday ? '昨天' : key.slice(5).replace('-', ' 月 ') + ' 日';
      group = { key, label, items: [] };
      groups.push(group);
    }
    group.items.push(event);
  }
  return groups;
});

function dateKey(date: Date): string {
  return date.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
}
function typeLabel(type: string): string {
  return type === 'signal' ? '信号' : '消息';
}
function directionLabel(dir?: string): string {
  return dir === 'long' ? '多' : dir === 'short' ? '空' : dir || '';
}
function actionLabel(action?: string): string {
  return ({ open: '开仓', close: '平仓', add: '加仓', reduce: '减仓' } as Record<string, string>)[action || ''] || action || '';
}
function eventText(event: ActivityEvent): string {
  if (event.type === 'signal') {
    const price = event.price !== null && event.price !== undefined ? ' @ ' + event.price : '';
    return [event.symbol || event.instrument, directionLabel(event.direction), actionLabel(event.action), event.qty ? event.qty + ' 手' : '', price].filter(Boolean).join(' ');
  }
  return event.text || '—';
}

async function loadAccounts(): Promise<void> {
  try { accounts.value = (await api.accounts()).items; } catch { accounts.value = []; }
}

async function loadEvents(reset = true): Promise<void> {
  if (reset) {
    feedLoading.value = true;
    events.value = [];
    nextBefore.value = null;
    hasMore.value = false;
  } else {
    if (!hasMore.value || feedLoadingMore.value) return;
    feedLoadingMore.value = true;
  }
  feedError.value = '';
  try {
    const res = await api.events({
      limit: 50,
      before_id: reset ? null : nextBefore.value,
      type: typeFilter.value === 'all' ? undefined : typeFilter.value,
      account_id: accountFilter.value === 'all' ? undefined : accountFilter.value,
      q: keyword.value.trim() || undefined,
      days: daysFilter.value || undefined,
    });
    events.value = reset ? res.items : [...events.value, ...res.items];
    hasMore.value = res.has_more;
    nextBefore.value = res.next_before_id;
  } catch (err) {
    feedError.value = err instanceof Error ? err.message : '动态加载失败';
  } finally {
    feedLoading.value = false;
    feedLoadingMore.value = false;
  }
}

async function loadAlerts(): Promise<void> {
  alertsLoading.value = true;
  alertsError.value = '';
  try {
    const [active, history] = await Promise.all([api.alerts('active'), api.alerts('history')]);
    activeAlerts.value = active.items;
    historyAlerts.value = history.items;
  } catch (err) {
    alertsError.value = err instanceof Error ? err.message : '告警加载失败';
  } finally {
    alertsLoading.value = false;
  }
}

async function ackAlert(alert: Alert): Promise<void> {
  acking.value = alert.id;
  try {
    await api.ackAlert(alert.id);
    message.success('告警已确认');
    await loadAlerts();
  } catch (err) {
    message.error(err instanceof Error ? err.message : '确认失败');
  } finally {
    acking.value = '';
  }
}

function onFeedScroll(): void {
  const el = feedScroll.value;
  if (!el || feedLoadingMore.value || !hasMore.value) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) void loadEvents(false);
}

function scheduleFilter(): void {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => { void loadEvents(true); }, 260);
}
function scheduleFeedRefresh(): void {
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => { void loadEvents(true); }, 350);
}
function scheduleAlertRefresh(): void {
  window.clearTimeout(alertTimer);
  alertTimer = window.setTimeout(() => { void loadAlerts(); }, 350);
}

watch(() => [typeFilter.value, accountFilter.value, daysFilter.value], () => { void loadEvents(true); });
watch(keyword, scheduleFilter);
watch(() => settings.refreshSeq, () => { void loadEvents(true); void loadAlerts(); });
watch(() => realtime.lastEventAt, scheduleFeedRefresh);
watch(() => realtime.lastAlertChangeAt, scheduleAlertRefresh);

onMounted(() => {
  void loadAccounts();
  void loadEvents(true);
  void loadAlerts();
});
onBeforeUnmount(() => {
  window.clearTimeout(searchTimer);
  window.clearTimeout(refreshTimer);
  window.clearTimeout(alertTimer);
});
</script>

<template>
  <div class="page activity-page">
    <div class="card activity-toolbar">
      <n-input v-model:value="keyword" clearable size="small" placeholder="搜索策略 / 账户 / 合约 / 内容" class="activity-search">
        <template #prefix><Search :size="14" /></template>
      </n-input>
      <n-select v-model:value="typeFilter" :options="typeOptions" size="small" class="type-select" />
      <n-select v-model:value="accountFilter" :options="accountOptions" size="small" class="account-select" />
      <n-select v-model:value="daysFilter" :options="rangeOptions" size="small" class="range-select" />
      <div class="toolbar-tail">
        <span class="count mono">{{ eventCount }} 条</span>
        <span class="live-indicator" :class="{ live: realtime.live }"><i />{{ realtime.live ? '实时' : '轮询' }}</span>
      </div>
    </div>

    <div class="activity-grid">
      <section class="card feed-card">
        <header class="card-bar">
          <div class="card-title">事件流 <span class="card-sub">EVENT STREAM</span></div>
          <span class="card-meta">{{ eventCount }} 条 · 按时间倒序</span>
        </header>
        <div ref="feedScroll" class="feed-scroll" @scroll.passive="onFeedScroll">
          <div v-if="feedError" class="inline-error">{{ feedError }}</div>
          <div v-if="feedLoading && !events.length" class="loading-block">正在加载动态…</div>
          <div v-else-if="!events.length && !feedError" class="empty-block">暂无动态</div>
          <template v-for="group in eventGroups" :key="group.key">
            <div class="day-head">{{ group.label }}</div>
            <button v-for="event in group.items" :key="event.id" type="button" class="event-row" @click="event.runner_id && router.push('/strategies/' + event.runner_id)">
              <time class="event-time mono">{{ fmtTime(event.ts) }}</time>
              <span class="event-type" :class="event.type">{{ typeLabel(event.type) }}</span>
              <span class="event-main">
                <span class="event-line"><strong>{{ event.runner_name || event.instrument }}</strong><span class="event-account">{{ event.account_name || '' }}</span><span class="event-instrument">{{ event.instrument }}</span></span>
                <span class="event-text">{{ eventText(event) }}</span>
              </span>
            </button>
          </template>
          <div v-if="hasMore" class="load-more">
            <n-button text size="small" :loading="feedLoadingMore" @click="loadEvents(false)">加载更早</n-button>
          </div>
          <div v-else-if="events.length" class="feed-end">已加载全部动态</div>
        </div>
      </section>

      <aside class="card alert-panel">
        <header class="card-bar alert-bar">
          <div class="card-title">告警 <span class="card-sub">ALERTS</span></div>
          <button type="button" class="card-meta refresh-link" @click="loadAlerts">刷新</button>
        </header>
        <div class="alert-tabs">
          <button type="button" :class="{ active: alertTab === 'active' }" @click="alertTab = 'active'">活跃 <b>{{ activeAlerts.length }}</b></button>
          <button type="button" :class="{ active: alertTab === 'history' }" @click="alertTab = 'history'">历史 <b>{{ historyAlerts.length }}</b></button>
        </div>
        <div class="alert-scroll">
          <div v-if="alertsError" class="inline-error">{{ alertsError }}</div>
          <div v-else-if="alertsLoading && !currentAlerts.length" class="loading-block">正在加载告警…</div>
          <div v-else-if="!currentAlerts.length" class="empty-alert">
            <span class="ok" />
            <div><strong>{{ alertTab === 'active' ? '当前没有活跃告警' : '暂无历史告警' }}</strong><span>{{ alertTab === 'active' ? '所有策略心跳与运行状态正常' : '确认或恢复后会出现在这里' }}</span></div>
          </div>
          <template v-else>
            <article v-for="alert in currentAlerts" :key="alert.id" class="alert-card" :class="alert.status">
            <div class="alert-top"><span class="rule">{{ ruleLabel(alert.rule) }}</span><span class="status">{{ alert.status === 'firing' ? '触发中' : alert.status === 'acknowledged' ? '已确认' : '已恢复' }}</span></div>
            <strong class="alert-runner">{{ alert.runner_name }}</strong>
            <p class="alert-summary">{{ alert.summary }}</p>
            <div class="alert-foot">
              <span>{{ fromNow(alert.starts_at) }}</span>
              <n-button v-if="alert.status === 'firing'" text size="tiny" :loading="acking === alert.id" @click="ackAlert(alert)">
                <template #icon><Check :size="12" /></template>
                确认
              </n-button>
              <span v-else class="alert-state">{{ alert.status === 'resolved' ? '已恢复' : '已确认' }}</span>
            </div>
            </article>
          </template>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.activity-page { height: 100%; min-height: 0; overflow: hidden; gap: 12px; }
.activity-toolbar { flex: none; display: flex; align-items: center; gap: 10px; padding: 9px 12px; }
.activity-search { width: 320px; max-width: 34vw; }
.type-select { width: 120px; }
.account-select { width: 150px; }
.range-select { width: 110px; }
.toolbar-tail { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.count { color: var(--text-3); font-size: 11px; }
.live-indicator { display: inline-flex; align-items: center; gap: 5px; color: var(--text-3); font-size: 11px; }
.live-indicator i { width: 5px; height: 5px; border-radius: 50%; background: var(--warning); }
.live-indicator.live { color: var(--down); }
.live-indicator.live i { background: var(--down); box-shadow: 0 0 7px var(--down); }
.activity-grid { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.9fr) minmax(320px, 0.8fr); gap: 12px; }
.feed-card, .alert-panel { min-height: 0; padding: 0; overflow: hidden; display: flex; flex-direction: column; }
.card-bar { flex: none; height: 44px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); }
.card-title { color: #fff; font-size: 14px; font-weight: 600; }
.card-sub { margin-left: 7px; color: var(--text-3); font: 9px var(--font-mono); letter-spacing: .1em; }
.card-meta { color: var(--text-3); font-size: 10px; }
.refresh-link { border: 0; background: transparent; cursor: pointer; padding: 0; }
.refresh-link:hover { color: var(--text-2); }
.feed-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 0 16px 8px; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.feed-scroll::-webkit-scrollbar { width: 6px; }
.feed-scroll::-webkit-scrollbar-thumb { background: #2b3a55; border-radius: 999px; }
.day-head { position: sticky; top: 0; z-index: 1; padding: 10px 0 6px; background: var(--surface); color: var(--text-3); font: 10px var(--font-mono); letter-spacing: .08em; }
.event-row { display: grid; grid-template-columns: 58px 40px minmax(0, 1fr); gap: 10px; width: 100%; padding: 10px 4px 10px 0; border: 0; border-bottom: 1px solid rgba(125,139,161,.1); background: transparent; color: inherit; text-align: left; cursor: pointer; }
.event-row:hover { background: rgba(91,140,255,.035); }
.event-time { padding-top: 2px; color: var(--text-3); font-size: 10px; }
.event-type { align-self: start; padding: 2px 5px; border: 1px solid rgba(56,189,248,.25); border-radius: 4px; color: #38bdf8; font-size: 10px; text-align: center; }
.event-type.message { border-color: rgba(125,139,161,.24); color: var(--text-3); }
.event-main { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.event-line { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.event-line strong { color: var(--text); font-size: 13px; font-weight: 550; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event-account { color: var(--text-3); font-size: 10px; white-space: nowrap; }
.event-instrument { margin-left: auto; padding: 1px 5px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-3); font: 9px var(--font-mono); }
.event-text { color: var(--text-2); font-size: 12px; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.load-more { padding: 10px 0 4px; text-align: center; }
.feed-end { padding: 12px 0; color: var(--text-3); font-size: 10px; text-align: center; }
.loading-block, .empty-block { display: grid; place-items: center; min-height: 220px; color: var(--text-3); font-size: 12px; }
.inline-error { padding: 10px 0; color: #ff8f86; font-size: 11px; }
.alert-bar { padding-left: 14px; }
.alert-tabs { flex: none; display: flex; gap: 2px; padding: 8px 12px; border-bottom: 1px solid var(--border); }
.alert-tabs button { flex: 1; height: 28px; border: 0; border-radius: 6px; background: transparent; color: var(--text-3); font-size: 11px; cursor: pointer; }
.alert-tabs button b { margin-left: 3px; color: var(--text-2); font: 10px var(--font-mono); font-weight: 500; }
.alert-tabs button.active { background: var(--primary-soft); color: var(--text); }
.alert-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 0 12px 12px; scrollbar-width: thin; scrollbar-color: #2b3a55 transparent; }
.alert-card { margin-top: 10px; padding: 11px 12px; border: 1px solid var(--border); border-left: 2px solid #f25c5c; border-radius: 8px; background: rgba(21,28,44,.48); }
.alert-card.resolved { border-left-color: var(--down); }
.alert-card.acknowledged { border-left-color: var(--warning); }
.alert-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.rule { color: #f47c74; font-size: 10px; }
.status { color: #f47c74; font-size: 9px; }
.alert-card.resolved .status { color: var(--down); }
.alert-card.acknowledged .status { color: var(--warning); }
.alert-runner { display: block; margin-top: 6px; color: var(--text); font-size: 12px; font-weight: 600; }
.alert-summary { margin: 4px 0 0; color: var(--text-2); font-size: 11px; line-height: 1.45; }
.alert-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; color: var(--text-3); font-size: 10px; }
.alert-state { color: var(--text-3); font-size: 10px; }
.empty-alert { display: flex; align-items: flex-start; gap: 8px; padding: 34px 4px; }
.empty-alert .ok { width: 6px; height: 6px; margin-top: 4px; border-radius: 50%; background: var(--down); box-shadow: 0 0 8px rgba(46,204,143,.5); }
.empty-alert div { display: flex; flex-direction: column; gap: 3px; }
.empty-alert strong { color: var(--text-2); font-size: 12px; font-weight: 500; }
.empty-alert span { color: var(--text-3); font-size: 10px; }
@media (max-width: 1100px) {
  .activity-page { height: auto; overflow: visible; }
  .activity-toolbar { flex-wrap: wrap; }
  .activity-search { width: 100%; max-width: none; }
  .activity-grid { flex: none; grid-template-columns: 1fr; }
  .feed-card { height: 620px; }
  .alert-panel { order: -1; height: 360px; }
}
@media (max-width: 760px) {
  .type-select, .account-select, .range-select { flex: 1; min-width: 120px; }
  .feed-card { height: 560px; }
  .event-row { grid-template-columns: 52px 36px minmax(0, 1fr); gap: 8px; }
}
</style>