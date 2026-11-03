<script setup lang="ts">
// PnlText.vue — 盈亏数字：红涨绿跌（可配）、千分位、等宽、正数带 +。
import { computed } from 'vue';
import { fmtNumber, fmtPct, fmtSignedMoney, pnlClass } from '@/utils/format';

const props = withDefaults(defineProps<{
  value: string | number | null | undefined;
  pct?: string | number | null;
  money?: boolean;
  digits?: number;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  bold?: boolean;
  showPct?: boolean;
}>(), {
  money: true,
  digits: 2,
  size: 'md',
  bold: false,
  showPct: false,
});

const text = computed(() => {
  const n = Number(props.value);
  if (!Number.isFinite(n)) return '—';
  return props.money
    ? fmtSignedMoney(n, props.digits)
    : (n > 0 ? '+' : '') + fmtNumber(n, props.digits);
});
const pctText = computed(() => {
  if (!props.showPct || props.pct === null || props.pct === undefined) return '';
  return '(' + fmtPct(props.pct) + ')';
});
</script>

<template>
  <span class="pnl-text" :class="[pnlClass(value), size, { bold }]">
    {{ text }}<span v-if="pctText" class="pct">{{ pctText }}</span>
  </span>
</template>

<style scoped>
.pnl-text {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.pnl-text.is-up { color: var(--up); }
.pnl-text.is-down { color: var(--down); }
.pnl-text.is-flat { color: var(--text-2); }
.xs { font-size: 11px; }
.sm { font-size: 12px; }
.md { font-size: 13px; }
.lg { font-size: 16px; }
.bold { font-weight: 600; }
.pct {
  opacity: 0.72;
  margin-left: 4px;
  font-size: 0.92em;
}
</style>
