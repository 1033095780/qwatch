<script setup lang="ts">
// MetricCard.vue — KPI 卡：标签 / 大数字 / 变化 / 图标。
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
</script>

<template>
  <div class="metric-card card">
    <div class="top">
      <span class="kpi-label">{{ label }}</span>
      <span v-if="icon" class="icon">
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
  min-height: 138px;
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
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: #a9c2ff;
  border: 1px solid rgba(91, 140, 255, 0.22);
  background: rgba(91, 140, 255, 0.1);
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
  color: var(--text-2);
}
</style>
