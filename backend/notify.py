"""钉钉 P0 投递：加签、异步重试、投递日志（alert_deliveries）。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from .db import connect, iso_now, loads

logger = logging.getLogger("qwatch.notify")
DINGTALK_KEYWORD = os.environ.get("QWATCH_DINGTALK_KEYWORD", "[+]")
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (2, 5, 15)


def dingtalk_endpoint(webhook: str, secret: str) -> str:
    """加签（secret 以 SEC 开头时）后的钉钉 webhook URL。"""
    if secret and secret.startswith("SEC"):
        timestamp = str(int(time.time() * 1000))
        digest = hmac.new(secret.encode("utf-8"), (timestamp + "\n" + secret).encode("utf-8"), hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(digest))
        return webhook + ("&" if "?" in webhook else "?") + "timestamp=" + timestamp + "&sign=" + sign
    return webhook


def deliver_sync(webhook: str, secret: str, text: str, timeout: float = 6.0) -> tuple[bool, str]:
    """同步发送一条钉钉文本消息；返回 (ok, error)。"""
    if not webhook:
        return False, "未配置 webhook"
    if "demo-" in webhook:
        return False, "demo 渠道跳过"
    url = dingtalk_endpoint(webhook, secret)
    body = json.dumps({"msgtype": "text", "text": {"content": DINGTALK_KEYWORD + " " + text}}, ensure_ascii=False)
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)
    result = loads(raw, {})
    if isinstance(result, dict) and int(result.get("errcode", 0) or 0) != 0:
        return False, "errcode=" + str(result.get("errcode")) + " " + str(result.get("errmsg") or raw[:160])
    return True, ""


def _next_attempt(attempts: int) -> str:
    delay = BACKOFF_SECONDS[min(attempts, len(BACKOFF_SECONDS) - 1)]
    return (iso_now_dt() + timedelta(seconds=delay)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def iso_now_dt():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def enqueue_for_alert(conn, alert_row, kind: str = "firing") -> int:
    """为启用的真实渠道创建投递记录（demo 占位渠道跳过）。"""
    count = 0
    for channel in conn.execute("SELECT * FROM channels WHERE enabled = 1").fetchall():
        webhook = str(channel["webhook"] or "")
        if not webhook or "demo-" in webhook:
            continue
        now = iso_now()
        conn.execute(
            "INSERT INTO alert_deliveries(alert_id, channel_id, kind, status, attempts, last_error, created_at, "
            "updated_at, next_attempt_at) VALUES(?,?,?,'pending',0,'',?,?,?)",
            (alert_row["id"], channel["id"], kind, now, now, now),
        )
        count += 1
    if count:
        logger.info("告警 %s 投递入队 %d 个渠道（%s）", alert_row["id"], count, kind)
    return count


def cancel_pending_deliveries(conn, alert_id: str, reason: str = "告警已恢复，取消投递") -> int:
    """告警恢复/暂停时取消尚未发出的 firing 投递，避免恢复后仍补发旧告警。"""
    cursor = conn.execute(
        "UPDATE alert_deliveries SET status='failed', last_error=?, updated_at=? "
        "WHERE alert_id = ? AND kind = 'firing' AND status = 'pending'",
        (reason, iso_now(), alert_id),
    )
    if cursor.rowcount:
        logger.info("取消未发送投递 %d 条：alert=%s", cursor.rowcount, alert_id)
    return cursor.rowcount


def enqueue_recovery(conn, alert_row) -> int:
    has_firing = conn.execute(
        "SELECT 1 FROM alert_deliveries WHERE alert_id = ? AND kind = 'firing' LIMIT 1", (alert_row["id"],)
    ).fetchone()
    if not has_firing:
        return 0
    return enqueue_for_alert(conn, alert_row, kind="recovery")


async def delivery_loop() -> None:
    """后台投递循环：1s 轮询到期记录，最多重试 3 次。"""
    while True:
        try:
            due: list[dict] = []
            with connect() as conn:
                rows = conn.execute(
                    "SELECT d.*, c.webhook AS webhook, c.secret AS secret, c.name AS channel_name, "
                    "a.summary AS summary, a.rule AS rule, a.status AS alert_status, a.labels AS alert_labels "
                    "FROM alert_deliveries d "
                    "JOIN channels c ON c.id = d.channel_id JOIN alerts a ON a.id = d.alert_id "
                    "WHERE d.status = 'pending' AND d.next_attempt_at <= ? AND c.enabled = 1 "
                    "ORDER BY d.id LIMIT 20",
                    (iso_now(),),
                ).fetchall()
                due = [dict(row) for row in rows]
            for row in due:
                if row["kind"] == "firing":
                    if row["alert_status"] == "resolved":
                        with connect() as conn:
                            conn.execute(
                                "UPDATE alert_deliveries SET status='failed', last_error='告警已恢复，取消投递', "
                                "updated_at=? WHERE id=? AND status='pending'",
                                (iso_now(), row["id"]),
                            )
                        logger.info("投递取消（已恢复）：alert=%s", row["alert_id"])
                        continue
                    silenced_until = str((loads(row["alert_labels"], {}) or {}).get("silenced_until") or "")
                    if silenced_until and silenced_until > iso_now():
                        with connect() as conn:
                            conn.execute(
                                "UPDATE alert_deliveries SET next_attempt_at=?, updated_at=? "
                                "WHERE id=? AND status='pending'",
                                (silenced_until, iso_now(), row["id"]),
                            )
                        logger.info("投递静默延后：alert=%s until=%s", row["alert_id"], silenced_until)
                        continue
                prefix = "【qwatch P0 告警】" if row["kind"] == "firing" else "【qwatch P0 恢复】"
                ok, error = await asyncio.to_thread(deliver_sync, row["webhook"], row["secret"], prefix + row["summary"])
                with connect() as conn:
                    current = conn.execute("SELECT attempts, status FROM alert_deliveries WHERE id = ?", (row["id"],)).fetchone()
                    if current is None or current["status"] != "pending":
                        continue
                    alert = conn.execute("SELECT status, labels FROM alerts WHERE id = ?", (row["alert_id"],)).fetchone()
                    alert_status = alert["status"] if alert else "resolved"
                    silenced_until = str((loads(alert["labels"], {}) or {}).get("silenced_until") or "") if alert else ""
                    attempts = int(current["attempts"]) + (0 if ok else 1)
                    if ok:
                        conn.execute(
                            "UPDATE alert_deliveries SET status='sent', attempts=?, last_error='', updated_at=?, sent_at=? "
                            "WHERE id = ?",
                            (attempts, iso_now(), iso_now(), row["id"]),
                        )
                        logger.info("钉钉投递成功：alert=%s channel=%s kind=%s", row["alert_id"], row["channel_name"], row["kind"])
                    elif alert_status == "resolved":
                        conn.execute(
                            "UPDATE alert_deliveries SET status='failed', attempts=?, last_error='告警已恢复，取消投递', "
                            "updated_at=? WHERE id = ?",
                            (attempts, iso_now(), row["id"]),
                        )
                        logger.info("投递取消（已恢复）：alert=%s", row["alert_id"])
                    elif silenced_until and silenced_until > iso_now():
                        conn.execute(
                            "UPDATE alert_deliveries SET attempts=?, last_error=?, updated_at=?, next_attempt_at=? "
                            "WHERE id = ?",
                            (attempts, str(error)[:500], iso_now(), silenced_until, row["id"]),
                        )
                        logger.info("投递静默延后：alert=%s until=%s", row["alert_id"], silenced_until)
                    elif attempts >= MAX_ATTEMPTS:
                        conn.execute(
                            "UPDATE alert_deliveries SET status='failed', attempts=?, last_error=?, updated_at=? WHERE id = ?",
                            (attempts, str(error)[:500], iso_now(), row["id"]),
                        )
                        logger.warning("钉钉投递最终失败：alert=%s channel=%s err=%s", row["alert_id"], row["channel_name"], error)
                    else:
                        conn.execute(
                            "UPDATE alert_deliveries SET attempts=?, last_error=?, updated_at=?, next_attempt_at=? WHERE id = ?",
                            (attempts, str(error)[:500], iso_now(), _next_attempt(attempts), row["id"]),
                        )
                        logger.warning("钉钉投递失败将重试：alert=%s channel=%s attempts=%d err=%s",
                                       row["alert_id"], row["channel_name"], attempts, error)
        except Exception:  # noqa: BLE001 - 后台循环不能退出
            logger.exception("钉钉投递循环异常")
        await asyncio.sleep(1)


def send_test(webhook: str, secret: str) -> tuple[bool, str, float]:
    started = time.perf_counter()
    ok, error = deliver_sync(webhook, secret, "qwatch 测试消息：通知渠道联通正常")
    latency = round((time.perf_counter() - started) * 1000, 1)
    return ok, error, latency
