"""基础数据：初始化 SQLite 后运行一次，写入账户 / 钉钉渠道 / 交易日历 / 配色。

演示策略、信号与告警由 sim/run.py 通过真实 API 产生，这里不再插入任何 mock 数据。
"""

from __future__ import annotations

from .db import DB_PATH, connect, dumps, init_db

ACCOUNTS = [
    ("qmt:8888", "QMT 主账户", "XSGE", "CN_FUT", "CNY", 700000),
    ("cffex:0666", "金融期货账户", "CFFEX", "CN_FUT", "CNY", 260000),
    ("xshg:6001", "华泰 A股账户", "XSHG", "CN_A", "CNY", 100000),
]

CHANNELS = [
    # id, name, webhook, secret, at_mobiles, enabled
    ("dingtalk_main", "钉钉 · 主机器人", "https://oapi.dingtalk.com/robot/send?access_token=demo-main-token",
     "SECdemo-main-secret", ["13800138000"], 1),
    ("dingtalk_backup", "钉钉 · 备用机器人", "https://oapi.dingtalk.com/robot/send?access_token=demo-backup-token",
     "", [], 0),
]

CALENDARS = [
    ("cn_a", "A股", "Asia/Shanghai", ["09:15-11:30", "13:00-15:00"], 0, "A股节假日表（周末休市不开市）"),
    ("cn_fut_2300", "商品期货 · 23:00 组", "Asia/Shanghai",
     ["09:00-10:15", "10:30-11:30", "13:30-15:00", "21:00-23:00"], 1, "期货节假日表（周末休市不开市）"),
    ("cn_fut_0100", "商品期货 · 01:00 组", "Asia/Shanghai",
     ["09:00-10:15", "10:30-11:30", "13:30-15:00", "21:00-01:00"], 1, "期货节假日表（周末休市不开市）"),
    ("cn_fut_0230", "商品期货 · 02:30 组", "Asia/Shanghai",
     ["09:00-10:15", "10:30-11:30", "13:30-15:00", "21:00-02:30"], 1, "期货节假日表（周末休市不开市）"),
    ("cffex", "金融期货 CFFEX", "Asia/Shanghai", ["09:30-11:30", "13:00-15:00"], 0, "期货节假日表（周末休市不开市）"),
]

TABLES = ["signals", "alerts", "equity_points", "tokens", "runners", "accounts",
          "channels", "calendars", "settings", "sessions"]


def seed() -> None:
    """清空运行时表，只写入账户、渠道、日历与配色等基础配置。"""
    init_db()
    with connect() as conn:
        for table in TABLES:
            conn.execute("DELETE FROM " + table)

        for row in ACCOUNTS:
            conn.execute("INSERT INTO accounts VALUES(?,?,?,?,?,?)", row)

        for channel_id, name, webhook, secret, mobiles, enabled in CHANNELS:
            conn.execute(
                "INSERT INTO channels(id,name,type,enabled,webhook,secret,at_mobiles,rate_limit_per_min)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (channel_id, name, "dingtalk_robot", enabled, webhook, secret, dumps(mobiles), 15),
            )

        for calendar_id, name, timezone, sessions, night, holidays in CALENDARS:
            conn.execute(
                "INSERT INTO calendars VALUES(?,?,?,?,?,?)",
                (calendar_id, name, timezone, dumps(sessions), night, holidays),
            )

        conn.execute("INSERT INTO settings(key,value) VALUES('up_color_scheme','red_up')")
    print("seeded", DB_PATH)


if __name__ == "__main__":
    seed()
