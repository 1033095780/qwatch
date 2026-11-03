// mock/api.mjs — qwatch mock API（/api/v1）：被 Vite dev 中间件与 mock-server.mjs 共用。
import {
  getOverview, getRunners, getRunnerDetail, createRunner, getAccounts, getAccountDetail,
  getSignals, getPositions, getAlerts, acknowledgeAlert, silenceAlert,
  getReports, getReport, getSettings, saveSettings, testChannel,
  getTokens, createToken, revokeToken, ingestReport, runWatchdog, mockMeta,
} from './data.mjs';

export const MOCK_TOKEN = 'mock-token';
export const API_PREFIX = '/api/v1';

const send = (res, status, body) => {
  const payload = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(payload);
};

const readBody = (req) => new Promise((resolve, reject) => {
  let raw = '';
  req.on('data', (chunk) => { raw += chunk; if (raw.length > 1e6) { reject(new Error('payload too large')); req.destroy(); } });
  req.on('end', () => {
    if (!raw) return resolve({});
    try { resolve(JSON.parse(raw)); } catch { reject(new Error('invalid json')); }
  });
  req.on('error', reject);
});

const bearer = (req) => {
  const h = req.headers.authorization || '';
  return h.startsWith('Bearer ') ? h.slice(7).trim() : '';
};

export async function handleApi(req, res) {
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname;
  if (!path.startsWith(API_PREFIX + '/') && path !== API_PREFIX && path !== '/healthz') return false;
  const route = path.replace(API_PREFIX, '');
  const method = (req.method || 'GET').toUpperCase();
  const query = Object.fromEntries(url.searchParams.entries());

  try {
    runWatchdog();
    if (method === 'GET' && route === '/healthz') {
      send(res, 200, { ok: true, service: 'qwatch-mock', version: '0.1.0', mock: mockMeta });
      return true;
    }

    if (method === 'POST' && route === '/auth/login') {
      const body = await readBody(req);
      if (body.password !== 'qwatch') {
        send(res, 401, { detail: '密码错误' });
        return true;
      }
      send(res, 200, { token: MOCK_TOKEN, user: { name: 'Trader', role: 'owner' }, demo: true });
      return true;
    }

    // 策略接入：用策略令牌鉴权，不走后台登录 token
    if (method === 'POST' && route === '/report') {
      const body = await readBody(req);
      const result = ingestReport(bearer(req), body);
      send(res, result.status, result.body);
      return true;
    }

    // 其余接口需要 Bearer token
    if (bearer(req) !== MOCK_TOKEN) {
      send(res, 401, { detail: '未登录或登录已过期' });
      return true;
    }

    if (method === 'GET' && route === '/auth/me') {
      send(res, 200, { user: { name: 'Trader', role: 'owner' } });
      return true;
    }
    if (method === 'POST' && route === '/auth/logout') {
      send(res, 200, { ok: true });
      return true;
    }

    if (method === 'GET' && route === '/overview') {
      send(res, 200, getOverview(query));
      return true;
    }

    if (method === 'GET' && route === '/runners') {
      send(res, 200, getRunners(query));
      return true;
    }
    if (method === 'POST' && route === '/runners') {
      const body = await readBody(req);
      const result = createRunner(body);
      if (result.error) { send(res, 400, { detail: result.error }); return true; }
      send(res, 201, result);
      return true;
    }

    const runnerMatch = route.match(/^\/runners\/([^/]+)$/);
    if (method === 'GET' && runnerMatch) {
      const detail = getRunnerDetail(decodeURIComponent(runnerMatch[1]), query);
      if (!detail) return send(res, 404, { detail: 'Runner 不存在' }), true;
      send(res, 200, detail);
      return true;
    }

    if (method === 'GET' && route === '/accounts') {
      send(res, 200, getAccounts());
      return true;
    }
    const accountMatch = route.match(/^\/accounts\/([^/]+)$/);
    if (method === 'GET' && accountMatch) {
      const detail = getAccountDetail(decodeURIComponent(accountMatch[1]));
      if (!detail) return send(res, 404, { detail: '账户不存在' }), true;
      send(res, 200, detail);
      return true;
    }

    if (method === 'GET' && route === '/signals') {
      send(res, 200, getSignals(query));
      return true;
    }
    if (method === 'GET' && route === '/positions') {
      send(res, 200, getPositions(query));
      return true;
    }
    if (method === 'GET' && route === '/alerts') {
      send(res, 200, getAlerts(query));
      return true;
    }
    const ackMatch = route.match(/^\/alerts\/([^/]+)\/ack$/);
    if (method === 'POST' && ackMatch) {
      const alert = acknowledgeAlert(decodeURIComponent(ackMatch[1]));
      if (!alert) return send(res, 404, { detail: '告警不存在' }), true;
      send(res, 200, { alert });
      return true;
    }
    const silenceMatch = route.match(/^\/alerts\/([^/]+)\/silence$/);
    if (method === 'POST' && silenceMatch) {
      const body = await readBody(req);
      const alert = silenceAlert(decodeURIComponent(silenceMatch[1]), body.duration || '1h');
      if (!alert) return send(res, 404, { detail: '告警不存在' }), true;
      send(res, 200, { alert });
      return true;
    }

    if (method === 'GET' && route === '/reports') {
      send(res, 200, getReports());
      return true;
    }
    const reportMatch = route.match(/^\/reports\/([^/]+)$/);
    if (method === 'GET' && reportMatch) {
      const report = getReport(decodeURIComponent(reportMatch[1]));
      if (!report) return send(res, 404, { detail: '日报不存在' }), true;
      send(res, 200, report);
      return true;
    }

    if (method === 'GET' && route === '/tokens') {
      send(res, 200, getTokens(query));
      return true;
    }
    if (method === 'POST' && route === '/tokens') {
      const body = await readBody(req);
      const result = createToken(body);
      if (result.error) { send(res, 400, { detail: result.error }); return true; }
      send(res, 201, result);
      return true;
    }
    const tokenRevokeMatch = route.match(/^\/tokens\/([^/]+)\/revoke$/);
    if (method === 'POST' && tokenRevokeMatch) {
      const record = revokeToken(decodeURIComponent(tokenRevokeMatch[1]));
      if (!record) { send(res, 404, { detail: '令牌不存在' }); return true; }
      send(res, 200, { record });
      return true;
    }

    if (route === '/settings') {
      if (method === 'GET') { send(res, 200, getSettings()); return true; }
      if (method === 'PUT') {
        const body = await readBody(req);
        send(res, 200, saveSettings(body));
        return true;
      }
    }

    const testMatch = route.match(/^\/channels\/([^/]+)\/test$/);
    if (method === 'POST' && testMatch) {
      const result = testChannel(decodeURIComponent(testMatch[1]));
      if (!result) return send(res, 404, { detail: '渠道不存在' }), true;
      send(res, 200, result);
      return true;
    }

    send(res, 404, { detail: 'Mock API 未实现：' + method + ' ' + path });
    return true;
  } catch (err) {
    send(res, 500, { detail: String((err && err.message) || err) });
    return true;
  }
}

// Vite 插件中间件：把 /api/v1/* 与 /healthz 交给同一套 mock 处理
export function apiMiddleware() {
  return async (req, res, next) => {
    const handled = await handleApi(req, res);
    if (!handled && next) next();
  };
}
