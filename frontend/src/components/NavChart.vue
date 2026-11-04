<script setup lang="ts">
// NavChart.vue — 策略组净值曲线（策略进程上报，最后一次为准）。
import { computed } from 'vue';

const props = withDefaults(defineProps<{ data: { ts: string; value: string }[]; height?: number }>(), { height: 140 });

const W = 600;
const PAD = 8;
const points = computed(() => {
  const values = props.data.map((p) => Number(p.value)).filter((v) => Number.isFinite(v));
  if (values.length < 2) return { line: '', area: '', min: 0, max: 0, last: values[0] ?? null };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = (W - PAD * 2) / (values.length - 1);
  const coords = values.map((v, i) => {
    const x = PAD + i * step;
    const y = PAD + (1 - (v - min) / span) * (props.height - PAD * 2);
    return [x, y] as const;
  });
  const line = coords.map(([x, y], i) => (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1)).join(' ');
  const area = line + ' L' + (PAD + (values.length - 1) * step).toFixed(1) + ' ' + (props.height - PAD) + ' L' + PAD + ' ' + (props.height - PAD) + ' Z';
  return { line, area, min, max, last: values[values.length - 1] };
});

const lastPoint = computed(() => {
  if (!props.data.length) return null;
  const v = Number(props.data[props.data.length - 1].value);
  return Number.isFinite(v) ? v : null;
});
</script>

<template>
  <div class="nav-chart">
    <svg v-if="points.line" :viewBox="'0 0 ' + W + ' ' + height" :style="{ height: height + 'px' }" preserveAspectRatio="none" role="img" aria-label="策略净值曲线">
      <defs>
        <linearGradient id="navArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#5b8cff" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#5b8cff" stop-opacity="0" />
        </linearGradient>
      </defs>
      <path :d="points.area" fill="url(#navArea)" />
      <path :d="points.line" fill="none" stroke="#7fa5ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
    </svg>
    <div v-else class="nav-empty">暂无净值上报</div>
  </div>
</template>

<style scoped>
.nav-chart {
  width: 100%;
  min-height: 80px;
}
.nav-chart svg {
  width: 100%;
  display: block;
}
.nav-empty {
  display: grid;
  place-items: center;
  height: 100px;
  color: var(--text-3);
  font-size: 12px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}
</style>
