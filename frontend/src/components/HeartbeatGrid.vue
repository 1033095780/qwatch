<script setup lang="ts">
// HeartbeatGrid.vue — 24 格心跳/状态格，保持 v0.1 的彩色块视觉。
import { computed } from 'vue';
import type { HeartbeatDay, ProcessStatus, RunnerStatus } from '@/api/types';

const props = withDefaults(defineProps<{
  status: RunnerStatus | ProcessStatus;
  retired?: boolean;
  lastSeen?: string | null;
  stretch?: boolean;
  history?: HeartbeatDay[];
}>(), {
  retired: false,
  lastSeen: null,
  stretch: false,
  history: () => [],
});

const bars = computed(() => {
  const status = props.retired ? 'retired' : props.status;
  if (status === 'running') return Array.from({ length: 24 }, () => 'ok');
  if (status === 'degraded') return [...Array(16).fill('ok'), ...Array(8).fill('warn')];
  if (status === 'offline') return [...Array(8).fill('off'), ...Array(16).fill('bad')];
  if (status === 'paused') return Array(24).fill('off');
  return Array(24).fill('off');
});
function dayTitle(day: HeartbeatDay): string {
  if (day.ratio === null) return day.date + ' 暂无采样';
  return day.date + ' 可用率 ' + (day.ratio * 100).toFixed(2) + '%';
}
function dayTone(day: HeartbeatDay): string {
  if (day.ratio === null) return 'off';
  if (day.ratio >= 0.995) return 'ok';
  if (day.ratio >= 0.98) return 'warn';
  return 'bad';
}
/** 把 7 天数据映射到 24 格，保留原来的 24 格心跳视觉。 */
const dayCells = computed(() => {
  if (!props.history.length) return [];
  const weights = props.history.length === 7 ? [4, 4, 4, 3, 3, 3, 3] : props.history.map(() => 24 / props.history.length);
  return props.history.flatMap((day, index) => {
    const count = Math.max(1, Math.round(weights[index] || 1));
    return Array.from({ length: count }, () => day);
  }).slice(0, 24);
});
</script>

<template>
  <div v-if="history.length" class="hb-grid" :class="{ stretch }" role="img" aria-label="最近 7 天可用率">
    <span v-for="(day, index) in dayCells" :key="day.date + '-' + index" class="hb-cell" :class="dayTone(day)" :title="dayTitle(day)" />
  </div>
  <div v-else class="hb-grid" :class="{ stretch }" :title="lastSeen ? '最后心跳 ' + lastSeen : '暂无心跳'" role="img" aria-label="心跳状态">
    <span v-for="(tone, i) in bars" :key="i" class="hb-cell" :class="tone" />
  </div>
</template>

<style scoped>
.hb-grid {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 14px;
}
.hb-cell {
  display: block;
  width: 4px;
  height: 10px;
  border-radius: 1.5px;
  background: #2a3448;
}
.hb-grid.stretch {
  display: flex;
  width: 100%;
  gap: 3px;
}
.hb-grid.stretch .hb-cell {
  flex: 1;
  width: auto;
  height: 9px;
}
.hb-cell.ok { background: #2ecc8f; }
.hb-cell.warn { background: #f5a524; }
.hb-cell.bad { background: #f04438; }
.hb-cell.off { background: #3a465c; }
</style>