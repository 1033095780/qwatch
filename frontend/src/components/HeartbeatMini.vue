<script setup lang="ts">
// HeartbeatMini.vue — 策略状态行下方的迷你心跳条，配色与详情页 HeartbeatBar 一致。
withDefaults(defineProps<{ bars?: ('ok' | 'miss' | 'off')[]; height?: number }>(), {
  bars: () => [],
  height: 8,
});

const COLOR: Record<string, string> = { ok: '#2ecc8f', miss: '#f5a524', off: '#2f3a4f' };
</script>

<template>
  <div v-if="bars.length" class="mini-hb" :style="{ height: height + 'px' }" title="近 12 小时心跳">
    <span
      v-for="(bar, index) in bars"
      :key="index"
      class="bar"
      :style="{ background: COLOR[bar] || COLOR.off }"
    />
  </div>
</template>

<style scoped>
.mini-hb {
  display: flex;
  align-items: stretch;
  gap: 2px;
  width: 100%;
  max-width: 148px;
  margin-top: 5px;
}
.bar {
  flex: 1 1 0;
  min-width: 2px;
  border-radius: 1px;
  opacity: 0.9;
}
</style>
