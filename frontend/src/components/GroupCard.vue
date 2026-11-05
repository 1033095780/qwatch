// GroupCard.vue — v0.5 策略卡片：策略权益（整数）、账户/券商、策略简介、进程数/异常、整行心跳；整卡点击。
<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { AlertTriangle } from 'lucide-vue-next';
import type { Runner } from '@/api/types';
import { fmtNumber } from '@/utils/format';
import HeartbeatGrid from './HeartbeatGrid.vue';
import NavSparkline from './NavSparkline.vue';
import StatusDot from './StatusDot.vue';
import StatusTag from './StatusTag.vue';

const props = defineProps<{ runner: Runner }>();
const router = useRouter();

const accountName = computed(() => props.runner.account_name || '未关联账户');
const broker = computed(() => props.runner.account_broker || '');
const equity = computed(() => props.runner.equity ?? null);
const issueCount = computed(() => Math.max(0, (props.runner.process_count || 0) - (props.runner.online_processes || 0)));

function goDetail(): void {
  void router.push('/strategies/' + props.runner.id);
}
</script>

<template>
  <article class="group-card" role="link" tabindex="0" @click="goDetail" @keydown.enter="goDetail">
    <header class="card-head">
      <div class="identity">
        <StatusDot :status="runner.status" :size="7" :pulse="runner.status === 'running'" />
        <span class="name truncate" :title="runner.name">{{ runner.name }}</span>
        <StatusTag :status="runner.status" compact />
      </div>
      <span v-if="issueCount" class="issue"><AlertTriangle :size="11" />{{ issueCount }} 个进程异常</span>
    </header>

    <div class="account-line">
      <span v-if="broker && broker !== accountName" class="broker">{{ broker }}</span>
      <span class="account-name truncate" :title="accountName">{{ accountName }}</span>
    </div>

    <p v-if="runner.description" class="strategy-desc truncate" :title="runner.description">{{ runner.description }}</p>

    <div class="equity-area">
      <div class="equity-copy">
        <span class="equity-label">策略权益</span>
        <strong class="equity-value mono">{{ equity !== null ? '¥' + fmtNumber(equity, 0) : '—' }}</strong>
      </div>
      <div class="spark-wrap">
        <NavSparkline v-if="runner.equity_sparkline && runner.equity_sparkline.length" :values="runner.equity_sparkline" :width="160" :height="38" />
      </div>
    </div>

    <footer class="card-foot">
      <div class="process-line">
        <span class="proc-meta">{{ runner.process_count > 1 ? runner.process_count + ' 个进程' : '单进程' }}</span>
        <span v-if="runner.status === 'paused'" class="paused-label">已暂停监控</span>
      </div>
      <HeartbeatGrid stretch :status="runner.status" :last-seen="runner.last_seen" class="card-heartbeat" />
    </footer>
  </article>
</template>

<style scoped>
.group-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  padding: 15px 16px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(28, 37, 57, 0.68), rgba(16, 22, 35, 0.72));
  transition: border-color 160ms ease, transform 160ms ease;
  color: inherit;
}
.group-card:hover { border-color: var(--border-strong); transform: translateY(-1px); }
.group-card:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.identity { display: flex; align-items: center; gap: 7px; min-width: 0; }
.name { font-size: 14px; font-weight: 600; color: #ffffff; }
.issue { display: inline-flex; align-items: center; gap: 3px; color: #f5b64b; font-size: 10px; white-space: nowrap; }
.account-line { display: flex; align-items: center; gap: 7px; margin-top: 7px; min-width: 0; font-size: 10px; color: var(--text-3); }
.broker { flex: none; padding: 1px 6px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-2); }
.account-name { color: var(--text-2); }
.strategy-desc { margin-top: 5px; font-size: 10px; color: var(--text-3); }
.equity-area { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; margin-top: 14px; }
.equity-copy { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.spark-wrap { flex: 1 1 auto; max-width: 44%; min-width: 60px; opacity: 0.9; }
.equity-label { font-size: 10px; color: var(--text-3); }
.equity-value { font-size: 23px; line-height: 1.15; letter-spacing: -0.03em; color: #ffffff; white-space: nowrap; }
.card-foot { margin-top: 14px; }
.process-line { display: flex; align-items: baseline; gap: 5px; margin-bottom: 7px; font-size: 10px; color: var(--text-3); }
.proc-meta { color: var(--text-2); font-size: 10px; }
.paused-label { margin-left: auto; color: #8b97ab; }
@media (max-width: 520px) { .equity-value { font-size: 20px; } }
</style>
