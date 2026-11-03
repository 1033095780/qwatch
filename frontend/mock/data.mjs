// mock/data.mjs — qwatch mock 数据集：seeded 随机，时间相对进程启动时刻，全部为演示假数据。
// 同一进程内 alerts/settings 可变（确认/静默/保存），刷新页面可见效果；重启进程后重置。

import { randomBytes } from 'node:crypto';

const DAY = 86400000;
const HOUR = 3600000;
const MIN = 60000;
const NOW = Date.now();
const ISO = (ts) => new Date(Math.round(ts)).toISOString();
const shDate = (ts) => new Date(ts + 8 * HOUR).toISOString().slice(0, 10);
const shDayStartUTC = (ts) => {
  const d = new Date(ts + 8 * HOUR);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - 8 * HOUR;
};
const money = (n) => (Math.round(n * 100) / 100).toFixed(2);
const num = (n, d = 2) => String(Math.round(n * 10 ** d) / 10 ** d);
const round = (n, d = 2) => Math.round(n * 10 ** d) / 10 ** d;
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(20261103);
const rnd = (lo = 0, hi = 1) => lo + rng() * (hi - lo);
const pick = (arr) => arr[Math.floor(rng() * arr.length)];

// ---------- 标的 ----------
const INSTRUMENTS = [
  { code: 'rb2601', name: '螺纹钢2601', market: 'CN_FUT', venue: 'XSGE', currency: 'CNY', price: 3521.0, tick: 1, mult: 10, unit: '吨' },
  { code: 'au2601', name: '沪金2601', market: 'CN_FUT', venue: 'XSGE', currency: 'CNY', price: 628.5, tick: 0.02, mult: 1000, unit: '克' },
  { code: 'ag2601', name: '沪银2601', market: 'CN_FUT', venue: 'XSGE', currency: 'CNY', price: 7680.0, tick: 1, mult: 15, unit: '千克' },
  { code: 'cu2601', name: '沪铜2601', market: 'CN_FUT', venue: 'XSGE', currency: 'CNY', price: 74520.0, tick: 10, mult: 5, unit: '吨' },
  { code: 'IF2612', name: '沪深300股指2612', market: 'CN_FUT', venue: 'CFFEX', currency: 'CNY', price: 3985.6, tick: 0.2, mult: 300, unit: '点' },
  { code: 'T2612', name: '十年国债2612', market: 'CN_FUT', venue: 'CFFEX', currency: 'CNY', price: 108.235, tick: 0.005, mult: 10000, unit: '元' },
  { code: '600519', name: '贵州茅台', market: 'CN_A', venue: 'XSHG', currency: 'CNY', price: 1468.2, tick: 0.01, mult: 1, unit: '股' },
  { code: '510300', name: '沪深300ETF', market: 'CN_A', venue: 'XSHG', currency: 'CNY', price: 4.128, tick: 0.001, mult: 1, unit: '份' },
  { code: '000001', name: '平安银行', market: 'CN_A', venue: 'XSHG', currency: 'CNY', price: 11.36, tick: 0.01, mult: 1, unit: '股' },
];
const INST = Object.fromEntries(INSTRUMENTS.map((i) => [i.code, i]));

// ---------- 平台 / 策略类型 / 市场 ----------
const PLATFORM_LABELS = { ptrade: 'PTrade', qmt: 'QMT', myquant: '掘金', tqsdk: '天勤', custom: '自研' };
const STRATEGY_TYPE_LABELS = {
  trend: '趋势', arbitrage: '套利', intraday: '日内', grid: '网格',
  multifactor: '多因子', market_making: '做市', other: '其他',
};
const MARKET_LABELS = { CN_A: 'A股', CN_FUT: '期货', FX: '外汇', CRYPTO: '加密', US: '美股' };

// ---------- 账户 ----------
const ACCOUNT_DEFS = [
  { id: 'qmt:8888', name: 'QMT 主账户', venue: 'XSGE', market: 'CN_FUT', currency: 'CNY', initial: 700000 },
  { id: 'cffex:0666', name: '金融期货账户', venue: 'CFFEX', market: 'CN_FUT', currency: 'CNY', initial: 260000 },
  { id: 'xshg:6001', name: '华泰 A股账户', venue: 'XSHG', market: 'CN_A', currency: 'CNY', initial: 100000 },
];

// ---------- Runner ----------
const RUNNER_DEFS = [
  {
    id: 'cta_rb-prod', name: '螺纹钢趋势', strategy: 'me/cta_rb', version: '1.2.0',
    market: 'CN_FUT', venue: 'XSGE', platform: 'qmt', strategy_type: 'trend', tags: ['期货主账户', '夜盘', '低频'],
    status: 'running', accounts: ['qmt:8888'],
    equity: 462300.12, today_pnl: 6240.5, total_return_pct: 32.64, max_drawdown_pct: 8.02,
    uptime_24h: 99.82, last_heartbeat_ago: 4 * 1000, heartbeat_every: 10,
    sharpe: 1.86, win_rate_pct: 57.3, uptime_30d: 99.71, initial: 348000, seed: 11,
  },
  {
    id: 'cta_au-night', name: '沪金夜盘', strategy: 'me/cta_au', version: '0.9.4',
    market: 'CN_FUT', venue: 'XSGE', platform: 'qmt', strategy_type: 'trend', tags: ['夜盘', '贵金属', '期货主账户'],
    status: 'running', accounts: ['qmt:8888'],
    equity: 212845.3, today_pnl: -1120.3, total_return_pct: 18.2, max_drawdown_pct: 6.41,
    uptime_24h: 99.31, last_heartbeat_ago: 6 * 1000, heartbeat_every: 10,
    sharpe: 1.41, win_rate_pct: 52.8, uptime_30d: 99.12, initial: 180000, seed: 12,
  },
  {
    id: 'cta_if-intraday', name: '股指日内动量', strategy: 'me/cta_if', version: '2.0.1',
    market: 'CN_FUT', venue: 'CFFEX', platform: 'ptrade', strategy_type: 'intraday', tags: ['股指', '日内', '对冲'],
    status: 'running', accounts: ['cffex:0666'],
    equity: 318720.55, today_pnl: 4812.6, total_return_pct: 21.47, max_drawdown_pct: 5.87,
    uptime_24h: 99.97, last_heartbeat_ago: 3 * 1000, heartbeat_every: 10,
    sharpe: 2.04, win_rate_pct: 55.1, uptime_30d: 99.94, initial: 262000, seed: 13,
  },
  {
    id: 'cta_ag-swing', name: '白银波段', strategy: 'me/cta_ag', version: '1.1.2',
    market: 'CN_FUT', venue: 'XSGE', platform: 'myquant', strategy_type: 'trend', tags: ['贵金属', '波段', '夜盘'],
    status: 'degraded', accounts: ['qmt:8888'],
    equity: 187352.48, today_pnl: -3485.2, total_return_pct: 12.44, max_drawdown_pct: 9.35,
    uptime_24h: 96.42, last_heartbeat_ago: 42 * 1000, heartbeat_every: 10,
    sharpe: 0.92, win_rate_pct: 48.6, uptime_30d: 97.03, initial: 166000, seed: 14,
  },
  {
    id: 'cta_cu-breakout', name: '沪铜突破', strategy: 'me/cta_cu', version: '0.8.7',
    market: 'CN_FUT', venue: 'XSGE', platform: 'tqsdk', strategy_type: 'multifactor', tags: ['有色金属', '突破', '期货主账户'],
    status: 'offline', accounts: ['qmt:8888'],
    equity: 45120.6, today_pnl: 0, total_return_pct: -3.21, max_drawdown_pct: 13.88,
    uptime_24h: 41.35, last_heartbeat_ago: 42 * MIN, heartbeat_every: 10,
    sharpe: -0.24, win_rate_pct: 44.2, uptime_30d: 88.41, initial: 46600, seed: 15,
  },
  {
    id: 'stock_ma600519', name: '茅台均线轮动', strategy: 'me/stock_ma', version: '1.0.3',
    market: 'CN_A', venue: 'XSHG', platform: 'ptrade', strategy_type: 'trend', tags: ['A股', '低频', '蓝筹'],
    status: 'off_hours', accounts: ['xshg:6001'],
    equity: 71500.0, today_pnl: 1260.0, total_return_pct: 8.44, max_drawdown_pct: 4.62,
    uptime_24h: 98.9, last_heartbeat_ago: 9 * MIN, heartbeat_every: 10,
    sharpe: 1.12, win_rate_pct: 50.0, uptime_30d: 98.77, initial: 66000, seed: 16,
  },
  {
    id: 'stock_etf-grid', name: 'ETF 网格 · 低波', strategy: 'me/stock_grid', version: '0.6.0',
    market: 'CN_A', venue: 'XSHG', platform: 'custom', strategy_type: 'grid', tags: ['A股', 'ETF', '网格'],
    status: 'off_hours', accounts: ['xshg:6001'],
    equity: 34300.0, today_pnl: 522.4, total_return_pct: -2.61, max_drawdown_pct: 7.14,
    uptime_24h: 100, last_heartbeat_ago: 7 * HOUR, heartbeat_every: 10,
    sharpe: -0.31, win_rate_pct: 46.9, uptime_30d: 99.4, initial: 35200, seed: 17,
  },
];

const POSITION_DEFS = {
  'cta_rb-prod': [{ code: 'rb2601', qty: 24, avg: 3468.2 }],
  'cta_au-night': [{ code: 'au2601', qty: 6, avg: 632.4 }],
  'cta_if-intraday': [{ code: 'IF2612', qty: 2, avg: 3948.6 }, { code: 'T2612', qty: 5, avg: 108.12 }],
  'cta_ag-swing': [{ code: 'ag2601', qty: 30, avg: 7820.0 }],
  'cta_cu-breakout': [{ code: 'cu2601', qty: 8, avg: 75260.0 }],
  'stock_ma600519': [{ code: '600519', qty: 300, avg: 1432.5 }],
  'stock_etf-grid': [{ code: '510300', qty: 20000, avg: 4.052 }, { code: '000001', qty: 5000, avg: 11.2 }],
};

// ---------- 曲线生成 ----------
function buildDailyNav({ days = 180, seed = 1, drift = 0.0022, vol = 0.0078, ddStart = 90, ddDays = 13, targetNav = 1.33 }) {
  const r = mulberry32(seed * 7919 + 17);
  let nav = 1;
  const raw = [];
  for (let d = 0; d < days; d += 1) {
    let ret = drift + (r() * 2 - 1) * vol;
    if (d >= ddStart && d < ddStart + ddDays) ret = -0.0068 + (r() * 2 - 1) * 0.0018;
    nav *= 1 + ret;
    raw.push(nav);
  }
  const k = targetNav / raw[raw.length - 1];
  const baseTs = shDayStartUTC(NOW) + 15 * HOUR; // 15:00 Asia/Shanghai
  return raw.map((n, i) => {
    const daysAgo = days - 1 - i;
    const ts = i === days - 1 ? NOW : baseTs - daysAgo * DAY;
    const v = n * k;
    return { ts, nav: round(v, 4), value: v };
  });
}

function buildBenchmark(seed = 99, days = 180, target = 1.086) {
  const r = mulberry32(seed);
  let nav = 1;
  const raw = [];
  for (let d = 0; d < days; d += 1) {
    let ret = 0.00055 + (r() * 2 - 1) * 0.0105;
    if (d >= 92 && d < 106) ret = -0.0072 + (r() * 2 - 1) * 0.003;
    nav *= 1 + ret;
    raw.push(nav);
  }
  const k = target / raw[raw.length - 1];
  const baseTs = shDayStartUTC(NOW) + 15 * HOUR;
  return raw.map((n, i) => {
    const daysAgo = days - 1 - i;
    const ts = i === days - 1 ? NOW : baseTs - daysAgo * DAY;
    return { ts, value: round(n * k * 1000000, 2) };
  });
}

function synthRange(series, range, seed) {
  const RANGES = {
    '1d': { span: DAY, points: 78, step: 5 * MIN },
    '1w': { span: 7 * DAY, points: 84, step: 2 * HOUR },
  };
  if (RANGES[range]) {
    const { span, points, step } = RANGES[range];
    const end = series[series.length - 1];
    let start;
    if (range === '1d') {
      start = series[Math.max(0, series.length - 2)];
    } else {
      const cutoff = end.ts - span;
      start = [...series].reverse().find((p) => p.ts <= cutoff) || series[Math.max(0, series.length - 8)];
    }
    const r = mulberry32(seed + range.length * 131 + points);
    const ratio = end.value / start.value;
    const out = [];
    for (let i = 0; i < points; i += 1) {
      const t = i / (points - 1);
      const trend = Math.pow(ratio, t);
      const wobble = 1 + (r() * 2 - 1) * 0.0022 * (1 - Math.abs(t - 0.5));
      const value = i === points - 1 ? end.value : start.value * trend * wobble;
      out.push({
        ts: Math.round(end.ts - (points - 1 - i) * step),
        value,
        nav: i === points - 1 ? end.nav : round(value / (end.value / end.nav), 4),
      });
    }
    return out;
  }
  if (range === '1m') return series.slice(-21);
  if (range === '3m') return series.slice(-63);
  return series;
}

function rangeOf(query) {
  const r = String(query || 'all');
  return ['1d', '1w', '1m', '3m', '1y', 'all'].includes(r) ? r : 'all';
}

function withRange(series, range, seed) {
  const out = synthRange(series, range, seed);
  if (out.length && out[0].nav === undefined) {
    // 用区间起点归一化生成 nav，便于回撤计算
    const base = out[0].value;
    out.forEach((p) => { p.nav = round(p.value / base, 4); });
  }
  return out;
}

function drawdownOf(points) {
  let peak = -Infinity;
  return points.map((p) => {
    peak = Math.max(peak, p.nav);
    return { ts: p.ts, value: round((p.nav / peak - 1) * 100, 2) };
  });
}

const sparkOf = (points) => points.slice(-24).map((p) => round(p.value, 2));

// ---------- 建造数据 ----------
const accounts = ACCOUNT_DEFS.map((a, idx) => {
  const runners = RUNNER_DEFS.filter((r) => r.accounts.includes(a.id));
  const equity = round(runners.reduce((s, r) => s + r.equity, 0), 2);
  const todayPnl = round(runners.reduce((s, r) => s + r.today_pnl, 0), 2);
  const curve = buildDailyNav({
    seed: a.initial + idx, drift: 0.0019, vol: 0.0052,
    targetNav: equity / a.initial, ddStart: 88 + idx * 3, ddDays: 12,
  }).map((p, i, arr) => ({ ts: p.ts, nav: p.nav, value: round((p.value / arr[arr.length - 1].value) * equity, 2) }));
  return {
    id: a.id, name: a.name, venue: a.venue, market: a.market, currency: a.currency,
    initial_equity: money(a.initial),
    equity: money(equity),
    today_pnl: money(todayPnl),
    today_pnl_pct: num((todayPnl / (equity - todayPnl)) * 100),
    positions_count: runners.filter((r) => r.status !== 'offline').reduce((s, r) => s + (POSITION_DEFS[r.id] || []).length, 0),
    sparkline: sparkOf(curve),
    curve,
    cash_flows: [
      { id: 'cf_' + idx + '1', ts: ISO(NOW - (170 - idx * 6) * DAY), amount: money(a.initial * 0.8), currency: 'CNY', kind: 'deposit', note: '初始入金' },
      { id: 'cf_' + idx + '2', ts: ISO(NOW - (120 - idx * 4) * DAY), amount: money(a.initial * 0.2), currency: 'CNY', kind: 'deposit', note: '追加保证金' },
      { id: 'cf_' + idx + '3', ts: ISO(NOW - (62 - idx * 3) * DAY), amount: money(a.initial * 0.06), currency: 'CNY', kind: 'withdraw', note: '利润提取' },
    ],
    runner_ids: runners.map((r) => r.id),
  };
});
const totalEquity = round(accounts.reduce((s, a) => s + Number(a.equity), 0), 2);
const totalTodayPnl = round(accounts.reduce((s, a) => s + Number(a.today_pnl), 0), 2);

const portfolioCurveFull = buildDailyNav({
  days: 180, seed: 4242, drift: 0.00235, vol: 0.0071, ddStart: 90, ddDays: 13,
  targetNav: totalEquity / 1000000,
}).map((p, i, arr) => ({
  ts: p.ts,
  nav: p.nav,
  value: round((p.value / arr[arr.length - 1].value) * totalEquity, 2),
}));
const benchmarkFull = buildBenchmark(777).map((p, i, arr) => ({
  ...p,
  value: round((p.value / (arr[arr.length - 1].value / 1.086)) * 1000000, 2),
}));

// 每个 runner 的净值曲线（nav 归一到 1 起点，value 归到当前权益）
const runnerCurves = {};
const runnerDetailsBase = {};
RUNNER_DEFS.forEach((def) => {
  const targetNav = 1 + def.total_return_pct / 100;
  const curve = buildDailyNav({
    days: 180, seed: def.seed, drift: def.total_return_pct > 0 ? 0.0024 : -0.0006,
    vol: 0.0085, ddStart: 88 + (def.seed % 5) * 2, ddDays: 12,
    targetNav: Math.max(0.7, targetNav),
  }).map((p, i, arr) => ({
    ts: p.ts, nav: p.nav,
    value: round((p.value / arr[arr.length - 1].value) * def.equity, 2),
  }));
  runnerCurves[def.id] = curve;

  const positions = (POSITION_DEFS[def.id] || []).map((p) => {
    const inst = INST[p.code];
    const last = inst.price;
    const mv = round(p.qty * last * inst.mult, 2);
    const pnl = round((last - p.avg) * p.qty * inst.mult, 2);
    return {
      instrument: inst.code, instrument_name: inst.name, market: inst.market, venue: inst.venue,
      qty: String(p.qty), avg_price: num(p.avg, inst.tick < 0.01 ? 3 : 2),
      last_price: num(last, inst.tick < 0.01 ? 3 : 2),
      market_value: money(mv), pnl: money(pnl), pnl_pct: num(((last / p.avg) - 1) * 100),
      currency: inst.currency,
    };
  });

  // 24h × 30min 心跳条：ok / miss / off
  const isStock = def.market === 'CN_A';
  const segments = 48;
  const timeline = [];
  for (let i = segments - 1; i >= 0; i -= 1) {
    const ts = NOW - i * 30 * MIN;
    const h = new Date(ts + 8 * HOUR).getUTCHours();
    const off = isStock && !((h >= 9 && h < 12) || (h >= 13 && h < 15));
    let status = off ? 'off' : 'ok';
    if (def.status === 'degraded' && !off && i < 4) status = pick(['miss', 'miss', 'ok']);
    if (def.status === 'offline' && !off && ts > NOW - 50 * MIN) status = 'miss';
    if (def.status === 'off_hours' && !isStock && i > 40) status = 'ok';
    timeline.push({ ts: ISO(ts), status });
  }
  const outages = def.status === 'offline'
    ? [{ start: ISO(NOW - 46 * MIN), end: null, duration_s: 46 * 60 }, { start: ISO(NOW - 2 * DAY - 3 * HOUR), end: ISO(NOW - 2 * DAY - 2 * HOUR), duration_s: 3600 }]
    : def.status === 'degraded'
      ? [{ start: ISO(NOW - 26 * MIN), end: ISO(NOW - 24 * MIN), duration_s: 120 }, { start: ISO(NOW - 9 * HOUR), end: ISO(NOW - 9 * HOUR - 4 * MIN), duration_s: 240 }]
      : [{ start: ISO(NOW - (def.seed % 4 + 1) * DAY - 2 * HOUR), end: ISO(NOW - (def.seed % 4 + 1) * DAY - 2 * HOUR + 78 * 1000), duration_s: 78 }];

  runnerDetailsBase[def.id] = {
    metrics: {
      total_return_pct: num(def.total_return_pct),
      today_pnl: money(def.today_pnl),
      max_drawdown_pct: num(def.max_drawdown_pct),
      sharpe: num(def.sharpe, 2),
      win_rate_pct: num(def.win_rate_pct, 1),
      uptime_30d: num(def.uptime_30d, 2),
    },
    positions,
    heartbeat_timeline: timeline,
    outages,
  };
});

const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a]));
const runnerMap = Object.fromEntries(RUNNER_DEFS.map((r) => [r.id, r]));

// ---------- 成交（约 200 条，近 3 个交易日） ----------
const FILL_PLAN = [
  { runner: 'cta_rb-prod', instruments: ['rb2601'], weight: 34 },
  { runner: 'cta_au-night', instruments: ['au2601'], weight: 18 },
  { runner: 'cta_if-intraday', instruments: ['IF2612', 'T2612'], weight: 36 },
  { runner: 'cta_ag-swing', instruments: ['ag2601'], weight: 24 },
  { runner: 'cta_cu-breakout', instruments: ['cu2601'], weight: 10 },
  { runner: 'stock_ma600519', instruments: ['600519'], weight: 16 },
  { runner: 'stock_etf-grid', instruments: ['510300', '000001'], weight: 22 },
];
const TOTAL_FILLS = 200;
const fills = [];
const weightedPlan = FILL_PLAN.flatMap((p) => Array(p.weight).fill(p));
for (let i = 0; i < TOTAL_FILLS; i += 1) {
  const plan = pick(weightedPlan);
  const def = runnerMap[plan.runner];
  const code = pick(plan.instruments);
  const inst = INST[code];
  const dayAgo = Math.floor(rnd(0, 3));
  const shStart = shDayStartUTC(NOW - dayAgo * DAY);
  const isNight = inst.market === 'CN_FUT' && inst.venue === 'XSGE' && rng() > 0.55;
  let sessionStart = shStart + (isNight ? 13 * HOUR : 9 * HOUR + 15 * MIN);
  let sessionLen = isNight ? 2 * HOUR : inst.market === 'CN_A' ? 5.5 * HOUR : 5 * HOUR;
  let ts = sessionStart + rnd(0, sessionLen);
  if (ts > NOW) ts = NOW - rnd(1, 90) * MIN;
  const drift = (rng() * 2 - 1) * 0.011;
  const price = round(inst.price * (1 + drift), inst.tick >= 1 ? 1 : inst.tick >= 0.1 ? 2 : inst.tick >= 0.01 ? 2 : 3);
  const qty = Math.max(1, Math.round((rnd(1, 34) * (inst.mult >= 100 ? 0.25 : 1)) * (inst.market === 'CN_A' ? 10 : 1)));
  const amount = round(qty * price * inst.mult, 2);
  const feeRate = inst.market === 'CN_A' ? 0.00025 : 0.00009;
  const fee = round(Math.max(1, amount * feeRate), 2);
  fills.push({
    id: 'fill_' + String(i + 1).padStart(5, '0'),
    ts: ISO(ts),
    runner_id: def.id,
    runner_name: def.name,
    account_id: def.accounts[0],
    account_name: accountMap[def.accounts[0]].name,
    instrument: inst.code,
    instrument_name: inst.name,
    side: rng() > 0.5 ? 'buy' : 'sell',
    position_effect: rng() > 0.42 ? 'open' : 'close',
    qty: String(qty),
    price: num(price, inst.tick < 0.01 ? 3 : 2),
    amount: money(amount),
    fee: money(fee),
    currency: inst.currency,
    status: rng() > 0.06 ? 'filled' : 'partial',
  });
}
fills.sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts));

// ---------- 交易信号（由 fills 派生：信号是策略的委托意图，status 表示执行状态） ----------
// status：每 20 条里 18 filled（90%）、1 pending（5%）、1 ignored（5%）；action 由 position_effect 推导。
const signals = fills.map((fill, i) => {
  const def = runnerMap[fill.runner_id];
  const inst = INST[fill.instrument];
  const bucket = i % 20;
  const status = bucket === 0 ? 'pending' : bucket === 1 ? 'ignored' : 'filled';
  const action = fill.position_effect === 'open'
    ? (i % 10 < 3 ? 'add' : 'open')
    : (i % 10 < 3 ? 'reduce' : 'close');
  return {
    id: 'sig_' + fill.id.slice(5),
    ts: fill.ts,
    runner_id: fill.runner_id,
    runner_name: fill.runner_name,
    platform: def.platform,
    platform_label: PLATFORM_LABELS[def.platform],
    strategy_type: def.strategy_type,
    strategy_type_label: STRATEGY_TYPE_LABELS[def.strategy_type],
    market: inst.market,
    market_label: MARKET_LABELS[inst.market],
    account_id: fill.account_id,
    account_name: fill.account_name,
    instrument: fill.instrument,
    instrument_name: fill.instrument_name,
    side: fill.side,
    action,
    price: fill.price,
    qty: fill.qty,
    amount: fill.amount,
    status,
    tags: [...def.tags],
  };
});

// ---------- 告警 ----------
const ALERT_DEFS = [
  {
    id: 'alert_0001', severity: 'P0', status: 'firing', rule: 'heartbeat_lost',
    runner: 'cta_cu-breakout', offset: -42 * MIN,
    summary: '策略心跳丢失：cta_cu-breakout 已 42 分钟未上报（心跳间隔 10s）',
    labels: { host: 'trade-pc', pid: '12884', market: 'CN_FUT' },
  },
  {
    id: 'alert_0002', severity: 'P1', status: 'firing', rule: 'drawdown_breach',
    runner: 'cta_ag-swing', offset: -72 * MIN,
    summary: '回撤超阈值：cta_ag-swing 当前回撤 -9.35%，阈值 -8.00%',
    labels: { window: '30d', account: 'qmt:8888', market: 'CN_FUT' },
  },
  {
    id: 'alert_0003', severity: 'P2', status: 'acknowledged', rule: 'fill_burst',
    runner: 'cta_rb-prod', offset: -140 * MIN,
    summary: '成交聚合：5s 窗口内成交 6 笔 rb2601，合计 120 手',
    labels: { instrument: 'rb2601', account: 'qmt:8888' },
  },
  {
    id: 'alert_0004', severity: 'P0', status: 'resolved', rule: 'heartbeat_lost',
    runner: 'cta_au-night', offset: -26 * HOUR, duration: 192,
    summary: '已恢复：cta_au-night 心跳中断 3m12s 后恢复',
    labels: { host: 'trade-pc', pid: '17321', market: 'CN_FUT' },
    acked: true,
  },
  {
    id: 'alert_0005', severity: 'P1', status: 'resolved', rule: 'market_data_stale',
    runner: 'cta_if-intraday', offset: -31 * HOUR, duration: 65,
    summary: '已恢复：IF2612 最新 tick 延迟 18s，行情连接重建完成',
    labels: { instrument: 'IF2612', feed: 'CFFEX-L2' },
  },
  {
    id: 'alert_0006', severity: 'P1', status: 'resolved', rule: 'runner_stalled',
    runner: 'cta_ag-swing', offset: -2 * DAY - 4 * HOUR, duration: 420,
    summary: '已恢复：cta_ag-swing loop_count 连续 3 次未增长，进程重启后恢复',
    labels: { host: 'trade-pc', pid: '12884' },
  },
  {
    id: 'alert_0007', severity: 'P2', status: 'acknowledged', rule: 'daily_report',
    runner: 'stock_ma600519', offset: -20 * HOUR,
    summary: '日报已生成：2026-11-02 收益 +1.24%，成交 6 笔，无异常',
    labels: { date: shDate(NOW - DAY), channel: 'dingtalk' },
    acked: true,
  },
  {
    id: 'alert_0008', severity: 'P2', status: 'resolved', rule: 'risk_limit',
    runner: 'cta_rb-prod', offset: -3 * DAY - 2 * HOUR, duration: 60,
    summary: '已恢复：日盈利达到 +1.20%，触发移动止盈，仓位降至 50%',
    labels: { account: 'qmt:8888', instrument: 'rb2601' },
    acked: true,
  },
];
const nowIso = ISO(NOW);
const alerts = ALERT_DEFS.map((a, i) => {
  const startsAt = ISO(NOW + a.offset);
  const endsAt = a.status === 'resolved' ? ISO(NOW + a.offset + (a.duration || 300) * 1000) : undefined;
  return {
    id: a.id,
    fingerprint: 'fp_' + (0xa1b2c3 + i * 977).toString(16),
    rule: a.rule,
    severity: a.severity,
    status: a.status,
    runner_id: a.runner,
    runner_name: runnerMap[a.runner].name,
    summary: a.summary,
    starts_at: startsAt,
    ends_at: endsAt,
    acked_at: a.acked || a.status === 'acknowledged' ? ISO(NOW + a.offset + 90 * 1000) : undefined,
    labels: a.labels,
    updated_at: endsAt || nowIso,
  };
});

// ---------- 日报 ----------
const reportStrategies = (pnlFactor) => RUNNER_DEFS.map((def) => {
  const pnl = round(def.today_pnl * pnlFactor + (rnd(-400, 400)), 2);
  return {
    runner_id: def.id,
    name: def.name,
    pnl: money(pnl),
    pct: num((pnl / def.equity) * 100),
    trades: Math.round(rnd(1, 14)),
    drawdown: num(Math.max(0, Math.min(def.max_drawdown_pct, Math.abs(pnl) / def.equity * 100 + rnd(0, 2))), 2),
  };
});
const reports = [];
// 最近 7 个交易日（跳过周六/周日）
const reportDates = [];
for (let offset = 0; reportDates.length < 7; offset += 1) {
  const date = shDate(NOW - offset * DAY);
  const weekday = new Date(date + 'T00:00:00+08:00').getDay();
  if (weekday !== 0 && weekday !== 6) reportDates.push({ date, offset });
}
for (let i = 0; i < reportDates.length; i += 1) {
  const { date } = reportDates[i];
  const factor = 1 - i * 0.11;
  const dayPnl = round(totalTodayPnl * factor + rnd(-2600, 2600), 2);
  const equity = round(totalEquity - i * (totalTodayPnl * 0.82) + rnd(-800, 800), 2);
  reports.push({
    date,
    total_equity: money(equity),
    today_pnl: money(dayPnl),
    today_pnl_pct: num((dayPnl / (equity - dayPnl)) * 100),
    trades: Math.round(rnd(18, 42)),
    alerts: Math.round(rnd(0, 3)),
    status: i === 2 ? 'warn' : 'ok',
    strategies: reportStrategies(factor),
  });
}

// ---------- 设置 ----------
// 渠道完整 webhook/secret 只存内存；GET /settings 返回掩码，PUT 支持只传要改的字段。
const CHANNEL_SECRETS = {
  'dingtalk-main': {
    webhook: 'https://oapi.dingtalk.com/robot/send?access_token=8f3a2c7d91b04e6fa5c2d8e71b3a9f46',
    secret: 'SECa1b2c3d4e5f6789012345678abcd9c1e',
  },
  'dingtalk-backup': {
    webhook: 'https://oapi.dingtalk.com/robot/send?access_token=7b81d2e4a6c04f1e9b3d5a7c2e8f0d17',
    secret: 'SEC9f8e7d6c5b4a39281706f5e4d3c2d40',
  },
};
const maskWebhook = (url) => String(url || '').replace(/access_token=([^&]+)/, (_, token) => 'access_token=****' + token.slice(-4));
const maskSecret = (secret) => {
  const s = String(secret || '');
  return s.length >= 8 ? 'SEC****' + s.slice(-4) : '未配置';
};
function channelView(channel) {
  const secrets = CHANNEL_SECRETS[channel.id] || {};
  return {
    ...channel,
    webhook_masked: maskWebhook(secrets.webhook),
    secret_masked: maskSecret(secrets.secret),
    at_mobiles: [...channel.at_mobiles],
  };
}
const settings = {
  user: { name: 'Trader', role: 'owner', timezone: 'Asia/Shanghai' },
  up_color_scheme: 'red_up',
  channels: [
    {
      id: 'dingtalk-main', name: '钉钉 · 主机器人', type: 'dingtalk_robot', enabled: true,
      at_mobiles: ['13800138000'], rate_limit_per_min: 15,
      last_test_at: ISO(NOW - 3 * HOUR), last_test_ok: true,
    },
    {
      id: 'dingtalk-backup', name: '钉钉 · 备用机器人', type: 'dingtalk_robot', enabled: false,
      at_mobiles: [], rate_limit_per_min: 15,
      last_test_at: null, last_test_ok: null,
    },
  ],
  calendars: [
    { id: 'cn_a', name: 'A股', timezone: 'Asia/Shanghai', sessions: ['09:15-11:30', '13:00-15:00'], night: false, holidays: 'cn_a' },
    { id: 'cn_fut_2300', name: '商品期货 · 23:00 组', timezone: 'Asia/Shanghai', sessions: ['09:00-10:15', '10:30-11:30', '13:30-15:00', '21:00-23:00'], night: true, holidays: 'cn_fut' },
    { id: 'cn_fut_0100', name: '商品期货 · 01:00 组', timezone: 'Asia/Shanghai', sessions: ['09:00-10:15', '10:30-11:30', '13:30-15:00', '21:00-01:00'], night: true, holidays: 'cn_fut' },
    { id: 'cn_fut_0230', name: '商品期货 · 02:30 组', timezone: 'Asia/Shanghai', sessions: ['09:00-10:15', '10:30-11:30', '13:30-15:00', '21:00-02:30'], night: true, holidays: 'cn_fut' },
    { id: 'cffex', name: '金融期货 CFFEX', timezone: 'Asia/Shanghai', sessions: ['09:30-11:30', '13:00-15:00'], night: false, holidays: 'cn_fut' },
  ],
  security: {
    session_hours: 12,
    login_rate_limit: '5 次/分钟/IP',
    totp_enabled: false,
    last_password_change: ISO(NOW - 45 * DAY),
  },
  about: { version: '0.1.0', build: '2026.11.03', mode: '本地部署', license: 'Apache-2.0' },
};

// ---------- 查询函数 ----------
function runnerView(def) {
  return {
    id: def.id,
    name: def.name,
    strategy: def.strategy,
    version: def.version,
    market: def.market,
    venue: def.venue,
    platform: def.platform,
    platform_label: PLATFORM_LABELS[def.platform],
    strategy_type: def.strategy_type,
    strategy_type_label: STRATEGY_TYPE_LABELS[def.strategy_type],
    tags: def.tags,
    status: def.status,
    accounts: def.accounts.map((id) => ({ id, name: accountMap[id].name, venue: accountMap[id].venue })),
    equity: money(def.equity),
    today_pnl: money(def.today_pnl),
    today_pnl_pct: num((def.today_pnl / (def.equity - def.today_pnl)) * 100),
    total_return_pct: num(def.total_return_pct),
    max_drawdown_pct: num(def.max_drawdown_pct),
    uptime_24h: num(def.uptime_24h, 2),
    last_heartbeat: ISO(Date.now() - def.last_heartbeat_ago),
    sparkline: sparkOf(runnerCurves[def.id]),
    position_count: (POSITION_DEFS[def.id] || []).length,
  };
}

export function getOverview(query) {
  const range = rangeOf(query.range);
  const equityCurve = withRange(portfolioCurveFull, range, 501);
  const benchmark = withRange(benchmarkFull, range, 502);
  return {
    as_of: ISO(Date.now()),
    total_equity: money(totalEquity),
    today_pnl: money(totalTodayPnl),
    today_pnl_pct: num((totalTodayPnl / (totalEquity - totalTodayPnl)) * 100),
    running: RUNNER_DEFS.filter((r) => r.status === 'running').length,
    total: RUNNER_DEFS.length,
    active_alerts: alerts.filter((a) => a.status !== 'resolved').length,
    range,
    equity_curve: equityCurve.map((p) => ({ ts: ISO(p.ts), nav: p.nav, value: money(p.value) })),
    benchmark: benchmark.map((p) => ({ ts: ISO(p.ts), value: money(p.value) })),
    runners: RUNNER_DEFS.map(runnerView),
    alerts: alerts.filter((a) => a.status !== 'resolved').slice(0, 4),
    recent_signals: signals.slice(0, 8),
  };
}

export function getRunners(query) {
  let items = RUNNER_DEFS.map(runnerView);
  if (query.status) items = items.filter((r) => r.status === query.status);
  if (query.market) items = items.filter((r) => r.market === query.market);
  if (query.q) {
    const q = String(query.q).toLowerCase();
    items = items.filter((r) => (r.name + r.strategy + r.id).toLowerCase().includes(q));
  }
  return { items, total: items.length };
}

export function getRunnerDetail(id, query) {
  const def = runnerMap[id];
  if (!def) return null;
  const base = runnerDetailsBase[id];
  const range = rangeOf(query.range);
  const equity = withRange(runnerCurves[id], range, def.seed + 33).map((p) => ({ ts: ISO(p.ts), nav: p.nav, value: money(p.value) }));
  const drawdown = drawdownOf(withRange(runnerCurves[id], range, def.seed + 33)).map((p) => ({ ts: ISO(p.ts), value: p.value }));
  return {
    runner: runnerView(def),
    range,
    metrics: base.metrics,
    equity,
    drawdown,
    heartbeat_timeline: base.heartbeat_timeline,
    outages: base.outages,
    signals: signals.filter((s) => s.runner_id === id).slice(0, 40),
    positions: base.positions,
    alerts: alerts.filter((a) => a.runner_id === id),
    config: {
      strategy: def.strategy,
      version: def.version,
      host: 'trade-pc',
      pid: 12884 + def.seed,
      calendar_id: def.market === 'CN_A' ? 'cn_a' : def.venue === 'CFFEX' ? 'cffex' : 'cn_fut_0230',
      heartbeat_interval_s: def.heartbeat_every,
      soft_timeout_s: 30,
      hard_timeout_s: 60,
      started_at: ISO(NOW - (40 + def.seed) * DAY),
      last_seq: 10231 + def.seed * 131,
      env: def.market === 'CN_A' ? 'prod' : 'prod',
      accounts: def.accounts,
    },
  };
}

export function getAccounts() {
  return {
    items: accounts.map((a) => ({
      id: a.id, name: a.name, venue: a.venue, market: a.market, currency: a.currency,
      equity: a.equity, today_pnl: a.today_pnl, today_pnl_pct: a.today_pnl_pct,
      positions_count: a.positions_count, sparkline: a.sparkline, runner_ids: a.runner_ids,
    })),
  };
}

export function getAccountDetail(id) {
  const a = accountMap[id];
  if (!a) return null;
  const accountFills = fills.filter((f) => f.account_id === id);
  return {
    account: {
      id: a.id, name: a.name, venue: a.venue, market: a.market, currency: a.currency,
      equity: a.equity, today_pnl: a.today_pnl, today_pnl_pct: a.today_pnl_pct,
      positions_count: a.positions_count, sparkline: a.sparkline,
      initial_equity: a.initial_equity,
    },
    equity: a.curve.map((p) => ({ ts: ISO(p.ts), nav: p.nav, value: money(p.value) })),
    positions: RUNNER_DEFS.filter((r) => r.accounts.includes(id)).flatMap((r) =>
      (POSITION_DEFS[r.id] || []).map((p) => {
        const inst = INST[p.code];
        const mv = round(p.qty * inst.price * inst.mult, 2);
        const pnl = round((inst.price - p.avg) * p.qty * inst.mult, 2);
        return {
          account_id: id, instrument: inst.code, instrument_name: inst.name, market: inst.market,
          qty: String(p.qty), avg_price: num(p.avg, inst.tick < 0.01 ? 3 : 2),
          last_price: num(inst.price, inst.tick < 0.01 ? 3 : 2), market_value: money(mv),
          pnl: money(pnl), pnl_pct: num((inst.price / p.avg - 1) * 100), currency: inst.currency,
        };
      })),
    cash_flows: a.cash_flows,
    signals: signals.filter((s) => s.account_id === id && shDate(Date.parse(s.ts)) === shDate(NOW)).slice(0, 30),
    total_return_pct: num(((Number(a.equity) / Number(a.initial_equity)) - 1) * 100),
  };
}

export function getSignals(query) {
  let items = signals;
  if (query.runner_id) items = items.filter((s) => s.runner_id === query.runner_id);
  if (query.account_id) items = items.filter((s) => s.account_id === query.account_id);
  if (query.platform) items = items.filter((s) => s.platform === query.platform);
  if (query.market) items = items.filter((s) => s.market === query.market);
  if (query.strategy_type) items = items.filter((s) => s.strategy_type === query.strategy_type);
  if (query.side) items = items.filter((s) => s.side === query.side);
  if (query.status) items = items.filter((s) => s.status === query.status);
  if (query.instrument) items = items.filter((s) => s.instrument.toLowerCase().includes(String(query.instrument).toLowerCase()));
  if (query.tag) items = items.filter((s) => s.tags.includes(query.tag));
  if (query.from) items = items.filter((s) => Date.parse(s.ts) >= Date.parse(query.from));
  if (query.to) items = items.filter((s) => Date.parse(s.ts) <= Date.parse(query.to));
  const total = items.length;
  const sumAmount = items.reduce((sum, s) => sum + Number(s.amount), 0);
  const limit = clamp(parseInt(query.limit, 10) || 20, 1, 500);
  const offset = clamp(parseInt(query.cursor, 10) || 0, 0, total);
  return {
    items: items.slice(offset, offset + limit),
    total,
    sum_amount: money(sumAmount),
    limit,
    next_cursor: offset + limit < total ? String(offset + limit) : null,
  };
}

export function getPositions(query) {
  let items = RUNNER_DEFS.flatMap((def) =>
    (POSITION_DEFS[def.id] || []).map((p) => {
      const inst = INST[p.code];
      const mv = round(p.qty * inst.price * inst.mult, 2);
      const pnl = round((inst.price - p.avg) * p.qty * inst.mult, 2);
      return {
        account_id: def.accounts[0], runner_id: def.id, runner_name: def.name,
        instrument: inst.code, instrument_name: inst.name, market: inst.market, venue: inst.venue,
        qty: String(p.qty), avg_price: num(p.avg, inst.tick < 0.01 ? 3 : 2),
        last_price: num(inst.price, inst.tick < 0.01 ? 3 : 2),
        market_value: money(mv), pnl: money(pnl), pnl_pct: num((inst.price / p.avg - 1) * 100),
        currency: inst.currency,
      };
    }));
  if (query.account_id) items = items.filter((p) => p.account_id === query.account_id);
  return { items };
}

export function getAlerts(query) {
  const status = query.status || 'active';
  const items = status === 'history'
    ? alerts.filter((a) => a.status === 'resolved')
    : alerts.filter((a) => a.status !== 'resolved');
  return {
    items: items.map((a) => ({ ...a, runner_name: runnerMap[a.runner_id].name })),
    active_count: alerts.filter((a) => a.status !== 'resolved').length,
    firing_count: alerts.filter((a) => a.status === 'firing').length,
  };
}

export function acknowledgeAlert(id) {
  const a = alerts.find((x) => x.id === id);
  if (!a) return null;
  a.status = 'acknowledged';
  a.acked_at = ISO(Date.now());
  a.updated_at = a.acked_at;
  return a;
}

export function silenceAlert(id, duration) {
  const a = alerts.find((x) => x.id === id);
  if (!a) return null;
  a.status = 'acknowledged';
  a.acked_at = ISO(Date.now());
  a.updated_at = a.acked_at;
  a.labels = { ...a.labels, silenced_until: ISO(Date.now() + (duration === '4h' ? 4 * HOUR : duration === '24h' ? 24 * HOUR : HOUR)) };
  return a;
}

export function getReports() {
  return { items: reports.map((r) => ({ date: r.date, total_equity: r.total_equity, today_pnl: r.today_pnl, today_pnl_pct: r.today_pnl_pct, trades: r.trades, alerts: r.alerts, status: r.status })) };
}

export function getReport(date) {
  return reports.find((r) => r.date === date) || null;
}

export function getSettings() {
  return JSON.parse(JSON.stringify({ ...settings, channels: settings.channels.map(channelView) }));
}

export function saveSettings(patch) {
  if (patch && typeof patch === 'object') {
    if (patch.up_color_scheme === 'red_up' || patch.up_color_scheme === 'green_up') settings.up_color_scheme = patch.up_color_scheme;
    if (typeof patch.security === 'object' && patch.security) {
      settings.security = { ...settings.security, ...patch.security };
    }
    if (Array.isArray(patch.channels)) {
      patch.channels.forEach((next) => {
        const channel = settings.channels.find((c) => c.id === next.id);
        if (!channel) return;
        if (typeof next.enabled === 'boolean') channel.enabled = next.enabled;
        if (Array.isArray(next.at_mobiles)) {
          channel.at_mobiles = next.at_mobiles.map((m) => String(m).trim()).filter(Boolean).slice(0, 8);
        }
        const secrets = CHANNEL_SECRETS[channel.id] || (CHANNEL_SECRETS[channel.id] = {});
        if (typeof next.webhook === 'string' && next.webhook.trim()) secrets.webhook = next.webhook.trim();
        if (typeof next.secret === 'string' && next.secret.trim()) secrets.secret = next.secret.trim();
      });
    }
  }
  return getSettings();
}

// ---------- 策略接入令牌（完整 token 只在创建响应中出现一次） ----------
const PLATFORM_VALUES = Object.keys(PLATFORM_LABELS);
const STRATEGY_TYPE_VALUES = Object.keys(STRATEGY_TYPE_LABELS);
const TOKEN_MARKET_VALUES = Object.keys(MARKET_LABELS);
const maskToken = (token) => 'qw_' + token.slice(0, 4) + '…' + token.slice(-4);

function tokenView(record) {
  return {
    ...record,
    platform_label: PLATFORM_LABELS[record.platform] || '',
    strategy_type_label: STRATEGY_TYPE_LABELS[record.strategy_type] || '',
    markets: [...record.markets],
    tags: [...record.tags],
  };
}

const tokens = [
  {
    id: 'tok_8f3a2b7d', name: 'cta_rb 生产接入', platform: 'qmt', markets: ['CN_FUT'], strategy_type: 'trend',
    tags: ['期货主账户', '夜盘'], note: '主力策略接入令牌，轮换周期 90 天',
    token_prefix: 'qw_8f3a…0c21', status: 'active',
    created_at: ISO(NOW - 88 * DAY), last_used_at: ISO(NOW - 4 * 1000), request_count: 128430,
  },
  {
    id: 'tok_4c81de09', name: 'cta_if 仿真接入', platform: 'ptrade', markets: ['CN_FUT'], strategy_type: 'intraday',
    tags: ['股指', '日内'], note: '仿真环境令牌，已按计划轮换',
    token_prefix: 'qw_4c81…e09b', status: 'revoked',
    created_at: ISO(NOW - 61 * DAY), last_used_at: ISO(NOW - 12 * DAY), request_count: 2150,
  },
];

export function getTokens() {
  return { items: tokens.map(tokenView), total: tokens.length };
}

export function createToken(body) {
  const payload = body && typeof body === 'object' ? body : {};
  const name = String(payload.name || '').trim();
  if (!name) return { error: '策略名称必填' };
  const token = randomBytes(32).toString('hex');
  const record = {
    id: 'tok_' + randomBytes(4).toString('hex'),
    name,
    platform: PLATFORM_VALUES.includes(payload.platform) ? payload.platform : '',
    markets: Array.isArray(payload.markets) ? payload.markets.filter((m) => TOKEN_MARKET_VALUES.includes(m)) : [],
    strategy_type: STRATEGY_TYPE_VALUES.includes(payload.strategy_type) ? payload.strategy_type : '',
    tags: Array.isArray(payload.tags) ? payload.tags.map((t) => String(t).trim()).filter(Boolean).slice(0, 8) : [],
    note: String(payload.note || '').trim(),
    token_prefix: maskToken(token),
    status: 'active',
    created_at: ISO(Date.now()),
    last_used_at: null,
    request_count: 0,
  };
  tokens.unshift(record);
  return { token, record: tokenView(record) };
}

export function revokeToken(id) {
  const record = tokens.find((t) => t.id === id);
  if (!record) return null;
  record.status = 'revoked';
  return tokenView(record);
}

export function testChannel(id) {
  const ch = settings.channels.find((c) => c.id === id);
  if (!ch) return null;
  ch.last_test_at = ISO(Date.now());
  ch.last_test_ok = true;
  return {
    ok: true,
    channel_id: ch.id,
    message: '测试消息已发送：qwatch 通知渠道联通正常',
    latency_ms: Math.round(180 + rng() * 320),
    at: ch.last_test_at,
  };
}

export const mockMeta = { now: ISO(NOW), totalSignals: signals.length, totalTokens: tokens.length, totalAlerts: alerts.length };
