"""v0.5 基础数据：初始化数据库后写入钉钉渠道占位与配色。

不再创建账户 / 策略 / 进程；账户由 API 创建，策略必须选择账户，进程上报自动发现。
权益以策略为准（runners.equity/nav + runner_equity_points），账户权益为策略求和。
运行会清空运行时数据（accounts/runners/processes/events/alerts/tokens/sessions），请先备份。
"""

from __future__ import annotations

from .db import DB_PATH, connect, init_db, set_setting

CHANNELS = [
    # id, name, type, enabled, webhook, secret
    ("dingtalk_main", "钉钉 · 主机器人", "dingtalk_robot", 1,
     "https://oapi.dingtalk.com/robot/send?access_token=demo-main-token", "SECdemo-main-secret"),
]

TABLES = [
    "runner_equity_points",
    "accounts",
    "alert_deliveries",
    "alerts",
    "events",
    "processes",
    "process_day_health",
    "runners",
    "tokens",
    "sessions",
    "channels",
    "settings",
]


def seed() -> None:
    """清空运行时表，只写入渠道配置与配色。"""
    init_db()
    with connect() as conn:
        for table in TABLES:
            conn.execute("DELETE FROM " + table)
        for channel_id, name, channel_type, enabled, webhook, secret in CHANNELS:
            conn.execute(
                "INSERT INTO channels(id, name, type, enabled, webhook, secret) VALUES(?,?,?,?,?,?)",
                (channel_id, name, channel_type, enabled, webhook, secret),
            )
        set_setting(conn, "up_color_scheme", "red_up")
    print("seeded", DB_PATH)


if __name__ == "__main__":
    seed()