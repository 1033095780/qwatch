<script setup lang="ts">
// RunnerCard.vue — 策略卡片：名称/市场/简介、净值曲线、权益与盈亏、四项分析指标。
import { computed } from 'vue';
import type { Runner } from '@/api/types';
import { fmtPct } from '@/utils/format';
import MarketTag from './MarketTag.vue';
import PnlText from './PnlText.vue';
import Sparkline from './Sparkline.vue';
import StatusDot from './StatusDot.vue';

const props = defineProps<{ runner: Runner }>();

const accent = computed(() => {
  switch (props.runner.status) {
    case 'running': return '#2ecc8f';
    case 'degraded': return '#f5a524';
    case 'offline': return '#f04438';
    default: return '#2f3a4f';
  }
});

const ratio = (value: string): string => {
  const number = Number(value);
  return number > 0 ? number.toFixed(2) : '—';
};
const winRate = (value: string): string => {
  const number = Number(value);
  return number > 0 ? number.toFixed(1) + '%' : '—';
};
</script>

<template>
  <router-link :to="'/strategies/' + runner.id" class="runner-card card card-hover">
    <span class="accent" :style="{ background: accent }" />

    <div class="head">
      <div class="name-wrap">
        <StatusDot :status="runner.status" :size="7" :pulse="runner.status === 'running'" />
        <span class="name truncate" :title="runner.name">{{ runner.name }}</span>
      </div>
      <MarketTag :market="runner.market" />
    </div>

    <p class="desc" :title="runner.description || ''">{{ runner.description || '暂无简介' }}</p>

    <div class="curve">
      <Sparkline :values="runner.sparkline" :width="560" :height="88" :stroke-width="1.6" />
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
      <div class="metric"><span class="k">夏普</span><span class="v num">{{ ratio(runner.sharpe) }}</span></div>
      <div class="metric"><span class="k">最大回撤</span><span class="v num">{{ fmtPct(runner.max_drawdown_pct, 2, false) }}</span></div>
      <div class="metric"><span class="k">日胜率</span><span class="v num">{{ winRate(runner.win_rate_pct) }}</span></div>
      <div class="metric"><span class="k">盈亏比</span><span class="v num">{{ ratio(runner.profit_factor) }}</span></div>
    </div>
  </router-link>
</template>

<style scoped>
.runner-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  color: var(--text);
}
.desc {
  min-height: 16px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: -2px 0 0;
}
.curve {
  margin: 4px 0 2px;
  height: 88px;
}
.curve :deep(svg) {
  width: 100%;
  height: 88px;
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
  font-size: 23px;
  font-weight: 600;
  letter-spacing: -0.02em;
  white-space: nowrap;
  color: var(--text);
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  margin-top: 2px;
}
.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.k {
  font-size: 10px;
  color: var(--text-2);
}
.v {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
}
@media (max-width: 639px) {
  .equity {
    font-size: 20px;
  }
  .curve {
    height: 68px;
  }
  .curve :deep(svg) {
    height: 68px;
  }
  .foot {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
