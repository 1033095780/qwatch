<script setup lang="ts">
import { computed } from 'vue';
const props = withDefaults(defineProps<{ values: number[]; width?: number; height?: number }>(), { width: 110, height: 30 });
const path = computed(() => {
  const vals = props.values.filter((v) => Number.isFinite(v));
  if (vals.length < 2) return '';
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = (props.width - 4) / (vals.length - 1);
  return vals.map((v, i) => (i ? 'L' : 'M') + (2 + i * step).toFixed(1) + ' ' + (2 + (1 - (v - min) / span) * (props.height - 4)).toFixed(1)).join(' ');
});
</script>
<template>
  <svg v-if="path" :width="width" :height="height" :viewBox="'0 0 ' + width + ' ' + height" class="spark" aria-hidden="true">
    <path :d="path" fill="none" stroke="#7fa5ff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
  <span v-else class="spark-empty">—</span>
</template>
<style scoped>
.spark { display: block; }
.spark-empty { color: var(--text-3); font-family: var(--font-mono); }
</style>
