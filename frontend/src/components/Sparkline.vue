<script setup lang="ts">
// Sparkline.vue — 纯 SVG 迷你曲线（无 ECharts 开销），用于卡片/表格内趋势。
import { computed } from 'vue';

const props = withDefaults(defineProps<{
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  strokeWidth?: number;
  fill?: boolean;
}>(), {
  width: 96,
  height: 28,
  color: 'var(--primary)',
  strokeWidth: 1.4,
  fill: true,
});

const uid = 'spark-' + Math.random().toString(36).slice(2, 9);

const geometry = computed(() => {
  const values = props.values.filter((v) => Number.isFinite(v));
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = props.strokeWidth;
  const w = props.width;
  const h = props.height;
  const step = (w - pad * 2) / (values.length - 1);
  const points = values.map((v, i) => {
    const x = pad + i * step;
    const y = pad + (1 - (v - min) / span) * (h - pad * 2);
    return [x, y] as const;
  });
  const line = points.map(([x, y], i) => (i === 0 ? 'M' : 'L') + x.toFixed(2) + ',' + y.toFixed(2)).join(' ');
  const area = line + ' L' + (w - pad).toFixed(2) + ',' + h + ' L' + pad.toFixed(2) + ',' + h + ' Z';
  return { line, area };
});
</script>

<template>
  <svg
    v-if="geometry"
    class="sparkline"
    :width="width"
    :height="height"
    :viewBox="'0 0 ' + width + ' ' + height"
    role="img"
    aria-label="趋势迷你图"
  >
    <defs>
      <linearGradient :id="uid" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.22" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path v-if="fill" :d="geometry.area" :fill="'url(#' + uid + ')'" />
    <path :d="geometry.line" fill="none" :stroke="color" :stroke-width="strokeWidth" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
  <span v-else class="spark-empty" :style="{ width: width + 'px', height: height + 'px' }" />
</template>

<style scoped>
.sparkline {
  display: block;
  overflow: visible;
}
.spark-empty {
  display: block;
  background: linear-gradient(90deg, var(--surface-2), transparent);
  border-radius: 4px;
}
</style>
