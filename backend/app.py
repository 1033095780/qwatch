"""qwatch 真实后端：FastAPI + SQLite。

启动：
    python -m backend          # http://127.0.0.1:8080
首次使用先初始化演示数据：
    python -m backend.seed
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import DB_PATH, connect, dumps, get_setting, init_db, iso_now, loads, set_setting

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"
PASSWORD = os.environ.get("QWATCH_PASSWORD", "qwatch")
SESSION_HOURS = 12
HEARTBEAT_TIMEOUT_S = 60

PLATFORM_LABELS = {"ptrade": "PTrade", "qmt": "QMT", "myquant": "掘金", "tqsdk": "天勤", "custom": "自研"}
STRATEGY_TYPE_LABELS = {
    "trend": "趋势", "arbitrage": "套利", "intraday": "日内", "grid": "网格",
    "multifactor": "多因子", "market_making": "做市", "other": "其他",
}
MARKET_LABELS = {"CN_A": "A股", "CN_FUT": "期货", "HK": "港股", "US": "美股", "CRYPTO": "加密", "FX": "外汇"}
TOKEN_STATUS = {"active", "revoked"}
INSTRUMENTS = {
    "rb2601": ("螺纹钢2601", "CN_FUT", "XSGE", 10),
    "au2601": ("沪金2601", "CN_FUT", "XSGE", 1000),
    "ag2601": ("沪银2601", "CN_FUT", "XSGE", 15),
    "cu2601": ("沪铜2601", "CN_FUT", "XSGE", 5),
    "IF2612": ("沪深300股指2612", "CN_FUT", "CFFEX", 300),
    "T2612": ("十年国债2612", "CN_FUT", "CFFEX", 10000),
    "600519": ("贵州茅台", "CN_A", "XSHG", 1),
    "510300": ("沪深300ETF", "CN_A", "XSHG", 1),
    "000001": ("平安银行", "CN_A", "XSHG", 1),
}
RANGE_DAYS = {"1d": 2, "1w": 7, "1m": 30, "3m": 90, "1y": 365, "all": 100000}
DIRECTIONS = {"long", "short"}
ACTIONS = {"open", "close", "add", "reduce"}


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def dt_from(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def mask_webhook(url: str) -> str:
    if not url:
        return "未配置"
    return re.sub(r"(access_token=)([^&]+)", lambda m: m.group(1) + "****" + m.group(2)[-4:], url)


def mask_secret(secret: str) -> str:
    if not secret:
        return "未配置"
    return "SEC****" + secret[-4:]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_prefix(token: str) -> str:
    return "qw_" + token[3:7] + "…" + token[-4:]


def alert_id() -> str:
    return "alert_" + uuid.uuid4().hex[:10]


def fingerprint(rule: str, runner_id: str) -> str:
    return "fp_" + hashlib.sha256((rule + ":" + runner_id).encode()).hexdigest()[:12]


def parse_iso(value: str) -> str:
    ts = dt_from(value)
    if not ts:
        raise HTTPException(status_code=400, detail="ts 不是合法时间")
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------- 鉴权 ----------

def require_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    hashed = token_hash(authorization[7:].strip())
    with connect() as conn:
        row = conn.execute("SELECT user, expires_at FROM sessions WHERE token_hash = ?", (hashed,)).fetchone()
    if not row or row["expires_at"] <= iso_now():
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return row["user"]


def strategy_token(conn: sqlite3.Connection, authorization: str | None) -> tuple[sqlite3.Row, sqlite3.Row]:
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


# ---------- 序列化 ----------

def accounts_of(conn: sqlite3.Connection, row: sqlite3.Row) -> list[dict[str, Any]]:
    ids = loads(row["accounts"], [])
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute("SELECT id, name, venue FROM accounts WHERE id IN (" + placeholders + ")", ids).fetchall()
    by_id = {item["id"]: {"id": item["id"], "name": item["name"], "venue": item["venue"]} for item in rows}
    return [by_id[i] for i in ids if i in by_id]


def sparkline_of(conn: sqlite3.Connection, runner_id: str) -> list[float]:
    rows = conn.execute("SELECT equity FROM equity_points WHERE runner_id = ? ORDER BY ts DESC LIMIT 24", (runner_id,)).fetchall()
    values = [round(float(row["equity"]), 2) for row in reversed(rows)]
    return values or [0.0]


def runner_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    equity = float(row["equity"])
    today = float(row["today_pnl"])
    base = equity - today
    return {
        "id": row["id"], "name": row["name"], "strategy": row["strategy"], "version": row["version"],
        "market": row["market"], "venue": row["venue"], "platform": row["platform"],
        "platform_label": PLATFORM_LABELS.get(row["platform"], ""),
        "strategy_type": row["strategy_type"], "strategy_type_label": STRATEGY_TYPE_LABELS.get(row["strategy_type"], ""),
        "tags": loads(row["tags"], []), "status": row["status"], "accounts": accounts_of(conn, row),
        "equity": f"{equity:.2f}", "today_pnl": f"{today:.2f}",
        "today_pnl_pct": f"{(today / base * 100) if base else 0:.2f}",
        "total_return_pct": f"{float(row['total_return_pct']):.2f}",
        "max_drawdown_pct": f"{float(row['max_drawdown_pct']):.2f}",
        "uptime_24h": "99.90" if row["status"] == "running" else "0.00",
        "last_heartbeat": row["last_seen"] or row["created_at"],
        "sparkline": sparkline_of(conn, row["id"]),
        "position_count": 0,
    }


def signal_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    runner = conn.execute("SELECT * FROM runners WHERE id = ?", (row["runner_id"],)).fetchone()
    account = conn.execute("SELECT name FROM accounts WHERE id = ?", (row["account_id"],)).fetchone()
    tags = loads(runner["tags"], []) if runner else []
    return {
        "id": row["id"], "ts": row["ts"], "runner_id": row["runner_id"],
        "runner_name": runner["name"] if runner else row["runner_id"],
        "platform": runner["platform"] if runner else "", "platform_label": PLATFORM_LABELS.get(runner["platform"], "") if runner else "",
        "strategy_type": runner["strategy_type"] if runner else "", "strategy_type_label": STRATEGY_TYPE_LABELS.get(runner["strategy_type"], "") if runner else "",
        "market": row["market"], "market_label": MARKET_LABELS.get(row["market"], row["market"]),
        "account_id": row["account_id"], "account_name": account["name"] if account else "",
        "instrument": row["instrument"], "instrument_name": row["instrument_name"],
        "direction": row["direction"], "side": row["side"], "action": row["action"],
        "price": f"{float(row['price']):.2f}" if row["price"] is not None else "",
        "qty": f"{float(row['qty']):g}",
        "amount": f"{float(row['amount']):.2f}",
        "status": row["status"], "msg": row["msg"], "tags": tags,
    }


def alert_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "fingerprint": row["fingerprint"], "rule": row["rule"], "severity": row["severity"],
        "status": row["status"], "runner_id": row["runner_id"],
        "runner_name": row["runner_name"] if "runner_name" in row.keys() else row["runner_id"],
        "summary": row["summary"], "starts_at": row["starts_at"], "ends_at": row["ends_at"],
        "acked_at": row["acked_at"], "labels": loads(row["labels"], {}), "updated_at": row["updated_at"],
    }


def alerts_query(conn: sqlite3.Connection, status: str) -> dict[str, Any]:
    if status == "history":
        rows = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.status = 'resolved' ORDER BY a.starts_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.status != 'resolved' ORDER BY a.starts_at DESC"
        ).fetchall()
    active_count = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE status != 'resolved'").fetchone()["n"]
    return {"items": [alert_view(row) for row in rows], "active_count": active_count}


def token_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "runner_id": row["runner_id"], "name": row["name"],
        "platform": row["platform"], "platform_label": PLATFORM_LABELS.get(row["platform"], ""),
        "markets": loads(row["markets"], []), "strategy_type": row["strategy_type"],
        "strategy_type_label": STRATEGY_TYPE_LABELS.get(row["strategy_type"], ""),
        "tags": loads(row["tags"], []), "note": row["note"], "token_prefix": row["token_prefix"],
        "status": row["status"], "created_at": row["created_at"], "last_used_at": row["last_used_at"],
        "request_count": row["request_count"],
    }


def channel_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "name": row["name"], "type": row["type"], "enabled": bool(row["enabled"]),
        "webhook_masked": mask_webhook(row["webhook"]), "secret_masked": mask_secret(row["secret"]),
        "at_mobiles": loads(row["at_mobiles"], []), "rate_limit_per_min": row["rate_limit_per_min"],
        "last_test_at": row["last_test_at"],
        "last_test_ok": None if row["last_test_ok"] is None else bool(row["last_test_ok"]),
    }


def settings_view(conn: sqlite3.Connection) -> dict[str, Any]:
    channels = [channel_view(row) for row in conn.execute("SELECT * FROM channels ORDER BY rowid").fetchall()]
    calendars = [
        {
            "id": row["id"], "name": row["name"], "timezone": row["timezone"],
            "sessions": loads(row["sessions"], []), "night": bool(row["night"]), "holidays": row["holidays"],
        }
        for row in conn.execute("SELECT * FROM calendars ORDER BY id").fetchall()
    ]
    return {
        "user": {"name": "Trader", "role": "owner", "timezone": "Asia/Shanghai"},
        "up_color_scheme": get_setting(conn, "up_color_scheme", "red_up"),
        "channels": channels,
        "calendars": calendars,
        "security": {
            "session_hours": SESSION_HOURS, "login_rate_limit": "5 次/分钟/IP",
            "totp_enabled": False, "last_password_change": "2026-10-01",
        },
        "about": {"version": "0.1.0", "build": "2026.11.03", "mode": "本地部署", "license": "Apache-2.0"},
    }


# ---------- 应用 ----------

app = FastAPI(title="qwatch", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "qwatch", "db": str(DB_PATH)}


@app.post("/api/v1/auth/login")
def login(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    if str(payload.get("password", "")) != PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    token = secrets.token_urlsafe(32)
    expires = (now_dt() + timedelta(hours=SESSION_HOURS)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with connect() as conn:
        conn.execute("INSERT INTO sessions(token_hash,user,expires_at) VALUES(?,?,?)", (token_hash(token), "Trader", expires))
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


@app.get("/api/v1/accounts")
def accounts_list(user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        account_rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        runner_rows = conn.execute("SELECT * FROM runners").fetchall()
        items = []
        for account in account_rows:
            linked = [row for row in runner_rows if account["id"] in loads(row["accounts"], [])]
            equity = sum(float(row["equity"]) for row in linked)
            today = sum(float(row["today_pnl"]) for row in linked)
            items.append({
                "id": account["id"], "name": account["name"], "venue": account["venue"], "market": account["market"],
                "currency": account["currency"], "equity": f"{equity:.2f}", "today_pnl": f"{today:.2f}",
                "today_pnl_pct": f"{(today / max(1, equity - today) * 100):.2f}",
                "positions_count": 0, "sparkline": [], "runner_ids": [row["id"] for row in linked],
            })
    return {"items": items, "total": len(items)}


@app.post("/api/v1/runners")
def create_runner(payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="策略名称必填")
    platform = str(payload.get("platform") or "custom")
    strategy_type = str(payload.get("strategy_type") or "other")
    market = str(payload.get("market") or "CN_A")
    tags = [str(tag).strip() for tag in (payload.get("tags") or []) if str(tag).strip()][:8]
    account_ids = [str(item) for item in (payload.get("accounts") or [])]
    with connect() as conn:
        if conn.execute("SELECT 1 FROM runners WHERE name = ?", (name,)).fetchone():
            raise HTTPException(status_code=400, detail="策略名称已存在")
        valid_accounts = conn.execute(
            "SELECT id, venue FROM accounts WHERE id IN (" + ",".join("?" for _ in account_ids) + ")", account_ids
        ).fetchall() if account_ids else []
        by_id = {row["id"]: row["venue"] for row in valid_accounts}
        account_ids = [item for item in account_ids if item in by_id]
        venue = by_id[account_ids[0]] if account_ids else ("XSHG" if market == "CN_A" else "XSGE")
        runner_id = "runner-" + uuid.uuid4().hex[:8]
        created = iso_now()
        conn.execute(
            """INSERT INTO runners(id,name,strategy,version,market,venue,platform,strategy_type,tags,status,accounts,
               equity,today_pnl,initial_equity,total_return_pct,max_drawdown_pct,sharpe,win_rate,uptime_30d,
               heartbeat_interval,last_seen,created_at,demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,0,0,0,0,0,0,0,30,NULL,?,0)""",
            (
                runner_id, name, "me/strategy_" + runner_id[7:], "0.1.0", market, venue, platform,
                strategy_type, dumps(tags), "offline", dumps(account_ids), created,
            ),
        )
        row = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        return {"runner": runner_view(conn, row)}


@app.get("/api/v1/runners")
def list_runners(
    status: str | None = Query(default=None), market: str | None = Query(default=None),
    q: str | None = Query(default=None), user: str = Depends(require_user),
) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        items = [runner_view(conn, row) for row in rows]
    if status:
        items = [item for item in items if item["status"] == status]
    if market:
        items = [item for item in items if item["market"] == market]
    if q:
        needle = q.lower()
        items = [item for item in items if needle in (item["name"] + item["strategy"] + item["id"]).lower()]
    return {"items": items, "total": len(items)}


def equity_points(conn: sqlite3.Connection, runner_id: str, days: int) -> list[sqlite3.Row]:
    rows = conn.execute("SELECT ts, equity FROM equity_points WHERE runner_id = ? ORDER BY ts", (runner_id,)).fetchall()
    if len(rows) <= days:
        return rows
    return rows[-days:]


@app.get("/api/v1/runners/{runner_id}")
def runner_detail(runner_id: str, range_key: str = Query(default="all", alias="range"), user: str = Depends(require_user)) -> dict[str, Any]:
    days = RANGE_DAYS.get(range_key, 100000)
    with connect() as conn:
        row = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runner 不存在")
        points = equity_points(conn, runner_id, days)
        if not points:
            points = []
        equity = []
        drawdown = []
        peak = 0.0
        initial = float(row["initial_equity"]) or float(row["equity"]) or 1
        for point in points:
            value = float(point["equity"])
            peak = max(peak, value)
            equity.append({"ts": point["ts"], "nav": round(value / initial, 6) if initial else 1, "value": f"{value:.2f}"})
            drawdown.append({"ts": point["ts"], "value": round((value / peak - 1) * 100, 2) if peak else 0})
        if not equity:
            equity = [{"ts": row["last_seen"] or row["created_at"], "nav": 1, "value": f"{float(row['equity']):.2f}"}]
            drawdown = [{"ts": equity[0]["ts"], "value": 0}]
        last_seen = dt_from(row["last_seen"])
        timeline = []
        now = now_dt()
        for index in range(47, -1, -1):
            ts = now - timedelta(minutes=30 * index)
            recent = last_seen and (now - last_seen).total_seconds() < 60
            status = "ok" if recent and index < 2 else ("miss" if row["status"] == "offline" and index < 2 else ("ok" if recent else "miss"))
            timeline.append({"ts": ts.isoformat(timespec="seconds").replace("+00:00", "Z"), "status": status})
        outages = []
        if row["status"] == "offline" and last_seen:
            outages = [{"start": last_seen.isoformat(timespec="seconds").replace("+00:00", "Z"), "end": None, "duration_s": int((now - last_seen).total_seconds())}]
        signals = conn.execute("SELECT * FROM signals WHERE runner_id = ? ORDER BY ts DESC LIMIT 40", (runner_id,)).fetchall()
        alert_rows = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.runner_id = ? ORDER BY a.starts_at DESC",
            (runner_id,),
        ).fetchall()
        account_ids = loads(row["accounts"], [])
        return {
            "runner": runner_view(conn, row), "range": range_key,
            "metrics": {
                "total_return_pct": f"{float(row['total_return_pct']):.2f}",
                "today_pnl": f"{float(row['today_pnl']):.2f}",
                "max_drawdown_pct": f"{float(row['max_drawdown_pct']):.2f}",
                "sharpe": f"{float(row['sharpe']):.2f}", "win_rate_pct": f"{float(row['win_rate']):.1f}",
                "uptime_30d": f"{float(row['uptime_30d']):.2f}",
            },
            "equity": equity, "drawdown": drawdown, "heartbeat_timeline": timeline, "outages": outages,
            "signals": [signal_view(conn, signal) for signal in signals],
            "positions": [],
            "alerts": [alert_view(alert) for alert in alert_rows],
            "config": {
                "strategy": row["strategy"], "version": row["version"], "host": "trade-pc", "pid": 12884,
                "calendar_id": "cffex" if row["venue"] == "CFFEX" else ("cn_a" if row["market"] == "CN_A" else "cn_fut_0230"),
                "heartbeat_interval_s": row["heartbeat_interval"], "soft_timeout_s": 45, "hard_timeout_s": 60,
                "started_at": row["created_at"], "last_seq": int((now - (dt_from(row["created_at"]) or now)).total_seconds() / 30),
                "env": "production", "accounts": account_ids,
            },
        }


@app.get("/api/v1/overview")
def overview(range_key: str = Query(default="all", alias="range"), user: str = Depends(require_user)) -> dict[str, Any]:
    days = RANGE_DAYS.get(range_key, 100000)
    with connect() as conn:
        runner_rows = conn.execute("SELECT * FROM runners ORDER BY created_at").fetchall()
        runners = [runner_view(conn, row) for row in runner_rows]
        total = sum(float(row["equity"]) for row in runner_rows)
        today = sum(float(row["today_pnl"]) for row in runner_rows)
        active_alerts = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE status != 'resolved'").fetchone()["n"]
        points = conn.execute("SELECT runner_id, ts, equity FROM equity_points ORDER BY ts").fetchall()
        by_day: dict[str, dict[str, float]] = {}
        for point in points:
            day = point["ts"][:10]
            by_day.setdefault(day, {})[point["runner_id"]] = float(point["equity"])
        curve = []
        for day in sorted(by_day):
            value = sum(by_day[day].values())
            curve.append({"ts": day + "T07:00:00Z", "nav": 0, "value": value})
        if not curve:
            curve = [{"ts": iso_now(), "nav": 1, "value": total}]
        curve = curve[-days:]
        first = curve[0]["value"] or 1
        for index, point in enumerate(curve):
            point["nav"] = round(point["value"] / first, 6)
            point["value"] = f"{point['value']:.2f}"
        benchmark = []
        for index, point in enumerate(curve):
            value = float(point["value"]) * (0.94 + index / max(1, len(curve)) * 0.10)
            benchmark.append({"ts": point["ts"], "value": f"{value:.2f}"})
        recent = conn.execute("SELECT * FROM signals ORDER BY ts DESC LIMIT 8").fetchall()
        alert_rows = conn.execute(
            "SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.status != 'resolved' ORDER BY a.starts_at DESC LIMIT 4"
        ).fetchall()
        return {
            "as_of": iso_now(), "total_equity": f"{total:.2f}", "today_pnl": f"{today:.2f}",
            "today_pnl_pct": f"{(today / max(1, total - today) * 100):.2f}",
            "running": sum(1 for row in runner_rows if row["status"] == "running"),
            "total": len(runner_rows), "active_alerts": active_alerts, "range": range_key,
            "equity_curve": curve, "benchmark": benchmark, "runners": runners,
            "alerts": [alert_view(row) for row in alert_rows],
            "recent_signals": [signal_view(conn, row) for row in recent],
        }


@app.get("/api/v1/signals")
def signals_list(
    runner_id: str | None = None, account_id: str | None = None, platform: str | None = None,
    market: str | None = None, strategy_type: str | None = None, side: str | None = None,
    status: str | None = None, instrument: str | None = None, tag: str | None = None,
    date_from: str | None = Query(default=None, alias="from"), date_to: str | None = Query(default=None, alias="to"),
    cursor: int = 0, limit: int = Query(default=200, ge=1, le=500), user: str = Depends(require_user),
) -> dict[str, Any]:
    where, params = [], []
    if runner_id:
        where.append("s.runner_id = ?"); params.append(runner_id)
    if account_id:
        where.append("s.account_id = ?"); params.append(account_id)
    if market:
        where.append("s.market = ?"); params.append(market)
    if side:
        where.append("s.side = ?"); params.append(side)
    if status:
        where.append("s.status = ?"); params.append(status)
    if instrument:
        where.append("s.instrument LIKE ?"); params.append("%" + instrument + "%")
    if platform:
        where.append("r.platform = ?"); params.append(platform)
    if strategy_type:
        where.append("r.strategy_type = ?"); params.append(strategy_type)
    if tag:
        where.append("r.tags LIKE ?"); params.append('%"' + tag + '"%')
    if date_from:
        where.append("s.ts >= ?"); params.append(date_from)
    if date_to:
        where.append("s.ts <= ?"); params.append(date_to)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM signals s JOIN runners r ON r.id = s.runner_id" + clause, params).fetchone()["n"]
        sum_amount = conn.execute("SELECT COALESCE(SUM(s.amount),0) AS n FROM signals s JOIN runners r ON r.id = s.runner_id" + clause, params).fetchone()["n"]
        rows = conn.execute(
            "SELECT s.* FROM signals s JOIN runners r ON r.id = s.runner_id" + clause + " ORDER BY s.ts DESC LIMIT ? OFFSET ?",
            params + [limit, cursor],
        ).fetchall()
        return {
            "items": [signal_view(conn, row) for row in rows], "total": total,
            "sum_amount": f"{float(sum_amount):.2f}", "limit": limit, "next_cursor": None,
        }


@app.get("/api/v1/alerts")
def alerts_list(status: str = Query(default="active"), user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        return alerts_query(conn, status)


@app.post("/api/v1/alerts/{alert_id}/ack")
def ack_alert(alert_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.id = ?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="告警不存在")
        conn.execute("UPDATE alerts SET status = 'acknowledged', acked_at = ?, updated_at = ? WHERE id = ?", (iso_now(), iso_now(), alert_id))
        updated = conn.execute("SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.id = ?", (alert_id,)).fetchone()
        return {"alert": alert_view(updated)}


@app.post("/api/v1/alerts/{alert_id}/silence")
def silence_alert(alert_id: str, payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    duration = str(payload.get("duration", "1h"))
    hours = {"1h": 1, "4h": 4, "24h": 24}.get(duration, 1)
    until = (now_dt() + timedelta(hours=hours)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with connect() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="告警不存在")
        labels = loads(row["labels"], {})
        labels["silenced_until"] = until
        conn.execute(
            "UPDATE alerts SET status = 'acknowledged', acked_at = ?, labels = ?, updated_at = ? WHERE id = ?",
            (iso_now(), dumps(labels), iso_now(), alert_id),
        )
        updated = conn.execute("SELECT a.*, r.name AS runner_name FROM alerts a LEFT JOIN runners r ON r.id = a.runner_id WHERE a.id = ?", (alert_id,)).fetchone()
        return {"alert": alert_view(updated)}


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
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="策略名称必填")
    runner_id = str(payload.get("runner_id") or "").strip() or None
    token = "qw_" + secrets.token_hex(32)
    record_id = "tok_" + uuid.uuid4().hex[:10]
    created = iso_now()
    with connect() as conn:
        if runner_id and not conn.execute("SELECT 1 FROM runners WHERE id = ?", (runner_id,)).fetchone():
            raise HTTPException(status_code=400, detail="策略不存在")
        conn.execute(
            """INSERT INTO tokens(id,runner_id,name,platform,markets,strategy_type,tags,note,token_hash,token_prefix,status,created_at,last_used_at,request_count)
               VALUES(?,?,?,?,?,?,?,?,?,?,'active',?,NULL,0)""",
            (
                record_id, runner_id, name, str(payload.get("platform") or ""), dumps(payload.get("markets") or []),
                str(payload.get("strategy_type") or ""), dumps(payload.get("tags") or []), str(payload.get("note") or ""),
                token_hash(token), token_prefix(token), created,
            ),
        )
        row = conn.execute("SELECT * FROM tokens WHERE id = ?", (record_id,)).fetchone()
        return {"token": token, "record": token_view(row)}


@app.post("/api/v1/tokens/{token_id}/revoke")
def revoke_token(token_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE id = ?", (token_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="令牌不存在")
        conn.execute("UPDATE tokens SET status = 'revoked' WHERE id = ?", (token_id,))
        updated = conn.execute("SELECT * FROM tokens WHERE id = ?", (token_id,)).fetchone()
        return {"record": token_view(updated)}


@app.get("/api/v1/settings")
def get_settings(user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        return settings_view(conn)


@app.put("/api/v1/settings")
def save_settings(payload: dict[str, Any] = Body(default={}), user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        if "up_color_scheme" in payload:
            set_setting(conn, "up_color_scheme", str(payload["up_color_scheme"]))
        for patch in payload.get("channels") or []:
            channel_id = patch.get("id")
            if not channel_id:
                continue
            row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
            if not row:
                continue
            enabled = 1 if patch.get("enabled", bool(row["enabled"])) else 0
            webhook = str(patch.get("webhook", row["webhook"]))
            secret = str(patch.get("secret", row["secret"]))
            mobiles = patch.get("at_mobiles", loads(row["at_mobiles"], []))
            conn.execute(
                "UPDATE channels SET enabled = ?, webhook = ?, secret = ?, at_mobiles = ? WHERE id = ?",
                (enabled, webhook, secret, dumps(mobiles), channel_id),
            )
        return settings_view(conn)


@app.post("/api/v1/channels/{channel_id}/test")
def test_channel(channel_id: str, user: str = Depends(require_user)) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="渠道不存在")
        webhook = row["webhook"]
        if not webhook:
            raise HTTPException(status_code=400, detail="未配置 Webhook")
    body = json.dumps({"msgtype": "text", "text": {"content": "qwatch 测试消息：通知渠道联通正常"}}).encode("utf-8")
    request = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json"}, method="POST")
    ok = False
    message = ""
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            ok = response.status < 300
            message = "测试消息已发送"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        message = "发送失败：" + str(exc)
    with connect() as conn:
        conn.execute(
            "UPDATE channels SET last_test_at = ?, last_test_ok = ? WHERE id = ?",
            (iso_now(), 1 if ok else 0, channel_id),
        )
    if not ok:
        raise HTTPException(status_code=502, detail=message)
    return {"ok": True, "channel_id": channel_id, "message": message, "latency_ms": 0, "at": iso_now()}


# ---------- 策略上报 ----------

@app.post("/api/v1/report")
def report(payload: dict[str, Any] = Body(default={}), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    with connect() as conn:
        token, runner = strategy_token(conn, authorization)
        now = iso_now()
        conn.execute("UPDATE tokens SET last_used_at = ?, request_count = request_count + 1 WHERE id = ?", (now, token["id"]))
        conn.execute("UPDATE runners SET last_seen = ?, status = 'running', demo = 0 WHERE id = ?", (now, runner["id"]))
        conn.execute(
            "UPDATE alerts SET status = 'resolved', ends_at = ?, updated_at = ? WHERE runner_id = ? AND rule = 'heartbeat_lost' AND status != 'resolved'",
            (now, now, runner["id"]),
        )
        if payload.get("msg"):
            conn.execute("UPDATE runners SET last_msg = ? WHERE id = ?", (str(payload["msg"])[:200], runner["id"]))
        if isinstance(payload.get("equity"), (int, float)) and math.isfinite(float(payload["equity"])):
            equity = float(payload["equity"])
            conn.execute("UPDATE runners SET equity = ? WHERE id = ?", (equity, runner["id"]))
            conn.execute("INSERT INTO equity_points(runner_id, ts, equity) VALUES(?,?,?)", (runner["id"], now, equity))

        if isinstance(payload.get("loop"), (int, float)):
            loop = int(payload["loop"])
            if runner["last_loop"] == loop:
                same = int(runner["loop_same"]) + 1
            else:
                same = 1
            conn.execute("UPDATE runners SET last_loop = ?, loop_same = ? WHERE id = ?", (loop, same, runner["id"]))
            existing = conn.execute(
                "SELECT * FROM alerts WHERE runner_id = ? AND rule = 'runner_stalled' AND status != 'resolved'", (runner["id"],)
            ).fetchone()
            if same >= 3 and not existing:
                conn.execute(
                    """INSERT INTO alerts(id,fingerprint,rule,severity,status,runner_id,summary,starts_at,ends_at,acked_at,labels,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,NULL,NULL,?,?)""",
                    (alert_id(), fingerprint("runner_stalled", runner["id"]), "runner_stalled", "P0", "firing", runner["id"],
                     "策略卡死：" + runner["name"] + " 的 loop 连续 " + str(same) + " 次未增长（当前 loop=" + str(loop) + "）",
                     now, dumps({"host": "runner", "loop": str(loop)}), now),
                )
            elif same < 3 and existing:
                conn.execute("UPDATE alerts SET status = 'resolved', ends_at = ?, updated_at = ? WHERE id = ?", (now, now, existing["id"]))
        if payload.get("last_tick"):
            try:
                tick_ts = parse_iso(str(payload["last_tick"]))
                conn.execute("UPDATE runners SET last_tick = ? WHERE id = ?", (tick_ts, runner["id"]))
            except HTTPException:
                pass

        signal_keys = ("symbol", "direction", "action", "qty", "price", "amount")
        if not any(key in payload and payload[key] not in (None, "") for key in signal_keys):
            return {"ok": True, "heartbeat": True, "signal_id": None, "server_time": iso_now()}

        symbol = str(payload.get("symbol") or "").strip()
        direction = str(payload.get("direction") or "").strip().lower()
        action = str(payload.get("action") or "").strip().lower()
        try:
            qty = float(payload.get("qty"))
        except (TypeError, ValueError):
            qty = 0
        if not symbol:
            raise HTTPException(status_code=400, detail="signal.symbol 必填")
        if direction not in DIRECTIONS:
            raise HTTPException(status_code=400, detail="signal.direction 必须是 long / short")
        if action not in ACTIONS:
            raise HTTPException(status_code=400, detail="signal.action 必须是 open / close / add / reduce")
        if not math.isfinite(qty) or qty <= 0:
            raise HTTPException(status_code=400, detail="signal.qty 必须是正数")

        signal_id = str(payload.get("id") or "").strip() or ("sig_" + uuid.uuid4().hex)
        if conn.execute("SELECT 1 FROM signals WHERE id = ?", (signal_id,)).fetchone():
            return {"ok": True, "heartbeat": True, "signal_id": signal_id, "server_time": iso_now()}

        code = symbol.split(":")[-1]
        name, market, venue, mult = INSTRUMENTS.get(code, (code, runner["market"], runner["venue"], 1))
        price = float(payload["price"]) if isinstance(payload.get("price"), (int, float)) else None
        amount = float(payload["amount"]) if isinstance(payload.get("amount"), (int, float)) else ((price or 0) * qty * mult)
        side = "buy" if (direction == "long") == (action in ("open", "add")) else "sell"
        account_ids = loads(runner["accounts"], [])
        account_id = str(payload.get("account") or "").strip()
        if not account_id:
            account_id = account_ids[0] if account_ids else ""
        ts = parse_iso(str(payload["ts"])) if payload.get("ts") else iso_now()
        conn.execute(
            """INSERT INTO signals(id,ts,runner_id,direction,side,action,instrument,instrument_name,market,venue,
               account_id,price,qty,amount,status,msg) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (signal_id, ts, runner["id"], direction, side, action, code, name, market, venue, account_id,
             price, qty, amount, "pending", str(payload.get("msg") or "")[:200]),
        )
        return {"ok": True, "heartbeat": True, "signal_id": signal_id, "server_time": iso_now()}


# ---------- 后台 watchdog ----------

async def watchdog_loop() -> None:
    while True:
        try:
            with connect() as conn:
                runners = conn.execute("SELECT * FROM runners WHERE last_seen IS NOT NULL AND status != 'offline' AND demo = 0").fetchall()
                now = now_dt()
                for runner in runners:
                    last_seen = dt_from(runner["last_seen"])
                    if not last_seen:
                        continue
                    if (now - last_seen).total_seconds() <= HEARTBEAT_TIMEOUT_S:
                        continue
                    conn.execute("UPDATE runners SET status = 'offline' WHERE id = ?", (runner["id"],))
                    existing = conn.execute(
                        "SELECT 1 FROM alerts WHERE runner_id = ? AND rule = 'heartbeat_lost' AND status != 'resolved'", (runner["id"],)
                    ).fetchone()
                    if not existing:
                        starts = iso_now()
                        conn.execute(
                            """INSERT INTO alerts(id,fingerprint,rule,severity,status,runner_id,summary,starts_at,ends_at,acked_at,labels,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,NULL,NULL,?,?)""",
                            (alert_id(), fingerprint("heartbeat_lost", runner["id"]), "heartbeat_lost", "P0", "firing", runner["id"],
                             "策略心跳丢失：" + runner["name"] + " 已超过 60 秒未上报", starts, dumps({"timeout_s": "60"}), starts),
                        )
        except Exception:
            pass
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    asyncio.create_task(watchdog_loop())


# ---------- 前端静态文件 ----------

if DIST.exists():
    assets = DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not Found")
