<script setup lang="ts">
// DrawdownChart.vue — 回撤图（0 轴在上，向下为回撤）；与净值图共用区间数据。
import { computed } from 'vue';
import type { EChartsOption } from 'echarts';
import ChartBox from './ChartBox.vue';
import { axisTimeLabel, fmtDateTime, fmtPct } from '@/utils/format';

const props = withDefaults(defineProps<{ data: { ts: string; value: number }[]; height?: number }>(), {
  height: 132,
});

const intraday = computed(() => {
  if (props.data.length < 2) return false;
  return (Date.parse(props.data[props.data.length - 1].ts) - Date.parse(props.data[0].ts)) / 86400000 < 3;
});

const option = computed<EChartsOption>(() => ({
  animationDuration: 320,
  grid: { left: 4, right: 10, top: 8, bottom: 2, containLabel: true },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#151c2c',
    borderColor: '#2a3448',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: '#e9eef6', fontSize: 12 },
    axisPointer: { type: 'line', lineStyle: { color: '#2a3448' } },
    formatter: (params: any) => {
      const list = Array.isArray(params) ? params : [params];
      if (!list.length) return '';
      const ts = Number(list[0].axisValue);
      const v = Number(list[0].value[1]);
      return (
        '<div style="font-size:11px;color:#9aa7bc">' + fmtDateTime(new Date(ts).toISOString()) + ' CST</div>' +
        '<div style="margin-top:4px;font-family:\'JetBrains Mono\',Consolas,monospace;color:#f0786f">回撤 ' + fmtPct(v, 2, false) + '</div>'
      );
    },
  },
  xAxis: {
    type: 'time',
    boundaryGap: false,
    axisLine: { lineStyle: { color: '#1e2637' } },
    axisTick: { show: false },
    axisLabel: {
      color: '#5f6d84',
      fontSize: 10,
      fontFamily: '"JetBrains Mono", Consolas, monospace',
      hideOverlap: true,
      formatter: (value: number) => axisTimeLabel(value, intraday.value),
    },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'value',
    max: 0,
    splitNumber: 2,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#5f6d84',
      fontSize: 10,
      fontFamily: '"JetBrains Mono", Consolas, monospace',
      formatter: (value: number) => value.toFixed(0) + '%',
    },
    splitLine: { lineStyle: { color: '#1a2230', type: 'dashed' } },
  },
  series: [
    {
      name: '回撤',
      type: 'line',
      data: props.data.map((p) => [Date.parse(p.ts), p.value]),
      symbol: 'none',
      smooth: 0.15,
      lineStyle: { color: '#f25c5c', width: 1.2 },
      itemStyle: { color: '#f25c5c' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(242,92,92,.02)' },
            { offset: 1, color: 'rgba(242,92,92,.26)' },
          ],
        },
      },
    },
  ],
}));
</script>

<template>
  <ChartBox v-if="data.length > 1" :option="option" :height="height" />
  <div v-else class="chart-empty" :style="{ height: typeof height === 'number' ? height + 'px' : height }">暂无回撤数据</div>
</template>

<style scoped>
.chart-empty {
  display: grid;
  place-items: center;
  color: var(--text-3);
  font-size: 12px;
}
</style>
