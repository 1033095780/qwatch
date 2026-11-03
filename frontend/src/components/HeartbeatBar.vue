<script setup lang="ts">
// HeartbeatBar.vue — 24h 心跳分段条（30min/段），ok 绿 / miss 黄 / off 灰。
import type { HeartbeatSegment } from '@/api/types';
import { fmtDateTime } from '@/utils/format';

withDefaults(defineProps<{ segments: HeartbeatSegment[]; showLegend?: boolean; height?: number }>(), {
  showLegend: true,
  height: 26,
});

const LABEL: Record<HeartbeatSegment['status'], string> = { ok: '心跳正常', miss: '心跳缺失', off: '非交易时段' };
const COLOR: Record<HeartbeatSegment['status'], string> = { ok: '#2ecc8f', miss: '#f5a524', off: '#2f3a4f' };
</script>

<template>
  <div class="hb-wrap">
    <div class="hb" :style="{ height: height + 'px' }">
      <span
        v-for="(seg, i) in segments"
        :key="seg.ts + i"
        class="seg-bar"
        :style="{ background: COLOR[seg.status] }"
        :title="fmtDateTime(seg.ts) + ' · ' + LABEL[seg.status]"
      />
    </div>
    <div v-if="showLegend" class="legend">
      <span class="item"><i style="background: #2ecc8f" />正常</span>
      <span class="item"><i style="background: #f5a524" />缺失</span>
      <span class="item"><i style="background: #2f3a4f" />非交易</span>
      <span class="range">近 24 小时 · 每段 30 分钟</span>
    </div>
  </div>
</template>

<style scoped>
.hb-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hb {
  display: flex;
  gap: 2px;
  align-items: stretch;
  width: 100%;
}
.seg-bar {
  flex: 1 1 0;
  min-width: 2px;
  border-radius: 2px;
  opacity: 0.9;
  transition: opacity 120ms ease, transform 120ms ease;
}
.seg-bar:hover {
  opacity: 1;
  transform: scaleY(1.15);
}
.legend {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 11px;
  color: var(--text-3);
  flex-wrap: wrap;
}
.item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.item i {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}
.range {
  margin-left: auto;
  font-family: var(--font-mono);
}
</style>
