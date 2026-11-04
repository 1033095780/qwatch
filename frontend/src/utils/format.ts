// utils/format.ts — 展示格式化：时间（Asia/Shanghai）、相对时间、数值；v0.2 不再有金额/收益格式。
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

/** 普通数值：千分位 + 固定小数位；空值返回 — */
export function fmtNumber(value: string | number | null | undefined, digits = 0): string {
  const n = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(n)) return '—';
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

/** 时间：MM-DD HH:mm:ss（Asia/Shanghai） */
export function fmtDateTime(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('MM-DD HH:mm:ss') : '—';
}

/** 完整时间：YYYY-MM-DD HH:mm:ss（Asia/Shanghai） */
export function fmtFullDateTime(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('YYYY-MM-DD HH:mm:ss') : '—';
}

/** 时间：HH:mm:ss（Asia/Shanghai） */
export function fmtTime(ts?: string | null): string {
  return ts ? dayjs(ts).tz(TZ).format('HH:mm:ss') : '—';
}

/** 相对时间：几秒前 / 3 分钟前 */
export function fromNow(ts?: string | null): string {
  return ts ? dayjs(ts).fromNow() : '—';
}

/** 时长：90s / 3m20s / 2h */
export function fmtDuration(seconds?: number | null): string {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  if (s < 60) return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm' + (s % 60 ? (s % 60) + 's' : '');
  return Math.floor(s / 3600) + 'h' + (Math.floor((s % 3600) / 60) ? Math.floor((s % 3600) / 60) + 'm' : '');
}

/** 数据新鲜度：刚刚更新 / x 秒前更新 / x 分钟前更新 */
export function fmtSecondsAgo(at: number): string {
  const s = Math.max(0, Math.round((Date.now() - at) / 1000));
  if (s < 5) return '刚刚更新';
  if (s < 60) return s + ' 秒前更新';
  if (s < 3600) return Math.floor(s / 60) + ' 分钟前更新';
  return Math.floor(s / 3600) + ' 小时前更新';
}
