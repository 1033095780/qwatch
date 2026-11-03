<script setup lang="ts">
// RangeTabs.vue — 净值区间切换（1D/1W/1M/3M/1Y/ALL）。
import type { RangeKey } from '@/api/types';

withDefaults(defineProps<{ modelValue: RangeKey; options?: { key: RangeKey; label: string }[] }>(), {
  options: () => [
    { key: '1d', label: '1D' },
    { key: '1w', label: '1W' },
    { key: '1m', label: '1M' },
    { key: '3m', label: '3M' },
    { key: '1y', label: '1Y' },
    { key: 'all', label: 'ALL' },
  ],
});
const emit = defineEmits<{ 'update:modelValue': [value: RangeKey] }>();
</script>

<template>
  <div class="seg" role="tablist" aria-label="净值区间">
    <button
      v-for="opt in options"
      :key="opt.key"
      type="button"
      :class="{ active: opt.key === modelValue }"
      role="tab"
      :aria-selected="opt.key === modelValue"
      @click="emit('update:modelValue', opt.key)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>
