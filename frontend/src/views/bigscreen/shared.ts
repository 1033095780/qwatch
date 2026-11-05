// bigscreen/shared.ts — 大屏预览共用排序与格式化；不改变正式总览。
import type { Account, Overview, Runner } from '@/api/types';
import { fmtNumber } from '@/utils/format';

export interface BigScreenData {
  overview: Overview;
  accounts: Account[];
  runners: Runner[];
}

export const STATUS_RANK: Record<string, number> = { offline: 0, degraded: 1, paused: 2, running: 3 };

export function sortRunners(list: Runner[]): Runner[] {
  return [...list].sort((a, b) => {
    const rank = (STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9);
    return rank || a.name.localeCompare(b.name, 'zh-CN');
  });
}

export function money(value: string | number | null | undefined): string {
  const n = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(n)) return '—';
  return '¥' + fmtNumber(n, 0);
}

export function pnl(value: string | number | null | undefined): string {
  const n = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(n)) return '—';
  return (n >= 0 ? '+' : '') + fmtNumber(n, 0);
}

export function pnlClass(value: string | number | null | undefined): 'up' | 'down' | '' {
  const n = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(n)) return '';
  return n >= 0 ? 'up' : 'down';
}

export function issueText(runner: Runner): string {
  if (runner.status === 'offline') return '离线';
  if (runner.status === 'degraded') return '异常';
  if (runner.status === 'paused') return '已暂停';
  return '运行中';
}

export function heartbeatTone(runner: Runner): string {
  if (runner.status === 'offline') return 'off';
  if (runner.status === 'degraded') return 'warn';
  if (runner.status === 'paused') return 'paused';
  return 'live';
}
