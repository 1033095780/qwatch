// utils/catalog.ts — 平台 / 策略类型 / 市场 / 信号动作的展示映射与筛选项（后端 *_label 与此保持一致）。
import type { Market, Platform, SignalAction, StrategyType } from '@/api/types';

export const PLATFORM_LABELS: Record<Platform, string> = {
  ptrade: 'PTrade', qmt: 'QMT', myquant: '掘金', tqsdk: '天勤', custom: '自研',
};

export const STRATEGY_TYPE_LABELS: Record<StrategyType, string> = {
  trend: '趋势', arbitrage: '套利', intraday: '日内', grid: '网格',
  multifactor: '多因子', market_making: '做市', other: '其他',
};

export const MARKET_LABELS: Record<Market, string> = {
  CN_A: 'A股', CN_FUT: '期货', FX: '外汇', CRYPTO: '加密', US: '美股', HK: '港股',
};

export const SIGNAL_ACTION_LABELS: Record<SignalAction, string> = {
  open: '开仓', close: '平仓', add: '加仓', reduce: '减仓',
};

export const PLATFORM_OPTIONS = (Object.keys(PLATFORM_LABELS) as Platform[]).map((value) => ({
  value, label: PLATFORM_LABELS[value],
}));

export const STRATEGY_TYPE_OPTIONS = (Object.keys(STRATEGY_TYPE_LABELS) as StrategyType[]).map((value) => ({
  value, label: STRATEGY_TYPE_LABELS[value],
}));

/** 令牌可绑定的市场（不含港股，与 docs/FEATURE-SIGNALS-TOKENS.md 一致） */
export const TOKEN_MARKET_OPTIONS: { value: Market; label: string }[] = [
  { value: 'CN_A', label: 'A股' },
  { value: 'CN_FUT', label: '期货' },
  { value: 'FX', label: '外汇' },
  { value: 'CRYPTO', label: '加密' },
  { value: 'US', label: '美股' },
];

/** 逗号分隔标签输入 → 去重后的字符串数组 */
export function parseTags(text: string): string[] {
  const seen = new Set<string>();
  return text
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter((item) => item && !seen.has(item) && seen.add(item));
}
