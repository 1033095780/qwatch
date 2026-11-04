<script setup lang="ts">
// GroupCard.vue — 策略卡片：权益分层展示，心跳占满底部，整卡进入详情。
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

    <div class="equity-area">
      <div class="equity-copy">
        <span class="equity-label">策略权益</span>
        <strong class="equity-value mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</strong>
      </div>
      <div class="spark-wrap">
        <NavSparkline v-if="runner.equity_sparkline && runner.equity_sparkline.length" :values="runner.equity_sparkline" :width="152" :height="38" />
      </div>
    </div>

    <HeartbeatGrid stretch :status="runner.status" :last-seen="runner.last_seen" class="card-heartbeat" />
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
}
.group-card:hover { border-color: var(--border-strong); transform: translateY(-1px); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.identity { display: flex; align-items: center; gap: 7px; min-width: 0; }
.name { font-size: 14px; font-weight: 600; color: #ffffff; }
.issue { display: inline-flex; align-items: center; gap: 3px; color: #f5b64b; font-size: 10px; white-space: nowrap; }
.equity-area { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; margin-top: 17px; }
.equity-copy { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.equity-label { font-size: 10px; color: var(--text-3); }
.equity-value { font-size: 23px; line-height: 1.15; letter-spacing: -0.03em; color: #ffffff; white-space: nowrap; }
.spark-wrap { flex: 0 0 auto; opacity: 0.9; }
.card-heartbeat { margin-top: 16px; }
@media (max-width: 520px) { .equity-value { font-size: 20px; } .spark-wrap { display: none; } }
</style>
