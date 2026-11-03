// utils/format.ts — 展示格式化：金额千分位/等宽、百分比、Asia/Shanghai 时间、相对时间。
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

export const TZ = 'Asia/Shanghai';

const formatters = new Map<string, Intl.NumberFormat>();
export function fmtNumber(value: string | number | null | undefined, digits = 2): string {
  const n = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(n)) return '—';
  const key = String(digits);
  let f = formatters.get(key);
  if (!f) {
    f = new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    formatters.set(key, f);
  }
  return f.format(n);
}

/** 金额：默认 2 位小数 + 千分位，可选 ¥ 前缀 */
export function fmtMoney(value: string | number | null | undefined, digits = 2, withSymbol = false): string {
  const s = fmtNumber(value, digits);
  return withSymbol && s !== '—' ? '¥' + s : s;
}

/** 带符号金额（正数 + 号） */
export function fmtSignedMoney(value: string | number | null | undefined, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return (n > 0 ? '+' : '') + fmtNumber(n, digits);
}

/** 百分比：默认 2 位；withSign 正数带 + */
export function fmtPct(value: string | number | null | undefined, digits = 2, withSign = true): string {
  const n = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(n)) return '—';
  return (withSign && n > 0 ? '+' : '') + n.toFixed(digits) + '%';
}

/** 数值（非金额），如手数、笔数 */
export function fmtQty(value: string | number | null | undefined, digits = 0): string {
  return fmtNumber(value, digits);
}

export function pnlClass(value: string | number | null | undefined): 'is-up' | 'is-down' | 'is-flat' {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return 'is-flat';
  return n > 0 ? 'is-up' : 'is-down';
}

export function fmtDate(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('YYYY-MM-DD') : '—';
}

export function fmtShortDate(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('MM-DD') : '—';
}

export function fmtDateTime(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('MM-DD HH:mm:ss') : '—';
}

export function fmtFullDateTime(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('YYYY-MM-DD HH:mm:ss') : '—';
}

export function fmtTime(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('HH:mm:ss') : '—';
}

/** tooltip 用：UTC 时间 */
export function fmtUtc(ts?: string | null): string {
  return ts ? dayjs(ts).utc().format('YYYY-MM-DD HH:mm:ss') + ' UTC' : '—';
}

/** 时区标注 */
export function fmtWithZone(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('YYYY-MM-DD HH:mm:ss') + ' CST' : '—';
}

export function fromNow(ts?: string | null): string {
  return ts ? dayjs(ts).fromNow() : '—';
}

export function fmtDuration(seconds?: number | null): string {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  if (s < 60) return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm' + (s % 60 ? (s % 60) + 's' : '');
  return Math.floor(s / 3600) + 'h' + (Math.floor((s % 3600) / 60) ? Math.floor((s % 3600) / 60) + 'm' : '');
}

export function fmtSecondsAgo(at: number): string {
  const s = Math.max(0, Math.round((Date.now() - at) / 1000));
  if (s < 5) return '刚刚更新';
  if (s < 60) return s + ' 秒前更新';
  if (s < 3600) return Math.floor(s / 60) + ' 分钟前更新';
  return Math.floor(s / 3600) + ' 小时前更新';
}

/** 图表 x 轴标签：区间短于 2 天用 HH:mm，否则 MM-DD */
export function axisTimeLabel(ts: number | string, intraday: boolean): string {
  const d = dayjs(ts).tz(TZ);
  return intraday ? d.format('HH:mm') : d.format('MM-DD');
}
