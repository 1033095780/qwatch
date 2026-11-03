<script setup lang="ts">
// RunnerCard.vue — 策略卡片：状态/平台/类型/标签、放大的净值曲线、权益与盈亏、关键指标。
import { computed } from 'vue';
import type { Runner } from '@/api/types';
import { fmtPct } from '@/utils/format';
import MarketTag from './MarketTag.vue';
import PnlText from './PnlText.vue';
import Sparkline from './Sparkline.vue';
import StatusDot from './StatusDot.vue';
import StatusTag from './StatusTag.vue';

const props = defineProps<{ runner: Runner }>();

const accent = computed(() => {
  switch (props.runner.status) {
    case 'running': return '#2ecc8f';
    case 'degraded': return '#f5a524';
    case 'offline': return '#f04438';
    default: return '#2f3a4f';
  }
});
</script>

<template>
  <router-link :to="'/strategies/' + runner.id" class="runner-card card card-hover">
    <span class="accent" :style="{ background: accent }" />

    <div class="head">
      <div class="name-wrap">
        <StatusDot :status="runner.status" :size="7" :pulse="runner.status === 'running'" />
        <span class="name truncate" :title="runner.name">{{ runner.name }}</span>
      </div>
      <div class="tags">
        <StatusTag :status="runner.status" compact />
        <MarketTag :market="runner.market" :venue="runner.venue" />
      </div>
    </div>
    <div class="id-row">
      <span class="mono strategy">{{ runner.strategy }}@{{ runner.version }}</span>
      <div class="meta-tags">
        <span v-if="runner.platform_label" class="mini-tag">{{ runner.platform_label }}</span>
        <span v-if="runner.strategy_type_label" class="mini-tag">{{ runner.strategy_type_label }}</span>
      </div>
    </div>
    <div v-if="runner.tags.length" class="tag-row">
      <span v-for="tag in runner.tags.slice(0, 3)" :key="tag" class="tag">#{{ tag }}</span>
      <span v-if="runner.tags.length > 3" class="tag">+{{ runner.tags.length - 3 }}</span>
    </div>

    <div class="curve">
      <Sparkline :values="runner.sparkline" :width="560" :height="84" :stroke-width="1.6" />
    </div>

    <div class="info">
      <div class="equity-wrap">
        <span class="eyebrow">权益</span>
        <span class="equity num">¥{{ Number(runner.equity).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
      </div>
      <div class="pnl-wrap">
        <PnlText :value="runner.today_pnl" :pct="runner.today_pnl_pct" show-pct size="sm" bold />
        <span class="muted sep">·</span>
        <span class="muted">总收益</span>
        <span class="mono" :class="Number(runner.total_return_pct) >= 0 ? 'pos' : 'neg'">{{ fmtPct(runner.total_return_pct) }}</span>
      </div>
    </div>

    <div class="foot">
      <div class="metric"><span class="k">最大回撤</span><span class="v mono">{{ fmtPct(runner.max_drawdown_pct, 2, false) }}</span></div>
      <div class="metric"><span class="k">24h 可用</span><span class="v mono">{{ runner.uptime_24h }}%</span></div>
      <div class="metric"><span class="k">持仓</span><span class="v mono">{{ runner.position_count }}</span></div>
    </div>
  </router-link>
</template>

<style scoped>
.runner-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  color: inherit;
}
.runner-card:hover {
  color: inherit;
}
.accent {
  position: absolute;
  left: 0;
  top: 16px;
  bottom: 16px;
  width: 2px;
  border-radius: 0 2px 2px 0;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.name-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}
.id-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: -6px;
}
.strategy {
  font-size: 11px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: none;
}
.mini-tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: rgba(91, 140, 255, 0.07);
  color: var(--text-2);
  font-size: 10px;
  font-family: var(--font-mono);
  white-space: nowrap;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: -4px;
}
.tag {
  font-size: 10px;
  color: var(--text-3);
}
.curve {
  margin: 4px 0 2px;
  height: 84px;
}
.curve :deep(svg) {
  width: 100%;
  height: 84px;
}
.info {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.equity-wrap {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.equity {
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.02em;
  white-space: nowrap;
}
.pnl-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  flex-wrap: wrap;
  padding-bottom: 2px;
}
.sep {
  opacity: 0.5;
}
.pos {
  color: var(--up);
}
.neg {
  color: var(--down);
}
.foot {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  margin-top: 2px;
}
.metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.k {
  font-size: 10px;
  color: var(--text-3);
}
.v {
  font-size: 12px;
  color: var(--text-2);
}
@media (max-width: 639px) {
  .equity {
    font-size: 18px;
  }
  .curve {
    height: 64px;
  }
  .curve :deep(svg) {
    height: 64px;
  }
}
</style>
