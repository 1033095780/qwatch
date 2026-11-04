// StatusTag.vue — 策略/进程状态标签（P0 看门狗状态体系）。
<script setup lang="ts">
import { computed } from 'vue';
import type { ProcessStatus } from '@/api/types';
import { PROCESS_STATUS_LABELS } from '@/utils/catalog';
import StatusDot from './StatusDot.vue';

const props = defineProps<{ status: ProcessStatus; compact?: boolean }>();

const META: Record<ProcessStatus, { color: string; bg: string; border: string }> = {
  running: { color: '#2ecc8f', bg: 'rgba(46,204,143,.1)', border: 'rgba(46,204,143,.26)' },
  degraded: { color: '#f5a524', bg: 'rgba(245,165,36,.1)', border: 'rgba(245,165,36,.26)' },
  offline: { color: '#f04438', bg: 'rgba(240,68,56,.1)', border: 'rgba(240,68,56,.26)' },
  paused: { color: '#8b97ab', bg: 'rgba(95,109,132,.12)', border: 'rgba(95,109,132,.3)' },
  retired: { color: '#5b667a', bg: 'rgba(95,109,132,.1)', border: 'rgba(95,109,132,.24)' },
};
const meta = computed(() => META[props.status] ?? META.offline);
</script>

<template>
  <span
    class="status-tag"
    :class="{ compact, retired: status === 'retired' }"
    :style="{ color: meta.color, background: meta.bg, borderColor: meta.border }"
  >
    <StatusDot :status="status" :size="6" />
    {{ PROCESS_STATUS_LABELS[status] || status }}
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
.retired {
  text-decoration: line-through;
}
</style>
