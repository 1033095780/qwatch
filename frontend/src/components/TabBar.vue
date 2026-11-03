<script setup lang="ts">
// TabBar.vue — 页内 Tab（下划线态，可横向滚动），用于策略详情/告警/设置。
export interface TabItem {
  key: string;
  label: string;
  count?: number | string;
}
withDefaults(defineProps<{ modelValue: string; tabs: TabItem[] }>(), {});
const emit = defineEmits<{ 'update:modelValue': [value: string] }>();
</script>

<template>
  <div class="tabbar" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      :class="{ active: tab.key === modelValue }"
      role="tab"
      :aria-selected="tab.key === modelValue"
      @click="emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
      <span v-if="tab.count !== undefined" class="tab-count">{{ tab.count }}</span>
    </button>
  </div>
</template>
