<script setup lang="ts">
// MetricCard.vue — KPI 卡：标签 / 大数字 / 变化 / 图标，可选底部插槽（sparkline 等）。
import type { Component } from 'vue';
import PnlText from './PnlText.vue';

withDefaults(defineProps<{
  label: string;
  value: string;
  sub?: string;
  change?: string | number | null;
  changePct?: string | number | null;
  icon?: Component;
  loading?: boolean;
  accent?: 'primary' | 'up' | 'down' | 'warning' | 'danger';
}>(), {
  sub: '',
  change: null,
  changePct: null,
  loading: false,
  accent: 'primary',
});

const ACCENT: Record<string, string> = {
  primary: 'rgba(91,140,255,.1)',
  up: 'rgba(240,68,56,.1)',
  down: 'rgba(46,204,143,.1)',
  warning: 'rgba(245,165,36,.1)',
  danger: 'rgba(240,68,56,.1)',
};
</script>

<template>
  <div class="metric-card card">
    <div class="top">
      <span class="kpi-label">{{ label }}</span>
      <span v-if="icon" class="icon" :style="{ background: ACCENT[accent] || ACCENT.primary }">
        <component :is="icon" :size="15" :stroke-width="1.8" />
      </span>
    </div>
    <template v-if="loading">
      <div class="skel skel-line" style="width: 62%; height: 24px; margin: 10px 0 8px" />
      <div class="skel skel-line" style="width: 38%" />
    </template>
    <template v-else>
      <div class="kpi-value">{{ value }}</div>
      <div class="foot">
        <PnlText v-if="change !== null && change !== undefined" :value="change" :pct="changePct" show-pct size="sm" />
        <span v-if="sub" class="sub">{{ sub }}</span>
      </div>
      <slot />
    </template>
  </div>
</template>

<style scoped>
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 128px;
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: var(--text-2);
  border: 1px solid var(--border);
}
.kpi-value {
  margin-top: 4px;
}
.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 18px;
  flex-wrap: wrap;
}
.sub {
  font-size: 12px;
  color: var(--text-3);
}
</style>
