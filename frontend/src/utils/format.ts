// utils/format.ts — 展示格式化：时间（Asia/Shanghai）、相对时间、数值；v0.2 不再有金额/收益格式。
import { ref } from 'vue';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import 'dayjs/locale/zh-cn';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.locale('zh-cn');

/** 全局秒级时钟：模板里调用 fromNow 会自动每秒刷新。 */
export const nowTick = ref(Date.now());

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

/** 相对时间：精确到秒的实时刷新 */
export function fromNow(ts?: string | null): string {
  if (!ts) return '—';
  const diff = Math.max(0, Math.floor((nowTick.value - Date.parse(ts)) / 1000));
  if (diff < 1) return '刚刚';
  if (diff < 60) return diff + ' 秒前';
  const minutes = Math.floor(diff / 60);
  if (minutes < 60) return minutes + ' 分钟前';
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours + ' 小时前';
  return Math.floor(hours / 24) + ' 天前';
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
