<script setup lang="ts">
// ChartBox.vue — ECharts 轻封装：init/setOption/resize/dispose + 容器尺寸监听（不使用 vue-echarts）。
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';

const props = withDefaults(defineProps<{ option: EChartsOption; height?: number | string }>(), {
  height: 300,
});

const el = ref<HTMLDivElement | null>(null);
const chart = shallowRef<echarts.ECharts | null>(null);
let observer: ResizeObserver | null = null;

onMounted(() => {
  if (!el.value) return;
  chart.value = echarts.init(el.value, undefined, { renderer: 'canvas' });
  chart.value.setOption(props.option);
  observer = new ResizeObserver(() => chart.value?.resize());
  observer.observe(el.value);
});

watch(
  () => props.option,
  (option) => chart.value?.setOption(option, { notMerge: true }),
  { deep: true },
);

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
  chart.value?.dispose();
  chart.value = null;
});
</script>

<template>
  <div
    ref="el"
    class="chart-box"
    :style="{ height: typeof height === 'number' ? height + 'px' : height }"
  />
</template>

<style scoped>
.chart-box {
  width: 100%;
  min-width: 0;
}
</style>
