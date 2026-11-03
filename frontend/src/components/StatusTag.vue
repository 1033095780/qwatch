<script setup lang="ts">
// StatusTag.vue — Runner 状态标签（颜色固定，不随涨跌配色方案变化）。
import { computed } from 'vue';
import type { RunnerStatus } from '@/api/types';
import StatusDot from './StatusDot.vue';

const props = defineProps<{ status: RunnerStatus; compact?: boolean }>();

const META: Record<RunnerStatus, { label: string; color: string; bg: string; border: string }> = {
  running: { label: '运行中', color: '#2ecc8f', bg: 'rgba(46,204,143,.1)', border: 'rgba(46,204,143,.26)' },
  degraded: { label: '降级', color: '#f5a524', bg: 'rgba(245,165,36,.1)', border: 'rgba(245,165,36,.26)' },
  offline: { label: '离线', color: '#f04438', bg: 'rgba(240,68,56,.1)', border: 'rgba(240,68,56,.26)' },
  off_hours: { label: '非交易时段', color: '#8b97ab', bg: 'rgba(95,109,132,.12)', border: 'rgba(95,109,132,.3)' },
};
const meta = computed(() => META[props.status]);
</script>

<template>
  <span
    class="status-tag"
    :class="{ compact }"
    :style="{ color: meta.color, background: meta.bg, borderColor: meta.border }"
  >
    <StatusDot :status="status" :size="6" />
    {{ meta.label }}
  </span>
</template>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 11px;
  white-space: nowrap;
}
.compact {
  padding: 0 6px;
  font-size: 11px;
}
</style>
