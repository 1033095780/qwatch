// api/types.ts — API 契约类型。
export type Market = 'CN_A' | 'CN_FUT' | 'HK' | 'US' | 'CRYPTO';
export type RunnerStatus = 'running' | 'degraded' | 'offline' | 'off_hours';
export type Severity = 'P0' | 'P1' | 'P2';
export type AlertStatus = 'firing' | 'acknowledged' | 'resolved';
export type FillSide = 'buy' | 'sell';
export type PositionEffect = 'open' | 'close';
export type RangeKey = '1d' | '1w' | '1m' | '3m' | '1y' | 'all';
export type UpColorScheme = 'red_up' | 'green_up';

export interface User {
  name: string;
  role: string;
}

export interface LoginResponse {
  token: string;
  user: User;
  demo?: boolean;
}

export interface RunnerAccount {
  id: string;
  name: string;
  venue: string;
}

export interface Runner {
  id: string;
  name: string;
  strategy: string;
  version: string;
  market: Market;
  venue: string;
  status: RunnerStatus;
  accounts: RunnerAccount[];
  equity: string;
  today_pnl: string;
  today_pnl_pct: string;
  total_return_pct: string;
  max_drawdown_pct: string;
  uptime_24h: string;
  last_heartbeat: string;
  sparkline: number[];
  position_count: number;
}

export interface Fill {
  id: string;
  ts: string;
  runner_id: string;
  runner_name: string;
  account_id: string;
  account_name: string;
  instrument: string;
  instrument_name: string;
  side: FillSide;
  position_effect: PositionEffect;
  qty: string;
  price: string;
  amount: string;
  fee: string;
  currency: string;
  status: 'filled' | 'partial';
}

export interface Alert {
  id: string;
  fingerprint: string;
  rule: string;
  severity: Severity;
  status: AlertStatus;
  runner_id: string;
  runner_name: string;
  summary: string;
  starts_at: string;
  ends_at?: string | null;
  acked_at?: string | null;
  labels: Record<string, string>;
  updated_at: string;
}

export interface EquityPoint {
  ts: string;
  nav: number;
  value: string;
}

export interface OverviewCurvePoint {
  ts: string;
  value: string;
  nav?: number;
}

export interface Overview {
  as_of: string;
  total_equity: string;
  today_pnl: string;
  today_pnl_pct: string;
  running: number;
  total: number;
  active_alerts: number;
  range: RangeKey;
  equity_curve: OverviewCurvePoint[];
  benchmark: OverviewCurvePoint[];
  runners: Runner[];
  alerts: Alert[];
  recent_fills: Fill[];
}

export interface Position {
  account_id?: string;
  runner_id?: string;
  runner_name?: string;
  instrument: string;
  instrument_name: string;
  market: Market;
  venue?: string;
  qty: string;
  avg_price: string;
  last_price: string;
  market_value: string;
  pnl: string;
  pnl_pct: string;
  currency: string;
}

export interface DrawdownPoint {
  ts: string;
  value: number;
}

export interface HeartbeatSegment {
  ts: string;
  status: 'ok' | 'miss' | 'off';
}

export interface Outage {
  start: string;
  end: string | null;
  duration_s: number;
}

export interface RunnerDetail {
  runner: Runner;
  range: RangeKey;
  metrics: {
    total_return_pct: string;
    today_pnl: string;
    max_drawdown_pct: string;
    sharpe: string;
    win_rate_pct: string;
    uptime_30d: string;
  };
  equity: EquityPoint[];
  drawdown: DrawdownPoint[];
  heartbeat_timeline: HeartbeatSegment[];
  outages: Outage[];
  fills: Fill[];
  positions: Position[];
  alerts: Alert[];
  config: {
    strategy: string;
    version: string;
    host: string;
    pid: number;
    calendar_id: string;
    heartbeat_interval_s: number;
    soft_timeout_s: number;
    hard_timeout_s: number;
    started_at: string;
    last_seq: number;
    env: string;
    accounts: string[];
  };
}

export interface Account {
  id: string;
  name: string;
  venue: string;
  market: Market;
  currency: string;
  equity: string;
  today_pnl: string;
  today_pnl_pct: string;
  positions_count: number;
  sparkline: number[];
  runner_ids: string[];
}

export interface CashFlow {
  id: string;
  ts: string;
  amount: string;
  currency: string;
  kind: 'deposit' | 'withdraw' | string;
  note: string;
}

export interface AccountDetail {
  account: Account & { initial_equity: string };
  equity: EquityPoint[];
  positions: Position[];
  cash_flows: CashFlow[];
  fills: Fill[];
  total_return_pct: string;
}

export interface ListResponse<T> {
  items: T[];
  total?: number;
}

export interface FillsResponse {
  items: Fill[];
  total: number;
  limit: number;
  next_cursor: string | null;
}

export interface AlertsResponse {
  items: Alert[];
  active_count: number;
}

export interface ReportSummary {
  date: string;
  total_equity: string;
  today_pnl: string;
  today_pnl_pct: string;
  trades: number;
  alerts: number;
  status: 'ok' | 'warn';
}

export interface ReportStrategy {
  runner_id: string;
  name: string;
  pnl: string;
  pct: string;
  trades: number;
  drawdown: string;
}

export interface Report extends ReportSummary {
  strategies: ReportStrategy[];
}

export interface Channel {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
  webhook: string;
  secret_masked: string;
  sign_enabled: boolean;
  rate_limit: string;
  last_test_at: string | null;
  last_test_ok: boolean | null;
}

export interface StrategyToken {
  id: string;
  name: string;
  scope: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
}

export interface TradingCalendar {
  id: string;
  name: string;
  timezone: string;
  sessions: string[];
  night: boolean;
  holidays: string;
}

export interface SettingsData {
  user: User & { timezone?: string };
  up_color_scheme: UpColorScheme;
  channels: Channel[];
  tokens: StrategyToken[];
  calendars: TradingCalendar[];
  security: {
    session_hours: number;
    login_rate_limit: string;
    totp_enabled: boolean;
    last_password_change: string;
  };
  about: { version: string; build: string; mode: string; license: string };
}

export interface TestChannelResult {
  ok: boolean;
  channel_id: string;
  message: string;
  latency_ms: number;
  at: string;
}

export interface FillQuery {
  runner_id?: string;
  account_id?: string;
  market?: string;
  instrument?: string;
  side?: string;
  from?: string;
  to?: string;
  cursor?: number | string;
  limit?: number;
}

export type SettingsPatch = {
  up_color_scheme?: UpColorScheme;
  channels?: Pick<Channel, 'id' | 'enabled'>[];
  tokens?: Pick<StrategyToken, 'id' | 'revoked'>[];
  security?: Partial<SettingsData['security']>;
};
