<script setup lang="ts">
// ActivityFeed.vue — 消息/信号统一动态流，侧重扫读和点击跳转。
import { ArrowUpRight, MessageSquare, TrendingDown, TrendingUp } from 'lucide-vue-next';
import type { RunnerEvent } from '@/api/types';
import { ACTION_LABELS, DIRECTION_LABELS } from '@/utils/catalog';
import { fmtDateTime, fmtNumber } from '@/utils/format';
import EmptyState from './EmptyState.vue';

withDefaults(defineProps<{ events: RunnerEvent[]; showRunner?: boolean; clickable?: boolean; emptyTitle?: string; emptyDesc?: string }>(), {
  showRunner: false,
  clickable: false,
  emptyTitle: '暂无动态',
  emptyDesc: '策略上报消息或信号后会出现在这里。',
});
const emit = defineEmits<{ select: [event: RunnerEvent] }>();
</script>

<template>
  <div v-if="events.length" class="feed">
    <article
      v-for="(event, index) in events"
      :key="String(event.id)"
      class="feed-row"
      :class="['type-' + event.type, { clickable, featured: index === 0 }]"
      :role="clickable ? 'link' : undefined"
      :tabindex="clickable ? 0 : undefined"
      @click="clickable && emit('select', event)"
      @keydown.enter="clickable && emit('select', event)"
    >
      <div class="rail">
        <span class="rail-icon" :class="event.type">
          <component :is="event.type === 'message' ? MessageSquare : event.direction === 'short' ? TrendingDown : TrendingUp" :size="13" />
        </span>
        <span class="rail-line" />
      </div>
      <div class="feed-body">
        <div class="feed-top">
          <span class="type-label">{{ event.type === 'message' ? '消息' : '信号' }}</span>
          <span v-if="showRunner && (event.runner_name || event.runner_id)" class="runner">{{ event.runner_name || event.runner_id }}</span>
          <span class="inst mono">{{ event.instrument }}</span>
          <time>{{ fmtDateTime(event.ts) }}</time>
        </div>
        <p v-if="event.type === 'message'" class="message">{{ event.text || '（空消息）' }}</p>
        <div v-else class="signal-line">
          <strong class="symbol mono">{{ event.symbol || '—' }}</strong>
          <span class="side" :class="event.direction">{{ DIRECTION_LABELS[event.direction || 'long'] }}</span>
          <span class="action">{{ ACTION_LABELS[event.action || 'open'] }}</span>
          <span v-if="event.qty" class="metric">数量 {{ fmtNumber(event.qty, 0) }}</span>
          <span v-if="event.price" class="metric">价格 {{ fmtNumber(event.price, 2) }}</span>
          <span v-if="event.text" class="signal-msg">{{ event.text }}</span>
        </div>
      </div>
      <ArrowUpRight v-if="clickable" :size="13" class="go" />
    </article>
  </div>
  <EmptyState v-else compact :title="emptyTitle" :description="emptyDesc" />
</template>

<style scoped>
.feed {
  display: flex;
  flex-direction: column;
}
.feed-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 16px;
  gap: 10px;
  padding: 11px 0;
  border-bottom: 1px solid var(--border);
  color: inherit;
  transition: background-color 150ms ease;
}
.feed-row:last-child { border-bottom: 0; }
.feed-row.clickable { cursor: pointer; }
.feed-row.clickable:hover { background: rgba(91, 140, 255, 0.055); }
.feed-row.featured .message { font-size: 13px; color: var(--text); }
.rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 1px;
}
.rail-icon {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  color: #9db9ff;
  background: rgba(91, 140, 255, 0.1);
  border: 1px solid rgba(91, 140, 255, 0.2);
}
.rail-icon.message {
  color: #93a4c4;
  background: rgba(147, 164, 196, 0.08);
  border-color: rgba(147, 164, 196, 0.16);
}
.rail-line {
  flex: 1;
  width: 1px;
  margin-top: 4px;
  background: var(--border);
}
.feed-row:last-child .rail-line { display: none; }
.feed-body { min-width: 0; }
.feed-top {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 9px;
  color: var(--text-3);
}
.type-label {
  color: #9db9ff;
  font-size: 10px;
}
.type-message .type-label { color: var(--text-3); }
.runner { color: var(--text-2); }
.inst { color: var(--text-2); }
.feed-top time { margin-left: auto; white-space: nowrap; }
.message {
  margin: 5px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-2);
  word-break: break-word;
}
.signal-line {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 5px;
  font-size: 11px;
  color: var(--text-3);
}
.symbol { font-size: 12px; color: var(--text); }
.side {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 10px;
  border: 1px solid rgba(242, 92, 92, 0.3);
  color: var(--up);
}
.side.short { color: var(--down); border-color: rgba(46, 204, 143, 0.3); }
.action { font-size: 10px; color: var(--text-2); }
.metric { font-size: 10px; }
.signal-msg { color: var(--text-3); }
.go { margin-top: 4px; color: var(--text-3); opacity: 0; transition: opacity 150ms ease; }
.feed-row:hover .go { opacity: 1; }
</style>
