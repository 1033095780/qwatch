<script setup lang="ts">
// MarketTag.vue — 市场标签：A股 / 期货 / 港股 / 美股 / 加密。
import { computed } from 'vue';
import type { Market } from '@/api/types';

const props = defineProps<{ market: Market; venue?: string }>();
const LABELS: Record<Market, string> = {
  CN_A: 'A股', CN_FUT: '期货', HK: '港股', US: '美股', CRYPTO: '加密', FX: '外汇',
};
const label = computed(() => LABELS[props.market] ?? props.market);
</script>

<template>
  <span class="market-tag">
    {{ label }}<span v-if="venue" class="venue">· {{ venue }}</span>
  </span>
</template>

<style scoped>
.market-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 5px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.22);
  color: #7cc7ef;
  font-size: 10px;
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.venue {
  color: rgba(124, 199, 239, 0.65);
  margin-left: 2px;
}
</style>
