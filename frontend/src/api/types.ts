// api/types.ts — qwatch v0.5 API 契约类型（docs/V05-CONTRACT.md）。
// 策略级权益：任意进程上报 equity/nav 写入所属策略，last-wins；账户权益 = 下属策略之和（API 计算字段）。

export type RunnerStatus = 'running' | 'degraded' | 'offline' | 'paused';
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

export interface AuthStatus {
  setup_required: boolean;
  min_password_length?: number;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface CurvePoint {
  ts: string;
  value: string;
}

/** 账户：只是策略的自然分组；equity/nav 为计算字段（Σ策略 / 加权净值） */
export interface Account {
  id: string;
  name: string;
  broker: string;
  description?: string;
  equity?: string | null;
  today_pnl?: string | null;
  equity_updated_at?: string | null;
  created_at?: string | null;
  strategy_count?: number;
  online_strategies?: number;
  /** 账户聚合曲线最后 24 点 */
  equity_sparkline?: number[];
}

export interface AccountCreateRequest {
  name: string;
  broker?: string;
  description?: string;
}

/** GET /runners 列表项（策略组；含策略级权益与所属账户信息） */
export interface HeartbeatBucket {
  start: string;
  end: string;
  ratio: number | null;
}

export interface Runner {
  id: string;
  name: string;
  description: string;
  status: RunnerStatus;
  process_count: number;
  online_processes: number;
  last_seen: string | null;
  last_msg?: string | null;
  account_id: string;
  account_name: string;
  account_broker: string;
  /** 策略级权益/净值（由该策略进程上报，last-wins） */
  equity?: string | null;
  today_pnl?: string | null;
  equity_updated_at?: string | null;
  equity_sparkline?: number[];
  heartbeat_7d?: HeartbeatBucket[];
  uptime_7d?: number | null;
  created_at?: string | null;
}

export interface ProcessInfo {
  name: string;
  status: ProcessStatus;
  last_seen: string | null;
  loop: number | null;
  retired: boolean;
  heartbeat_7d?: HeartbeatBucket[];
}

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

export interface ActivityEvent extends RunnerEvent {
  runner_id?: string;
  runner_name?: string;
  account_name?: string;
}

export interface EventFeedResponse {
  items: ActivityEvent[];
  has_more: boolean;
  next_before_id: number | null;
}

export interface Alert {
  id: string;
  rule: AlertRule | string;
  status: AlertStatus;
  runner_id: string;
  runner_name: string;
  summary: string;
  starts_at: string;
  ends_at?: string | null;
  acked_at?: string | null;
  labels?: Record<string, string>;
  updated_at?: string;
}

export interface RunnerDetail {
  runner: Runner;
  account: Account | null;
  processes: ProcessInfo[];
  events: RunnerEvent[];
  alerts: Alert[];
  /** 该策略自身的权益曲线（策略级） */
  equity_curve: CurvePoint[];
}

export interface Overview {
  running: number;
  total: number;
  processes_total: number;
  processes_online: number;
  active_alerts: number;
  account_count?: number;
  total_equity?: string | null;
  today_equity_change?: string | null;
  today_pnl?: string | null;
  equity_curve?: CurvePoint[];
  accounts: Account[];
  runners: Runner[];
  recent_events?: RunnerEvent[];
  recent_alerts: Alert[];
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
  account_id: string;
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

export interface StreamEvent {
  type: string;
  data: unknown;
}