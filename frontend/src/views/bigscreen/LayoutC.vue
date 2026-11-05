<script setup lang="ts">
// LayoutC.vue — 矩阵：四象限信息架构，适合挂在墙上扫读。
import { computed } from 'vue';
import type { BigScreenData } from './shared';
import { issueText, money, pnl, pnlClass } from './shared';
import NavChart from '@/components/NavChart.vue';
import NavSparkline from '@/components/NavSparkline.vue';

const props = defineProps<{ data: BigScreenData; now: Date; timeText: string; dateText: string }>();
const accounts = computed(() => props.data.accounts);
const runners = computed(() => props.data.runners);
const events = computed(() => (props.data.overview.recent_events || []).slice(0, 5));
const alerts = computed(() => (props.data.overview.recent_alerts || []).slice(0, 3));
const curve = computed(() => props.data.overview.equity_curve || []);
const today = computed(() => props.data.overview.today_pnl ?? props.data.overview.today_equity_change);
</script>

<template>
  <div class="bs-c">
    <header class="head">
      <div class="brand"><span class="grid-mark"><i /><i /><i /><i /></span><strong>qwatch</strong><span>全局监控矩阵</span></div>
      <div class="head-right"><span class="live"><i />LIVE</span><span>{{ dateText }} · {{ timeText }}</span><span class="back">布局预览</span></div>
    </header>

    <main class="matrix">
      <section class="cell hero">
        <span class="eyebrow">TOTAL EQUITY / 总权益</span>
        <div class="hero-value">{{ money(data.overview.total_equity) }}</div>
        <div class="hero-today">今日盈利额 <b :class="pnlClass(today)">{{ pnl(today) }}</b></div>
        <div class="hero-meta"><span>{{ data.overview.account_count }} 账户</span><span>{{ data.overview.running }} / {{ data.overview.total }} 在线</span><span>{{ data.overview.processes_online }} / {{ data.overview.processes_total }} 进程</span></div>
      </section>

      <section class="cell accounts">
        <div class="cell-head"><h3>账户</h3><span>ACCOUNTS</span></div>
        <div class="account-list">
          <article v-for="account in accounts" :key="account.id" class="account">
            <div class="account-name"><strong>{{ account.name }}</strong><span>{{ account.strategy_count }} 策略 · {{ account.online_strategies }} 在线</span></div>
            <div class="account-value">{{ money(account.equity) }}</div>
            <div class="account-pnl" :class="pnlClass(account.today_pnl)">今日 {{ pnl(account.today_pnl) }}</div>
          </article>
        </div>
      </section>

      <section class="cell chart">
        <div class="cell-head"><h3>组合权益</h3><div class="range"><span class="active">1D</span><span>1W</span><span>1M</span><span>ALL</span></div></div>
        <NavChart :data="curve" :height="520" />
      </section>

      <section class="cell strategies">
        <div class="cell-head"><h3>策略状态</h3><span>{{ data.overview.running }} / {{ data.overview.total }}</span></div>
        <div class="strategy-list">
          <article v-for="runner in runners" :key="runner.id" class="strategy" :class="{ issue: runner.status !== 'running' }">
            <div class="strategy-head"><span class="dot" :class="runner.status" /><strong>{{ runner.name }}</strong><em :class="runner.status">{{ issueText(runner) }}</em></div>
            <div class="strategy-sub">{{ runner.account_name }} · {{ runner.process_count > 1 ? runner.process_count + ' 个进程' : '单进程' }}</div>
            <div class="strategy-data">
              <div><span>权益</span><b>{{ money(runner.equity) }}</b></div>
              <div><span>今日</span><b :class="pnlClass(runner.today_pnl)">{{ pnl(runner.today_pnl) }}</b></div>
              <NavSparkline v-if="runner.equity_sparkline?.length" :values="runner.equity_sparkline" :width="120" :height="32" />
            </div>
          </article>
        </div>
      </section>

      <section class="cell activity">
        <div class="cell-head"><h3>实时动态</h3><span>EVENT STREAM</span></div>
        <div class="event-list">
          <div v-for="event in events" :key="event.id" class="event">
            <span class="type" :class="event.type">{{ event.type === 'signal' ? 'SIGNAL' : 'MSG' }}</span>
            <strong>{{ event.runner_name || event.instrument }}</strong>
            <span>{{ event.type === 'signal' ? event.symbol + ' ' + event.action + ' ' + event.qty + ' @ ' + event.price : event.text }}</span>
            <time>{{ event.ts ? new Date(event.ts).toLocaleTimeString('zh-CN', { hour12: false }) : '' }}</time>
          </div>
        </div>
      </section>

      <section class="cell alerts">
        <div class="cell-head"><h3>最近告警</h3><span class="danger">{{ data.overview.active_alerts }} ACTIVE</span></div>
        <div v-if="alerts.length" class="alert-list">
          <div v-for="alert in alerts" :key="alert.id" class="alert">
            <span class="alert-mark" :class="alert.status" />
            <div><strong>{{ alert.runner_name }}</strong><span>{{ alert.summary }}</span></div>
            <time>{{ alert.status === 'firing' ? '触发中' : '已恢复' }}</time>
          </div>
        </div>
        <div v-else class="all-clear"><i />全部正常</div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.bs-c { height: 100vh; box-sizing: border-box; padding: 18px 22px; overflow: hidden; display: flex; flex-direction: column; gap: 12px; background: #090d15; }
.head { flex: none; height: 42px; display: flex; align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 10px; }
.grid-mark { width: 23px; height: 23px; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 2px; }
.grid-mark i { border: 1px solid #5b8cff; border-radius: 1px; }
.grid-mark i:nth-child(2) { background: rgba(91, 140, 255, 0.55); }
.brand strong { color: #fff; font-size: 14px; letter-spacing: 0.12em; }
.brand > span:last-child { color: #63738a; font: 9px var(--font-mono); letter-spacing: 0.14em; }
.head-right { display: flex; align-items: center; gap: 16px; color: #63738a; font: 9px var(--font-mono); }
.live { display: inline-flex; align-items: center; gap: 5px; color: #2ecc8f; }
.live i { width: 5px; height: 5px; border-radius: 50%; background: #2ecc8f; }
.back { padding-left: 12px; border-left: 1px solid rgba(125, 139, 161, 0.2); color: #44536a; }
.matrix { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.18fr) minmax(380px, 0.82fr); grid-template-rows: 190px minmax(0, 1fr) 168px; gap: 12px; }
.cell { min-height: 0; padding: 14px 17px; border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 7px; background: rgba(16, 22, 36, 0.66); overflow: hidden; }
.hero { display: flex; flex-direction: column; justify-content: center; border-color: rgba(91, 140, 255, 0.26); background: linear-gradient(130deg, rgba(91, 140, 255, 0.1), rgba(16, 22, 36, 0.7)); }
.eyebrow { color: #63738a; font: 9px var(--font-mono); letter-spacing: 0.15em; }
.hero-value { margin-top: 5px; color: #fff; font: 700 48px/1 var(--font-mono); letter-spacing: -0.055em; }
.hero-today { margin-top: 10px; color: #7d8ba1; font-size: 10px; }
.hero-today b { margin-left: 5px; font: 600 16px var(--font-mono); }
.hero-meta { display: flex; gap: 18px; margin-top: 13px; padding-top: 10px; border-top: 1px solid rgba(125, 139, 161, 0.12); color: #63738a; font: 9px var(--font-mono); }
.up { color: var(--up) !important; }
.down { color: var(--down) !important; }
.accounts { display: flex; flex-direction: column; }
.cell-head { flex: none; display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 9px; }
.cell-head h3 { margin: 0; color: #dfe7f3; font-size: 12px; font-weight: 600; letter-spacing: 0.05em; }
.cell-head > span { color: #63738a; font: 9px var(--font-mono); }
.cell-head .danger { color: #f25c5c; }
.account-list { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.account { padding: 11px 13px; border: 1px solid rgba(125, 139, 161, 0.12); border-radius: 5px; background: rgba(21, 28, 44, 0.45); }
.account-name strong { display: block; color: #fff; font-size: 11px; font-weight: 500; }
.account-name span { display: block; margin-top: 3px; color: #63738a; font-size: 8px; }
.account-value { margin-top: 8px; color: #fff; font: 600 22px var(--font-mono); letter-spacing: -0.03em; }
.account-pnl { margin-top: 3px; font: 10px var(--font-mono); }
.chart { display: flex; flex-direction: column; }
.chart :deep(.nav-chart) { flex: 1; min-height: 0; }
.range { display: flex; gap: 2px; }
.range span { padding: 3px 7px; border-radius: 3px; color: #63738a; font: 9px var(--font-mono); }
.range span.active { background: rgba(91, 140, 255, 0.16); color: #dfe7f3; }
.strategies { display: flex; flex-direction: column; }
.strategy-list { flex: 1; display: flex; flex-direction: column; gap: 7px; }
.strategy { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 9px 11px; border: 1px solid rgba(125, 139, 161, 0.12); border-radius: 5px; background: rgba(21, 28, 44, 0.4); }
.strategy.issue { border-color: rgba(240, 68, 56, 0.38); }
.strategy-head { display: flex; align-items: center; gap: 7px; }
.dot { width: 5px; height: 5px; border-radius: 50%; background: #2ecc8f; }
.dot.offline { background: #f25c5c; }
.dot.degraded { background: #f5a524; }
.dot.paused { background: #7d8ba1; }
.strategy-head strong { flex: 1; min-width: 0; color: #fff; font-size: 11px; font-weight: 500; }
.strategy-head em { font-size: 8px; font-style: normal; color: #2ecc8f; }
.strategy-head em.offline { color: #f25c5c; }
.strategy-head em.degraded { color: #f5a524; }
.strategy-head em.paused { color: #7d8ba1; }
.strategy-sub { margin-top: 3px; color: #63738a; font-size: 8px; }
.strategy-data { display: flex; align-items: flex-end; gap: 16px; margin-top: 6px; }
.strategy-data > div { display: flex; flex-direction: column; gap: 2px; }
.strategy-data span { color: #63738a; font-size: 8px; }
.strategy-data b { color: #fff; font: 600 14px var(--font-mono); }
.strategy-data > :last-child { margin-left: auto; }
.activity { display: flex; flex-direction: column; }
.event-list { flex: 1; display: flex; flex-direction: column; }
.event { display: grid; grid-template-columns: 46px 100px minmax(0, 1fr) auto; gap: 9px; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.09); }
.event:last-child { border-bottom: 0; }
.type { color: #38bdf8; font: 7px var(--font-mono); letter-spacing: 0.05em; }
.type.message { color: #63738a; }
.event strong { color: #dfe7f3; font-size: 9px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event > span:nth-child(3) { color: #7d8ba1; font-size: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event time { color: #44536a; font: 8px var(--font-mono); }
.alerts { display: flex; flex-direction: column; }
.alert-list { flex: 1; display: flex; flex-direction: column; }
.alert { display: grid; grid-template-columns: 6px minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 7px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.09); }
.alert:last-child { border-bottom: 0; }
.alert-mark { width: 5px; height: 5px; margin-top: 4px; border-radius: 50%; background: #f25c5c; }
.alert-mark.resolved { background: #2ecc8f; }
.alert div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.alert strong { color: #dfe7f3; font-size: 9px; font-weight: 500; }
.alert span { color: #7d8ba1; font-size: 8px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.alert time { color: #f25c5c; font: 8px var(--font-mono); }
.all-clear { flex: 1; display: flex; align-items: center; justify-content: center; gap: 7px; color: #63738a; font-size: 10px; }
.all-clear i { width: 5px; height: 5px; border-radius: 50%; background: #2ecc8f; }
</style>
