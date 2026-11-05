"""qwatch v0.6 后端：策略级权益 + 账户聚合 + 可信看门狗。

- accounts = 账户（策略的自然分组，不存权益真相）；runners = 策略（必须归属账户）
- processes = 策略下稳定进程（自动发现，可 retired）；token = 策略
- POST /api/v1/report 接收心跳/loop/msg/signal/equity/nav；equity/nav 写入策略（last-wins）
- 账户权益=策略权益求和，账户净值=按策略 equity 加权；曲线按策略曲线聚合
- 告警只有 P0：heartbeat_lost / runner_stalled，按策略汇总一条
- GET /api/v1/stream 为 SSE 实时事件（alert.* / process.updated / event.* / strategy.equity_updated / account.updated）
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import math
import os
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import notify, sse
from .db import DB_PATH, SCHEMA_VERSION, connect, dumps, get_setting, init_db, iso_now, loads, set_setting

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"
VERSION = "0.6.0"
PASSWORD = os.environ.get("QWATCH_PASSWORD", "qwatch")
SESSION_HOURS = 12
HEARTBEAT_TIMEOUT_S = 60
STALL_REPEAT = 3
WATCHDOG_INTERVAL_S = 5
# 后端重启后给策略进程一个重连窗口，避免启动瞬间把昨天的心跳判死并发送 P0
STARTUP_GRACE_S = 90
MAX_EVENTS_RETURN = 100

logging.basicConfig(
    level=os.environ.get("QWATCH_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("qwatch")

app = FastAPI(title="qwatch", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()

LOGIN_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)
LOGIN_LOCK = threading.Lock()


# ---------- 通用工具 ----------

def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def dt_from(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_iso(value: str) -> str:
    ts = dt_from(value)
    if not ts:
        raise HTTPException(status_code=400, detail="ts 不是合法时间")
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_prefix(token: str) -> str:
    return "qw_" + token[3:7] + "…" + token[-4:]


def new_alert_id() -> str:
    return "alert_" + uuid.uuid4().hex[:10]


def fingerprint(rule: str, runner_id: str) -> str:
    return "fp_" + hashlib.sha256((rule + ":" + runner_id).encode()).hexdigest()[:12]


def require_number(value: Any, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(status_code=400, detail=field + " 必须是数字")
    number = float(value)
    if not math.isfinite(number):
        raise HTTPException(status_code=400, detail=field + " 必须是有限数字")
    if minimum is not None and number < minimum:
        raise HTTPException(status_code=400, detail=field + " 不能小于 " + str(minimum))
    return number


def mask_webhook(url: str) -> str:
    if not url:
        return "未配置"
    return re.sub(r"(access_token=)([^&]+)", lambda m: m.group(1) + "****" + m.group(2)[-4:], url)


def mask_secret(secret: str) -> str:
    if not secret:
        return "未配置"
    return "SEC****" + secret[-4:]


# ---------- 鉴权 ----------

def _session_user(token: str) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    hashed = token_hash(token)
    with connect() as conn:
        row = conn.execute("SELECT user, expires_at FROM sessions WHERE token_hash = ?", (hashed,)).fetchone()
    if not row or row["expires_at"] <= iso_now():
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return row["user"]


def require_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return _session_user(authorization[7:].strip())


def strategy_token(conn, authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="token 无效或已吊销")
    hashed = token_hash(authorization[7:].strip())
    token = conn.execute("SELECT * FROM tokens WHERE token_hash = ? AND status = 'active'", (hashed,)).fetchone()
    if not token:
        raise HTTPException(status_code=401, detail="token 无效或已吊销")
    runner = conn.execute("SELECT * FROM runners WHERE id = ?", (token["runner_id"],)).fetchone()
    if not runner:
        raise HTTPException(status_code=401, detail="token 未绑定有效策略")
    return token, runner


def _purge_expired_sessions(conn) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (iso_now(),))


# ---------- 序列化 ----------

def process_status(row, at: datetime, group_paused: bool) -> str:
    if row["retired"]:
        return "offline"
    if group_paused:
        return "paused"
    last = dt_from(row["last_seen"])
    if not last or (at - last).total_seconds() > HEARTBEAT_TIMEOUT_S:
        return "offline"
    if int(row["loop_same"] or 0) >= STALL_REPEAT:
        return "degraded"
    return "running"


def process_view(row, status: str | None = None, at: datetime | None = None, group_paused: bool = False) -> dict[str, Any]:
    at = at or now_dt()
    state = status or process_status(row, at, group_paused)
    return {
        "name": row["name"],
        "status": state,
        "last_seen": row["last_seen"],
        "loop": row["last_loop"],
        "retired": bool(row["retired"]),
    }


def _runner_state(runner, processes, statuses: dict[int, str]) -> dict[str, Any]:
    paused = bool(runner["paused"])
    active = [p for p in processes if not p["retired"]]
    online = sum(1 for p in active if statuses[p["id"]] == "running")
    last_seen_values = [p["last_seen"] for p in active if p["last_seen"]]
    last_seen = max(last_seen_values) if last_seen_values else None
    if paused:
        status = "paused"
    elif not active or online == 0:
        status = "offline"
    elif online < len(active):
        status = "degraded"
    else:
        status = "running"
    return {
        "status": status,
        "process_count": len(active),
        "online_processes": online,
        "active_processes": len(active),
        "retired_processes": len(processes) - len(active),
        "last_seen": last_seen,
    }


def runner_view(runner, processes, statuses: dict[int, str], account=None) -> dict[str, Any]:
    state = _runner_state(runner, processes, statuses)
    keys = set(runner.keys())
    return {
        "id": runner["id"],
        "name": runner["name"],
        "description": runner["description"] or "",
        "status": state["status"],
        "process_count": state["process_count"],
        "online_processes": state["online_processes"],
        "last_seen": state["last_seen"],
        "last_msg": runner["last_msg"] or "",
        "account_id": runner["account_id"] if "account_id" in keys else "",
        "account_name": account["name"] if account else "",
        "account_broker": (account["broker"] or "") if account else "",
        "equity": _fmt_money(runner["equity"]) if "equity" in keys else None,
        "equity_updated_at": runner["equity_updated_at"] if "equity_updated_at" in keys else None,
        "created_at": runner["created_at"],
    }


def _fmt_money(value) -> str | None:
    return f"{float(value):.2f}" if value is not None else None


def _fmt_nav(value) -> str | None:
    return f"{float(value):.6f}" if value is not None else None


def runner_equity_curve(conn: sqlite3.Connection, runner_id: str, limit: int = 1000) -> list[dict[str, str]]:
    rows = list(conn.execute(
        "SELECT ts, equity FROM runner_equity_points WHERE runner_id = ? AND equity IS NOT NULL "
        "ORDER BY id DESC LIMIT ?",
        (runner_id, limit),
    ))
    return [{"ts": row["ts"], "value": _fmt_money(row["equity"])} for row in reversed(rows)]


def _strategy_series(conn: sqlite3.Connection, runner_ids: list[str], per_limit: int = 500) -> dict[str, list[tuple[str, float]]]:
    per: dict[str, list[tuple[str, float]]] = {}
    for runner_id in runner_ids:
        rows = conn.execute(
            "SELECT ts, equity FROM runner_equity_points WHERE runner_id = ? AND equity IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (runner_id, per_limit),
        ).fetchall()
        if rows:
            per[runner_id] = [(row["ts"], float(row["equity"])) for row in reversed(rows)]
    return per


def merged_equity_curve(conn: sqlite3.Connection, runner_ids: list[str], limit: int = 1000) -> list[dict[str, str]]:
    """把多个策略的权益曲线按时间合并求和（前向填充，尚未上报的策略按 0 计）。"""
    per = _strategy_series(conn, runner_ids)
    if not per:
        return []
    timeline = sorted({ts for series in per.values() for ts, _ in series})
    latest: dict[str, float] = {}
    pointers: dict[str, int] = {runner_id: 0 for runner_id in per}
    curve: list[dict[str, str]] = []
    for ts in timeline:
        for runner_id, series in per.items():
            idx = pointers[runner_id]
            while idx < len(series) and series[idx][0] <= ts:
                latest[runner_id] = series[idx][1]
                idx += 1
            pointers[runner_id] = idx
        if latest:
            curve.append({"ts": ts, "value": f"{sum(latest.values()):.2f}"})
    return curve[-limit:]


def account_equity_curve(conn: sqlite3.Connection, account_id: str, limit: int = 1000) -> list[dict[str, str]]:
    runner_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM runners WHERE account_id = ? ORDER BY created_at", (account_id,)
    )]
    return merged_equity_curve(conn, runner_ids, limit)


def daily_equity_curve(conn: sqlite3.Connection, runner_ids: list[str]) -> list[dict[str, str]]:
    """从日权益表读取长期曲线，按日求和；不再扫全量原始点。"""
    if not runner_ids:
        return []
    placeholders = ",".join("?" for _ in runner_ids)
    rows = conn.execute(
        "SELECT runner_id, day, equity FROM runner_daily_equity WHERE runner_id IN (" + placeholders + ") ORDER BY day",
        runner_ids,
    ).fetchall()
    per: dict[str, dict[str, float]] = {}
    for row in rows:
        per.setdefault(row["runner_id"], {})[row["day"]] = float(row["equity"])
    if not per:
        return []
    days = sorted({day for values in per.values() for day in values})
    latest: dict[str, float] = {}
    curve: list[dict[str, str]] = []
    for day in days:
        for runner_id, values in per.items():
            if day in values:
                latest[runner_id] = values[day]
        if latest:
            curve.append({"ts": day + "T00:00:00Z", "value": f"{sum(latest.values()):.2f}"})
    return curve


def runner_today_pnl(conn: sqlite3.Connection, runner, today_start: str) -> float | None:
    equity = runner["equity"] if "equity" in runner.keys() else None
    if equity is None:
        return None
    prev = conn.execute(
        "SELECT equity FROM runner_equity_points WHERE runner_id = ? AND equity IS NOT NULL AND ts < ? "
        "ORDER BY id DESC LIMIT 1",
        (runner["id"], today_start),
    ).fetchone()
    if prev is None:
        prev = conn.execute(
            "SELECT equity FROM runner_equity_points WHERE runner_id = ? AND equity IS NOT NULL AND ts >= ? "
            "ORDER BY id ASC LIMIT 1",
            (runner["id"], today_start),
        ).fetchone()
    if prev is None or prev["equity"] is None:
        return None
    return float(equity) - float(prev["equity"])


def _today_start_iso() -> str:
    return datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()


def _last_seven_days() -> list[str]:
    today = datetime.now().astimezone().date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]


def _daily_last_values(rows) -> dict[str, float]:
    by_day: dict[str, float] = {}
    for row in rows:
        dt = dt_from(row["ts"])
        if dt is not None:
            by_day[dt.astimezone().date().isoformat()] = float(row["value"])
    return by_day


def strategy_equity_sparkline(conn: sqlite3.Connection, runner_id: str) -> list[float]:
    """最近 7 天日权益。"""
    rows = conn.execute(
        "SELECT day, equity FROM runner_daily_equity WHERE runner_id = ? ORDER BY day DESC LIMIT 7",
        (runner_id,),
    ).fetchall()
    return [round(float(row["equity"]), 2) for row in reversed(rows)]


def _health_bucket_starts() -> list[tuple[str, str]]:
    """28 个 6 小时桶，覆盖最近 7 天。"""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    current = now.replace(hour=(now.hour // 6) * 6)
    buckets = []
    for offset in range(27, -1, -1):
        start = current - timedelta(hours=6 * offset)
        buckets.append((
            start.isoformat().replace("+00:00", "Z"),
            (start + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        ))
    return buckets


def _health_stats(conn: sqlite3.Connection, process_ids: list[int]) -> tuple[list[dict[str, Any]], float | None]:
    if not process_ids:
        return [], None
    starts = _health_bucket_starts()
    placeholders = ",".join("?" for _ in process_ids)
    rows = conn.execute(
        "SELECT bucket_start, SUM(up_samples) AS up, SUM(total_samples) AS total "
        "FROM process_health_bucket WHERE process_id IN (" + placeholders + ") AND bucket_start >= ? "
        "GROUP BY bucket_start",
        [*process_ids, starts[0][0]],
    ).fetchall()
    by_bucket = {row["bucket_start"]: (int(row["up"] or 0), int(row["total"] or 0)) for row in rows}
    buckets = []
    total_up = total_samples = 0
    for start, end in starts:
        up, total = by_bucket.get(start, (0, 0))
        total_up += up
        total_samples += total
        buckets.append({"start": start, "end": end, "ratio": round(up / total, 4) if total else None})
    uptime = round(total_up / total_samples * 100, 2) if total_samples else None
    return buckets, uptime


def process_heartbeat_history(conn: sqlite3.Connection, process_id: int) -> list[dict[str, Any]]:
    return _health_stats(conn, [process_id])[0]


def runner_heartbeat_history(conn: sqlite3.Connection, runner_id: str) -> list[dict[str, Any]]:
    process_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM processes WHERE runner_id = ? AND retired = 0", (runner_id,)
    )]
    return _health_stats(conn, process_ids)[0]


def runner_uptime_7d(conn: sqlite3.Connection, runner_id: str) -> float | None:
    process_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM processes WHERE runner_id = ? AND retired = 0", (runner_id,)
    )]
    return _health_stats(conn, process_ids)[1]


def account_equity_sparkline(conn: sqlite3.Connection, account_id: str) -> list[float]:
    runner_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM runners WHERE account_id = ? ORDER BY created_at", (account_id,)
    )]
    curve = daily_equity_curve(conn, runner_ids)
    return [round(float(point["value"]), 2) for point in curve[-7:]]


def account_view(conn: sqlite3.Connection, row, strategy_views: list[dict[str, Any]] | None = None,
                 with_sparkline: bool = True) -> dict[str, Any]:
    strategies = strategy_views or []
    online = sum(1 for item in strategies if item["status"] == "running")
    equities = [float(item["equity"]) for item in strategies if item.get("equity") is not None]
    total_equity = sum(equities) if equities else None
    updated_values = [item.get("equity_updated_at") for item in strategies if item.get("equity_updated_at")]
    pnl_values = [float(item["today_pnl"]) for item in strategies if item.get("today_pnl") is not None]
    today_pnl = sum(pnl_values) if pnl_values else None
    return {
        "id": row["id"],
        "name": row["name"],
        "broker": row["broker"] or "",
        "description": row["description"] or "",
        "equity": _fmt_money(total_equity),
        "today_pnl": _fmt_money(today_pnl),
        "equity_updated_at": max(updated_values) if updated_values else None,
        "strategy_count": len(strategies),
        "online_strategies": online,
        "equity_sparkline": account_equity_sparkline(conn, row["id"]) if with_sparkline else [],
        "created_at": row["created_at"],
    }


def _runner_views(conn: sqlite3.Connection, runner_rows, processes_by_runner, accounts_by_id) -> dict[str, list[dict[str, Any]]]:
    """按账户分组构造 Runner 视图（供 /accounts 与 overview 复用）。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    today_start = _today_start_iso()
    for runner in runner_rows:
        rows = processes_by_runner.get(runner["id"], [])
        statuses = {row["id"]: process_status(row, now_dt(), bool(runner["paused"])) for row in rows}
        account = accounts_by_id.get(runner["account_id"] if "account_id" in runner.keys() else "")
        view = runner_view(runner, rows, statuses, account)
        view["equity_sparkline"] = strategy_equity_sparkline(conn, runner["id"])
        view["heartbeat_7d"] = runner_heartbeat_history(conn, runner["id"])
        view["uptime_7d"] = runner_uptime_7d(conn, runner["id"])
        view["today_pnl"] = _fmt_money(runner_today_pnl(conn, runner, today_start))
        grouped[runner["account_id"] if "account_id" in runner.keys() else ""].append(view)
    return grouped


def event_view(row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": row["id"],
        "ts": row["ts"],
        "type": row["type"],
        "instrument": row["instrument"],
        "text": row["text"],
        "symbol": row["symbol"],
        "direction": row["direction"],
        "action": row["action"],
        "qty": row["qty"],
        "price": row["price"],
        "amount": row["amount"],
        "runner_id": row["runner_id"] if "runner_id" in keys else None,
        "runner_name": row["runner_name"] if "runner_name" in keys else None,
    }


def alert_view(row, runner_name: str | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "fingerprint": row["fingerprint"],
        "rule": row["rule"],
        "severity": row["severity"],
        "status": row["status"],
        "runner_id": row["runner_id"],
        "runner_name": runner_name or row["runner_id"],
        "summary": row["summary"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "acked_at": row["acked_at"],
        "labels": loads(row["labels"], {}),
        "updated_at": row["updated_at"],
    }


def channel_view(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "enabled": bool(row["enabled"]),
        "webhook_masked": mask_webhook(row["webhook"]),
        "secret_masked": mask_secret(row["secret"]),
        "last_test_at": row["last_test_at"],
        "last_test_ok": None if row["last_test_ok"] is None else bool(row["last_test_ok"]),
    }


def token_view(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "runner_id": row["runner_id"],
        "name": row["name"],
        "token_prefix": row["token_prefix"],
        "status": row["status"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
        "request_count": row["request_count"],
    }


def _load_state(conn, runner_id: str):
    runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
    if not runner:
        return None
    at = now_dt()
    processes = conn.execute("SELECT * FROM processes WHERE runner_id = ? ORDER BY name", (runner_id,)).fetchall()
    statuses = {row["id"]: process_status(row, at, bool(runner["paused"])) for row in processes}
    state = _runner_state(runner, processes, statuses)
    return runner, list(processes), statuses, state


# ---------- 进程 / 状态 / 告警 ----------

def _ensure_process(conn, runner, name: str, at: datetime):
    now = iso_now()
    row = conn.execute("SELECT * FROM processes WHERE runner_id = ? AND name = ?", (runner["id"], name)).fetchone()
    if row:
        conn.execute("UPDATE processes SET last_seen = ?, updated_at = ? WHERE id = ?", (now, now, row["id"]))
        return conn.execute("SELECT * FROM processes WHERE id = ?", (row["id"],)).fetchone()
    conn.execute(
        "INSERT INTO processes(runner_id, name, last_seen, loop_same, status, retired, created_at, updated_at) "
        "VALUES(?,?,?,0,'offline',0,?,?)",
        (runner["id"], name, now, now, now),
    )
    return conn.execute("SELECT * FROM processes WHERE runner_id = ? AND name = ?", (runner["id"], name)).fetchone()


def _publish_process(conn, runner, process_row, state: dict[str, Any]) -> None:
    sse.publish({
        "type": "process.updated",
        "ts": iso_now(),
        "runner_id": runner["id"],
        "runner_status": state["status"],
        "process": process_view(process_row, at=now_dt(), group_paused=bool(runner["paused"])),
    })


def _alert_summary(runner, rule: str, names: list[str]) -> str:
    shown = "、".join(names[:5]) + ("等" if len(names) > 5 else "")
    if rule == "heartbeat_lost":
        return "策略 " + runner["name"] + " 下 " + str(len(names)) + " 个进程心跳丢失（" + shown + "）"
    return "策略 " + runner["name"] + " 的进程 " + shown + " loop 连续 " + str(STALL_REPEAT) + " 次未增长"


def _alert_labels(rule: str, names: list[str]) -> dict[str, Any]:
    if rule == "heartbeat_lost":
        return {"timeout_s": str(HEARTBEAT_TIMEOUT_S), "processes": names[:20]}
    return {"stall_repeat": str(STALL_REPEAT), "processes": names[:20]}


def _sync_alert(conn, runner, rule: str, names: list[str], publish: bool) -> None:
    existing = conn.execute(
        "SELECT * FROM alerts WHERE runner_id = ? AND rule = ? AND status != 'resolved' "
        "ORDER BY starts_at DESC LIMIT 1",
        (runner["id"], rule),
    ).fetchone()
    now = iso_now()
    if names:
        summary = _alert_summary(runner, rule, names)
        merged_labels = _alert_labels(rule, names)
        if existing:
            old_labels = loads(existing["labels"], {})
            if old_labels.get("silenced_until"):
                merged_labels["silenced_until"] = old_labels["silenced_until"]
        labels = dumps(merged_labels)
        if existing:
            if existing["summary"] != summary or existing["labels"] != labels:
                conn.execute(
                    "UPDATE alerts SET summary = ?, labels = ?, updated_at = ? WHERE id = ?",
                    (summary, labels, now, existing["id"]),
                )
                row = conn.execute("SELECT * FROM alerts WHERE id = ?", (existing["id"],)).fetchone()
                if publish:
                    sse.publish({"type": "alert.updated", "ts": now, "alert": alert_view(row, runner["name"])})
            return
        record_id = new_alert_id()
        conn.execute(
            "INSERT INTO alerts(id, fingerprint, rule, severity, status, runner_id, summary, starts_at, ends_at, "
            "acked_at, labels, updated_at) VALUES(?,?,?,?,'firing',?,?,?,NULL,NULL,?,?)",
            (record_id, fingerprint(rule, runner["id"]), rule, "P0", runner["id"], summary, now, labels, now),
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (record_id,)).fetchone()
        notify.enqueue_for_alert(conn, row)
        logger.warning("P0 告警触发 %s runner=%s: %s", rule, runner["id"], summary)
        if publish:
            sse.publish({"type": "alert.firing", "ts": now, "alert": alert_view(row, runner["name"])})
        return
    if existing:
        conn.execute(
            "UPDATE alerts SET status = 'resolved', ends_at = ?, updated_at = ? WHERE id = ?",
            (now, now, existing["id"]),
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (existing["id"],)).fetchone()
        notify.cancel_pending_deliveries(conn, existing["id"])
        notify.enqueue_recovery(conn, row)
        logger.info("P0 告警恢复 %s runner=%s", rule, runner["id"])
        if publish:
            sse.publish({"type": "alert.resolved", "ts": now, "alert": alert_view(row, runner["name"])})


def refresh_runner_state(conn, runner_id: str, publish: bool = True) -> dict[str, Any] | None:
    loaded = _load_state(conn, runner_id)
    if loaded is None:
        return None
    runner, processes, statuses, state = loaded
    at = now_dt()
    for row in processes:
        if row["status"] != statuses[row["id"]]:
            conn.execute(
                "UPDATE processes SET status = ?, updated_at = ? WHERE id = ?",
                (statuses[row["id"]], iso_now(), row["id"]),
            )
            if publish:
                _publish_process(conn, runner, row, state)
    if runner["paused"]:
        return state
    active = [row for row in processes if not row["retired"]]
    stale = [row["name"] for row in active if statuses[row["id"]] == "offline"]
    stalled = [row["name"] for row in active if statuses[row["id"]] == "degraded"]
    _sync_alert(conn, runner, "heartbeat_lost", stale, publish)
    _sync_alert(conn, runner, "runner_stalled", stalled, publish)
    return state


def _resolve_runner_alerts(conn, runner) -> None:
    rows = conn.execute(
        "SELECT * FROM alerts WHERE runner_id = ? AND status != 'resolved'", (runner["id"],)
    ).fetchall()
    now = iso_now()
    for row in rows:
        conn.execute(
            "UPDATE alerts SET status = 'resolved', ends_at = ?, updated_at = ? WHERE id = ?",
            (now, now, row["id"]),
        )
        updated = conn.execute("SELECT * FROM alerts WHERE id = ?", (row["id"],)).fetchone()
        notify.cancel_pending_deliveries(conn, row["id"], "策略暂停，取消投递")
        sse.publish({"type": "alert.resolved", "ts": now, "alert": alert_view(updated, runner["name"])})


# ---------- 路由：健康检查 ----------

@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "qwatch", "version": VERSION, "schema_version": SCHEMA_VERSION}


# ---------- 路由：鉴权 ----------

@app.post("/api/v1/auth/login")
def login(request: Request, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "local"
    current = time.monotonic()
    password = str(payload.get("password", ""))
    correct = hmac.compare_digest(password, PASSWORD)
    with LOGIN_LOCK:
        attempts = LOGIN_ATTEMPTS[client_ip]
        while attempts and current - attempts[0] > 60:
            attempts.popleft()
        if correct:
            attempts.clear()
        else:
            attempts.append(current)
            if len(attempts) >= 5:
                raise HTTPException(status_code=429, detail="登录尝试过多，请稍后再试")
            raise HTTPException(status_code=401, detail="密码错误")
    token = secrets.token_urlsafe(32)
    expires = (now_dt() + timedelta(hours=SESSION_HOURS)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with connect() as conn:
        _purge_expired_sessions(conn)
        conn.execute("INSERT INTO sessions(token_hash,user,expires_at) VALUES(?,?,?)", (token_hash(token), "Trader", expires))
    logger.info("登录成功：ip=%s", client_ip)
    return {"token": token, "user": {"name": "Trader", "role": "owner"}}


@app.get("/api/v1/auth/me")
def me(user: str = Depends(require_user)) -> dict[str, Any]:
    return {"user": {"name": user, "role": "owner"}}


@app.post("/api/v1/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if authorization and authorization.startswith("Bearer "):
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(authorization[7:].strip()),))
    return {"ok": True}


# ---------- 路由：账户 ----------

def _account_or_404(conn, account_id: str):
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="账户不存在")
    return row


def _account_strategy_views(conn, account_id: str) -> list[dict[str, Any]]:
    account = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    runners = conn.execute("SELECT * FROM runners WHERE account_id = ? ORDER BY created_at", (account_id,)).fetchall()
    processes = conn.execute("SELECT * FROM processes ORDER BY name").fetchall()
    by_runner: dict[str, list[Any]] = defaultdict(list)
    for row in processes:
        by_runner[row["runner_id"]].append(row)
    views: list[dict[str, Any]] = []
    today_start = _today_start_iso()
    for runner in runners:
        rows = by_runner.get(runner["id"], [])
        statuses = {row["id"]: process_status(row, now_dt(), bool(runner["paused"])) for row in rows}
        view = runner_view(runner, rows, statuses, account)
        view["equity_sparkline"] = strategy_equity_sparkline(conn, runner["id"])
        view["heartbeat_7d"] = runner_heartbeat_history(conn, runner["id"])
        view["uptime_7d"] = runner_uptime_7d(conn, runner["id"])
        view["today_pnl"] = _fmt_money(runner_today_pnl(conn, runner, today_start))
        views.append(view)
    return views


@app.get("/api/v1/accounts")
def list_accounts(user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        accounts = conn.execute("SELECT * FROM accounts ORDER BY created_at").fetchall()
        runner_rows = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        process_rows = conn.execute("SELECT * FROM processes ORDER BY name").fetchall()
        by_runner: dict[str, list[Any]] = defaultdict(list)
        for row in process_rows:
            by_runner[row["runner_id"]].append(row)
        accounts_by_id = {row["id"]: row for row in accounts}
        grouped = _runner_views(conn, runner_rows, by_runner, accounts_by_id)
        items = [account_view(conn, row, grouped.get(row["id"], [])) for row in accounts]
        return {"items": items, "total": len(items)}


@app.post("/api/v1/accounts")
def create_account(payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    broker = str(payload.get("broker") or "").strip()
    description = str(payload.get("description") or "").strip()[:300]
    if not name:
        raise HTTPException(status_code=400, detail="账户名称必填")
    account_id = "account-" + uuid.uuid4().hex[:8]
    created = iso_now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO accounts(id,name,broker,description,created_at) VALUES(?,?,?,?,?)",
            (account_id, name[:80], broker[:80], description, created),
        )
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        logger.info("创建账户 %s/%s (%s)", name, broker, account_id)
        return {"account": account_view(conn, row, [], with_sparkline=False)}


@app.patch("/api/v1/accounts/{account_id}")
def update_account(account_id: str, payload: dict[str, Any] = Body(default={}),
                   user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = _account_or_404(conn, account_id)
        name = str(payload.get("name")).strip() if "name" in payload else row["name"]
        broker = str(payload.get("broker")).strip() if "broker" in payload else row["broker"]
        description = str(payload.get("description")).strip()[:300] if "description" in payload else row["description"]
        if not name:
            raise HTTPException(status_code=400, detail="账户名称不能为空")
        if not broker:
            raise HTTPException(status_code=400, detail="券商不能为空")
        conn.execute("UPDATE accounts SET name = ?, broker = ?, description = ? WHERE id = ?",
                     (name[:80], broker[:80], description, account_id))
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        views = _account_strategy_views(conn, account_id)
        logger.info("更新账户 %s", account_id)
        return {"account": account_view(conn, row, views)}


@app.get("/api/v1/accounts/{account_id}")
def account_detail(account_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = _account_or_404(conn, account_id)
        strategies = _account_strategy_views(conn, account_id)
        return {"account": account_view(conn, row, strategies), "strategies": strategies}


@app.get("/api/v1/accounts/{account_id}/equity_curve")
def account_equity_curve_endpoint(account_id: str, user: str = Depends(require_user)) -> list[dict[str, str]]:
    """账户聚合权益曲线：该账户下各策略 equity 曲线按时间相加。"""
    with connect() as conn:
        _account_or_404(conn, account_id)
        return account_equity_curve(conn, account_id)


# ---------- 路由：策略组 ----------

@app.post("/api/v1/runners")
def create_runner(payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="策略名称必填")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="策略名称过长")
    description = str(payload.get("description") or "").strip()[:300]
    platform = str(payload.get("platform") or "").strip()[:32]
    market = str(payload.get("market") or "").strip()[:32]
    strategy_type = str(payload.get("strategy_type") or "").strip()[:32]
    raw_tags = payload.get("tags")
    tags = [str(tag).strip()[:32] for tag in raw_tags if str(tag).strip()][:8] if isinstance(raw_tags, list) else []
    account_id = str(payload.get("account_id") or "").strip()
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id 必填（策略必须归属账户）")
    with connect() as conn:
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not account:
            raise HTTPException(status_code=400, detail="账户不存在")
        if conn.execute("SELECT 1 FROM runners WHERE name = ?", (name,)).fetchone():
            raise HTTPException(status_code=400, detail="策略名称已存在")
        runner_id = "runner-" + uuid.uuid4().hex[:8]
        created = iso_now()
        conn.execute(
            "INSERT INTO runners(id, name, description, platform, market, strategy_type, tags, paused, account_id, "
            "created_at) VALUES(?,?,?,?,?,?,?,0,?,?)",
            (runner_id, name, description, platform, market, strategy_type, dumps(tags), account_id, created),
        )
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
    logger.info("创建策略 %s (%s) -> 账户 %s", name, runner_id, account_id)
    return {"runner": runner_view(runner, [], {}, account)}


@app.patch("/api/v1/runners/{runner_id}")
def update_runner(runner_id: str, payload: dict[str, Any] = Body(default={}),
                  user: str = Depends(require_user)) -> dict[str, Any]:
    """更新策略基础信息或改绑账户（账户迁移需要）。"""
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        if not runner:
            raise HTTPException(status_code=404, detail="策略不存在")
        name = runner["name"]
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name or len(name) > 80:
                raise HTTPException(status_code=400, detail="策略名称无效")
            duplicate = conn.execute("SELECT 1 FROM runners WHERE name = ? AND id != ?", (name, runner_id)).fetchone()
            if duplicate:
                raise HTTPException(status_code=400, detail="策略名称已存在")
        description = str(payload.get("description", runner["description"]) or "").strip()[:300]
        account_id = str(payload.get("account_id", runner["account_id"]) or "").strip()
        account = _account_or_404(conn, account_id)
        conn.execute(
            "UPDATE runners SET name = ?, description = ?, account_id = ? WHERE id = ?",
            (name, description, account_id, runner_id),
        )
        updated = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        processes = conn.execute("SELECT * FROM processes WHERE runner_id = ?", (runner_id,)).fetchall()
        statuses = {row["id"]: process_status(row, now_dt(), bool(updated["paused"])) for row in processes}
        old_account = conn.execute("SELECT * FROM accounts WHERE id = ?", (runner["account_id"],)).fetchone()
        now = iso_now()
        sse.publish({"type": "account.updated", "ts": now, "account_id": account_id})
        if old_account and old_account["id"] != account_id:
            sse.publish({"type": "account.updated", "ts": now, "account_id": old_account["id"]})
    logger.info("更新策略 %s (%s) -> 账户 %s", name, runner_id, account_id)
    return {"runner": runner_view(updated, processes, statuses, account)}

@app.get("/api/v1/runners")
def list_runners(
    status: str | None = Query(default=None), q: str | None = Query(default=None),
    account_id: str | None = Query(default=None), user: str = Depends(require_user),
) -> dict[str, Any]:
    with connect() as conn:
        runners = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        processes = conn.execute("SELECT * FROM processes ORDER BY name").fetchall()
        accounts = conn.execute("SELECT * FROM accounts").fetchall()
        accounts_by_id = {row["id"]: row for row in accounts}
        by_runner: dict[str, list[Any]] = defaultdict(list)
        for row in processes:
            by_runner[row["runner_id"]].append(row)
        items = []
        for runner in runners:
            if account_id and runner["account_id"] != account_id:
                continue
            rows = by_runner.get(runner["id"], [])
            statuses = {row["id"]: process_status(row, now_dt(), bool(runner["paused"])) for row in rows}
            view = runner_view(runner, rows, statuses, accounts_by_id.get(runner["account_id"]))
            view["equity_sparkline"] = strategy_equity_sparkline(conn, runner["id"])
            view["heartbeat_7d"] = runner_heartbeat_history(conn, runner["id"])
            view["uptime_7d"] = runner_uptime_7d(conn, runner["id"])
            view["today_pnl"] = _fmt_money(runner_today_pnl(conn, runner, _today_start_iso()))
            items.append(view)
    if status:
        items = [item for item in items if item["status"] == status]
    if q:
        needle = q.lower()
        items = [item for item in items if needle in (item["name"] + item["description"] + item["id"]).lower()]
    return {"items": items, "total": len(items)}


@app.get("/api/v1/runners/{runner_id}")
def runner_detail(runner_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        loaded = _load_state(conn, runner_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        runner, processes, statuses, state = loaded
        at = now_dt()
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (runner["account_id"],)).fetchone()
        events = conn.execute(
            "SELECT * FROM events WHERE runner_id = ? ORDER BY id DESC LIMIT ?", (runner_id, MAX_EVENTS_RETURN)
        ).fetchall()
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE runner_id = ? ORDER BY starts_at DESC LIMIT 50", (runner_id,)
        ).fetchall()
        strategy_views = _account_strategy_views(conn, runner["account_id"]) if account else []
        runner_data = runner_view(runner, processes, statuses, account)
        runner_data["equity_sparkline"] = strategy_equity_sparkline(conn, runner_id)
        runner_data["heartbeat_7d"] = runner_heartbeat_history(conn, runner_id)
        runner_data["uptime_7d"] = runner_uptime_7d(conn, runner_id)
        runner_data["today_pnl"] = _fmt_money(runner_today_pnl(conn, runner, _today_start_iso()))
        return {
            "runner": runner_data,
            "account": account_view(conn, account, strategy_views) if account else None,
            "processes": [
                {**process_view(row, statuses[row["id"]], at, bool(runner["paused"])),
                 "heartbeat_7d": process_heartbeat_history(conn, row["id"])}
                for row in processes
            ],
            "events": [event_view(row) for row in events],
            "alerts": [alert_view(row, runner["name"]) for row in alerts],
            "equity_curve": runner_equity_curve(conn, runner_id),
        }


@app.post("/api/v1/runners/{runner_id}/pause")
def pause_runner(runner_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        if not runner:
            raise HTTPException(status_code=404, detail="策略不存在")
        conn.execute("UPDATE runners SET paused = 1 WHERE id = ?", (runner_id,))
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        _resolve_runner_alerts(conn, runner)
        loaded = _load_state(conn, runner_id)
        assert loaded is not None
        runner, processes, statuses, state = loaded
        for row in processes:
            _publish_process(conn, runner, row, state)
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (runner["account_id"],)).fetchone()
        logger.info("暂停策略 %s", runner_id)
        return {"runner": runner_view(runner, processes, statuses, account)}


@app.post("/api/v1/runners/{runner_id}/resume")
def resume_runner(runner_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        if not runner:
            raise HTTPException(status_code=404, detail="策略不存在")
        conn.execute("UPDATE runners SET paused = 0 WHERE id = ?", (runner_id,))
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        refresh_runner_state(conn, runner_id, publish=True)
        loaded = _load_state(conn, runner_id)
        assert loaded is not None
        runner, processes, statuses, state = loaded
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (runner["account_id"],)).fetchone()
        logger.info("恢复策略 %s", runner_id)
        return {"runner": runner_view(runner, processes, statuses, account)}


@app.post("/api/v1/runners/{runner_id}/processes/{name}/retire")
def retire_process(runner_id: str, name: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        if not runner:
            raise HTTPException(status_code=404, detail="策略不存在")
        row = conn.execute("SELECT * FROM processes WHERE runner_id = ? AND name = ?", (runner_id, name)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="进程不存在")
        conn.execute(
            "UPDATE processes SET retired = 1, retired_at = ?, updated_at = ? WHERE id = ?",
            (iso_now(), iso_now(), row["id"]),
        )
        refresh_runner_state(conn, runner_id, publish=True)
        loaded = _load_state(conn, runner_id)
        assert loaded is not None
        runner, processes, statuses, state = loaded
        updated = conn.execute("SELECT * FROM processes WHERE id = ?", (row["id"],)).fetchone()
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (runner["account_id"],)).fetchone()
        logger.info("停用进程 %s/%s", runner_id, name)
        return {
            "runner": runner_view(runner, processes, statuses, account),
            "process": process_view(updated, statuses.get(row["id"]), now_dt(), bool(runner["paused"])),
        }


@app.post("/api/v1/runners/{runner_id}/processes/{name}/activate")
def activate_process(runner_id: str, name: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        if not runner:
            raise HTTPException(status_code=404, detail="策略不存在")
        row = conn.execute("SELECT * FROM processes WHERE runner_id = ? AND name = ?", (runner_id, name)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="进程不存在")
        now = iso_now()
        conn.execute(
            "UPDATE processes SET retired = 0, retired_at = NULL, last_seen = ?, updated_at = ? WHERE id = ?",
            (now, now, row["id"]),
        )
        refresh_runner_state(conn, runner_id, publish=True)
        loaded = _load_state(conn, runner_id)
        assert loaded is not None
        runner, processes, statuses, state = loaded
        updated = conn.execute("SELECT * FROM processes WHERE id = ?", (row["id"],)).fetchone()
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (runner["account_id"],)).fetchone()
        logger.info("启用进程 %s/%s", runner_id, name)
        return {
            "runner": runner_view(runner, processes, statuses, account),
            "process": process_view(updated, statuses.get(row["id"]), now_dt(), bool(runner["paused"])),
        }


# ---------- 路由：上报 ----------

@app.post("/api/v1/report")
def report(payload: dict[str, Any] = Body(default={}), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    with connect() as conn:
        token, runner = strategy_token(conn, authorization)
    instrument = str(payload.get("instrument") or "").strip()[:64]
    if not instrument:
        raise HTTPException(status_code=400, detail="instrument 必填（进程名）")

    # 1) 心跳先独立提交：任何鉴权成功的 report 都刷新该进程 last_seen（即使后续字段 400）
    with connect() as conn:
        now = iso_now()
        conn.execute("UPDATE tokens SET last_used_at = ?, request_count = request_count + 1 WHERE id = ?",
                     (now, token["id"]))
        process = _ensure_process(conn, runner, instrument, now_dt())
        state = refresh_runner_state(conn, runner["id"], publish=True)
        if state:
            _publish_process(conn, runner, conn.execute("SELECT * FROM processes WHERE id = ?",
                                                        (process["id"],)).fetchone(), state)

    # 2) 拒绝 v0.1 财务字段
    forbidden = sorted(key for key in ("pnl", "cash_flow", "nav", "account_nav") if key in payload)
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail="字段 " + "、".join(forbidden) + " 已废弃；qwatch 只使用 equity",
        )

    # 3) 解析与校验
    loop_value: int | None = None
    if payload.get("loop") is not None:
        loop_value = int(require_number(payload["loop"], "loop", minimum=0))
    last_tick = parse_iso(str(payload["last_tick"])) if payload.get("last_tick") else None
    msg = str(payload.get("msg") or "").strip()[:500]
    equity_value: float | None = None
    if payload.get("equity") is not None:
        equity_value = require_number(payload["equity"], "equity")
        if equity_value <= 0:
            raise HTTPException(status_code=400, detail="equity 必须大于 0")
    signal_keys = ("symbol", "contract", "direction", "action", "qty", "price", "amount")
    has_signal = any(key in payload and payload[key] not in (None, "") for key in signal_keys)
    signal_id = ""
    symbol = direction = action = ""
    qty = price = amount = None
    if has_signal:
        symbol = str(payload.get("symbol") or payload.get("contract") or "").strip()[:64]
        direction = str(payload.get("direction") or "").strip().lower()
        action = str(payload.get("action") or "").strip().lower()
        if not symbol:
            raise HTTPException(status_code=400, detail="signal.symbol 必填")
        if direction not in ("long", "short"):
            raise HTTPException(status_code=400, detail="signal.direction 必须是 long / short")
        if action not in ("open", "close", "add", "reduce"):
            raise HTTPException(status_code=400, detail="signal.action 必须是 open / close / add / reduce")
        qty = require_number(payload.get("qty"), "signal.qty")
        if qty <= 0:
            raise HTTPException(status_code=400, detail="signal.qty 必须是正数")
        if payload.get("price") is not None:
            price = require_number(payload["price"], "signal.price", minimum=0)
        if payload.get("amount") is not None:
            amount = require_number(payload["amount"], "signal.amount", minimum=0)
        signal_id = str(payload.get("id") or "").strip()[:128]

    # 4) 落库：动态 / loop / last_tick
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner["id"],)).fetchone()
        process = conn.execute("SELECT * FROM processes WHERE runner_id = ? AND name = ?",
                               (runner["id"], instrument)).fetchone()
        if process is None:
            raise HTTPException(status_code=500, detail="进程心跳写入失败")
        if signal_id:
            existing = conn.execute(
                "SELECT id FROM events WHERE runner_id = ? AND external_id = ?", (runner["id"], signal_id)
            ).fetchone()
            if existing:
                return {"ok": True, "heartbeat": True, "signal_id": signal_id, "server_time": iso_now()}
        now = iso_now()
        if loop_value is not None:
            same = int(process["loop_same"] or 0) + 1 if process["last_loop"] == loop_value else 1
            conn.execute("UPDATE processes SET last_loop = ?, loop_same = ?, updated_at = ? WHERE id = ?",
                         (loop_value, same, now, process["id"]))
        if last_tick is not None:
            conn.execute("UPDATE processes SET last_tick = ?, updated_at = ? WHERE id = ?",
                         (last_tick, now, process["id"]))
        if equity_value is not None:
            conn.execute(
                "UPDATE runners SET equity = ?, equity_updated_at = ? WHERE id = ?",
                (equity_value, now, runner["id"]),
            )
            conn.execute(
                "INSERT INTO runner_equity_points(runner_id, ts, equity, nav, created_at) VALUES(?,?,?,NULL,?)",
                (runner["id"], now, equity_value, now),
            )
            day = datetime.now().astimezone().date().isoformat()
            conn.execute(
                "INSERT INTO runner_daily_equity(runner_id, day, equity, updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(runner_id, day) DO UPDATE SET equity = excluded.equity, updated_at = excluded.updated_at",
                (runner["id"], day, equity_value, now),
            )
            sse.publish({
                "type": "strategy.equity_updated",
                "ts": now,
                "runner_id": runner["id"],
                "equity": _fmt_money(equity_value),
                "equity_updated_at": now,
            })
            sse.publish({"type": "account.updated", "ts": now, "account_id": runner["account_id"]})
        if msg and not has_signal:
            cursor = conn.execute(
                "INSERT INTO events(runner_id, instrument, ts, type, text, created_at) VALUES(?,?,?,?,?,?)",
                (runner["id"], instrument, now, "message", msg, now),
            )
            conn.execute("UPDATE runners SET last_msg = ? WHERE id = ?", (msg, runner["id"]))
            row = conn.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,)).fetchone()
            sse.publish({"type": "event.message", "ts": now, "runner_id": runner["id"], "event": event_view(row)})
        if has_signal:
            signal_id = signal_id or ("sig_" + uuid.uuid4().hex)
            cursor = conn.execute(
                "INSERT INTO events(runner_id, instrument, ts, type, text, symbol, direction, action, qty, price, "
                "amount, external_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (runner["id"], instrument, now, "signal", msg, symbol, direction, action, qty, price, amount,
                 signal_id, now),
            )
            row = conn.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,)).fetchone()
            sse.publish({"type": "event.signal", "ts": now, "runner_id": runner["id"], "event": event_view(row)})
        refresh_runner_state(conn, runner["id"], publish=True)
    return {"ok": True, "heartbeat": True, "signal_id": signal_id or None, "server_time": iso_now()}


# ---------- 路由：总览 / 告警 ----------

@app.get("/api/v1/overview")
def overview(user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        account_rows = conn.execute("SELECT * FROM accounts ORDER BY created_at").fetchall()
        runner_rows = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        process_rows = conn.execute("SELECT * FROM processes ORDER BY name").fetchall()
        accounts_by_id = {row["id"]: row for row in account_rows}
        by_runner: dict[str, list[Any]] = defaultdict(list)
        for row in process_rows:
            by_runner[row["runner_id"]].append(row)
        runner_views_list: list[dict[str, Any]] = []
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for runner in runner_rows:
            rows = by_runner.get(runner["id"], [])
            statuses = {row["id"]: process_status(row, now_dt(), bool(runner["paused"])) for row in rows}
            view = runner_view(runner, rows, statuses, accounts_by_id.get(runner["account_id"]))
            view["equity_sparkline"] = strategy_equity_sparkline(conn, runner["id"])
            view["heartbeat_7d"] = runner_heartbeat_history(conn, runner["id"])
            view["uptime_7d"] = runner_uptime_7d(conn, runner["id"])
            view["today_pnl"] = _fmt_money(runner_today_pnl(conn, runner, _today_start_iso()))
            runner_views_list.append(view)
            grouped[runner["account_id"]].append(view)
        account_items = [account_view(conn, row, grouped.get(row["id"], [])) for row in account_rows]
        processes_total = sum(1 for row in process_rows if not row["retired"])
        processes_online = 0
        for runner in runner_rows:
            rows = by_runner.get(runner["id"], [])
            paused = bool(runner["paused"])
            processes_online += sum(
                1 for row in rows if not row["retired"] and process_status(row, now_dt(), paused) == "running"
            )
        alert_rows = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id "
            "ORDER BY a.starts_at DESC LIMIT 10"
        ).fetchall()
        event_rows = conn.execute(
            "SELECT e.*, r.name AS runner_name FROM events e LEFT JOIN runners r ON r.id = e.runner_id "
            "ORDER BY e.id DESC LIMIT 30"
        ).fetchall()
        active_alerts = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE status = 'firing'").fetchone()["n"]
        total_equity = 0.0
        today_change = 0.0
        has_equity = False
        has_prev_equity = False
        today_start = datetime.now().astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc).isoformat()
        for runner in runner_rows:
            if runner["equity"] is None:
                continue
            has_equity = True
            total_equity += float(runner["equity"])
            prev = conn.execute(
                "SELECT equity FROM runner_equity_points WHERE runner_id = ? AND equity IS NOT NULL AND ts < ? "
                "ORDER BY id DESC LIMIT 1",
                (runner["id"], today_start),
            ).fetchone()
            if prev is None:
                # 当日首次上报：用当天首个点做基线，避免面板显示空值
                prev = conn.execute(
                    "SELECT equity FROM runner_equity_points WHERE runner_id = ? AND equity IS NOT NULL AND ts >= ? "
                    "ORDER BY id ASC LIMIT 1",
                    (runner["id"], today_start),
                ).fetchone()
            if prev is not None:
                today_change += float(runner["equity"]) - float(prev["equity"])
                has_prev_equity = True
        return {
            "as_of": iso_now(),
            "running": sum(1 for view in runner_views_list if view["status"] == "running"),
            "total": len(runner_views_list),
            "processes_total": processes_total,
            "processes_online": processes_online,
            "active_alerts": active_alerts,
            "account_count": len(account_rows),
            "recent_alerts": [alert_view(row, row["runner_name"]) for row in alert_rows],
            "recent_events": [event_view(row) for row in event_rows],
            "total_equity": f"{total_equity:.2f}" if has_equity else None,
            "today_equity_change": f"{today_change:.2f}" if has_equity and has_prev_equity else None,
            "today_pnl": f"{today_change:.2f}" if has_equity and has_prev_equity else None,
            "equity_curve": merged_equity_curve(conn, [row["id"] for row in runner_rows]),
            "accounts": account_items,
            "runners": runner_views_list,
        }


@app.get("/api/v1/equity_curve")
def equity_curve(
    scope: str = Query(default="all"),
    id: str | None = Query(default=None),
    user: str = Depends(require_user),
) -> dict[str, Any]:
    """大图数据：全部历史、按日粒度；scope=all/account/runner。"""
    with connect() as conn:
        if scope == "runner":
            if not id:
                raise HTTPException(status_code=400, detail="runner 需要 id")
            runner_ids = [id]
        elif scope == "account":
            if not id:
                raise HTTPException(status_code=400, detail="account 需要 id")
            runner_ids = [row["id"] for row in conn.execute(
                "SELECT id FROM runners WHERE account_id = ? ORDER BY created_at", (id,)
            )]
        elif scope == "all":
            runner_ids = [row["id"] for row in conn.execute("SELECT id FROM runners ORDER BY created_at")]
        else:
            raise HTTPException(status_code=400, detail="scope 必须是 all/account/runner")
        return {"items": daily_equity_curve(conn, runner_ids)}


@app.get("/api/v1/events")
def list_events(
    limit: int = Query(default=50, ge=1, le=100),
    before_id: int | None = Query(default=None, ge=1),
    type: str | None = Query(default=None),
    runner_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    days: int = Query(default=0, ge=0, le=365),
    user: str = Depends(require_user),
) -> dict[str, Any]:
    """全局动态流：消息/信号，按 id 倒序游标分页。"""
    where = ["1 = 1"]
    params: list[Any] = []
    if before_id is not None:
        where.append("e.id < ?")
        params.append(before_id)
    if type in ("message", "signal"):
        where.append("e.type = ?")
        params.append(type)
    if runner_id:
        where.append("e.runner_id = ?")
        params.append(runner_id)
    if account_id:
        where.append("r.account_id = ?")
        params.append(account_id)
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        where.append("e.ts >= ?")
        params.append(cutoff)
    if q and q.strip():
        like = "%" + q.strip().lower() + "%"
        where.append("(lower(r.name) LIKE ? OR lower(a.name) LIKE ? OR lower(e.text) LIKE ? OR lower(e.symbol) LIKE ? OR lower(e.instrument) LIKE ?)")
        params.extend([like, like, like, like, like])
    sql = (
        "SELECT e.*, r.name AS runner_name, a.name AS account_name "
        "FROM events e JOIN runners r ON r.id = e.runner_id LEFT JOIN accounts a ON a.id = r.account_id "
        "WHERE " + " AND ".join(where) + " ORDER BY e.id DESC LIMIT ?"
    )
    with connect() as conn:
        rows = conn.execute(sql, [*params, limit + 1]).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = []
        for row in rows:
            item = event_view(row)
            item["account_name"] = row["account_name"] if "account_name" in row.keys() else None
            items.append(item)
        return {
            "items": items,
            "has_more": has_more,
            "next_before_id": rows[-1]["id"] if rows else None,
        }


@app.get("/api/v1/alerts")
def alerts_list(status: str = Query(default="active"), user: str = Depends(require_user)) -> dict[str, Any]:
    if status not in ("active", "history"):
        raise HTTPException(status_code=400, detail="status 必须是 active 或 history")
    with connect() as conn:
        if status == "active":
            rows = conn.execute(
                "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id "
                "WHERE a.status = 'firing' ORDER BY a.starts_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id "
                "WHERE a.status IN ('acknowledged', 'resolved') ORDER BY a.starts_at DESC"
            ).fetchall()
        active_count = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE status = 'firing'").fetchone()["n"]
        return {"items": [alert_view(row, row["runner_name"]) for row in rows], "active_count": active_count}


@app.post("/api/v1/alerts/{alert_id}/ack")
def ack_alert(alert_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.id = ?",
            (alert_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="告警不存在")
        if row["status"] != "firing":
            raise HTTPException(status_code=409, detail="只有 firing 状态的告警可以确认")
        now = iso_now()
        conn.execute("UPDATE alerts SET status = 'acknowledged', acked_at = ?, updated_at = ? WHERE id = ?",
                     (now, now, alert_id))
        updated = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.id = ?",
            (alert_id,),
        ).fetchone()
        alert = alert_view(updated, updated["runner_name"])
        sse.publish({"type": "alert.updated", "ts": now, "alert": alert})
        return {"alert": alert}


@app.post("/api/v1/alerts/{alert_id}/silence")
def silence_alert(alert_id: str, payload: dict[str, Any] = Body(default={}),
                  user: str = Depends(require_user)) -> dict[str, Any]:
    duration = str(payload.get("duration", "1h"))
    if duration not in ("1h", "4h", "24h"):
        raise HTTPException(status_code=400, detail="duration 必须是 1h / 4h / 24h")
    hours = {"1h": 1, "4h": 4, "24h": 24}[duration]
    with connect() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="告警不存在")
        if row["status"] == "resolved":
            raise HTTPException(status_code=409, detail="已恢复的告警不能静默")
        until = (now_dt() + timedelta(hours=hours)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        labels = loads(row["labels"], {})
        labels["silenced_until"] = until
        now = iso_now()
        conn.execute("UPDATE alerts SET labels = ?, updated_at = ? WHERE id = ?", (dumps(labels), now, alert_id))
        updated = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.id = ?",
            (alert_id,),
        ).fetchone()
        alert = alert_view(updated, updated["runner_name"])
        sse.publish({"type": "alert.updated", "ts": now, "alert": alert})
        return {"alert": alert}


# ---------- 路由：令牌 ----------

@app.get("/api/v1/tokens")
def tokens_list(runner_id: str | None = None, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        if runner_id:
            rows = conn.execute("SELECT * FROM tokens WHERE runner_id = ? ORDER BY created_at DESC", (runner_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tokens ORDER BY created_at DESC").fetchall()
        return {"items": [token_view(row) for row in rows], "total": len(rows)}


@app.post("/api/v1/tokens")
def create_token(payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="令牌名称必填")
    runner_id = str(payload.get("runner_id") or "").strip()
    if not runner_id:
        raise HTTPException(status_code=400, detail="runner_id 必填（令牌绑定策略组）")
    token = "qw_" + secrets.token_hex(32)
    record_id = "tok_" + uuid.uuid4().hex[:10]
    created = iso_now()
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM runners WHERE id = ?", (runner_id,)).fetchone():
            raise HTTPException(status_code=400, detail="策略不存在")
        conn.execute(
            "INSERT INTO tokens(id, runner_id, name, token_hash, token_prefix, status, created_at, last_used_at, "
            "request_count) VALUES(?,?,?,?,?,'active',?,NULL,0)",
            (record_id, runner_id, name[:100], token_hash(token), token_prefix(token), created),
        )
        row = conn.execute("SELECT * FROM tokens WHERE id = ?", (record_id,)).fetchone()
        logger.info("创建令牌 %s -> runner=%s", record_id, runner_id)
        return {"token": token, "record": token_view(row)}


@app.post("/api/v1/tokens/{token_id}/revoke")
def revoke_token(token_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE id = ?", (token_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="令牌不存在")
        conn.execute("UPDATE tokens SET status = 'revoked' WHERE id = ?", (token_id,))
        updated = conn.execute("SELECT * FROM tokens WHERE id = ?", (token_id,)).fetchone()
        logger.info("吊销令牌 %s", token_id)
        return {"record": token_view(updated)}


# ---------- 路由：设置 / 渠道 ----------

@app.get("/api/v1/settings")
def get_settings(user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        channels = [channel_view(row) for row in conn.execute("SELECT * FROM channels ORDER BY rowid").fetchall()]
        return {"channels": channels, "up_color_scheme": get_setting(conn, "up_color_scheme", "red_up")}


@app.put("/api/v1/settings")
def save_settings(payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        if "up_color_scheme" in payload:
            scheme = str(payload["up_color_scheme"])
            if scheme not in ("red_up", "green_up"):
                raise HTTPException(status_code=400, detail="up_color_scheme 必须是 red_up / green_up")
            set_setting(conn, "up_color_scheme", scheme)
        channels = payload.get("channels")
        if channels is not None and not isinstance(channels, list):
            raise HTTPException(status_code=400, detail="channels 必须是数组")
        for patch in channels or []:
            if not isinstance(patch, dict):
                continue
            channel_id = str(patch.get("id") or "").strip()
            if not channel_id:
                continue
            row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
            if not row:
                continue
            enabled = 1 if patch.get("enabled", bool(row["enabled"])) else 0
            webhook = str(patch.get("webhook", row["webhook"])).strip()
            secret = str(patch.get("secret", row["secret"])).strip()
            if "****" in webhook:
                raise HTTPException(status_code=400, detail="webhook 不能是掩码值，请填写完整地址")
            conn.execute("UPDATE channels SET enabled = ?, webhook = ?, secret = ? WHERE id = ?",
                         (enabled, webhook, secret, channel_id))
        channels_out = [channel_view(row) for row in conn.execute("SELECT * FROM channels ORDER BY rowid").fetchall()]
        return {"channels": channels_out, "up_color_scheme": get_setting(conn, "up_color_scheme", "red_up")}


@app.post("/api/v1/channels/{channel_id}/test")
def test_channel(channel_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="渠道不存在")
    ok, error, latency = notify.send_test(row["webhook"], row["secret"])
    with connect() as conn:
        conn.execute("UPDATE channels SET last_test_at = ?, last_test_ok = ? WHERE id = ?",
                     (iso_now(), 1 if ok else 0, channel_id))
    if not ok:
        raise HTTPException(status_code=502, detail="发送失败：" + error)
    return {"ok": True, "channel_id": channel_id, "message": "测试消息已发送",
            "latency_ms": latency, "at": iso_now()}


# ---------- 路由：SSE ----------

@app.get("/api/v1/stream")
async def stream(
    request: Request,
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> StreamingResponse:
    raw = ""
    if authorization and authorization.startswith("Bearer "):
        raw = authorization[7:].strip()
    elif token:
        raw = token.strip()
    _session_user(raw)
    queue = await sse.bus.subscribe()

    async def generator():
        try:
            yield sse.format_sse({"type": "stream.ready", "ts": iso_now()})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield sse.format_sse(event)
        finally:
            sse.bus.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ---------- 后台任务 ----------

_started_monotonic = 0.0
_last_maintenance = 0.0


async def watchdog_loop() -> None:
    global _started_monotonic, _last_maintenance
    _started_monotonic = time.monotonic()
    while True:
        try:
            if time.monotonic() - _started_monotonic < STARTUP_GRACE_S:
                await asyncio.sleep(WATCHDOG_INTERVAL_S)
                continue
            with connect() as conn:
                runners = conn.execute("SELECT id FROM runners WHERE paused = 0").fetchall()
                for row in runners:
                    refresh_runner_state(conn, row["id"], publish=True)
                # 7 天可用率采样：每 5 秒记录一次进程在线/总数，供心跳条展示
                day = datetime.now().astimezone().date().isoformat()
                now = now_dt()
                utc_now = datetime.now(timezone.utc)
                bucket_start = utc_now.replace(
                    hour=(utc_now.hour // 6) * 6, minute=0, second=0, microsecond=0
                ).isoformat().replace("+00:00", "Z")
                processes = conn.execute(
                    "SELECT p.* FROM processes p JOIN runners r ON r.id = p.runner_id "
                    "WHERE p.retired = 0 AND r.paused = 0"
                ).fetchall()
                for process in processes:
                    up = 1 if process_status(process, now, False) == "running" else 0
                    conn.execute(
                        "INSERT INTO process_day_health(process_id, day, up_samples, total_samples) "
                        "VALUES(?,?,?,1) ON CONFLICT(process_id, day) DO UPDATE SET "
                        "up_samples = up_samples + excluded.up_samples, "
                        "total_samples = total_samples + 1",
                        (process["id"], day, up),
                    )
                    conn.execute(
                        "INSERT INTO process_health_bucket(process_id, bucket_start, up_samples, total_samples) "
                        "VALUES(?,?,?,1) ON CONFLICT(process_id, bucket_start) DO UPDATE SET "
                        "up_samples = up_samples + excluded.up_samples, "
                        "total_samples = total_samples + 1",
                        (process["id"], bucket_start, up),
                    )
                if time.monotonic() - _last_maintenance > 3600:
                    _last_maintenance = time.monotonic()
                    raw_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                    health_cutoff = (datetime.now().astimezone().date() - timedelta(days=30)).isoformat()
                    bucket_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
                    event_cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
                    conn.execute("DELETE FROM runner_equity_points WHERE ts < ?", (raw_cutoff,))
                    conn.execute("DELETE FROM process_day_health WHERE day < ?", (health_cutoff,))
                    conn.execute("DELETE FROM process_health_bucket WHERE bucket_start < ?", (bucket_cutoff,))
                    conn.execute("DELETE FROM events WHERE ts < ?", (event_cutoff,))
        except Exception:  # noqa: BLE001 - 后台循环不能退出
            logger.exception("watchdog 扫描失败")
        await asyncio.sleep(WATCHDOG_INTERVAL_S)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    sse.bus.set_loop(asyncio.get_running_loop())
    app.state.watchdog_task = asyncio.create_task(watchdog_loop())
    app.state.delivery_task = asyncio.create_task(notify.delivery_loop())
    logger.info("qwatch v%s 启动：DB=%s", VERSION, DB_PATH)


@app.on_event("shutdown")
async def shutdown() -> None:
    for name in ("watchdog_task", "delivery_task"):
        task = getattr(app.state, name, None)
        if task:
            task.cancel()


# ---------- 静态文件 ----------

if DIST.exists():
    assets = DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        base = DIST.resolve()
        candidate = (DIST / full_path).resolve()
        if full_path and not candidate.is_relative_to(base):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not Found")
