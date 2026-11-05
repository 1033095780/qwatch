<script setup lang="ts">
// LayoutD.vue — 纸面报告：浅色编辑风，适合投屏/复盘，信息层级最克制。
import { computed } from 'vue';
import type { BigScreenData } from './shared';
import { issueText, money, pnl, pnlClass } from './shared';
import NavChart from '@/components/NavChart.vue';
import NavSparkline from '@/components/NavSparkline.vue';

const props = defineProps<{ data: BigScreenData; now: Date; timeText: string; dateText: string }>();
const accounts = computed(() => props.data.accounts);
const runners = computed(() => props.data.runners);
const events = computed(() => (props.data.overview.recent_events || []).slice(0, 4));
const alerts = computed(() => (props.data.overview.recent_alerts || []).slice(0, 2));
const curve = computed(() => props.data.overview.equity_curve || []);
const today = computed(() => props.data.overview.today_pnl ?? props.data.overview.today_equity_change);
const issues = computed(() => runners.value.filter((r) => r.status !== 'running'));
</script>

<template>
  <div class="bs-d">
    <header class="head">
      <div class="brand"><strong>qwatch</strong><span>每日监控简报</span></div>
      <div class="head-right"><span>DAILY BRIEF / {{ dateText }}</span><b>{{ timeText }}</b><span class="back">布局预览</span></div>
    </header>

    <section class="hero">
      <div>
        <span class="eyebrow">TOTAL EQUITY</span>
        <h1>{{ money(data.overview.total_equity) }}</h1>
        <p class="hero-note">{{ data.overview.account_count }} 个账户 · {{ data.overview.running }} / {{ data.overview.total }} 个策略在线</p>
      </div>
      <div class="hero-side">
        <span>今日盈利额</span>
        <strong :class="pnlClass(today)">{{ pnl(today) }}</strong>
        <p>{{ issues.length ? issues.length + ' 个策略需要关注' : '所有策略运行正常' }}</p>
      </div>
    </section>

    <section class="chart-wrap">
      <div class="chart-head"><span>组合权益曲线</span><span class="period">1D</span></div>
      <NavChart :data="curve" :height="470" />
    </section>

    <main class="bottom">
      <section class="col accounts">
        <h2>账户</h2>
        <article v-for="account in accounts" :key="account.id" class="account">
          <div class="row"><strong>{{ account.name }}</strong><span>{{ account.strategy_count }} 策略</span></div>
          <div class="row value"><b>{{ money(account.equity) }}</b><span :class="pnlClass(account.today_pnl)">今日 {{ pnl(account.today_pnl) }}</span></div>
        </article>
      </section>

      <section class="col strategies">
        <h2>策略状态</h2>
        <article v-for="runner in runners" :key="runner.id" class="strategy" :class="{ issue: runner.status !== 'running' }">
          <div class="row"><strong><i class="dot" :class="runner.status" />{{ runner.name }}</strong><span class="state" :class="runner.status">{{ issueText(runner) }}</span></div>
          <div class="strategy-foot"><span>{{ runner.account_name }}</span><span>{{ money(runner.equity) }}</span><span :class="pnlClass(runner.today_pnl)">{{ pnl(runner.today_pnl) }}</span><NavSparkline v-if="runner.equity_sparkline?.length" :values="runner.equity_sparkline" :width="62" :height="22" /></div>
        </article>
      </section>

      <section class="col feed">
        <h2>动态</h2>
        <div v-for="event in events" :key="event.id" class="event">
          <span class="type">{{ event.type === 'signal' ? '信号' : '消息' }}</span>
          <div><strong>{{ event.runner_name || event.instrument }}</strong><span>{{ event.type === 'signal' ? event.symbol + ' ' + event.action + ' ' + event.qty : event.text }}</span></div>
          <time>{{ event.ts ? new Date(event.ts).toLocaleTimeString('zh-CN', { hour12: false }) : '' }}</time>
        </div>
        <div class="alert-line" :class="{ active: data.overview.active_alerts }"><span>{{ data.overview.active_alerts ? data.overview.active_alerts + ' 个活跃告警' : '无活跃告警' }}</span><em v-if="alerts.length">{{ alerts[0].runner_name }} · {{ alerts[0].summary }}</em></div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.bs-d { --bg: #f3f1ea; --surface: #faf8f2; --surface-2: #edeae1; --border: #d8d3c7; --border-strong: #bdb7a9; --text: #17202a; --text-2: #566070; --text-3: #89909b; --up: #c74343; --down: #2f8a68; --primary: #315b8a; --primary-soft: rgba(49, 91, 138, 0.1); --grid-line: #e2ded4; --font-display: "Georgia", "Songti SC", "STSong", serif; height: 100vh; box-sizing: border-box; padding: 22px 36px 18px; overflow: hidden; display: flex; flex-direction: column; gap: 12px; background: var(--bg); color: var(--text); }
.head { flex: none; display: flex; align-items: baseline; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
.brand { display: flex; align-items: baseline; gap: 12px; }
.brand strong { color: var(--text); font: 700 17px var(--font-display); letter-spacing: 0.06em; }
.brand span { color: var(--text-3); font: 9px var(--font-mono); letter-spacing: 0.16em; }
.head-right { display: flex; align-items: baseline; gap: 14px; color: var(--text-3); font: 9px var(--font-mono); }
.head-right b { color: var(--text); font-size: 14px; font-weight: 500; }
.back { padding-left: 12px; border-left: 1px solid var(--border); color: #aaa294; }
.hero { flex: none; display: flex; align-items: flex-end; justify-content: space-between; gap: 30px; padding: 4px 0 14px; border-bottom: 1px solid var(--border); }
.eyebrow { color: var(--text-3); font: 9px var(--font-mono); letter-spacing: 0.18em; }
h1 { margin: 3px 0 0; color: var(--text); font: 500 58px/1 var(--font-display); letter-spacing: -0.045em; }
.hero-note { margin-top: 9px; color: var(--text-3); font-size: 10px; }
.hero-side { text-align: right; padding-bottom: 3px; }
.hero-side > span { color: var(--text-3); font-size: 10px; }
.hero-side > strong { display: block; margin-top: 4px; font: 500 30px var(--font-display); }
.hero-side p { margin-top: 6px; color: var(--text-3); font-size: 9px; }
.up { color: var(--up) !important; }
.down { color: var(--down) !important; }
.chart-wrap { flex: 1; min-height: 0; padding: 11px 16px 6px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface); }
.chart-head { display: flex; justify-content: space-between; color: var(--text-2); font-size: 10px; }
.period { color: var(--text-3); font: 9px var(--font-mono); }
.bottom { flex: none; height: 270px; display: grid; grid-template-columns: 1fr 1.12fr 1.2fr; gap: 22px; border-top: 1px solid var(--border); padding-top: 13px; overflow: hidden; }
.col { min-width: 0; border-left: 1px solid var(--border); padding-left: 16px; }
.col:first-child { border-left: 0; padding-left: 0; }
h2 { margin: 0 0 9px; color: var(--text); font: 500 13px var(--font-display); letter-spacing: 0.06em; }
.account { padding: 8px 0; border-bottom: 1px solid var(--border); }
.account:last-child { border-bottom: 0; }
.row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.row strong { color: var(--text); font-size: 11px; font-weight: 600; }
.row > span { color: var(--text-3); font-size: 9px; }
.value { margin-top: 5px; }
.value b { color: var(--text); font: 500 20px var(--font-display); }
.value span { font: 9px var(--font-mono); }
.strategy { padding: 7px 0; border-bottom: 1px solid var(--border); }
.strategy:last-child { border-bottom: 0; }
.strategy.issue .state { color: var(--up); }
.dot { display: inline-block; width: 5px; height: 5px; margin-right: 6px; border-radius: 50%; background: var(--down); vertical-align: 1px; }
.dot.offline { background: var(--up); }
.dot.degraded { background: #b7791f; }
.dot.paused { background: var(--text-3); }
.state { font: 8px var(--font-mono); color: var(--down); }
.state.offline { color: var(--up); }
.state.degraded { color: #b7791f; }
.state.paused { color: var(--text-3); }
.strategy-foot { display: flex; align-items: center; gap: 9px; margin-top: 5px; color: var(--text-3); font: 8px var(--font-mono); }
.strategy-foot > span:nth-child(2) { margin-left: auto; color: var(--text-2); }
.strategy-foot > :last-child { margin-left: 0; }
.event { display: grid; grid-template-columns: 26px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--border); }
.type { color: var(--primary); font-size: 8px; }
.event div { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.event strong { color: var(--text); font-size: 9px; font-weight: 600; }
.event span { color: var(--text-3); font-size: 8px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.event time { color: var(--text-3); font: 8px var(--font-mono); }
.alert-line { margin-top: 8px; padding: 7px 9px; border: 1px solid var(--border); background: var(--surface); }
.alert-line span { color: var(--text-3); font-size: 9px; }
.alert-line.active span { color: var(--up); }
.alert-line em { display: block; margin-top: 2px; color: var(--text-2); font-size: 8px; font-style: normal; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
