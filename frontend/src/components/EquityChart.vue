<script setup lang="ts">
// EquityChart.vue — 净值面积图（主色渐变 + 可选基准虚线）；坐标轴弱化、tooltip 用上海时间。
import { computed } from 'vue';
import type { EChartsOption } from 'echarts';
import ChartBox from './ChartBox.vue';
import { axisTimeLabel, fmtDateTime, fmtMoney } from '@/utils/format';

interface CurvePoint {
  ts: string;
  value: string;
  nav?: number;
}

const props = withDefaults(defineProps<{
  data: CurvePoint[];
  benchmark?: CurvePoint[] | null;
  showBenchmark?: boolean;
  height?: number;
  valueLabel?: string;
  benchmarkLabel?: string;
  valueMode?: 'money' | 'nav';
}>(), {
  benchmark: null,
  showBenchmark: false,
  height: 300,
  valueLabel: '组合权益',
  benchmarkLabel: '沪深300（归一）',
  valueMode: 'money',
});

const spanDays = computed(() => {
  if (props.data.length < 2) return 0;
  return (Date.parse(props.data[props.data.length - 1].ts) - Date.parse(props.data[0].ts)) / 86400000;
});
const intraday = computed(() => spanDays.value < 3);

function fmtAxisValue(value: number): string {
  if (props.valueMode === 'nav') return value.toFixed(2);
  const abs = Math.abs(value);
  if (abs >= 1e8) return (value / 1e8).toFixed(2) + '亿';
  if (abs >= 1e4) return (value / 1e4).toFixed(0) + '万';
  return value.toFixed(0);
}

const option = computed<EChartsOption>(() => {
  const hasData = props.data.length > 1;
  const benchmarkSeries = props.showBenchmark && props.benchmark && props.benchmark.length > 1
    ? [{
        name: props.benchmarkLabel,
        type: 'line' as const,
        data: props.benchmark.map((p) => [Date.parse(p.ts), Number(p.value)]),
        symbol: 'none',
        lineStyle: { color: '#5f6d84', width: 1.2, type: 'dashed' as const },
        itemStyle: { color: '#5f6d84' },
        emphasis: { disabled: true },
        animationDuration: 400,
      }]
    : [];
  return {
    animationDuration: 320,
    animationEasing: 'cubicOut',
    grid: { left: 4, right: 10, top: 14, bottom: 2, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#151c2c',
      borderColor: '#2a3448',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: '#e9eef6', fontSize: 12, fontFamily: 'Inter, "PingFang SC", sans-serif' },
      axisPointer: { type: 'line', lineStyle: { color: '#2a3448', width: 1 } },
      formatter: (params: any) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return '';
        const ts = Number(list[0].axisValue);
        const lines = list.map((p: any) => {
          const v = Number(p.value[1]);
          return (
            '<div style="display:flex;justify-content:space-between;gap:18px;margin-top:4px">' +
            '<span style="color:#9aa7bc">' + p.marker + ' ' + p.seriesName + '</span>' +
            '<span style="font-family:\'JetBrains Mono\',Consolas,monospace">' +
            (props.valueMode === 'nav' ? v.toFixed(4) : '¥' + fmtMoney(v, 2)) + '</span></div>'
          );
        });
        return '<div style="font-size:11px;color:#9aa7bc">' + fmtDateTime(new Date(ts).toISOString()) + ' CST</div>' + lines.join('');
      },
    },
    xAxis: {
      type: 'time',
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#1e2637' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#5f6d84',
        fontSize: 11,
        fontFamily: '"JetBrains Mono", Consolas, monospace',
        hideOverlap: true,
        formatter: (value: number) => axisTimeLabel(value, intraday.value),
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitNumber: 4,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#5f6d84',
        fontSize: 11,
        fontFamily: '"JetBrains Mono", Consolas, monospace',
        formatter: (value: number) => fmtAxisValue(value),
      },
      splitLine: { lineStyle: { color: '#1a2230', type: 'dashed' } },
    },
    series: [
      ...(hasData
        ? [{
            name: props.valueLabel,
            type: 'line' as const,
            data: props.data.map((p) => [Date.parse(p.ts), Number(p.value)]),
            symbol: 'none',
            smooth: 0.18,
            lineStyle: { color: '#5b8cff', width: 1.7, shadowColor: 'rgba(91,140,255,.35)', shadowBlur: 10, shadowOffsetY: 4 },
            itemStyle: { color: '#5b8cff' },
            areaStyle: {
              color: {
                type: 'linear' as const,
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(91,140,255,.30)' },
                  { offset: 0.62, color: 'rgba(91,140,255,.08)' },
                  { offset: 1, color: 'rgba(91,140,255,0)' },
                ],
              },
            },
          }]
        : []),
      ...benchmarkSeries,
    ],
  };
});
</script>

<template>
  <ChartBox v-if="data.length > 1" :option="option" :height="height" />
  <div v-else class="chart-empty" :style="{ height: typeof height === 'number' ? height + 'px' : height }">
    暂无净值数据
  </div>
</template>

<style scoped>
.chart-empty {
  display: grid;
  place-items: center;
  color: var(--text-3);
  font-size: 12px;
  background: linear-gradient(180deg, rgba(21, 28, 44, 0.4), transparent);
  border-radius: 8px;
}
</style>
