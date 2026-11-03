"""SQLite 存储层：建表、连接、通用查询。"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("QWATCH_DB", ROOT / "data" / "qwatch.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  currency TEXT NOT NULL,
  initial_equity REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS runners (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  strategy TEXT NOT NULL,
  version TEXT NOT NULL,
  market TEXT NOT NULL,
  venue TEXT NOT NULL,
  platform TEXT NOT NULL,
  strategy_type TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'offline',
  accounts TEXT NOT NULL DEFAULT '[]',
  equity REAL NOT NULL DEFAULT 0,
  today_pnl REAL NOT NULL DEFAULT 0,
  initial_equity REAL NOT NULL DEFAULT 0,
  total_return_pct REAL NOT NULL DEFAULT 0,
  max_drawdown_pct REAL NOT NULL DEFAULT 0,
  sharpe REAL NOT NULL DEFAULT 0,
  win_rate REAL NOT NULL DEFAULT 0,
  uptime_30d REAL NOT NULL DEFAULT 0,
  heartbeat_interval INTEGER NOT NULL DEFAULT 30,
  demo INTEGER NOT NULL DEFAULT 0,
  last_seen TEXT,
  last_loop INTEGER,
  loop_same INTEGER NOT NULL DEFAULT 0,
  last_tick TEXT,
  last_msg TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS equity_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runner_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  equity REAL NOT NULL,
  pnl REAL,
  nav REAL
);
CREATE INDEX IF NOT EXISTS idx_equity_runner_ts ON equity_points(runner_id, ts);
CREATE TABLE IF NOT EXISTS cash_flows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runner_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'flow'
);
CREATE INDEX IF NOT EXISTS idx_cash_flows_runner_ts ON cash_flows(runner_id, ts);
CREATE TABLE IF NOT EXISTS tokens (
  id TEXT PRIMARY KEY,
  runner_id TEXT,
  name TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT '',
  markets TEXT NOT NULL DEFAULT '[]',
  strategy_type TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT '',
  token_hash TEXT NOT NULL UNIQUE,
  token_prefix TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  request_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  runner_id TEXT NOT NULL,
  direction TEXT NOT NULL,
  side TEXT NOT NULL,
  action TEXT NOT NULL,
  instrument TEXT NOT NULL,
  instrument_name TEXT NOT NULL,
  market TEXT NOT NULL,
  venue TEXT NOT NULL,
  account_id TEXT NOT NULL DEFAULT '',
  price REAL,
  qty REAL NOT NULL,
  amount REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  msg TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
CREATE INDEX IF NOT EXISTS idx_signals_runner ON signals(runner_id);
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
CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  webhook TEXT NOT NULL DEFAULT '',
  secret TEXT NOT NULL DEFAULT '',
  at_mobiles TEXT NOT NULL DEFAULT '[]',
  rate_limit_per_min INTEGER NOT NULL DEFAULT 15,
  last_test_at TEXT,
  last_test_ok INTEGER
);
CREATE TABLE IF NOT EXISTS calendars (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  timezone TEXT NOT NULL,
  sessions TEXT NOT NULL DEFAULT '[]',
  night INTEGER NOT NULL DEFAULT 0,
  holidays TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(runners)").fetchall()]
        if "description" not in columns:
            conn.execute("ALTER TABLE runners ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        if "demo" not in columns:
            conn.execute("ALTER TABLE runners ADD COLUMN demo INTEGER NOT NULL DEFAULT 0")
        flow_columns = [row["name"] for row in conn.execute("PRAGMA table_info(cash_flows)").fetchall()]
        if "kind" not in flow_columns:
            conn.execute("ALTER TABLE cash_flows ADD COLUMN kind TEXT NOT NULL DEFAULT 'flow'")
        equity_columns = [row["name"] for row in conn.execute("PRAGMA table_info(equity_points)").fetchall()]
        if "pnl" not in equity_columns:
            conn.execute("ALTER TABLE equity_points ADD COLUMN pnl REAL")
        if "nav" not in equity_columns:
            conn.execute("ALTER TABLE equity_points ADD COLUMN nav REAL")


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
