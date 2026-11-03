<script setup lang="ts">
// SeverityTag.vue — 告警级别标签：P0 红 / P1 黄 / P2 蓝。
import { computed } from 'vue';
import type { Severity } from '@/api/types';

const props = defineProps<{ severity: Severity; size?: 'sm' | 'md' }>();
const META: Record<Severity, { color: string; bg: string; border: string }> = {
  P0: { color: '#ff7b72', bg: 'rgba(240,68,56,.12)', border: 'rgba(240,68,56,.32)' },
  P1: { color: '#f5b64b', bg: 'rgba(245,165,36,.1)', border: 'rgba(245,165,36,.3)' },
  P2: { color: '#7cc7ef', bg: 'rgba(56,189,248,.1)', border: 'rgba(56,189,248,.28)' },
};
const meta = computed(() => META[props.severity]);
</script>

<template>
  <span class="sev" :class="size || 'md'" :style="{ color: meta.color, background: meta.bg, borderColor: meta.border }">
    {{ severity }}
  </span>
</template>

<style scoped>
.sev {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 20px;
  padding: 0 6px;
  border-radius: 5px;
  border: 1px solid transparent;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.sm {
  height: 18px;
  min-width: 26px;
  font-size: 10px;
}
</style>
