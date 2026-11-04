"""qwatch v0.3 后端：可信看门狗（策略组 + 进程心跳 + 策略组净值 + SSE + 钉钉 P0）。

- runners = 策略组；processes = 稳定进程名（自动发现，可 retired）
- POST /api/v1/report 接收心跳/loop/msg/signal/nav/equity；拒绝 pnl/cash_flow
- 告警只有 P0：heartbeat_lost / runner_stalled，按策略组汇总一条
- GET /api/v1/stream 为 SSE 实时事件（alert.* / process.updated / event.*）
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
VERSION = "0.3.0"
PASSWORD = os.environ.get("QWATCH_PASSWORD", "qwatch")
SESSION_HOURS = 12
HEARTBEAT_TIMEOUT_S = 60
STALL_REPEAT = 3
WATCHDOG_INTERVAL_S = 5
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


def runner_view(runner, processes, statuses: dict[int, str]) -> dict[str, Any]:
    state = _runner_state(runner, processes, statuses)
    return {
        "id": runner["id"],
        "name": runner["name"],
        "description": runner["description"] or "",
        "status": state["status"],
        "process_count": state["process_count"],
        "online_processes": state["online_processes"],
        "last_seen": state["last_seen"],
        "last_msg": runner["last_msg"] or "",
        "nav": f"{float(runner['nav']):.6f}" if runner["nav"] is not None else None,
        "nav_updated_at": runner["nav_updated_at"],
        "equity": f"{float(runner['equity']):.2f}" if runner["equity"] is not None else None,
        "equity_updated_at": runner["equity_updated_at"],
        "created_at": runner["created_at"],
    }


def nav_sparkline(conn: sqlite3.Connection, runner_id: str) -> list[float]:
    rows = conn.execute(
        "SELECT nav FROM nav_points WHERE runner_id = ? ORDER BY id DESC LIMIT 24", (runner_id,)
    ).fetchall()
    return [round(float(row["nav"]), 6) for row in reversed(rows)]


def equity_sparkline(conn: sqlite3.Connection, runner_id: str) -> list[float]:
    rows = conn.execute(
        "SELECT equity FROM equity_points WHERE runner_id = ? ORDER BY id DESC LIMIT 24", (runner_id,)
    ).fetchall()
    return [round(float(row["equity"]), 2) for row in reversed(rows)]


def portfolio_equity_curve(conn: sqlite3.Connection, runner_ids: list[str]) -> list[dict[str, str]]:
    """把各策略组权益点合并成组合权益曲线；每个时间点取各组最近一次权益后求和。"""
    per_runner: dict[str, list[tuple[str, float]]] = {}
    for rid in runner_ids:
        rows = conn.execute(
            "SELECT ts, equity FROM equity_points WHERE runner_id = ? ORDER BY id DESC LIMIT 500", (rid,)
        ).fetchall()
        if rows:
            per_runner[rid] = [(row["ts"], float(row["equity"])) for row in reversed(rows)]
    if not per_runner:
        return []
    timeline = sorted({ts for series in per_runner.values() for ts, _ in series})
    latest: dict[str, float] = {}
    pointers: dict[str, int] = {rid: 0 for rid in per_runner}
    required = set(per_runner)
    curve: list[dict[str, str]] = []
    for ts in timeline:
        for rid, series in per_runner.items():
            idx = pointers[rid]
            while idx < len(series) and series[idx][0] <= ts:
                latest[rid] = series[idx][1]
                idx += 1
            pointers[rid] = idx
        # 等所有策略组都有权益点后再画组合曲线，避免逐组上线造成假的垂直跳变
        if required.issubset(latest):
            curve.append({"ts": ts, "value": f"{sum(latest.values()):.2f}"})
    return curve[-500:]


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
    with connect() as conn:
        if conn.execute("SELECT 1 FROM runners WHERE name = ?", (name,)).fetchone():
            raise HTTPException(status_code=400, detail="策略名称已存在")
        runner_id = "runner-" + uuid.uuid4().hex[:8]
        created = iso_now()
        conn.execute(
            "INSERT INTO runners(id, name, description, platform, market, strategy_type, tags, paused, created_at) "
            "VALUES(?,?,?,?,?,?,?,0,?)",
            (runner_id, name, description, platform, market, strategy_type, dumps(tags), created),
        )
        runner = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
    logger.info("创建策略组 %s (%s)", name, runner_id)
    return {"runner": runner_view(runner, [], {})}


@app.get("/api/v1/runners")
def list_runners(
    status: str | None = Query(default=None), q: str | None = Query(default=None),
    user: str = Depends(require_user),
) -> dict[str, Any]:
    with connect() as conn:
        runners = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        processes = conn.execute("SELECT * FROM processes ORDER BY name").fetchall()
        by_runner: dict[str, list[Any]] = defaultdict(list)
        for row in processes:
            by_runner[row["runner_id"]].append(row)
        items = []
        for runner in runners:
            rows = by_runner.get(runner["id"], [])
            statuses = {row["id"]: process_status(row, now_dt(), bool(runner["paused"])) for row in rows}
            view = runner_view(runner, rows, statuses)
            view["nav_sparkline"] = nav_sparkline(conn, runner["id"])
            view["equity_sparkline"] = equity_sparkline(conn, runner["id"])
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
        events = conn.execute(
            "SELECT * FROM events WHERE runner_id = ? ORDER BY id DESC LIMIT ?", (runner_id, MAX_EVENTS_RETURN)
        ).fetchall()
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE runner_id = ? ORDER BY starts_at DESC LIMIT 50", (runner_id,)
        ).fetchall()
        nav_rows = list(reversed(conn.execute(
            "SELECT ts, nav FROM nav_points WHERE runner_id = ? ORDER BY id DESC LIMIT 1000",
            (runner_id,),
        ).fetchall()))
        nav_curve = [{"ts": row["ts"], "value": f"{float(row['nav']):.6f}"} for row in nav_rows]
        equity_rows = list(reversed(conn.execute(
            "SELECT ts, equity FROM equity_points WHERE runner_id = ? ORDER BY id DESC LIMIT 1000",
            (runner_id,),
        ).fetchall()))
        equity_curve = [{"ts": row["ts"], "value": f"{float(row['equity']):.2f}"} for row in equity_rows]
        runner_data = runner_view(runner, processes, statuses)
        runner_data["nav_sparkline"] = nav_sparkline(conn, runner_id)
        runner_data["equity_sparkline"] = equity_sparkline(conn, runner_id)
        return {
            "runner": runner_data,
            "processes": [process_view(row, statuses[row["id"]], at, bool(runner["paused"])) for row in processes],
            "events": [event_view(row) for row in events],
            "alerts": [alert_view(row, runner["name"]) for row in alerts],
            "nav_curve": nav_curve,
            "equity_curve": equity_curve,
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
        logger.info("暂停策略组 %s", runner_id)
        return {"runner": runner_view(runner, processes, statuses)}


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
        logger.info("恢复策略组 %s", runner_id)
        return {"runner": runner_view(runner, processes, statuses)}


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
        logger.info("停用进程 %s/%s", runner_id, name)
        return {
            "runner": runner_view(runner, processes, statuses),
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
        logger.info("启用进程 %s/%s", runner_id, name)
        return {
            "runner": runner_view(runner, processes, statuses),
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
    forbidden = sorted(key for key in ("pnl", "cash_flow") if key in payload)
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail="字段 " + "、".join(forbidden) + " 已废弃；只接收心跳/loop/msg/signal/nav/equity",
        )

    # 3) 解析与校验
    loop_value: int | None = None
    if payload.get("loop") is not None:
        loop_value = int(require_number(payload["loop"], "loop", minimum=0))
    last_tick = parse_iso(str(payload["last_tick"])) if payload.get("last_tick") else None
    msg = str(payload.get("msg") or "").strip()[:500]
    nav_value: float | None = None
    if payload.get("nav") is not None:
        nav_value = require_number(payload["nav"], "nav")
        if nav_value <= 0:
            raise HTTPException(status_code=400, detail="nav 必须大于 0")
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
        if nav_value is not None:
            conn.execute("UPDATE runners SET nav = ?, nav_updated_at = ? WHERE id = ?",
                         (nav_value, now, runner["id"]))
            conn.execute(
                "INSERT INTO nav_points(runner_id, ts, nav, created_at) VALUES(?,?,?,?)",
                (runner["id"], now, nav_value, now),
            )
        if equity_value is not None:
            conn.execute("UPDATE runners SET equity = ?, equity_updated_at = ? WHERE id = ?",
                         (equity_value, now, runner["id"]))
            conn.execute(
                "INSERT INTO equity_points(runner_id, ts, equity, created_at) VALUES(?,?,?,?)",
                (runner["id"], now, equity_value, now),
            )
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
        runner_rows = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        process_rows = conn.execute("SELECT * FROM processes ORDER BY name").fetchall()
        by_runner: dict[str, list[Any]] = defaultdict(list)
        for row in process_rows:
            by_runner[row["runner_id"]].append(row)
        views = []
        for runner in runner_rows:
            rows = by_runner.get(runner["id"], [])
            statuses = {row["id"]: process_status(row, now_dt(), bool(runner["paused"])) for row in rows}
            view = runner_view(runner, rows, statuses)
            view["nav_sparkline"] = nav_sparkline(conn, runner["id"])
            view["equity_sparkline"] = equity_sparkline(conn, runner["id"])
            views.append(view)
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
            "ORDER BY e.id DESC LIMIT 8"
        ).fetchall()
        active_alerts = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE status = 'firing'").fetchone()["n"]
        total_equity = 0.0
        prev_equity = 0.0
        has_equity = False
        has_prev_equity = False
        equity_as_of: str | None = None
        today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
        for runner in runner_rows:
            if runner["equity"] is None:
                continue
            has_equity = True
            total_equity += float(runner["equity"])
            if runner["equity_updated_at"] and (equity_as_of is None or runner["equity_updated_at"] > equity_as_of):
                equity_as_of = runner["equity_updated_at"]
            prev = conn.execute(
                "SELECT equity FROM equity_points WHERE runner_id = ? AND ts < ? ORDER BY id DESC LIMIT 1",
                (runner["id"], today_start),
            ).fetchone()
            if prev is None:
                # 当天首次部署没有昨日收盘：用当天首个点做基线，避免面板显示空值
                prev = conn.execute(
                    "SELECT equity FROM equity_points WHERE runner_id = ? AND ts >= ? ORDER BY id ASC LIMIT 1",
                    (runner["id"], today_start),
                ).fetchone()
            if prev is not None:
                prev_equity += float(prev["equity"])
                has_prev_equity = True
        return {
            "as_of": iso_now(),
            "running": sum(1 for view in views if view["status"] == "running"),
            "total": len(views),
            "active_alerts": active_alerts,
            "processes_total": processes_total,
            "processes_online": processes_online,
            "recent_alerts": [alert_view(row, row["runner_name"]) for row in alert_rows],
            "recent_events": [event_view(row) for row in event_rows],
            "total_equity": f"{total_equity:.2f}" if has_equity else None,
            "today_equity_change": f"{total_equity - prev_equity:.2f}" if has_equity and has_prev_equity else None,
            "equity_as_of": equity_as_of,
            "equity_curve": portfolio_equity_curve(conn, [runner["id"] for runner in runner_rows]),
            "runners": views,
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

async def watchdog_loop() -> None:
    while True:
        try:
            with connect() as conn:
                runners = conn.execute("SELECT id FROM runners WHERE paused = 0").fetchall()
                for row in runners:
                    refresh_runner_state(conn, row["id"], publish=True)
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
