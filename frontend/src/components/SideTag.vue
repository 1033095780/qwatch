<script setup lang="ts">
// SideTag.vue — 信号方向标签：买红 / 卖绿（跟随全站涨跌配色变量）。
import type { SignalSide } from '@/api/types';

defineProps<{ side: SignalSide }>();
</script>

<template>
  <span class="side-tag" :class="side">{{ side === 'buy' ? '买入' : '卖出' }}</span>
</template>

<style scoped>
.side-tag {
  display: inline-flex;
  height: 19px;
  align-items: center;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
  white-space: nowrap;
}
.side-tag.buy {
  color: var(--up);
  background: color-mix(in srgb, var(--up) 12%, transparent);
}
.side-tag.sell {
  color: var(--down);
  background: color-mix(in srgb, var(--down) 12%, transparent);
}
</style>
