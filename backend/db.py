"""SQLite 存储层（v0.5）：策略级权益 + 账户聚合 + 策略/进程/动态/告警。

v0.5 模型：权益/净值真相在策略（runners.equity/nav）+ runner_equity_points；
accounts 只是策略的自然分组（不再存账户权益）；旧版库启动时单事务迁移，失败回滚，
迁移完成后按 schema_version + 表/列探测跳过，避免每次启动误迁移。
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
SCHEMA_VERSION = 5
logger = logging.getLogger("qwatch.db")

V04_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  broker TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  equity REAL,
  nav REAL,
  equity_updated_at TEXT,
  nav_updated_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_equity_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  equity REAL,
  nav REAL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_equity_points ON account_equity_points(account_id, id);

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
  account_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runners_account ON runners(account_id);

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

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  broker TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
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
  account_id TEXT NOT NULL,
  equity REAL,
  nav REAL,
  equity_updated_at TEXT,
  nav_updated_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runners_account ON runners(account_id);

CREATE TABLE IF NOT EXISTS runner_equity_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runner_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  equity REAL,
  nav REAL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runner_equity_points ON runner_equity_points(runner_id, id);

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

# v0.3 schema：仅用于 v0.1 旧库或 v0.2 库升级到 v0.3 中间态；随后依次迁移到 v0.5。
V03_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runners (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
  platform TEXT NOT NULL DEFAULT '', market TEXT NOT NULL DEFAULT '', strategy_type TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]', paused INTEGER NOT NULL DEFAULT 0, last_msg TEXT,
  nav REAL, nav_updated_at TEXT, equity REAL, equity_updated_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nav_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT, runner_id TEXT NOT NULL, ts TEXT NOT NULL,
  nav REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nav_points_runner ON nav_points(runner_id, id);
CREATE TABLE IF NOT EXISTS equity_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT, runner_id TEXT NOT NULL, ts TEXT NOT NULL,
  equity REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_equity_points_runner ON equity_points(runner_id, id);
CREATE TABLE IF NOT EXISTS processes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, runner_id TEXT NOT NULL, name TEXT NOT NULL,
  last_seen TEXT, last_loop INTEGER, loop_same INTEGER NOT NULL DEFAULT 0, last_tick TEXT,
  status TEXT NOT NULL DEFAULT 'offline', retired INTEGER NOT NULL DEFAULT 0, retired_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(runner_id, name)
);
CREATE INDEX IF NOT EXISTS idx_processes_runner ON processes(runner_id);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, runner_id TEXT NOT NULL, instrument TEXT NOT NULL,
  ts TEXT NOT NULL, type TEXT NOT NULL, text TEXT NOT NULL DEFAULT '', symbol TEXT NOT NULL DEFAULT '',
  direction TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '', qty REAL, price REAL, amount REAL,
  external_id TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_runner_id ON events(runner_id, id);
CREATE INDEX IF NOT EXISTS idx_events_runner_ts ON events(runner_id, ts);
CREATE UNIQUE INDEX IF NOT EXISTS uq_events_signal_id
  ON events(runner_id, external_id) WHERE external_id IS NOT NULL AND external_id <> '';
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, rule TEXT NOT NULL, severity TEXT NOT NULL,
  status TEXT NOT NULL, runner_id TEXT NOT NULL, summary TEXT NOT NULL, starts_at TEXT NOT NULL,
  ends_at TEXT, acked_at TEXT, labels TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_runner ON alerts(runner_id);
CREATE TABLE IF NOT EXISTS alert_deliveries (
  id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT NOT NULL, channel_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'firing', status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, sent_at TEXT, next_attempt_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deliveries_due ON alert_deliveries(status, next_attempt_at);
CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'dingtalk_robot',
  enabled INTEGER NOT NULL DEFAULT 1, webhook TEXT NOT NULL DEFAULT '', secret TEXT NOT NULL DEFAULT '',
  last_test_at TEXT, last_test_ok INTEGER
);
CREATE TABLE IF NOT EXISTS tokens (
  id TEXT PRIMARY KEY, runner_id TEXT, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  token_prefix TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL,
  last_used_at TEXT, request_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tokens_runner ON tokens(runner_id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

LEGACY_TABLES = (
    "sessions", "accounts", "runners", "instruments", "equity_points", "messages", "cash_flows",
    "tokens", "signals", "alerts", "channels", "calendars", "settings",
)

DEFAULT_ACCOUNT_ID = "account-default"


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
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


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


def _schema_version(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "settings"):
        return 0
    raw = get_setting(conn, "schema_version", "0")
    try:
        return int(raw or 0)
    except ValueError:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    if _table_exists(conn, "settings"):
        conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('schema_version', ?)", (str(version),))


def _load_legacy(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    data: dict[str, list[sqlite3.Row]] = {}
    for table in LEGACY_TABLES:
        data[table] = list(conn.execute("SELECT * FROM " + table)) if _table_exists(conn, table) else []
    return data


def _migrate_v01(conn: sqlite3.Connection, data: dict[str, list[sqlite3.Row]]) -> None:
    """v0.1（含权益/账户/日历）-> v0.3 中间态；随后由 _migrate_v3_to_v4 迁移。"""
    now = iso_now()
    existing = [table for table in LEGACY_TABLES if _table_exists(conn, table)]
    for table in existing:
        conn.execute("ALTER TABLE " + table + " RENAME TO legacy_" + table)
    _exec_script(conn, V03_SCHEMA)

    for row in data["sessions"]:
        conn.execute(
            "INSERT OR IGNORE INTO sessions(token_hash, user, expires_at) VALUES(?,?,?)",
            (_row_get(row, "token_hash"), _row_get(row, "user", "Trader"), _row_get(row, "expires_at")),
        )
    for row in data["channels"]:
        conn.execute(
            "INSERT OR REPLACE INTO channels(id,name,type,enabled,webhook,secret,last_test_at,last_test_ok) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (_row_get(row, "id"), _row_get(row, "name", _row_get(row, "id")), _row_get(row, "type", "dingtalk_robot"),
             _row_get(row, "enabled", 1), _row_get(row, "webhook", ""), _row_get(row, "secret", ""),
             _row_get(row, "last_test_at"), _row_get(row, "last_test_ok")),
        )
    for row in data["settings"]:
        key = _row_get(row, "key")
        if key and key != "schema_version":
            conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, _row_get(row, "value", "")))
    for row in data["tokens"]:
        conn.execute(
            "INSERT OR REPLACE INTO tokens(id,runner_id,name,token_hash,token_prefix,status,created_at,"
            "last_used_at,request_count) VALUES(?,?,?,?,?,?,?,?,?)",
            (_row_get(row, "id"), _row_get(row, "runner_id"), _row_get(row, "name", "token"),
             _row_get(row, "token_hash"), _row_get(row, "token_prefix", ""), _row_get(row, "status", "active"),
             _row_get(row, "created_at", now), _row_get(row, "last_used_at"), _row_get(row, "request_count", 0)),
        )

    runner_ids: list[str] = []
    for row in data["runners"]:
        runner_id = _row_get(row, "id")
        if not runner_id:
            continue
        runner_ids.append(runner_id)
        conn.execute(
            "INSERT OR REPLACE INTO runners(id,name,description,platform,market,strategy_type,tags,paused,last_msg,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (runner_id, _row_get(row, "name", runner_id), _row_get(row, "description", ""),
             _row_get(row, "platform", ""), _row_get(row, "market", ""), _row_get(row, "strategy_type", ""),
             _row_get(row, "tags", "[]"), 1 if str(_row_get(row, "status", "")) == "paused" else 0,
             _row_get(row, "last_msg"), _row_get(row, "created_at", now)),
        )

    # 旧 instruments -> 进程；合约号/主账户默认 retired，避免旧进程永久 stale
    seen: set[str] = set()
    for row in data["instruments"]:
        runner_id = _row_get(row, "runner_id")
        name = str(_row_get(row, "name", "") or "").strip() or "main"
        if not runner_id:
            continue
        seen.add(runner_id)
        retired = 1 if re.fullmatch(r"[A-Za-z]+\d+", name) or name in ("main", "主账户") else 0
        conn.execute(
            "INSERT OR REPLACE INTO processes(runner_id,name,last_seen,last_loop,loop_same,status,retired,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (runner_id, name, _row_get(row, "last_seen"), _row_get(row, "last_loop"),
             _row_get(row, "loop_same", 0), "offline", retired,
             _row_get(row, "updated_at", now), _row_get(row, "updated_at", now)),
        )
    by_runner = {_row_get(row, "id"): row for row in data["runners"]}
    for runner_id in runner_ids:
        if runner_id in seen:
            continue
        row = by_runner.get(runner_id)
        conn.execute(
            "INSERT OR REPLACE INTO processes(runner_id,name,last_seen,last_loop,loop_same,status,retired,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (runner_id, "main", _row_get(row, "last_seen") if row else None,
             _row_get(row, "last_loop") if row else None, _row_get(row, "loop_same", 0) if row else 0,
             "offline", 1, _row_get(row, "created_at", now) if row else now, now),
        )

    timeline: list[tuple[str, str, dict[str, Any]]] = []
    for row in data["messages"]:
        timeline.append((_row_get(row, "ts") or now, _row_get(row, "runner_id", ""), {
            "instrument": str(_row_get(row, "instrument", "") or "main"), "type": "message",
            "text": _row_get(row, "text", ""), "symbol": "", "direction": "", "action": "",
            "qty": None, "price": None, "amount": None, "external_id": None}))
    for row in data["signals"]:
        timeline.append((_row_get(row, "ts") or now, _row_get(row, "runner_id", ""), {
            "instrument": str(_row_get(row, "instrument", "") or "main"), "type": "signal",
            "text": _row_get(row, "msg", ""), "symbol": str(_row_get(row, "instrument", "") or ""),
            "direction": str(_row_get(row, "direction", "") or ""), "action": str(_row_get(row, "action", "") or ""),
            "qty": _row_get(row, "qty"), "price": _row_get(row, "price"), "amount": _row_get(row, "amount"),
            "external_id": _row_get(row, "id")}))
    timeline.sort(key=lambda item: item[0])
    for ts, runner_id, event in timeline:
        if not runner_id:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO events(runner_id,instrument,ts,type,text,symbol,direction,action,qty,price,amount,"
            "external_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (runner_id, event["instrument"], ts, event["type"], event["text"], event["symbol"],
             event["direction"], event["action"], event["qty"], event["price"], event["amount"],
             event["external_id"], ts),
        )
    for row in data["alerts"]:
        if _row_get(row, "rule") not in ("heartbeat_lost", "runner_stalled"):
            continue
        if _row_get(row, "runner_id") not in runner_ids:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO alerts(id,fingerprint,rule,severity,status,runner_id,summary,starts_at,ends_at,"
            "acked_at,labels,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (_row_get(row, "id"), _row_get(row, "fingerprint", ""), _row_get(row, "rule"),
             _row_get(row, "severity", "P0"), _row_get(row, "status", "resolved"), _row_get(row, "runner_id"),
             _row_get(row, "summary", ""), _row_get(row, "starts_at", now), _row_get(row, "ends_at"),
             _row_get(row, "acked_at"), _row_get(row, "labels", "{}"), _row_get(row, "updated_at", now)),
        )
    for table in existing:
        conn.execute("DROP TABLE legacy_" + table)
    _set_schema_version(conn, 3)
    logger.info("v0.1 -> v0.3 迁移完成：runners=%d events=%d", len(runner_ids), len(timeline))


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """v0.3 -> v0.4：默认账户、runners.account_id、账户权益与账户权益曲线。"""
    now = iso_now()
    runners = list(conn.execute("SELECT * FROM runners")) if _table_exists(conn, "runners") else []
    equity_rows = list(conn.execute("SELECT * FROM equity_points ORDER BY id")) if _table_exists(conn, "equity_points") else []
    nav_rows = list(conn.execute("SELECT * FROM nav_points ORDER BY id")) if _table_exists(conn, "nav_points") else []

    # 选择默认账户的最新权益/净值（最后上报者胜出，与运行时 last-wins 语义一致）
    latest_equity: float | None = None
    latest_equity_at: str | None = None
    latest_nav: float | None = None
    latest_nav_at: str | None = None
    for row in runners:
        equity = _row_get(row, "equity")
        if equity is not None:
            at = _row_get(row, "equity_updated_at") or _row_get(row, "created_at") or now
            if latest_equity_at is None or at > latest_equity_at:
                latest_equity, latest_equity_at = float(equity), at
        nav = _row_get(row, "nav")
        if nav is not None:
            at = _row_get(row, "nav_updated_at") or _row_get(row, "created_at") or now
            if latest_nav_at is None or at > latest_nav_at:
                latest_nav, latest_nav_at = float(nav), at
    if latest_equity is None and equity_rows:
        last = equity_rows[-1]
        latest_equity = float(last["equity"])
        latest_equity_at = last["ts"] or last["created_at"] or now

    # 备份旧表 -> 建 v0.4 schema -> 复制
    conn.execute("ALTER TABLE runners RENAME TO legacy_v3_runners")
    if _table_exists(conn, "equity_points"):
        conn.execute("ALTER TABLE equity_points RENAME TO legacy_v3_equity_points")
    if _table_exists(conn, "nav_points"):
        conn.execute("ALTER TABLE nav_points RENAME TO legacy_v3_nav_points")
    _exec_script(conn, V04_SCHEMA)

    if runners:
        conn.execute(
            "INSERT INTO accounts(id,name,broker,description,equity,nav,equity_updated_at,nav_updated_at,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (DEFAULT_ACCOUNT_ID, "默认账户", "未分类", "由 v0.3 自动迁移的历史策略账户",
             latest_equity, latest_nav, latest_equity_at, latest_nav_at, now),
        )
        for row in runners:
            conn.execute(
                "INSERT INTO runners(id,name,description,platform,market,strategy_type,tags,paused,last_msg,account_id,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (_row_get(row, "id"), _row_get(row, "name", _row_get(row, "id")), _row_get(row, "description", ""),
                 _row_get(row, "platform", ""), _row_get(row, "market", ""), _row_get(row, "strategy_type", ""),
                 _row_get(row, "tags", "[]"), _row_get(row, "paused", 0), _row_get(row, "last_msg"),
                 DEFAULT_ACCOUNT_ID, _row_get(row, "created_at", now)),
            )
        for row in equity_rows:
            conn.execute(
                "INSERT INTO account_equity_points(account_id, ts, equity, nav, created_at) VALUES(?,?,?,NULL,?)",
                (DEFAULT_ACCOUNT_ID, _row_get(row, "ts") or now, float(_row_get(row, "equity") or 0.0),
                 _row_get(row, "created_at") or now),
            )
        # 旧策略净值历史（若有）也保留为账户点，equity 为空、不参与权益曲线
        for row in nav_rows:
            conn.execute(
                "INSERT INTO account_equity_points(account_id, ts, equity, nav, created_at) VALUES(?,?,NULL,?,?)",
                (DEFAULT_ACCOUNT_ID, _row_get(row, "ts") or now, float(_row_get(row, "nav") or 0.0),
                 _row_get(row, "created_at") or now),
            )
    conn.execute("DROP TABLE legacy_v3_runners")
    if _table_exists(conn, "legacy_v3_equity_points"):
        conn.execute("DROP TABLE legacy_v3_equity_points")
    if _table_exists(conn, "legacy_v3_nav_points"):
        conn.execute("DROP TABLE legacy_v3_nav_points")
    _set_schema_version(conn, 4)
    logger.info(
        "v0.3 -> v0.4 迁移完成：accounts=1 runners=%d account_equity_points=%d（默认账户权益=%s）",
        len(runners), len(equity_rows), latest_equity,
    )


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """v0.4 -> v0.5：权益真相回到策略。

    - 旧账户权益/净值赋给该账户下最早创建的策略（其余策略从 NULL 开始）
    - 旧 account_equity_points 全部转给该最早策略 -> runner_equity_points
    - 删除 account_equity_points，accounts 不再保留权益列
    """
    now = iso_now()
    accounts = list(conn.execute("SELECT * FROM accounts")) if _table_exists(conn, "accounts") else []
    account_points = (
        list(conn.execute("SELECT * FROM account_equity_points ORDER BY id"))
        if _table_exists(conn, "account_equity_points") else []
    )
    runners = list(conn.execute("SELECT * FROM runners")) if _table_exists(conn, "runners") else []

    # 每个账户最早创建的策略（created_at 优先、id 兜底）
    earliest: dict[str, str] = {}
    for runner in sorted(runners, key=lambda item: (_row_get(item, "created_at") or "", _row_get(item, "id") or "")):
        account_id = _row_get(runner, "account_id")
        runner_id = _row_get(runner, "id")
        if account_id and runner_id and account_id not in earliest:
            earliest[account_id] = runner_id

    # 旧表体改名 -> 建 v0.5 schema（accounts 新表无权益列、runners 由 ALTER 补列）
    conn.execute("ALTER TABLE accounts RENAME TO legacy_v4_accounts")
    if _table_exists(conn, "account_equity_points"):
        conn.execute("ALTER TABLE account_equity_points RENAME TO legacy_v4_account_points")
    _exec_script(conn, SCHEMA)
    runner_columns = _columns(conn, "runners")
    for column, ddl in (
        ("equity", "REAL"), ("nav", "REAL"), ("equity_updated_at", "TEXT"), ("nav_updated_at", "TEXT"),
    ):
        if column not in runner_columns:
            conn.execute("ALTER TABLE runners ADD COLUMN " + column + " " + ddl)

    for row in accounts:
        conn.execute(
            "INSERT INTO accounts(id,name,broker,description,created_at) VALUES(?,?,?,?,?)",
            (_row_get(row, "id"), _row_get(row, "name", _row_get(row, "id")), _row_get(row, "broker", ""),
             _row_get(row, "description", ""), _row_get(row, "created_at", now)),
        )

    assigned = 0
    for row in accounts:
        runner_id = earliest.get(_row_get(row, "id"))
        if not runner_id:
            continue
        equity = _row_get(row, "equity")
        nav = _row_get(row, "nav")
        if equity is None and nav is None:
            continue
        conn.execute(
            "UPDATE runners SET equity = ?, nav = ?, equity_updated_at = ?, nav_updated_at = ? WHERE id = ?",
            (equity, nav, _row_get(row, "equity_updated_at"), _row_get(row, "nav_updated_at"), runner_id),
        )
        assigned += 1

    migrated_points = 0
    for row in account_points:
        runner_id = earliest.get(_row_get(row, "account_id"))
        if not runner_id:
            continue
        conn.execute(
            "INSERT INTO runner_equity_points(runner_id, ts, equity, nav, created_at) VALUES(?,?,?,?,?)",
            (runner_id, _row_get(row, "ts") or now, _row_get(row, "equity"), _row_get(row, "nav"),
             _row_get(row, "created_at") or now),
        )
        migrated_points += 1

    conn.execute("DROP TABLE legacy_v4_accounts")
    if _table_exists(conn, "legacy_v4_account_points"):
        conn.execute("DROP TABLE legacy_v4_account_points")
    _set_schema_version(conn, 5)
    logger.info(
        "v0.4 -> v0.5 迁移完成：accounts=%d assigned_runners=%d runner_equity_points=%d",
        len(accounts), assigned, migrated_points,
    )


def _upgrade_v02_to_v03(conn: sqlite3.Connection) -> None:
    """v0.2 库（runners 无 nav/equity 列）补齐 v0.3 表/列，随后迁移 v0.4。"""
    _exec_script(conn, V03_SCHEMA)
    columns = _columns(conn, "runners")
    for column, ddl in (
        ("nav", "REAL"), ("nav_updated_at", "TEXT"), ("equity", "REAL"), ("equity_updated_at", "TEXT"),
    ):
        if column not in columns:
            conn.execute("ALTER TABLE runners ADD COLUMN " + column + " " + ddl)
    _set_schema_version(conn, 3)


def init_db() -> None:
    """创建/迁移数据库；检测顺序保证 v0.5 库启动不会重复迁移。"""
    with connect() as conn:
        runner_columns = _columns(conn, "runners")
        account_columns = _columns(conn, "accounts")
        has_accounts = _table_exists(conn, "accounts")
        is_v5 = (
            has_accounts
            and "equity" in runner_columns
            and _table_exists(conn, "runner_equity_points")
            and "equity" not in account_columns
        )
        if is_v5:
            _exec_script(conn, SCHEMA)
            if _schema_version(conn) != SCHEMA_VERSION:
                _set_schema_version(conn, SCHEMA_VERSION)
            return
        try:
            if has_accounts and "equity" in account_columns:
                logger.info("检测到 v0.4 旧库，迁移到 v0.5：%s", str(DB_PATH))
                _migrate_v4_to_v5(conn)
            elif _table_exists(conn, "runners") and "equity" in runner_columns and "nav" not in runner_columns:
                logger.info("检测到 v0.1 旧库，开始迁移：%s", str(DB_PATH))
                _migrate_v01(conn, _load_legacy(conn))
                _migrate_v3_to_v4(conn)
                _migrate_v4_to_v5(conn)
            elif _table_exists(conn, "runners") and "nav" in runner_columns:
                logger.info("检测到 v0.3 旧库，迁移到 v0.5：%s", str(DB_PATH))
                _migrate_v3_to_v4(conn)
                _migrate_v4_to_v5(conn)
            elif _table_exists(conn, "runners"):
                logger.info("检测到 v0.2 旧库，升级到 v0.5：%s", str(DB_PATH))
                _upgrade_v02_to_v03(conn)
                _migrate_v3_to_v4(conn)
                _migrate_v4_to_v5(conn)
            else:
                _exec_script(conn, SCHEMA)
        except Exception as exc:  # noqa: BLE001
            logger.exception("旧库迁移失败，已回滚，请先备份 data/qwatch.db")
            raise RuntimeError("旧库迁移失败，已回滚；请备份 data/qwatch.db 后重试") from exc
        _exec_script(conn, SCHEMA)
        _set_schema_version(conn, SCHEMA_VERSION)
