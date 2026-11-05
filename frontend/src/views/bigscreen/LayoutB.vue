<script setup lang="ts">
// LayoutB.vue — 交易台：横向指标带 + 大曲线 + 右栏关注流。
import { computed } from 'vue';
import type { BigScreenData } from './shared';
import { issueText, money, pnl, pnlClass } from './shared';
import NavChart from '@/components/NavChart.vue';
import NavSparkline from '@/components/NavSparkline.vue';

const props = defineProps<{ data: BigScreenData; now: Date; timeText: string; dateText: string }>();
const accounts = computed(() => props.data.accounts);
const runners = computed(() => props.data.runners);
const events = computed(() => (props.data.overview.recent_events || []).slice(0, 4));
const curve = computed(() => props.data.overview.equity_curve || []);
const today = computed(() => props.data.overview.today_pnl ?? props.data.overview.today_equity_change);
const issues = computed(() => runners.value.filter((r) => r.status !== 'running'));
</script>

<template>
  <div class="bs-b">
    <header class="head">
      <div class="brand"><span class="mark">Q</span><strong>qwatch</strong><span class="slash">/</span><span>TRADING DESK</span></div>
      <div class="head-right"><span class="pill"><i />LIVE</span><span>{{ dateText }}</span><b>{{ timeText }}</b><span class="back">大屏预览</span></div>
    </header>

    <section class="hero">
      <div class="hero-main">
        <span class="eyebrow">TOTAL EQUITY</span>
        <div class="hero-value">{{ money(data.overview.total_equity) }}</div>
        <div class="hero-sub"><span class="today" :class="pnlClass(today)">今日 {{ pnl(today) }}</span><span>{{ data.overview.account_count }} 个账户 · {{ data.overview.total }} 个策略</span></div>
      </div>
      <div class="metrics">
        <div class="metric"><span>策略在线</span><strong>{{ data.overview.running }}<em>/{{ data.overview.total }}</em></strong></div>
        <div class="metric"><span>进程在线</span><strong>{{ data.overview.processes_online }}<em>/{{ data.overview.processes_total }}</em></strong></div>
        <div class="metric danger"><span>活跃告警</span><strong>{{ data.overview.active_alerts }}</strong></div>
        <div class="metric"><span>需要关注</span><strong>{{ issues.length }}</strong></div>
      </div>
    </section>

    <main class="main">
      <section class="left">
        <div class="panel chart-panel">
          <div class="panel-head"><h3>组合权益曲线</h3><div class="range"><span class="active">1D</span><span>1W</span><span>1M</span><span>ALL</span></div></div>
          <NavChart :data="curve" :height="680" />
        </div>
        <div class="accounts">
          <article v-for="account in accounts" :key="account.id" class="account">
            <div class="account-top"><span>{{ account.name }}</span><em>{{ account.strategy_count }} 策略</em></div>
            <strong>{{ money(account.equity) }}</strong>
            <div class="account-bottom"><span :class="pnlClass(account.today_pnl)">今日 {{ pnl(account.today_pnl) }}</span><span>{{ account.online_strategies }}/{{ account.strategy_count }} 在线</span></div>
          </article>
        </div>
      </section>

      <aside class="right">
        <section class="panel focus">
          <div class="panel-head"><h3>策略与关注</h3><span>{{ issues.length ? issues.length + ' 项需关注' : '全部正常' }}</span></div>
          <div class="focus-list">
            <article v-for="runner in runners" :key="runner.id" class="focus-item" :class="{ issue: runner.status !== 'running' }">
              <div class="focus-head">
                <span class="dot" :class="runner.status" />
                <strong>{{ runner.name }}</strong>
                <em :class="runner.status">{{ issueText(runner) }}</em>
              </div>
              <div class="focus-meta"><span>{{ runner.account_name }}</span><span>{{ runner.process_count > 1 ? runner.process_count + ' 进程' : '单进程' }}</span></div>
              <div class="focus-data">
                <b>{{ money(runner.equity) }}</b>
                <span :class="pnlClass(runner.today_pnl)">今日 {{ pnl(runner.today_pnl) }}</span>
                <NavSparkline v-if="runner.equity_sparkline?.length" :values="runner.equity_sparkline" :width="120" :height="30" />
              </div>
            </article>
          </div>
        </section>

        <section class="panel feed">
          <div class="panel-head"><h3>实时动态</h3><span>EVENT STREAM</span></div>
          <div v-for="event in events" :key="event.id" class="feed-row">
            <span class="type" :class="event.type">{{ event.type === 'signal' ? 'S' : 'M' }}</span>
            <div><strong>{{ event.runner_name || event.instrument }}</strong><span>{{ event.type === 'signal' ? event.symbol + ' ' + event.action + ' ' + event.qty : event.text }}</span></div>
            <time>{{ event.ts ? new Date(event.ts).toLocaleTimeString('zh-CN', { hour12: false }) : '' }}</time>
          </div>
        </section>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.bs-b { height: 100vh; box-sizing: border-box; padding: 18px 24px 18px; overflow: hidden; display: flex; flex-direction: column; gap: 13px; background: #090d16; }
.head { flex: none; height: 43px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(125, 139, 161, 0.16); }
.brand { display: flex; align-items: center; gap: 9px; }
.mark { width: 28px; height: 28px; display: grid; place-items: center; color: #5b8cff; border: 1px solid rgba(91, 140, 255, 0.5); border-radius: 6px; font: 700 14px var(--font-mono); }
.brand strong { color: #fff; font-size: 14px; letter-spacing: 0.12em; }
.brand .slash { color: #3c4a5f; font: 12px var(--font-mono); }
.brand > span:last-child { color: #63738a; font: 9px var(--font-mono); letter-spacing: 0.18em; }
.head-right { display: flex; align-items: center; gap: 15px; color: #63738a; font: 9px var(--font-mono); }
.head-right b { color: #dfe7f3; font-size: 14px; font-weight: 500; }
.pill { display: inline-flex; align-items: center; gap: 5px; color: #2ecc8f; }
.pill i { width: 5px; height: 5px; border-radius: 50%; background: #2ecc8f; box-shadow: 0 0 7px #2ecc8f; }
.back { padding-left: 12px; border-left: 1px solid rgba(125, 139, 161, 0.2); color: #44536a; }
.hero { flex: none; min-height: 146px; display: grid; grid-template-columns: 1.1fr 1fr; gap: 24px; padding: 17px 22px; border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 8px; background: linear-gradient(110deg, rgba(91, 140, 255, 0.095), rgba(16, 22, 36, 0.65) 55%); }
.hero-main { display: flex; flex-direction: column; justify-content: center; }
.eyebrow { color: #63738a; font: 9px var(--font-mono); letter-spacing: 0.16em; }
.hero-value { margin-top: 6px; color: #fff; font: 700 52px/1 var(--font-mono); letter-spacing: -0.055em; }
.hero-sub { display: flex; align-items: center; gap: 16px; margin-top: 10px; color: #63738a; font-size: 10px; }
.today { font: 600 14px var(--font-mono); }
.up { color: var(--up); }
.down { color: var(--down); }
.metrics { display: grid; grid-template-columns: repeat(2, 1fr); align-content: center; gap: 10px; }
.metric { display: flex; align-items: baseline; justify-content: space-between; padding: 10px 13px; border-left: 2px solid rgba(91, 140, 255, 0.25); background: rgba(21, 28, 44, 0.5); }
.metric span { color: #7d8ba1; font-size: 9px; }
.metric strong { color: #fff; font: 600 22px var(--font-mono); }
.metric em { color: #63738a; font-style: normal; font-size: 11px; }
.metric.danger { border-left-color: rgba(242, 92, 92, 0.45); }
.main { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.8fr); gap: 13px; }
.left, .right { min-height: 0; display: flex; flex-direction: column; gap: 13px; }
.panel { min-height: 0; padding: 14px 16px; border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 8px; background: rgba(16, 22, 36, 0.66); overflow: hidden; }
.chart-panel { flex: 1; display: flex; flex-direction: column; }
.panel-head { flex: none; display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.panel-head h3 { margin: 0; color: #dfe7f3; font-size: 12px; font-weight: 600; letter-spacing: 0.05em; }
.panel-head > span { color: #63738a; font: 9px var(--font-mono); }
.range { display: flex; gap: 2px; }
.range span { padding: 3px 7px; border-radius: 3px; color: #63738a; font: 9px var(--font-mono); }
.range span.active { background: rgba(91, 140, 255, 0.16); color: #dfe7f3; }
.accounts { flex: none; height: 136px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.account { min-width: 0; padding: 12px 15px; border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 8px; background: rgba(21, 28, 44, 0.48); }
.account-top { display: flex; justify-content: space-between; color: #aab8cc; font-size: 10px; }
.account-top em { color: #63738a; font-style: normal; font-size: 9px; }
.account > strong { display: block; margin-top: 8px; color: #fff; font: 600 25px var(--font-mono); letter-spacing: -0.03em; }
.account-bottom { display: flex; justify-content: space-between; margin-top: 8px; color: #63738a; font: 9px var(--font-mono); }
.focus { flex: 1; display: flex; flex-direction: column; }
.focus-list { flex: 1; display: flex; flex-direction: column; gap: 7px; }
.focus-item { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 11px 13px; border: 1px solid rgba(125, 139, 161, 0.14); border-radius: 6px; background: rgba(21, 28, 44, 0.4); }
.focus-item.issue { border-color: rgba(240, 68, 56, 0.35); }
.focus-head { display: flex; align-items: center; gap: 7px; }
.dot { width: 5px; height: 5px; border-radius: 50%; background: #2ecc8f; }
.dot.offline { background: #f25c5c; }
.dot.degraded { background: #f5a524; }
.dot.paused { background: #7d8ba1; }
.focus-head strong { flex: 1; min-width: 0; color: #fff; font-size: 11px; font-weight: 500; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.focus-head em { color: #2ecc8f; font-size: 8px; font-style: normal; }
.focus-head em.offline { color: #f25c5c; }
.focus-head em.degraded { color: #f5a524; }
.focus-head em.paused { color: #7d8ba1; }
.focus-meta { display: flex; gap: 9px; margin-top: 3px; color: #63738a; font-size: 8px; }
.focus-data { display: flex; align-items: flex-end; gap: 13px; margin-top: 7px; }
.focus-data b { color: #fff; font: 600 15px var(--font-mono); }
.focus-data span { color: #7d8ba1; font: 9px var(--font-mono); padding-bottom: 2px; }
.focus-data > :last-child { margin-left: auto; }
.feed { flex: none; height: 210px; }
.feed-row { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 7px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.1); }
.feed-row:last-child { border-bottom: 0; }
.type { width: 17px; height: 17px; display: grid; place-items: center; border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 3px; color: #38bdf8; font: 8px var(--font-mono); }
.type.message { border-color: rgba(125, 139, 161, 0.2); color: #7d8ba1; }
.feed-row div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.feed-row strong { color: #dfe7f3; font-size: 9px; font-weight: 500; }
.feed-row span { color: #7d8ba1; font-size: 9px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.feed-row time { color: #44536a; font: 8px var(--font-mono); }
</style>
