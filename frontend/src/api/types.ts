// api/types.ts — qwatch v0.2 API 契约类型（docs/V02-CONTRACT.md）。
// 定位：可信看门狗。策略 token = 策略组；instrument = 稳定进程名；无 PnL/净值/收益/风险/账户/日历。

export type RunnerStatus = 'running' | 'degraded' | 'offline' | 'paused';
/** 进程状态：与策略状态同构；retired 表示已停用（不参与存活判定） */
export type ProcessStatus = RunnerStatus | 'retired';
export type AlertStatus = 'firing' | 'acknowledged' | 'resolved';
export type AlertRule = 'heartbeat_lost' | 'runner_stalled';
export type EventType = 'message' | 'signal';
export type SignalDirection = 'long' | 'short';
export type SignalAction = 'open' | 'close' | 'add' | 'reduce';
export type UpColorScheme = 'red_up' | 'green_up';

export interface User {
  name: string;
  role: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

/** GET /runners 列表项（策略组） */
export interface Runner {
  id: string;
  name: string;
  description: string;
  status: RunnerStatus;
  /** 进程总数 / 在线进程数（契约字段 process_count / online_processes） */
  process_count: number;
  online_processes: number;
  last_seen: string | null;
  last_msg: string | null;
  nav?: string | null;
  nav_updated_at?: string | null;
  nav_sparkline?: number[];
  equity?: string | null;
  equity_updated_at?: string | null;
  /** 以下为可选的展示辅助字段，后端未提供时前端不显示 */
  created_at?: string | null;
}

/** GET /runners/{id} 中的进程 */
export interface ProcessInfo {
  name: string;
  status: ProcessStatus;
  last_seen: string | null;
  loop: number | null;
  retired: boolean;
}

/** GET /runners/{id} 中的动态：message + signal 合并 */
export interface RunnerEvent {
  id: string | number;
  ts: string;
  type: EventType;
  instrument: string;
  runner_id?: string;
  runner_name?: string;
  text?: string;
  symbol?: string;
  direction?: SignalDirection;
  action?: SignalAction;
  qty?: number | string;
  price?: number | string | null;
  amount?: number | string | null;
}

export interface Alert {
  id: string;
  rule: AlertRule | string;
  status: AlertStatus;
  runner_id: string;
  runner_name: string;
  /** 摘要列出进程名（heartbeat_lost / runner_stalled 按策略组汇总一条） */
  summary: string;
  starts_at: string;
  ends_at?: string | null;
  acked_at?: string | null;
  labels?: Record<string, string>;
  updated_at?: string;
}

export interface RunnerDetail {
  runner: Runner;
  processes: ProcessInfo[];
  events: RunnerEvent[];
  alerts: Alert[];
  nav_curve?: { ts: string; value: string }[];
  equity_curve?: { ts: string; value: string }[];
}

export interface Overview {
  running: number;
  total: number;
  active_alerts: number;
  processes_total: number;
  processes_online: number;
  total_equity?: string | null;
  today_equity_change?: string | null;
  equity_as_of?: string | null;
  recent_alerts: Alert[];
  recent_events?: RunnerEvent[];
  runners: Runner[];
}

export interface ListResponse<T> {
  items: T[];
  total?: number;
}

export interface AlertsResponse {
  items: Alert[];
  active_count: number;
}

export interface Channel {
  id: string;
  name: string;
  type?: 'dingtalk_robot';
  enabled: boolean;
  webhook_masked: string;
  secret_masked: string;
  rate_limit_per_min?: number;
  last_test_at: string | null;
  last_test_ok: boolean | null;
}

export interface ChannelPatch {
  id: string;
  enabled?: boolean;
  webhook?: string;
  secret?: string;
}

export interface SettingsData {
  channels: Channel[];
}

export interface TestChannelResult {
  ok: boolean;
  channel_id: string;
  message: string;
  latency_ms?: number;
  at?: string;
}

export interface RunnerCreateRequest {
  name: string;
  description?: string;
}

export interface StrategyToken {
  id: string;
  runner_id: string | null;
  name: string;
  token_prefix: string;
  status: 'active' | 'revoked';
  created_at: string;
  last_used_at: string | null;
  request_count: number;
}

export interface TokensResponse {
  items: StrategyToken[];
  total?: number;
}

export interface TokenCreateRequest {
  name: string;
  runner_id?: string;
}

export interface TokenCreateResult {
  token: string;
  record: StrategyToken;
}

/** SSE 事件：GET /api/v1/stream（Authorization: Bearer） */
export interface StreamEvent {
  /** 契约事件名：alert.firing / alert.resolved / alert.updated / process.updated / event.message / event.signal；兼容服务端仅发 data 时由 data.type 推断 */
  type: string;
  /** 事件原始负载（已 JSON.parse；无法解析时为字符串） */
  data: unknown;
}
