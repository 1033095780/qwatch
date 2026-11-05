// stores/realtime.ts — SSE 实时流状态与最近动态缓冲（AppShell 启动；页面订阅使用）。
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { connectStream, disconnectStream, onStreamEvent, streamMeta } from '@/api/stream';
import type { RunnerEvent, StreamEvent } from '@/api/types';

export interface LiveEvent extends RunnerEvent {
  runner_id: string;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

/** 兼容服务端事件负载的几种包裹方式：直接对象 / { event } / { data } */
function normalizeEvent(data: unknown, type: string): LiveEvent | null {
  const outer = asRecord(data);
  const inner = asRecord(outer.event ?? outer.data ?? outer);
  const runnerId = String(inner.runner_id ?? outer.runner_id ?? '').trim();
  const ts = String(inner.ts ?? outer.ts ?? '');
  if (!runnerId || !ts) return null;
  const rawType = String(inner.type ?? '');
  const eventType: RunnerEvent['type'] = type.endsWith('signal') || rawType === 'signal' ? 'signal' : 'message';
  return {
    id: String(inner.id ?? outer.id ?? ts + '-' + runnerId),
    ts,
    type: eventType,
    instrument: String(inner.instrument ?? outer.instrument ?? '—'),
    text: inner.text != null ? String(inner.text) : (inner.msg != null ? String(inner.msg) : undefined),
    symbol: inner.symbol != null ? String(inner.symbol) : undefined,
    direction: inner.direction as RunnerEvent['direction'],
    action: inner.action as RunnerEvent['action'],
    qty: inner.qty as RunnerEvent['qty'],
    price: inner.price as RunnerEvent['price'],
    amount: inner.amount as RunnerEvent['amount'],
    runner_id: runnerId,
  };
}

export const useRealtimeStore = defineStore('realtime', () => {
  const events = ref<LiveEvent[]>([]);
  const lastAlertChangeAt = ref(0);
  const lastProcessChangeAt = ref(0);
  const lastEventAt = ref(0);
  const lastAccountChangeAt = ref(0);
  const lastEquityChangeAt = ref(0);
  const started = ref(false);
  let off: (() => void) | null = null;

  const state = computed(() => streamMeta.state);
  const live = computed(() => streamMeta.state === 'open');

  function handle(event: StreamEvent): void {
    const type = event.type || '';
    if (type.indexOf('alert.') === 0) {
      lastAlertChangeAt.value = Date.now();
      return;
    }
    if (type.indexOf('account.') === 0) {
      lastAccountChangeAt.value = Date.now();
      return;
    }
    if (type.indexOf('strategy.equity') === 0 || type === 'strategy.equity_updated') {
      lastEquityChangeAt.value = Date.now();
      return;
    }
    if (type === 'process.updated' || type.indexOf('process.') === 0) {
      lastProcessChangeAt.value = Date.now();
      return;
    }
    if (type === 'event.message' || type === 'event.signal' || type === 'message' || type === 'signal') {
      const e = normalizeEvent(event.data, type);
      if (!e) return;
      lastEventAt.value = Date.now();
      events.value = [e, ...events.value].slice(0, 120);
    }
  }

  function start(): void {
    if (started.value) return;
    started.value = true;
    off = onStreamEvent(handle);
    connectStream();
  }

  function stop(): void {
    started.value = false;
    off?.();
    off = null;
    disconnectStream();
  }

  function clear(): void {
    events.value = [];
  }

  return {
    events, lastAlertChangeAt, lastProcessChangeAt, lastEventAt, lastAccountChangeAt, lastEquityChangeAt,
    state, live, started, start, stop, clear,
  };
});
