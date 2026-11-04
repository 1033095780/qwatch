// EventTimeline.vue — 动态时间线：message + signal 合并展示（v0.2）。
<script setup lang="ts">
import type { RunnerEvent } from '@/api/types';
import { ACTION_LABELS, DIRECTION_LABELS, EVENT_TYPE_LABELS } from '@/utils/catalog';
import { fmtDateTime, fmtNumber } from '@/utils/format';
import EmptyState from './EmptyState.vue';

const props = withDefaults(defineProps<{ events: RunnerEvent[]; showRunner?: boolean; clickable?: boolean; emptyTitle?: string; emptyDesc?: string }>(), {
  showRunner: false,
  clickable: false,
  emptyTitle: '暂无动态',
  emptyDesc: '策略上报消息或交易信号后会实时出现在这里。',
});
const emit = defineEmits<{ select: [event: RunnerEvent] }>();

function open(event: RunnerEvent): void {
  if (props.clickable) emit('select', event);
}
</script>

<template>
  <div v-if="events.length" class="timeline">
    <article
      v-for="e in events"
      :key="String(e.id)"
      class="event-row"
      :class="['type-' + e.type, { clickable }]"
      :role="clickable ? 'link' : undefined"
      :tabindex="clickable ? 0 : undefined"
      @click="open(e)"
      @keydown.enter="open(e)"
    >
      <div class="event-head">
        <span class="type-chip" :class="e.type">{{ EVENT_TYPE_LABELS[e.type] }}</span>
        <span class="mono ts">{{ fmtDateTime(e.ts) }}</span>
        <span v-if="e.instrument" class="mono inst">{{ e.instrument }}</span>
        <span v-if="showRunner && (e.runner_name || e.runner_id)" class="mono runner">{{ e.runner_name || e.runner_id }}</span>
        <span class="spacer" />
      </div>
      <p v-if="e.type === 'message'" class="event-text">{{ e.text || '（空消息）' }}</p>
      <p v-else class="event-text signal">
        <span class="mono symbol">{{ e.symbol || '—' }}</span>
        <span class="tag" :class="e.direction === 'long' ? 'long' : 'short'">{{ DIRECTION_LABELS[e.direction || 'long'] }}</span>
        <span class="tag action">{{ ACTION_LABELS[e.action || 'open'] }}</span>
        <span v-if="e.qty !== undefined && e.qty !== null" class="mono">数量 {{ fmtNumber(e.qty, 0) }}</span>
        <span v-if="e.price !== undefined && e.price !== null && e.price !== ''" class="mono">价格 {{ fmtNumber(e.price, 2) }}</span>
        <span v-if="e.amount !== undefined && e.amount !== null && e.amount !== ''" class="mono">金额 {{ fmtNumber(e.amount, 2) }}</span>
      </p>
    </article>
  </div>
  <EmptyState v-else compact :title="emptyTitle" :description="emptyDesc" />
</template>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.event-row {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(21, 28, 44, 0.45);
}
.event-row.type-signal {
  border-left: 2px solid var(--primary);
}
.event-row.clickable {
  cursor: pointer;
  transition: border-color 150ms ease, background-color 150ms ease;
}
.event-row.clickable:hover {
  border-color: var(--border-strong);
  background: rgba(91, 140, 255, 0.06);
}
.event-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--text-3);
}
.type-chip {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-2);
  font-size: 10px;
}
.type-chip.signal {
  color: #9db9ff;
  border-color: rgba(91, 140, 255, 0.35);
  background: var(--primary-soft);
}
.ts,
.inst,
.runner {
  font-size: 10px;
}
.spacer {
  flex: 1;
}
.event-text {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text);
  word-break: break-word;
}
.event-text.signal {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--text-2);
}
.symbol {
  color: var(--text);
}
.tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 10px;
  border: 1px solid var(--border);
}
.tag.long {
  color: var(--up);
  border-color: rgba(242, 92, 92, 0.35);
}
.tag.short {
  color: var(--down);
  border-color: rgba(46, 204, 143, 0.35);
}
.tag.action {
  color: var(--text-2);
  background: var(--surface-2);
}
</style>
