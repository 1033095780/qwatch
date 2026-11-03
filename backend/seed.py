"""可选的演示数据：初始化 SQLite 后运行一次，界面就有完整数据。"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .db import DB_PATH, connect, dumps, init_db

CST = timezone(timedelta(hours=8))
RNG = random.Random(20261103)

ACCOUNTS = [
    ("qmt:8888", "QMT 主账户", "XSGE", "CN_FUT", "CNY", 700000),
    ("cffex:0666", "金融期货账户", "CFFEX", "CN_FUT", "CNY", 260000),
    ("xshg:6001", "华泰 A股账户", "XSHG", "CN_A", "CNY", 100000),
]

INSTRUMENTS = {
    "rb2601": ("螺纹钢2601", "CN_FUT", "XSGE", 10, 3510.0),
    "au2601": ("沪金2601", "CN_FUT", "XSGE", 1000, 625.0),
    "ag2601": ("沪银2601", "CN_FUT", "XSGE", 15, 7700.0),
    "cu2601": ("沪铜2601", "CN_FUT", "XSGE", 5, 74700.0),
    "IF2612": ("沪深300股指2612", "CN_FUT", "CFFEX", 300, 3985.0),
    "T2612": ("十年国债2612", "CN_FUT", "CFFEX", 10000, 108.2),
    "600519": ("贵州茅台", "CN_A", "XSHG", 1, 1468.0),
    "510300": ("沪深300ETF", "CN_A", "XSHG", 1, 4.128),
    "000001": ("平安银行", "CN_A", "XSHG", 1, 11.36),
}

RUNNERS = [
    {
        "id": "cta_rb-prod", "name": "螺纹钢趋势", "strategy": "me/cta_rb", "version": "1.2.0",
        "market": "CN_FUT", "venue": "XSGE", "platform": "qmt", "strategy_type": "trend",
        "tags": ["期货主账户", "夜盘", "低频"], "status": "running", "accounts": ["qmt:8888"],
        "description": "黑色系趋势跟踪，15 分钟级别，夜盘连续持有。",
        "equity": 462300.12, "today_pnl": 6240.5, "initial": 348000,
        "sharpe": 1.86, "win_rate": 57.3, "uptime_30d": 99.71,
        "last_seen_offset": 4, "heartbeat_interval": 30,
    },
    {
        "id": "cta_if-intraday", "name": "股指日内动量", "strategy": "me/cta_if", "version": "2.0.1",
        "market": "CN_FUT", "venue": "CFFEX", "platform": "ptrade", "strategy_type": "intraday",
        "tags": ["股指", "日内", "对冲"], "status": "running", "accounts": ["cffex:0666"],
        "description": "IF / IH 日内动量，开盘后半小时入场，收盘前平仓。",
        "equity": 318720.55, "today_pnl": 4812.6, "initial": 262000,
        "sharpe": 2.04, "win_rate": 55.1, "uptime_30d": 99.94,
        "last_seen_offset": 2, "heartbeat_interval": 30,
    },
    {
        "id": "cta_ag-swing", "name": "白银波段", "strategy": "me/cta_ag", "version": "1.1.2",
        "market": "CN_FUT", "venue": "XSGE", "platform": "myquant", "strategy_type": "trend",
        "tags": ["贵金属", "波段", "夜盘"], "status": "degraded", "accounts": ["qmt:8888"],
        "description": "贵金属波段，ATR 止损，隔夜仓位不超过 30%。",
        "equity": 187352.48, "today_pnl": -3485.2, "initial": 166000,
        "sharpe": 0.92, "win_rate": 48.6, "uptime_30d": 97.03,
        "last_seen_offset": 44, "heartbeat_interval": 30,
    },
    {
        "id": "cta_cu-breakout", "name": "沪铜突破", "strategy": "me/cta_cu", "version": "0.8.7",
        "market": "CN_FUT", "venue": "XSGE", "platform": "tqsdk", "strategy_type": "multifactor",
        "tags": ["有色金属", "突破", "期货主账户"], "status": "offline", "accounts": ["qmt:8888"],
        "description": "沪铜趋势突破，日线级别，等待行情恢复后上线。",
        "equity": 45120.6, "today_pnl": 0, "initial": 60000,
        "sharpe": 0.71, "win_rate": 44.2, "uptime_30d": 88.4,
        "last_seen_offset": 5 * 60, "heartbeat_interval": 30,
    },
]


def _ts(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _curve(initial: float, target: float, days: int, seed: int) -> list[float]:
    rnd = random.Random(seed)
    values = [initial]
    drift = (target / initial) ** (1 / max(1, days - 1)) - 1
    for _ in range(days - 1):
        noise = rnd.gauss(0, 0.006)
        values.append(max(1.0, values[-1] * (1 + drift + noise)))
    scale = target / values[-1]
    return [round(v * scale, 2) for v in values]


def seed() -> None:
    init_db()
    now = datetime.now(CST)
    with connect() as conn:
        for table in ["signals", "alerts", "equity_points", "tokens", "runners", "accounts", "channels", "calendars", "settings", "sessions"]:
            conn.execute("DELETE FROM " + table)

        for row in ACCOUNTS:
            conn.execute("INSERT INTO accounts VALUES(?,?,?,?,?,?)", row)

        for index, runner in enumerate(RUNNERS):
            initial = float(runner["initial"])
            target = float(runner["equity"])
            values = _curve(initial, target, 180, 100 + index)
            start = now - timedelta(days=179)
            for day_index, value in enumerate(values):
                ts = _ts((start + timedelta(days=day_index)).replace(hour=7, minute=0, second=0, microsecond=0))
                conn.execute(
                    "INSERT INTO equity_points(runner_id, ts, equity) VALUES(?,?,?)",
                    (runner["id"], ts, value),
                )
            total_return = (target / initial - 1) * 100
            peak, max_dd = 0.0, 0.0
            for value in values:
                peak = max(peak, value)
                max_dd = min(max_dd, (value / peak - 1) * 100)
            last_seen = _ts(now - timedelta(seconds=runner["last_seen_offset"]))
            conn.execute(
                """INSERT INTO runners(
                  id,name,strategy,version,market,venue,platform,strategy_type,description,tags,status,accounts,
                  equity,today_pnl,initial_equity,total_return_pct,max_drawdown_pct,sharpe,win_rate,uptime_30d,
                  heartbeat_interval,last_seen,last_loop,loop_same,last_tick,last_msg,created_at,demo
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    runner["id"], runner["name"], runner["strategy"], runner["version"], runner["market"], runner["venue"],
                    runner["platform"], runner["strategy_type"], runner.get("description", ""), dumps(runner["tags"]), runner["status"], dumps(runner["accounts"]),
                    target, float(runner["today_pnl"]), initial, round(total_return, 2), round(abs(max_dd), 2),
                    runner["sharpe"], runner["win_rate"], runner["uptime_30d"], runner["heartbeat_interval"],
                    last_seen, 128000 + index * 97, 0, None, "", _ts(now - timedelta(days=180)),
                ),
            )

        # 信号：近 3 个交易日
        statuses = ["filled", "filled", "filled", "pending", "ignored"]
        msgs = ["突破前高", "均线金叉", "止损离场", "夜盘减仓", "止盈", ""]
        signal_instruments = {
            "cta_rb-prod": ["rb2601", "ag2601", "au2601", "cu2601"],
            "cta_if-intraday": ["IF2612", "T2612"],
            "cta_ag-swing": ["ag2601", "au2601", "cu2601"],
        }
        for i in range(90):
            runner = RUNNERS[i % 3]
            code = RNG.choice(signal_instruments[runner["id"]])
            name, market, venue, mult, base = INSTRUMENTS[code]
            direction = RNG.choice(["long", "short"])
            action = RNG.choice(["open", "close", "add", "reduce"])
            side = "buy" if (direction == "long") == (action in ("open", "add")) else "sell"
            price = round(base * (1 + RNG.uniform(-0.012, 0.012)), 2)
            qty = RNG.randint(1, 20)
            amount = round(price * qty * mult, 2)
            ts = _ts(now - timedelta(minutes=RNG.randint(5, 3 * 24 * 60)))
            conn.execute(
                """INSERT INTO signals(id,ts,runner_id,direction,side,action,instrument,instrument_name,market,venue,
                   account_id,price,qty,amount,status,msg) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "sig_" + f"{i:05d}" + format(RNG.getrandbits(16), "04x"), ts, runner["id"], direction, side, action,
                    code, name, market, venue, runner["accounts"][0], price, qty, amount,
                    RNG.choice(statuses), RNG.choice(msgs),
                ),
            )

        # 告警
        alert_rows = [
            ("alert_heartbeat_cu", "heartbeat_lost", "P0", "firing", "cta_cu-breakout",
             "策略心跳丢失：沪铜突破已 5 分钟未上报（阈值 60 秒）", now - timedelta(minutes=5), None, None),
            ("alert_drawdown_ag", "drawdown_breach", "P1", "firing", "cta_ag-swing",
             "回撤超阈值：白银波段当前回撤 -9.35%，阈值 -8.00%", now - timedelta(minutes=72), None, None),
            ("alert_stalled_if", "runner_stalled", "P1", "resolved", "cta_if-intraday",
             "已恢复：股指日内动量 loop 连续 3 次未增长，进程重启后恢复", now - timedelta(hours=5), now - timedelta(hours=4), now - timedelta(hours=4, minutes=-10)),
            ("alert_burst_rb", "fill_burst", "P2", "resolved", "cta_rb-prod",
             "已恢复：螺纹钢趋势 1 分钟内触发 6 笔信号，已确认非异常", now - timedelta(days=1), now - timedelta(days=1, minutes=-8), None),
        ]
        for row in alert_rows:
            alert_id, rule, severity, status, runner_id, summary, starts, ends, acked = row
            conn.execute(
                """INSERT INTO alerts(id,fingerprint,rule,severity,status,runner_id,summary,starts_at,ends_at,acked_at,labels,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    alert_id, "fp_" + alert_id, rule, severity, status, runner_id, summary,
                    _ts(starts), _ts(ends) if ends else None, _ts(acked) if acked else None,
                    dumps({"source": "seed"}), _ts(ends or starts),
                ),
            )

        # 通知渠道
        for channel_id, name, webhook, secret, mobiles, enabled in [
            ("dingtalk_main", "钉钉 · 主机器人", "https://oapi.dingtalk.com/robot/send?access_token=demo-main-token", "SECdemo-main-secret", ["13800138000"], 1),
            ("dingtalk_backup", "钉钉 · 备用机器人", "https://oapi.dingtalk.com/robot/send?access_token=demo-backup-token", "", [], 0),
        ]:
            conn.execute(
                "INSERT INTO channels VALUES(?,?,?,?,?,?,?,?,?,?)",
                (channel_id, name, "dingtalk_robot", enabled, webhook, secret, dumps(mobiles), 15, None, None),
            )

        calendars = [
            ("cn_a", "A股", "Asia/Shanghai", ["09:15-11:30", "13:00-15:00"], 0, "A股节假日表（周末休市不开市）"),
            ("cn_fut_2300", "商品期货 · 23:00 组", "Asia/Shanghai", ["09:00-10:15", "10:30-11:30", "13:30-15:00", "21:00-23:00"], 1, "期货节假日表（周末休市不开市）"),
            ("cn_fut_0100", "商品期货 · 01:00 组", "Asia/Shanghai", ["09:00-10:15", "10:30-11:30", "13:30-15:00", "21:00-01:00"], 1, "期货节假日表（周末休市不开市）"),
            ("cn_fut_0230", "商品期货 · 02:30 组", "Asia/Shanghai", ["09:00-10:15", "10:30-11:30", "13:30-15:00", "21:00-02:30"], 1, "期货节假日表（周末休市不开市）"),
            ("cffex", "金融期货 CFFEX", "Asia/Shanghai", ["09:30-11:30", "13:00-15:00"], 0, "期货节假日表（周末休市不开市）"),
        ]
        for row in calendars:
            conn.execute("INSERT INTO calendars VALUES(?,?,?,?,?,?)", (row[0], row[1], row[2], dumps(row[3]), row[4], row[5]))

        conn.execute("INSERT INTO settings(key,value) VALUES('up_color_scheme','red_up')")
    print("seeded", DB_PATH)


if __name__ == "__main__":
    seed()