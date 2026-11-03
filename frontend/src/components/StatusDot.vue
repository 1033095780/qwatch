<script setup lang="ts">
// StatusDot.vue — 状态点：running 绿 / degraded 黄 / offline 红 / off_hours 灰，带同色光晕。
import { computed } from 'vue';
import type { RunnerStatus } from '@/api/types';

const props = withDefaults(defineProps<{ status: RunnerStatus | 'ok' | 'warn' | 'error'; pulse?: boolean; size?: number }>(), {
  pulse: false,
  size: 8,
});
const color = computed(() => {
  switch (props.status) {
    case 'running': return '#2ecc8f';
    case 'degraded': return '#f5a524';
    case 'offline': return '#f04438';
    case 'off_hours': return '#5f6d84';
    case 'ok': return '#2ecc8f';
    case 'warn': return '#f5a524';
    default: return '#f04438';
  }
});
</script>

<template>
  <span
    class="status-dot"
    :class="{ pulse }"
    :style="{ width: size + 'px', height: size + 'px', background: color, boxShadow: '0 0 0 3px ' + color + '22' }"
    aria-hidden="true"
  />
</template>

<style scoped>
.status-dot {
  display: inline-block;
  flex: none;
  border-radius: 50%;
}
.pulse {
  animation: dot-pulse 2.4s ease-out infinite;
}
@keyframes dot-pulse {
  0% { box-shadow: 0 0 0 3px rgba(46, 204, 143, 0.13); }
  50% { box-shadow: 0 0 0 6px rgba(46, 204, 143, 0.05); }
  100% { box-shadow: 0 0 0 3px rgba(46, 204, 143, 0.13); }
}
</style>
