// utils/catalog.ts — v0.2 展示映射：状态、动态类型、方向/动作、告警规则（无市场/平台/策略类型）。
import type { AlertRule, EventType, ProcessStatus, RunnerStatus, SignalAction, SignalDirection } from '@/api/types';

export const RUNNER_STATUS_LABELS: Record<RunnerStatus, string> = {
  running: '运行中',
  degraded: '降级',
  offline: '离线',
  paused: '已暂停',
};

export const PROCESS_STATUS_LABELS: Record<ProcessStatus, string> = {
  running: '运行中',
  degraded: '降级',
  offline: '离线',
  paused: '已暂停',
  retired: '已停用',
};

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  message: '消息',
  signal: '信号',
};

export const DIRECTION_LABELS: Record<SignalDirection, string> = {
  long: '做多',
  short: '做空',
};

export const ACTION_LABELS: Record<SignalAction, string> = {
  open: '开仓',
  close: '平仓',
  add: '加仓',
  reduce: '减仓',
};

export const RULE_LABELS: Record<AlertRule, string> = {
  heartbeat_lost: '心跳丢失',
  runner_stalled: '策略卡死',
};

export function ruleLabel(rule: string): string {
  return RULE_LABELS[rule as AlertRule] || rule;
}
