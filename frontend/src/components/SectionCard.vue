<script setup lang="ts">
// SectionCard.vue — 通用面板：标题/副标题/右侧 extra + 内容插槽。
withDefaults(defineProps<{ title?: string; subtitle?: string; flush?: boolean; compact?: boolean }>(), {
  flush: false,
  compact: false,
});
</script>

<template>
  <section class="section-card card" :class="{ 'card--flush': flush, 'card--tight': compact }">
    <div v-if="title || subtitle || $slots.extra" class="panel-head">
      <div>
        <h2 v-if="title" class="panel-title">{{ title }}</h2>
        <p v-if="subtitle" class="panel-sub">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.extra" class="head-extra"><slot name="extra" /></div>
    </div>
    <slot />
  </section>
</template>

<style scoped>
.section-card {
  display: flex;
  flex-direction: column;
}
.head-extra {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
