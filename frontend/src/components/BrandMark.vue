<script setup lang="ts">
// BrandMark.vue — qwatch 品牌标：心跳折线 + 文字副标题。
withDefaults(defineProps<{ collapsed?: boolean; size?: 'sm' | 'md' | 'lg' }>(), {
  collapsed: false,
  size: 'md',
});
</script>

<template>
  <div class="brand" :class="[size, { collapsed }]">
    <span class="mark">
      <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path d="M3 17h5.2l3.1-8.4 4.1 15 3.2-9.2 1.8 2.6H29" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </span>
    <span v-if="!collapsed" class="text">
      <span class="name">qwatch</span>
      <span class="sub">监控工作台</span>
    </span>
  </div>
</template>

<style scoped>
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.mark {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: 9px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(91, 140, 255, 0.28);
}
.mark svg {
  width: 20px;
  height: 20px;
}
.name {
  display: block;
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  line-height: 1.1;
}
.sub {
  display: block;
  font-size: 10px;
  letter-spacing: 0.22em;
  color: var(--text-3);
  margin-top: 1px;
}
.lg .mark {
  width: 38px;
  height: 38px;
  border-radius: 11px;
}
.lg .mark svg {
  width: 26px;
  height: 26px;
}
.lg .name {
  font-size: 20px;
}
.lg .sub {
  font-size: 11px;
}
.sm .mark {
  width: 26px;
  height: 26px;
  border-radius: 8px;
}
.sm .name {
  font-size: 13px;
}
.collapsed {
  justify-content: center;
}
</style>
