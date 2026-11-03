// api/client.ts — 统一 fetch 封装：Bearer token、错误映射、401 广播、全局新鲜度标记。
import { reactive } from 'vue';
import type {
  Account, AccountDetail, Alert, AlertsResponse, AlertStatus, Fill, FillQuery, FillsResponse,
  ListResponse, LoginResponse, Market, Overview, Position, RangeKey, Report, ReportSummary,
  Runner, RunnerDetail, SettingsData, SettingsPatch, TestChannelResult, User,
} from './types';

const API_BASE = '/api/v1';
const TOKEN_KEY = 'qwatch.token';

export const tokenStorage = {
  get(): string {
    try {
      return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || '';
    } catch {
      return '';
    }
  },
  set(token: string, remember: boolean): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
    } catch {
      /* 隐私模式降级：内存态由 auth store 持有 */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** 全局请求元信息：顶部「x 秒前更新」与加载态使用 */
export const apiMeta = reactive({ pending: 0, lastResponseAt: Date.now() });

function qs(params: Record<string, string | number | undefined | null> = {}): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  });
  const s = search.toString();
  return s ? '?' + s : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body !== undefined) headers.set('Content-Type', 'application/json');
  const token = tokenStorage.get();
  if (token) headers.set('Authorization', 'Bearer ' + token);

  apiMeta.pending += 1;
  try {
    let res: Response;
    try {
      res = await fetch(API_BASE + path, { ...init, headers });
    } catch {
      throw new ApiError(0, '无法连接服务，请确认服务已启动');
    }
    apiMeta.lastResponseAt = Date.now();
    if (!res.ok) {
      let detail = 'HTTP ' + res.status;
      try {
        const body = (await res.json()) as { detail?: string };
        if (body && body.detail) detail = body.detail;
      } catch {
        /* 非 JSON 错误体 */
      }
      if (res.status === 401 && !path.startsWith('/auth/login')) {
        window.dispatchEvent(new CustomEvent('qwatch:unauthorized'));
      }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } finally {
    apiMeta.pending -= 1;
  }
}

export const api = {
  login(password: string) {
    return request<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ password }) });
  },
  me() {
    return request<{ user: User }>('/auth/me');
  },
  logout() {
    return request<{ ok: boolean }>('/auth/logout', { method: 'POST' });
  },
  overview(range: RangeKey = 'all') {
    return request<Overview>('/overview' + qs({ range }));
  },
  runners(params: { status?: string; market?: string; q?: string } = {}) {
    return request<ListResponse<Runner>>('/runners' + qs(params));
  },
  runner(id: string, range: RangeKey = 'all') {
    return request<RunnerDetail>('/runners/' + encodeURIComponent(id) + qs({ range }));
  },
  accounts() {
    return request<ListResponse<Account>>('/accounts');
  },
  account(id: string) {
    return request<AccountDetail>('/accounts/' + encodeURIComponent(id));
  },
  fills(query: FillQuery = {}) {
    return request<FillsResponse>('/fills' + qs(query as Record<string, string | number | undefined>));
  },
  positions(params: { account_id?: string } = {}) {
    return request<ListResponse<Position>>('/positions' + qs(params));
  },
  alerts(status: Exclude<AlertStatus, 'firing'> | 'active' | 'history' = 'active') {
    return request<AlertsResponse>('/alerts' + qs({ status }));
  },
  ackAlert(id: string) {
    return request<{ alert: Alert }>('/alerts/' + encodeURIComponent(id) + '/ack', { method: 'POST' });
  },
  silenceAlert(id: string, duration = '1h') {
    return request<{ alert: Alert }>('/alerts/' + encodeURIComponent(id) + '/silence', {
      method: 'POST',
      body: JSON.stringify({ duration }),
    });
  },
  reports() {
    return request<ListResponse<ReportSummary>>('/reports');
  },
  report(date: string) {
    return request<Report>('/reports/' + encodeURIComponent(date));
  },
  settings() {
    return request<SettingsData>('/settings');
  },
  saveSettings(patch: SettingsPatch) {
    return request<SettingsData>('/settings', { method: 'PUT', body: JSON.stringify(patch) });
  },
  testChannel(id: string) {
    return request<TestChannelResult>('/channels/' + encodeURIComponent(id) + '/test', { method: 'POST' });
  },
};

export type { Market };
