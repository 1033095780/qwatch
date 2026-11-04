// StrategyGrid.vue — 策略卡片统一网格（总览与策略页完全一致）：3/2/1 列，弹性，无横向溢出。
<template>
  <div class="strategy-grid">
    <slot />
  </div>
</template>

<style scoped>
.strategy-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--gap);
}
@media (max-width: 1100px) {
  .strategy-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .strategy-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
