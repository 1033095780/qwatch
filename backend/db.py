"""SQLite 存储层（v0.2）：建表、连接与旧库迁移。

v0.2 模型：策略组（runners）+ 进程（processes）+ 动态事件（events）+ 告警（alerts）。
旧库（v0.1：含 equity/pnl/账户/日历等）在启动时自动迁移，迁移过程单事务、失败回滚。
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("QWATCH_DB", ROOT / "data" / "qwatch.db"))
SCHEMA_VERSION = 3
logger = logging.getLogger("qwatch.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runners (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  platform TEXT NOT NULL DEFAULT '',
  market TEXT NOT NULL DEFAULT '',
  strategy_type TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',
  paused INTEGER NOT NULL DEFAULT 0,
  last_msg TEXT,
  nav REAL,
  nav_updated_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nav_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runner_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  nav REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nav_points_runner ON nav_points(runner_id, id);

CREATE TABLE IF NOT EXISTS processes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runner_id TEXT NOT NULL,
  name TEXT NOT NULL,
  last_seen TEXT,
  last_loop INTEGER,
  loop_same INTEGER NOT NULL DEFAULT 0,
  last_tick TEXT,
  status TEXT NOT NULL DEFAULT 'offline',
  retired INTEGER NOT NULL DEFAULT 0,
  retired_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(runner_id, name)
);
CREATE INDEX IF NOT EXISTS idx_processes_runner ON processes(runner_id);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runner_id TEXT NOT NULL,
  instrument TEXT NOT NULL,
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  text TEXT NOT NULL DEFAULT '',
  symbol TEXT NOT NULL DEFAULT '',
  direction TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL DEFAULT '',
  qty REAL,
  price REAL,
  amount REAL,
  external_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_runner_id ON events(runner_id, id);
CREATE INDEX IF NOT EXISTS idx_events_runner_ts ON events(runner_id, ts);
CREATE UNIQUE INDEX IF NOT EXISTS uq_events_signal_id
  ON events(runner_id, external_id) WHERE external_id IS NOT NULL AND external_id <> '';

CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  rule TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  runner_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  starts_at TEXT NOT NULL,
  ends_at TEXT,
  acked_at TEXT,
  labels TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_runner ON alerts(runner_id);

CREATE TABLE IF NOT EXISTS alert_deliveries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'firing',
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT,
  next_attempt_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deliveries_due ON alert_deliveries(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'dingtalk_robot',
  enabled INTEGER NOT NULL DEFAULT 1,
  webhook TEXT NOT NULL DEFAULT '',
  secret TEXT NOT NULL DEFAULT '',
  last_test_at TEXT,
  last_test_ok INTEGER
);

CREATE TABLE IF NOT EXISTS tokens (
  id TEXT PRIMARY KEY,
  runner_id TEXT,
  name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  token_prefix TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  request_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tokens_runner ON tokens(runner_id);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

# v0.1 可能存在的表；迁移时先整体改名再按新 schema 重建。
LEGACY_TABLES = (
    "sessions",
    "accounts",
    "runners",
    "instruments",
    "equity_points",
    "messages",
    "cash_flows",
    "tokens",
    "signals",
    "alerts",
    "channels",
    "calendars",
    "settings",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, name: str) -> list[str]:
    if not _table_exists(conn, name):
        return []
    return [row["name"] for row in conn.execute("PRAGMA table_info(" + name + ")").fetchall()]


def _exec_script(conn: sqlite3.Connection, script: str) -> None:
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _load_legacy(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    data: dict[str, list[sqlite3.Row]] = {}
    for table in LEGACY_TABLES:
        data[table] = list(conn.execute("SELECT * FROM " + table)) if _table_exists(conn, table) else []
    return data


def _migrate_legacy(conn: sqlite3.Connection, data: dict[str, list[sqlite3.Row]]) -> None:
    """把 v0.1 库在同事务内迁移到 v0.2；任何异常都会由调用方回滚。"""
    now = iso_now()
    existing = [table for table in LEGACY_TABLES if _table_exists(conn, table)]
    for table in existing:
        conn.execute("ALTER TABLE " + table + " RENAME TO legacy_" + table)
    _exec_script(conn, SCHEMA)

    # 会话 / 渠道 / 设置 / 令牌原样保留
    for row in data["sessions"]:
        conn.execute(
            "INSERT OR IGNORE INTO sessions(token_hash, user, expires_at) VALUES(?,?,?)",
            (_row_get(row, "token_hash"), _row_get(row, "user", "Trader"), _row_get(row, "expires_at")),
        )
    for row in data["channels"]:
        conn.execute(
            "INSERT OR REPLACE INTO channels(id, name, type, enabled, webhook, secret, last_test_at, last_test_ok) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                _row_get(row, "id"),
                _row_get(row, "name", _row_get(row, "id")),
                _row_get(row, "type", "dingtalk_robot"),
                _row_get(row, "enabled", 1),
                _row_get(row, "webhook", ""),
                _row_get(row, "secret", ""),
                _row_get(row, "last_test_at"),
                _row_get(row, "last_test_ok"),
            ),
        )
    for row in data["settings"]:
        key = _row_get(row, "key")
        if key and key != "schema_version":
            conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, _row_get(row, "value", "")))
    for row in data["tokens"]:
        conn.execute(
            "INSERT OR REPLACE INTO tokens(id, runner_id, name, token_hash, token_prefix, status, created_at, "
            "last_used_at, request_count) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                _row_get(row, "id"),
                _row_get(row, "runner_id"),
                _row_get(row, "name", "token"),
                _row_get(row, "token_hash"),
                _row_get(row, "token_prefix", ""),
                _row_get(row, "status", "active"),
                _row_get(row, "created_at", now),
                _row_get(row, "last_used_at"),
                _row_get(row, "request_count", 0),
            ),
        )

    # 策略组
    runner_ids: list[str] = []
    for row in data["runners"]:
        runner_id = _row_get(row, "id")
        if not runner_id:
            continue
        runner_ids.append(runner_id)
        conn.execute(
            "INSERT OR REPLACE INTO runners(id, name, description, platform, market, strategy_type, tags, paused, "
            "last_msg, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                runner_id,
                _row_get(row, "name", runner_id),
                _row_get(row, "description", ""),
                _row_get(row, "platform", ""),
                _row_get(row, "market", ""),
                _row_get(row, "strategy_type", ""),
                _row_get(row, "tags", "[]"),
                1 if str(_row_get(row, "status", "")) == "paused" else 0,
                _row_get(row, "last_msg"),
                _row_get(row, "created_at", now),
            ),
        )

    # 进程：旧 instruments -> processes；没有 instruments 的旧策略补一个 main 进程
    seen_runners: set[str] = set()
    for row in data["instruments"]:
        runner_id = _row_get(row, "runner_id")
        name = str(_row_get(row, "name", "") or "").strip() or "main"
        if not runner_id:
            continue
        seen_runners.add(runner_id)
        # v0.1 的品种名多为 rb2601/IF2612 等合约号；v0.2 用稳定进程名 rb/IF。
        # 旧合约行迁移后默认 retired，避免旧进程永久 stale/污染告警。
        retired = 1 if re.fullmatch(r"[A-Za-z]+\d+", name) or name in ("main", "主账户") else 0
        conn.execute(
            "INSERT OR REPLACE INTO processes(runner_id, name, last_seen, last_loop, loop_same, status, retired, "
            "created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                runner_id,
                name,
                _row_get(row, "last_seen"),
                _row_get(row, "last_loop"),
                _row_get(row, "loop_same", 0),
                "offline",
                retired,
                _row_get(row, "updated_at", now),
                _row_get(row, "updated_at", now),
            ),
        )
    by_runner = {_row_get(row, "id"): row for row in data["runners"]}
    for runner_id in runner_ids:
        if runner_id in seen_runners:
            continue
        row = by_runner.get(runner_id)
        conn.execute(
            "INSERT OR REPLACE INTO processes(runner_id, name, last_seen, last_loop, loop_same, status, retired, "
            "created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                runner_id,
                "main",
                _row_get(row, "last_seen") if row is not None else None,
                _row_get(row, "last_loop") if row is not None else None,
                _row_get(row, "loop_same", 0) if row is not None else 0,
                "offline",
                1,
                _row_get(row, "created_at", now) if row is not None else now,
                now,
            ),
        )

    # 动态：旧 messages + signals -> events；按 ts 合并排序
    timeline: list[tuple[str, str, dict[str, Any]]] = []
    for row in data["messages"]:
        ts = _row_get(row, "ts") or now
        timeline.append((
            ts,
            _row_get(row, "runner_id", ""),
            {
                "instrument": str(_row_get(row, "instrument", "") or "main"),
                "type": "message",
                "text": _row_get(row, "text", ""),
                "symbol": "",
                "direction": "",
                "action": "",
                "qty": None,
                "price": None,
                "amount": None,
                "external_id": None,
            },
        ))
    for row in data["signals"]:
        ts = _row_get(row, "ts") or now
        timeline.append((
            ts,
            _row_get(row, "runner_id", ""),
            {
                "instrument": str(_row_get(row, "instrument", "") or "main"),
                "type": "signal",
                "text": _row_get(row, "msg", ""),
                "symbol": str(_row_get(row, "instrument", "") or ""),
                "direction": str(_row_get(row, "direction", "") or ""),
                "action": str(_row_get(row, "action", "") or ""),
                "qty": _row_get(row, "qty"),
                "price": _row_get(row, "price"),
                "amount": _row_get(row, "amount"),
                "external_id": _row_get(row, "id"),
            },
        ))
    timeline.sort(key=lambda item: item[0])
    for ts, runner_id, event in timeline:
        if not runner_id:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO events(runner_id, instrument, ts, type, text, symbol, direction, action, qty, "
            "price, amount, external_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                runner_id, event["instrument"], ts, event["type"], event["text"], event["symbol"],
                event["direction"], event["action"], event["qty"], event["price"], event["amount"],
                event["external_id"], ts,
            ),
        )

    # 告警：保留两类 P0 历史（旧 firing 会被 watchdog 立即重算）
    for row in data["alerts"]:
        if _row_get(row, "rule") not in ("heartbeat_lost", "runner_stalled"):
            continue
        if _row_get(row, "runner_id") not in runner_ids:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO alerts(id, fingerprint, rule, severity, status, runner_id, summary, starts_at, "
            "ends_at, acked_at, labels, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                _row_get(row, "id"), _row_get(row, "fingerprint", ""), _row_get(row, "rule"),
                _row_get(row, "severity", "P0"), _row_get(row, "status", "resolved"),
                _row_get(row, "runner_id"), _row_get(row, "summary", ""),
                _row_get(row, "starts_at", now), _row_get(row, "ends_at"), _row_get(row, "acked_at"),
                _row_get(row, "labels", "{}"), _row_get(row, "updated_at", now),
            ),
        )

    for table in existing:
        conn.execute("DROP TABLE legacy_" + table)
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
    logger.info(
        "旧库迁移完成：runners=%d processes=%d events=%d alerts=%d",
        len(runner_ids), len(data["instruments"]) or len(runner_ids), len(timeline), len(data["alerts"]),
    )


def init_db() -> None:
    """创建/迁移数据库；旧库迁移失败会抛出异常（事务已回滚）。"""
    with connect() as conn:
        legacy = _table_exists(conn, "runners") and "equity" in _columns(conn, "runners")
        if legacy:
            logger.info("检测到 v0.1 旧库，开始迁移：%s", str(DB_PATH))
            try:
                _migrate_legacy(conn, _load_legacy(conn))
            except Exception as exc:  # noqa: BLE001
                logger.exception("旧库迁移失败，已回滚，请先备份 data/qwatch.db")
                raise RuntimeError("旧库迁移失败，已回滚；请备份 data/qwatch.db 后重试") from exc
        else:
            _exec_script(conn, SCHEMA)
        # v0.2 -> v0.3：策略组净值（进程上报，最后一次为准）+ 净值历史
        runner_columns = _columns(conn, "runners")
        if "nav" not in runner_columns:
            conn.execute("ALTER TABLE runners ADD COLUMN nav REAL")
        if "nav_updated_at" not in runner_columns:
            conn.execute("ALTER TABLE runners ADD COLUMN nav_updated_at TEXT")
        if not _table_exists(conn, "settings"):
            _exec_script(conn, SCHEMA)
        row = conn.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()
        if row is None:
            conn.execute("INSERT INTO settings(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        elif row["value"] != str(SCHEMA_VERSION):
            conn.execute("UPDATE settings SET value = ? WHERE key = 'schema_version'", (str(SCHEMA_VERSION),))
