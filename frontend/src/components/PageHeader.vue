<script setup lang="ts">
// PageHeader.vue — 页面标题：可选返回链接 + 标题/副标题 + 右侧操作插槽。
import { ChevronLeft } from 'lucide-vue-next';

defineProps<{ title: string; subtitle?: string; backTo?: string; backLabel?: string }>();
</script>

<template>
  <header class="page-header">
    <div class="left">
      <router-link v-if="backTo" :to="backTo" class="back">
        <ChevronLeft :size="14" />
        <span>{{ backLabel || '返回' }}</span>
      </router-link>
      <h1 class="title">{{ title }}</h1>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.extra" class="extra">
      <slot name="extra" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 2px 0 0;
}
.left {
  min-width: 0;
}
.back {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 4px;
}
.back:hover {
  color: var(--text-2);
}
.title {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.25;
}
.subtitle {
  font-size: 12px;
  color: var(--text-2);
  margin-top: 3px;
}
.extra {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 639px) {
  .title {
    font-size: 20px;
  }
}
</style>
