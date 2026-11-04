"""v0.2 基础数据：初始化数据库后写入钉钉渠道占位与配色。

不再创建账户 / 交易日历 / 策略 / 进程；策略与进程由 API 创建、上报自动发现。
运行会清空运行时数据（runners/processes/events/alerts/tokens/sessions），请先备份。
"""

from __future__ import annotations

from .db import DB_PATH, connect, init_db, set_setting

CHANNELS = [
    # id, name, type, enabled, webhook, secret
    ("dingtalk_main", "钉钉 · 主机器人", "dingtalk_robot", 1,
     "https://oapi.dingtalk.com/robot/send?access_token=demo-main-token", "SECdemo-main-secret"),
    ("dingtalk_backup", "钉钉 · 备用机器人", "dingtalk_robot", 0,
     "https://oapi.dingtalk.com/robot/send?access_token=demo-backup-token", ""),
]

TABLES = [
    "alert_deliveries",
    "alerts",
    "events",
    "nav_points",
    "processes",
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
