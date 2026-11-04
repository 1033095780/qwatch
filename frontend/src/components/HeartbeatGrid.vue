<script setup lang="ts">
// HeartbeatGrid.vue — 24 格心跳/状态格，保持 v0.1 的彩色块视觉。
import { computed } from 'vue';
import type { ProcessStatus, RunnerStatus } from '@/api/types';

const props = withDefaults(defineProps<{ status: RunnerStatus | ProcessStatus; retired?: boolean; lastSeen?: string | null }>(), {
  retired: false,
  lastSeen: null,
});

const bars = computed(() => {
  const status = props.retired ? 'retired' : props.status;
  if (status === 'running') return Array.from({ length: 24 }, () => 'ok');
  if (status === 'degraded') return [...Array(16).fill('ok'), ...Array(8).fill('warn')];
  if (status === 'offline') return [...Array(8).fill('off'), ...Array(16).fill('bad')];
  if (status === 'paused') return Array(24).fill('off');
  return Array(24).fill('off');
});
</script>

<template>
  <div class="hb-grid" :title="lastSeen ? '最后心跳 ' + lastSeen : '暂无心跳'" role="img" aria-label="心跳状态">
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
.hb-cell.ok { background: #2ecc8f; }
.hb-cell.warn { background: #f5a524; }
.hb-cell.bad { background: #f04438; }
.hb-cell.off { background: #3a465c; }
</style>
