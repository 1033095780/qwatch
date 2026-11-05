<script setup lang="ts">
// LayoutA.vue — 指挥中心：左指标/账户、中权益+动态、右策略状态。
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
const ranked = computed(() => [...runners.value].sort((a, b) => Number(b.today_pnl || 0) - Number(a.today_pnl || 0)));
const maxAbs = computed(() => Math.max(1, ...ranked.value.map((r) => Math.abs(Number(r.today_pnl || 0)))));
</script>

<template>
  <div class="bs-a">
    <header class="top">
      <div class="brand">
        <span class="mark">Q</span>
        <div><strong>qwatch</strong><span>交易监控指挥中心</span></div>
      </div>
      <div class="top-meta">
        <span class="live"><i />LIVE</span>
        <span>{{ dateText }}</span>
        <strong class="clock">{{ timeText }}</strong>
      </div>
    </header>

    <main class="grid">
      <aside class="left">
        <section class="hero">
          <div class="eyebrow">TOTAL EQUITY / 总权益</div>
          <div class="hero-value">{{ money(data.overview.total_equity) }}</div>
          <div class="hero-pnl" :class="pnlClass(today)">
            <span>今日盈利额</span>
            <strong>{{ pnl(today) }}</strong>
          </div>
          <div class="hero-foot"><span>{{ data.overview.account_count }} 个账户</span><span>{{ data.overview.running }} / {{ data.overview.total }} 策略在线</span></div>
        </section>

        <section class="panel accounts">
          <div class="panel-head"><h3>账户</h3><span>{{ accounts.length }}</span></div>
          <div v-for="account in accounts" :key="account.id" class="account-row">
            <div class="account-name"><strong>{{ account.name }}</strong><span>{{ account.strategy_count }} 个策略 · {{ account.online_strategies }} 在线</span></div>
            <div class="account-num"><b>{{ money(account.equity) }}</b><span :class="pnlClass(account.today_pnl)">今日 {{ pnl(account.today_pnl) }}</span><NavSparkline v-if="account.equity_sparkline?.length" :values="account.equity_sparkline" :width="150" :height="44" /></div>
          </div>
        </section>

        <section class="panel health">
          <div class="panel-head"><h3>系统</h3><span>HEALTH</span></div>
          <div class="health-row"><span>进程在线</span><b>{{ data.overview.processes_online }}<i>/{{ data.overview.processes_total }}</i></b></div>
          <div class="health-row"><span>账户</span><b>{{ data.overview.account_count }}</b></div>
          <div class="health-row"><span>数据延迟</span><b class="ok-value">&lt; 1s</b></div>
        </section>
      </aside>

      <section class="middle">
        <section class="panel chart-panel">
          <div class="panel-head chart-head">
            <div><h3>权益曲线</h3><span>PORTFOLIO EQUITY</span></div>
            <div class="range"><span class="active">1D</span><span>1W</span><span>1M</span><span>ALL</span></div>
          </div>
          <NavChart :data="curve" :height="680" />
          <div class="chart-stats">
            <span><em>进程在线</em><b>{{ data.overview.processes_online }}<i>/{{ data.overview.processes_total }}</i></b></span>
            <span><em>活跃告警</em><b :class="{ danger: data.overview.active_alerts }">{{ data.overview.active_alerts }}</b></span>
            <span><em>账户</em><b>{{ data.overview.account_count }}</b></span>
          </div>
        </section>

        <section class="panel activity">
          <div class="panel-head"><h3>实时动态</h3><span>EVENT STREAM</span></div>
          <div class="activity-list">
            <div v-for="event in events" :key="event.id" class="event-row">
              <span class="event-type" :class="event.type">{{ event.type === 'signal' ? '信号' : '消息' }}</span>
              <strong>{{ event.runner_name || event.instrument }}</strong>
              <span class="event-text">{{ event.type === 'signal' ? (event.symbol + ' ' + event.action + ' ' + event.qty + ' @ ' + event.price) : event.text }}</span>
              <time>{{ event.ts ? new Date(event.ts).toLocaleTimeString('zh-CN', { hour12: false }) : '' }}</time>
            </div>
          </div>
        </section>
      </section>

      <aside class="right">
        <section class="panel strategy-panel">
          <div class="panel-head"><h3>策略状态</h3><span>{{ data.overview.running }} / {{ data.overview.total }} 在线</span></div>
          <div class="strategy-list">
            <article v-for="runner in runners" :key="runner.id" class="strategy-row" :class="{ issue: runner.status !== 'running' }">
              <div class="strategy-main">
                <span class="status-dot" :class="runner.status" />
                <div class="strategy-name"><strong>{{ runner.name }}</strong><span>{{ runner.account_name }}</span></div>
                <span class="status-label" :class="runner.status">{{ issueText(runner) }}</span>
              </div>
              <div class="strategy-data">
                <div><em>策略权益</em><b>{{ money(runner.equity) }}</b></div>
                <div><em>今日盈利</em><b :class="pnlClass(runner.today_pnl)">{{ pnl(runner.today_pnl) }}</b></div>
                <NavSparkline v-if="runner.equity_sparkline?.length" :values="runner.equity_sparkline" :width="130" :height="34" />
              </div>
              <div class="strategy-foot"><span>{{ runner.process_count > 1 ? runner.process_count + ' 个进程' : '单进程' }}</span><span>{{ runner.online_processes }}/{{ runner.process_count }} 在线</span></div>
            </article>
          </div>
        </section>

        <section class="panel contribution">
          <div class="panel-head"><h3>今日盈利贡献</h3><span>PNL RANK</span></div>
          <div v-for="runner in ranked" :key="runner.id" class="contrib-row">
            <span class="contrib-name">{{ runner.name }}</span>
            <span class="contrib-bar"><i :class="pnlClass(runner.today_pnl)" :style="{ width: Math.max(5, Math.abs(Number(runner.today_pnl || 0)) / maxAbs * 100) + '%' }" /></span>
            <b :class="pnlClass(runner.today_pnl)">{{ pnl(runner.today_pnl) }}</b>
          </div>
        </section>
        <section class="panel right-alerts">
          <div class="panel-head"><h3>告警</h3><span class="alert-count">{{ data.overview.active_alerts }} ACTIVE</span></div>
          <div v-if="alerts.length" class="alert-list">
            <div v-for="alert in alerts" :key="alert.id" class="alert-row">
              <span class="alert-dot" :class="alert.status" />
              <div><strong>{{ alert.runner_name }}</strong><span>{{ alert.summary }}</span></div>
              <em>{{ alert.status === 'firing' ? '触发中' : '已恢复' }}</em>
            </div>
          </div>
          <div v-else class="quiet"><span class="ok" />全部正常</div>
        </section>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.bs-a { height: 100vh; padding: 20px 24px 18px; display: flex; flex-direction: column; gap: 14px; box-sizing: border-box; overflow: hidden; background: radial-gradient(1100px 500px at 45% -10%, rgba(31, 60, 120, 0.22), transparent 70%), #0a0e16; }
.top { flex: none; height: 52px; display: flex; align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 11px; }
.mark { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid rgba(91, 140, 255, 0.55); border-radius: 9px; color: #9db9ff; font: 700 17px var(--font-mono); background: rgba(91, 140, 255, 0.09); }
.brand div { display: flex; flex-direction: column; gap: 2px; }
.brand strong { font-size: 16px; letter-spacing: 0.08em; color: #fff; }
.brand span { color: #7d8ba1; font-size: 9px; letter-spacing: 0.16em; }
.top-meta { display: flex; align-items: center; gap: 18px; color: #7d8ba1; font: 10px var(--font-mono); letter-spacing: 0.08em; }
.live { display: inline-flex; align-items: center; gap: 5px; color: #2ecc8f; }
.live i { width: 5px; height: 5px; border-radius: 50%; background: #2ecc8f; box-shadow: 0 0 8px #2ecc8f; }
.clock { color: #e9eef6; font-size: 18px; letter-spacing: 0.04em; font-weight: 500; }
.grid { flex: 1; min-height: 0; display: grid; grid-template-columns: 318px minmax(0, 1fr) 470px; gap: 13px; }
.left, .middle, .right { min-height: 0; display: flex; flex-direction: column; gap: 13px; }
.panel { border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 8px; background: rgba(16, 22, 36, 0.72); padding: 15px 17px; min-height: 0; }
.hero { flex: none; min-height: 196px; padding: 19px 20px 18px; border: 1px solid rgba(91, 140, 255, 0.25); border-radius: 8px; background: linear-gradient(145deg, rgba(91, 140, 255, 0.12), rgba(16, 22, 36, 0.7)); }
.eyebrow { color: #6f86a8; font: 9px var(--font-mono); letter-spacing: 0.14em; }
.hero-value { margin-top: 9px; color: #fff; font: 700 44px/1 var(--font-mono); letter-spacing: -0.05em; }
.hero-pnl { display: flex; align-items: baseline; gap: 10px; margin-top: 16px; color: #7d8ba1; font-size: 10px; }
.hero-pnl strong { font: 600 22px var(--font-mono); }
.up { color: var(--up) !important; }
.down { color: var(--down) !important; }
.hero-foot { display: flex; gap: 15px; margin-top: 16px; padding-top: 12px; border-top: 1px solid rgba(125, 139, 161, 0.14); color: #7d8ba1; font-size: 10px; }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.panel-head h3 { margin: 0; color: #dfe7f3; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; }
.panel-head > span { color: #63738a; font: 9px var(--font-mono); letter-spacing: 0.08em; }
.accounts { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.accounts .panel-head { flex: none; }
.account-row { flex: 1; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 13px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.12); }
.account-row:last-child { border-bottom: 0; }
.account-name { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.account-name strong { color: #fff; font-size: 12px; font-weight: 500; }
.account-name span { color: #63738a; font-size: 9px; }
.account-num { text-align: right; display: flex; flex-direction: column; gap: 4px; }
.account-num b { color: #fff; font: 600 16px var(--font-mono); }
.account-num span { font: 10px var(--font-mono); }
.health { flex: none; }
.health-row { display: flex; align-items: baseline; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.1); color: #7d8ba1; font-size: 9px; }
.health-row:last-child { border-bottom: 0; }
.health-row b { color: #dfe7f3; font: 600 14px var(--font-mono); }
.health-row b i { color: #63738a; font-style: normal; font-size: 9px; }
.ok-value { color: #2ecc8f !important; }
.contribution { flex: 1; }
.contrib-row { display: grid; grid-template-columns: 84px minmax(0, 1fr) 66px; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.1); }
.contrib-row:last-child { border-bottom: 0; }
.contrib-name { color: #aab8cc; font-size: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.contrib-bar { height: 4px; border-radius: 2px; background: rgba(125, 139, 161, 0.12); overflow: hidden; }
.contrib-bar i { display: block; height: 100%; border-radius: 2px; background: #2ecc8f; }
.contrib-bar i.up { background: var(--up); }
.contrib-bar i.down { background: var(--down); }
.contrib-row b { text-align: right; font: 600 10px var(--font-mono); }
.right-alerts { flex: none; height: 150px; }
.alert-count { color: #f25c5c !important; }
.alert-list { display: flex; flex-direction: column; gap: 9px; }
.alert-row { display: grid; grid-template-columns: 7px minmax(0, 1fr) auto; gap: 8px; align-items: start; }
.alert-dot { width: 6px; height: 6px; margin-top: 4px; border-radius: 50%; background: #f25c5c; }
.alert-dot.resolved { background: #2ecc8f; }
.alert-row div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.alert-row strong { color: #dfe7f3; font-size: 10px; font-weight: 500; }
.alert-row span { color: #7d8ba1; font-size: 9px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.alert-row em { color: #f25c5c; font: 9px var(--font-mono); font-style: normal; }
.quiet { display: flex; align-items: center; gap: 7px; padding: 30px 0; color: #7d8ba1; font-size: 11px; }
.ok { width: 6px; height: 6px; border-radius: 50%; background: #2ecc8f; }
.chart-panel { flex: 1; display: flex; flex-direction: column; padding-bottom: 10px; overflow: hidden; }
.chart-head { flex: none; }
.chart-head div { display: flex; align-items: baseline; gap: 9px; }
.chart-head span { color: #63738a; font: 8px var(--font-mono); letter-spacing: 0.12em; }
.range { display: flex; gap: 3px; padding: 2px; border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 5px; }
.range span { padding: 3px 7px; border-radius: 3px; color: #63738a; font: 9px var(--font-mono); }
.range span.active { background: rgba(91, 140, 255, 0.18); color: #dfe7f3; }
.chart-stats { display: flex; gap: 30px; padding: 10px 2px 0; border-top: 1px solid rgba(125, 139, 161, 0.12); }
.chart-stats span { display: flex; align-items: baseline; gap: 6px; }
.chart-stats em { color: #63738a; font-style: normal; font-size: 9px; }
.chart-stats b { color: #dfe7f3; font: 600 15px var(--font-mono); }
.chart-stats b.danger { color: #f25c5c; }
.chart-stats b i { color: #63738a; font-style: normal; font-size: 10px; }
.activity { flex: none; height: 186px; overflow: hidden; }
.activity-list { display: flex; flex-direction: column; }
.event-row { display: grid; grid-template-columns: 34px 88px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px solid rgba(125, 139, 161, 0.1); }
.event-row:last-child { border-bottom: 0; }
.event-type { padding: 2px 4px; border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 3px; color: #38bdf8; font-size: 8px; text-align: center; }
.event-type.message { border-color: rgba(125, 139, 161, 0.25); color: #7d8ba1; }
.event-row strong { color: #dfe7f3; font-size: 9px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event-text { color: #8d9bb0; font-size: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event-row time { color: #63738a; font: 8px var(--font-mono); }
.strategy-panel { flex: none; overflow: hidden; }
.strategy-list { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.strategy-row { padding: 13px 13px 11px; border: 1px solid rgba(125, 139, 161, 0.16); border-radius: 6px; background: rgba(21, 28, 44, 0.48); }
.strategy-row.issue { border-color: rgba(240, 68, 56, 0.4); background: rgba(240, 68, 56, 0.045); }
.strategy-main { display: flex; align-items: center; gap: 8px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #2ecc8f; }
.status-dot.offline { background: #f25c5c; box-shadow: 0 0 7px rgba(242, 92, 92, 0.55); }
.status-dot.degraded { background: #f5a524; box-shadow: 0 0 7px rgba(245, 165, 36, 0.45); }
.status-dot.paused { background: #7d8ba1; }
.strategy-name { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.strategy-name strong { color: #fff; font-size: 12px; font-weight: 500; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.strategy-name span { color: #63738a; font-size: 9px; }
.status-label { padding: 2px 6px; border: 1px solid rgba(46, 204, 143, 0.25); border-radius: 3px; color: #2ecc8f; font-size: 8px; }
.status-label.offline { border-color: rgba(242, 92, 92, 0.4); color: #f25c5c; }
.status-label.degraded { border-color: rgba(245, 165, 36, 0.35); color: #f5a524; }
.status-label.paused { border-color: rgba(125, 139, 161, 0.3); color: #7d8ba1; }
.strategy-data { display: flex; align-items: flex-end; gap: 20px; margin-top: 11px; }
.strategy-data > div { display: flex; flex-direction: column; gap: 3px; }
.strategy-data em { color: #63738a; font-style: normal; font-size: 8px; }
.strategy-data b { color: #fff; font: 600 16px var(--font-mono); }
.strategy-data > :last-child { margin-left: auto; }
.strategy-foot { display: flex; justify-content: space-between; margin-top: 9px; padding-top: 7px; border-top: 1px solid rgba(125, 139, 161, 0.1); color: #63738a; font-size: 8px; }
</style>