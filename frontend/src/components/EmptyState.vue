<script setup lang="ts">
// EmptyState.vue — 空状态：图标 + 标题 + 描述 + 可选操作。
import { Inbox } from 'lucide-vue-next';

withDefaults(defineProps<{ title?: string; description?: string; compact?: boolean }>(), {
  title: '暂无数据',
  description: '',
  compact: false,
});
</script>

<template>
  <div class="empty" :class="{ compact }">
    <div class="icon"><slot name="icon"><Inbox :size="22" :stroke-width="1.5" /></slot></div>
    <p class="title">{{ title }}</p>
    <p v-if="description" class="desc">{{ description }}</p>
    <div v-if="$slots.action" class="action"><slot name="action" /></div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  text-align: center;
}
.compact {
  padding: 24px 12px;
}
.icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-3);
  margin-bottom: 12px;
}
.title {
  font-size: 13px;
  color: var(--text-2);
  font-weight: 500;
}
.desc {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 4px;
  max-width: 320px;
}
.action {
  margin-top: 14px;
}
</style>
