<script setup lang="ts">
// SignalStatusTag.vue — 信号执行状态标签：已执行 / 待执行 / 已忽略。
import { computed } from 'vue';
import type { SignalStatus } from '@/api/types';

const props = defineProps<{ status: SignalStatus }>();

const META: Record<SignalStatus, { label: string; color: string; bg: string; border: string }> = {
  filled: { label: '已执行', color: '#2ecc8f', bg: 'rgba(46,204,143,.1)', border: 'rgba(46,204,143,.26)' },
  pending: { label: '待执行', color: '#f5a524', bg: 'rgba(245,165,36,.1)', border: 'rgba(245,165,36,.26)' },
  ignored: { label: '已忽略', color: '#8b97ab', bg: 'rgba(95,109,132,.12)', border: 'rgba(95,109,132,.3)' },
};
const meta = computed(() => META[props.status]);
</script>

<template>
  <span class="signal-status" :style="{ color: meta.color, background: meta.bg, borderColor: meta.border }">
    {{ meta.label }}
  </span>
</template>

<style scoped>
.signal-status {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: 5px;
  border: 1px solid transparent;
  font-size: 11px;
  white-space: nowrap;
}
</style>
