<script setup lang="ts">
// NavChart.vue — 权益曲线：面积渐变 + 悬停十字线/提示，支持周期筛选后的数据。
import { computed, ref } from 'vue';
import { fmtDateTime, fmtNumber } from '@/utils/format';

const props = withDefaults(defineProps<{
  data: { ts: string; value: string }[];
  height?: number;
  currency?: boolean;
}>(), { height: 200, currency: true });

const wrap = ref<HTMLElement | null>(null);
const hoverIndex = ref<number | null>(null);
const hoverLeft = ref(0);
const hoverTop = ref(0);
const W = 600;
const PAD_X = 10;
const PAD_Y = 12;

const values = computed(() => props.data.map((p) => Number(p.value)).filter((v) => Number.isFinite(v)));
const rawMin = computed(() => (values.value.length ? Math.min(...values.value) : 0));
const rawMax = computed(() => (values.value.length ? Math.max(...values.value) : 1));
const pad = computed(() => Math.max((rawMax.value - rawMin.value) * 0.08, Math.abs(rawMax.value) * 0.005, 1));
const min = computed(() => rawMin.value - pad.value);
const max = computed(() => rawMax.value + pad.value);
const span = computed(() => max.value - min.value || 1);
const coords = computed(() => {
  const n = values.value.length;
  if (!n) return [] as { x: number; y: number; value: number; ts: string }[];
  const plotW = W - PAD_X * 2;
  const plotH = props.height - PAD_Y * 2;
  return values.value.map((value, index) => {
    const x = n === 1 ? W / 2 : PAD_X + (index / (n - 1)) * plotW;
    const y = PAD_Y + (1 - (value - min.value) / span.value) * plotH;
    return { x, y, value, ts: props.data[index]?.ts || '' };
  });
});
const line = computed(() => coords.value.map((p, i) => (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' '));
const area = computed(() => {
  if (!coords.value.length) return '';
  const last = coords.value[coords.value.length - 1];
  return line.value + ' L' + last.x.toFixed(1) + ' ' + (props.height - PAD_Y) + ' L' + coords.value[0].x.toFixed(1) + ' ' + (props.height - PAD_Y) + ' Z';
});
const hover = computed(() => (hoverIndex.value === null ? null : coords.value[hoverIndex.value] || null));
const startLabel = computed(() => props.data.length ? fmtDateTime(props.data[0].ts) : '');
const endLabel = computed(() => props.data.length ? fmtDateTime(props.data[props.data.length - 1].ts) : '');
const fmtValue = (value: number): string => (props.currency ? '¥' + fmtNumber(value, 0) : fmtNumber(value, 4));

function onMove(event: MouseEvent): void {
  const svg = (event.currentTarget as SVGElement).getBoundingClientRect();
  if (!svg.width || !coords.value.length) return;
  const ratio = Math.min(1, Math.max(0, (event.clientX - svg.left) / svg.width));
  const index = Math.round(ratio * (coords.value.length - 1));
  hoverIndex.value = index;
  hoverLeft.value = ratio * 100;
  hoverTop.value = (coords.value[index].y / props.height) * 100;
}
function onLeave(): void { hoverIndex.value = null; }
</script>

<template>
  <div ref="wrap" class="nav-chart" :style="{ height: height + 'px' }">
    <svg v-if="coords.length" :viewBox="'0 0 ' + W + ' ' + height" preserveAspectRatio="none" role="img" aria-label="权益曲线" @mousemove="onMove" @mouseleave="onLeave">
      <defs>
        <linearGradient id="navArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#6f9bff" stop-opacity="0.24" />
          <stop offset="100%" stop-color="#6f9bff" stop-opacity="0" />
        </linearGradient>
      </defs>
      <line v-for="i in 4" :key="i" :x1="PAD_X" :x2="W - PAD_X" :y1="PAD_Y + (i - 1) * (height - PAD_Y * 2) / 3" :y2="PAD_Y + (i - 1) * (height - PAD_Y * 2) / 3" class="grid" />
      <path :d="area" fill="url(#navArea)" />
      <path :d="line" class="curve" />
      <line v-if="hover" :x1="hover.x" :x2="hover.x" :y1="PAD_Y" :y2="height - PAD_Y" class="crosshair" />
      <circle v-if="hover" :cx="hover.x" :cy="hover.y" r="3.5" class="hover-dot" />
      <circle v-else-if="coords.length" :cx="coords[coords.length - 1].x" :cy="coords[coords.length - 1].y" r="2.5" class="last-dot" />
    </svg>
    <div v-else class="empty-chart">暂无权益数据</div>
    <div class="x-labels"><span>{{ startLabel }}</span><span>{{ endLabel }}</span></div>
    <div v-if="hover" class="chart-tip" :style="{ left: hoverLeft + '%', top: hoverTop + '%' }">
      <span class="tip-time">{{ fmtDateTime(hover.ts) }}</span>
      <strong class="tip-value">{{ fmtValue(hover.value) }}</strong>
    </div>
  </div>
</template>

<style scoped>
.nav-chart {
  position: relative;
  width: 100%;
  min-height: 80px;
}
.nav-chart svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}
.grid {
  stroke: rgba(255, 255, 255, 0.045);
  stroke-width: 1;
}
.curve {
  fill: none;
  stroke: #7fa5ff;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}
.crosshair {
  stroke: rgba(180, 200, 255, 0.35);
  stroke-width: 1;
  stroke-dasharray: 3 3;
  vector-effect: non-scaling-stroke;
}
.hover-dot,
.last-dot {
  fill: #b8ccff;
  stroke: #5b8cff;
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
}
.last-dot { fill: #7fa5ff; stroke: none; }
.empty-chart {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--text-3);
  font-size: 12px;
}
.x-labels {
  position: absolute;
  left: 4px;
  right: 4px;
  bottom: -2px;
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: var(--text-3);
  pointer-events: none;
}
.chart-tip {
  position: absolute;
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 9px;
  border: 1px solid rgba(120, 150, 220, 0.28);
  border-radius: 7px;
  background: rgba(12, 17, 28, 0.94);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  pointer-events: none;
  transform: translate(-50%, calc(-100% - 10px));
  white-space: nowrap;
}
.tip-time {
  font-size: 9px;
  color: var(--text-3);
}
.tip-value {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text);
}
</style>