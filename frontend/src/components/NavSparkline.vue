// NavSparkline.vue — 账户权益迷你曲线：弹性宽度、固定高度，按容器拉伸不产生滚动。
<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{ values: number[]; width?: number; height?: number }>(), { width: 160, height: 38 });

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
  <svg
    v-if="path"
    class="spark"
    :viewBox="'0 0 ' + width + ' ' + height"
    preserveAspectRatio="none"
    :style="{ height: height + 'px' }"
    aria-hidden="true"
  >
    <path :d="path" fill="none" stroke="#7fa5ff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
  </svg>
  <span v-else class="spark-empty">—</span>
</template>

<style scoped>
.spark {
  display: block;
  width: 100%;
}
.spark-empty {
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>
