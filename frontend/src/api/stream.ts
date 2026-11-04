// api/stream.ts — SSE 实时流（fetch + ReadableStream，支持 Authorization；断线自动重连）。
// 契约：GET /api/v1/stream，Bearer 鉴权；事件 alert.* / process.updated / event.message / event.signal。
import { reactive } from 'vue';
import { API_BASE, tokenStorage } from './client';
import type { StreamEvent } from './types';

export type StreamState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'error' | 'stopped';

export const streamMeta = reactive({
  state: 'idle' as StreamState,
  retries: 0,
  lastEventAt: 0,
  lastError: '',
});

type Handler = (event: StreamEvent) => void;
const handlers = new Set<Handler>();
let controller: AbortController | null = null;
let reconnectTimer: number | undefined;
let running = false;
let retries = 0;

export function onStreamEvent(fn: Handler): () => void {
  handlers.add(fn);
  return () => { handlers.delete(fn); };
}

function emit(event: StreamEvent): void {
  streamMeta.lastEventAt = Date.now();
  handlers.forEach((fn) => {
    try { fn(event); } catch { /* 单个订阅异常不影响其它订阅 */ }
  });
}

function scheduleReconnect(): void {
  if (!running) return;
  retries += 1;
  streamMeta.state = 'reconnecting';
  streamMeta.retries = retries;
  const delay = Math.min(30000, 1000 * Math.pow(1.6, Math.min(retries, 6)));
  window.clearTimeout(reconnectTimer);
  reconnectTimer = window.setTimeout(() => { void connect(); }, delay);
}

async function connect(): Promise<void> {
  if (!running) return;
  const token = tokenStorage.get();
  if (!token) { streamMeta.state = 'stopped'; return; }
  controller?.abort();
  controller = new AbortController();
  streamMeta.state = retries ? 'reconnecting' : 'connecting';
  try {
    const res = await fetch(API_BASE + '/stream', {
      headers: { Accept: 'text/event-stream', Authorization: 'Bearer ' + token },
      signal: controller.signal,
      cache: 'no-store',
    });
    if (res.status === 401) {
      streamMeta.state = 'stopped';
      window.dispatchEvent(new CustomEvent('qwatch:unauthorized'));
      return;
    }
    // 后端尚未提供 SSE 时（部分版本返回 404/405）：降级为轮询，60s 后再探测，避免频繁重连刷屏
    if (res.status === 404 || res.status === 405) {
      streamMeta.state = 'error';
      streamMeta.lastError = '实时接口不可用（HTTP ' + res.status + '），已降级轮询';
      window.clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(() => { void connect(); }, 60000);
      return;
    }
    if (!res.ok || !res.body) {
      throw new Error('SSE HTTP ' + res.status);
    }
    retries = 0;
    streamMeta.retries = 0;
    streamMeta.state = 'open';
    streamMeta.lastError = '';
    await readStream(res.body);
    // 正常结束（服务端关闭）：按断线处理
    if (running) scheduleReconnect();
  } catch (err) {
    if (!running || (err instanceof DOMException && err.name === 'AbortError')) return;
    streamMeta.state = 'error';
    streamMeta.lastError = err instanceof Error ? err.message : String(err);
    scheduleReconnect();
  }
}

async function readStream(body: ReadableStream<Uint8Array>): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let eventName = '';
  let dataLines: string[] = [];
  const flush = (): void => {
    if (!eventName && !dataLines.length) return;
    const raw = dataLines.join('\n').trim();
    eventName = '';
    dataLines = [];
    if (!raw || raw === '[DONE]') return;
    let payload: unknown = raw;
    try { payload = JSON.parse(raw); } catch { /* 保留原始文本 */ }
    const wrapped = payload as { type?: unknown; data?: unknown; event?: unknown };
    const data = wrapped && typeof wrapped === 'object' && wrapped.data !== undefined ? wrapped.data : payload;
    const type = eventName || (wrapped && typeof wrapped.type === 'string' ? wrapped.type : 'message');
    emit({ type, data });
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      let line = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 1);
      if (line.endsWith('\r')) line = line.slice(0, -1);
      if (line === '') { flush(); continue; }
      if (line.startsWith(':')) continue; // 注释/心跳
      if (line.startsWith('event:')) { eventName = line.slice(6).trim(); continue; }
      if (line.startsWith('data:')) { dataLines.push(line.slice(5).trimStart()); continue; }
      if (line.startsWith('id:') || line.startsWith('retry:')) continue;
    }
  }
  flush();
}

export function connectStream(): void {
  if (running) return;
  running = true;
  retries = 0;
  void connect();
}

export function disconnectStream(): void {
  running = false;
  window.clearTimeout(reconnectTimer);
  controller?.abort();
  controller = null;
  streamMeta.state = 'stopped';
}

export function streamIsLive(): boolean {
  return streamMeta.state === 'open';
}
