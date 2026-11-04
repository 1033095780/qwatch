// api/types.ts — qwatch v0.4 API 契约类型（docs/V04-CONTRACT.md）。
// 账户（券商/账户）是净值/权益来源；策略属于账户；进程属于策略。权益/净值按账户展示。

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

export interface LoginResponse {
  token: string;
  user: User;
}

export interface CurvePoint {
  ts: string;
  value: string;
}

/** 账户：券商/账户层级；equity/nav 由下属任意策略进程上报更新（最后一次为准） */
export interface Account {
  id: string;
  name: string;
  broker: string;
  description?: string;
  equity?: string | null;
  nav?: string | null;
  equity_updated_at?: string | null;
  nav_updated_at?: string | null;
  created_at?: string | null;
  strategy_count?: number;
  online_strategies?: number;
  equity_sparkline?: number[];
}

export interface AccountCreateRequest {
  name: string;
  broker: string;
  description?: string;
}

export interface AccountPatch {
  name?: string;
  broker?: string;
  description?: string;
}

export interface AccountDetail {
  account: Account;
  strategies: Runner[];
}

/** GET /runners 列表项（策略组，含所属账户信息；不返回 runner 自身权益） */
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
  created_at?: string | null;
}

export interface ProcessInfo {
  name: string;
  status: ProcessStatus;
  last_seen: string | null;
  loop: number | null;
  retired: boolean;
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
  account: Account;
  processes: ProcessInfo[];
  events: RunnerEvent[];
  alerts: Alert[];
  /** 该策略所属账户的权益曲线（账户级） */
  account_equity_curve: CurvePoint[];
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
