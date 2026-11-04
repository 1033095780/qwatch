"""qwatch Python SDK v0.2 — 零依赖策略接入库（心跳 / 动态 / 信号，按进程分文件日志）。

一个策略进程一个实例：实例绑定稳定进程名 instrument，自动心跳、动态消息和交易信号都走
POST /api/v1/report；本地按 instrument 分文件记录 HTTP 日志，失败自动重试，401 停止上报。
不提供净值/盈亏/权益相关方法（v0.2 后端不再接收这些字段）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

__all__ = ["Qwatch", "QwatchError", "AuthError"]

# 日志轮转：单文件 5MB，保留 3 个历史文件
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
# 网络类失败的重试退避：0.5s 起，上限 5s
RETRY_BASE_S = 0.5
RETRY_MAX_S = 5.0

_LOGGERS: Dict[str, logging.Logger] = {}
_LOGGERS_LOCK = threading.Lock()


class QwatchError(Exception):
    """SDK 基础异常。"""


class AuthError(QwatchError):
    """token 无效或已吊销。"""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("._") or "instrument"


def _file_logger(path: Path) -> logging.Logger:
    """同一日志文件在进程内只挂一个 RotatingFileHandler，多个实例共享。"""
    key = str(path.resolve())
    with _LOGGERS_LOCK:
        logger = _LOGGERS.get(key)
        if logger is not None:
            return logger
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            key, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger = logging.getLogger("qwatch.file." + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12])
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _LOGGERS[key] = logger
        return logger


class Qwatch:
    """一个策略进程一个实例。

        q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", instrument="rb")
        q.tick()                                    # 主循环每轮调用，心跳携带 loop
        q.msg("夜盘暂停")                            # 动态消息
        q.signal("rb2601", "long", "open", 2, price=3521, msg="突破前高")

    - 初始化即同步发一次心跳（token 错立刻抛 AuthError），之后每 heartbeat 秒自动心跳。
    - 心跳 / 消息 / 信号统一 POST /api/v1/report，instrument 自动补齐。
    - 网络或 5xx 失败进入队列自动重试；4xx 参数错误丢弃并记日志；401 停止上报。
    - 本地日志默认 log_dir/{instrument}.log，5MB x 3 轮转，不记录 token。
    """

    DIRECTIONS = {"long", "short"}
    ACTIONS = {"open", "close", "add", "reduce"}

    def __init__(
        self,
        base_url: str,
        token: str,
        heartbeat: float = 30,
        timeout: float = 5,
        queue_size: int = 1000,
        instrument: str = "rb",
        log_dir: str = "logs",
        log_path: Optional[str] = None,
    ) -> None:
        base = str(base_url or "").strip()
        if not base.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        secret = str(token or "").strip()
        if not secret:
            raise ValueError("token 不能为空")
        instrument = str(instrument or "").strip()
        if not instrument:
            raise ValueError("instrument 不能为空")
        interval = float(heartbeat)
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("heartbeat 必须大于 0")
        wait = float(timeout)
        if not math.isfinite(wait) or wait <= 0:
            raise ValueError("timeout 必须大于 0")
        capacity = int(queue_size)
        if capacity <= 0:
            raise ValueError("queue_size 必须大于 0")

        self._url = base.rstrip("/") + "/api/v1/report"
        self._token = secret
        self._instrument = instrument
        self._interval = interval
        self._timeout = wait
        self._queue_size = capacity
        self._log_file = Path(log_path) if log_path else Path(log_dir) / (_safe_name(instrument) + ".log")
        self._log = _file_logger(self._log_file)

        self._queue: Deque[Tuple[Dict[str, Any], int]] = deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop = 0
        self._last_tick: Optional[str] = None
        self._auth_failed = False
        self._last_error: Optional[str] = None
        self._stats = {"sent": 0, "failed": 0, "retried": 0, "dropped": 0, "queued": 0}

        self._log.info(
            "event=init instrument=%s heartbeat=%s timeout=%s queue_size=%s url=%s log=%s",
            instrument, interval, wait, capacity, base, self._log_file,
        )

        # 初始化同步心跳：token 错立刻暴露；网络失败则入队由后台重试
        payload = self._heartbeat_payload()
        ok, status, detail, latency = self._post(payload)
        if status == 401:
            self._log.error("instrument=%s action=heartbeat status=401 event=auth_failed error=%s", instrument, detail)
            raise AuthError("token 无效或已吊销")
        self._record(payload, ok, status, detail, latency, 1)
        if not ok:
            self._enqueue(payload, 1)

        self._thread = threading.Thread(target=self._worker, name="qwatch-" + _safe_name(instrument), daemon=True)
        self._thread.start()

    # ---------- 对外方法 ----------

    def tick(self, last_tick: Optional[str] = None) -> int:
        """主循环每轮调用：loop 自增，不发送请求；下一次自动心跳携带 loop。"""
        with self._lock:
            self._loop += 1
            if last_tick is not None:
                self._last_tick = str(last_tick)
            return self._loop

    def nav(self, value: float) -> None:
        """上报策略组净值（同一 token 下任意进程可报；服务端以最后一次为准）。"""
        number = self._number(value, "nav")
        if number <= 0:
            raise ValueError("nav 必须大于 0")
        self._enqueue({"ts": _now_iso(), "instrument": self._instrument, "nav": number})

    def equity(self, value: float) -> None:
        """上报策略组权益（同一 token 下任意进程可报；服务端以最后一次为准）。"""
        number = self._number(value, "equity")
        if number <= 0:
            raise ValueError("equity 必须大于 0")
        self._enqueue({"ts": _now_iso(), "instrument": self._instrument, "equity": number})

    def msg(self, text: str) -> None:
        """发送一条动态消息（也算心跳）。"""
        text = str(text or "").strip()[:200]
        if not text:
            return
        self._enqueue({"ts": _now_iso(), "instrument": self._instrument, "msg": text})

    def signal(
        self,
        contract: str,
        direction: str,
        action: str,
        qty: float,
        *,
        price: Optional[float] = None,
        amount: Optional[float] = None,
        msg: Optional[str] = None,
        id: Optional[str] = None,
    ) -> str:
        """上报一个交易信号，自动补齐 ts / instrument / id。返回 signal_id。"""
        contract = str(contract or "").strip()
        if not contract:
            raise ValueError("contract 不能为空")
        direction = str(direction or "").strip().lower()
        if direction not in self.DIRECTIONS:
            raise ValueError("direction 必须是 long 或 short")
        action = str(action or "").strip().lower()
        if action not in self.ACTIONS:
            raise ValueError("action 必须是 open / close / add / reduce")
        qty = self._number(qty, "qty")
        if qty <= 0:
            raise ValueError("qty 必须是正数")

        payload: Dict[str, Any] = {
            "ts": _now_iso(),
            "instrument": self._instrument,
            # v0.2 契约信号字段写作 symbol / contract，两个命名携带同一合约代码以兼容后端实现
            "symbol": contract,
            "contract": contract,
            "direction": direction,
            "action": action,
            "qty": qty,
        }
        if price is not None:
            payload["price"] = self._number(price, "price", minimum=0.0)
        if amount is not None:
            payload["amount"] = self._number(amount, "amount", minimum=0.0)
        if msg:
            payload["msg"] = str(msg).strip()[:200]
        payload["id"] = str(id).strip() if id else "sig_" + uuid.uuid4().hex
        self._enqueue(payload)
        return payload["id"]

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def instrument(self) -> str:
        return self._instrument

    @property
    def log_path(self) -> str:
        return str(self._log_file)

    def close(self, flush_timeout: float = 2.0) -> None:
        """停止自动心跳，尽力把队列里剩余请求发完。"""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=flush_timeout)
        deadline = time.monotonic() + max(0.0, float(flush_timeout))
        while time.monotonic() < deadline:
            item = self._pop()
            if item is None:
                break
            payload, attempt = item
            ok, status, detail, latency = self._post(payload)
            self._record(payload, ok, status, detail, latency, attempt)
        self._log.info(
            "event=close instrument=%s sent=%s failed=%s dropped=%s retried=%s",
            self._instrument, self._stats["sent"], self._stats["failed"], self._stats["dropped"], self._stats["retried"],
        )

    def __enter__(self) -> "Qwatch":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------- 内部 ----------

    @staticmethod
    def _number(value: Any, name: str, minimum: Optional[float] = None) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(name + " 必须是数字") from None
        if not math.isfinite(number):
            raise ValueError(name + " 必须是有限数字")
        if minimum is not None and number < minimum:
            raise ValueError(name + " 不能小于 " + str(minimum))
        return number

    @staticmethod
    def _action_of(payload: Dict[str, Any]) -> str:
        if "symbol" in payload or "contract" in payload:
            return "signal"
        if "msg" in payload:
            return "msg"
        return "heartbeat"

    def _heartbeat_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"ts": _now_iso(), "instrument": self._instrument}
        with self._lock:
            if self._loop:
                payload["loop"] = self._loop
            if self._last_tick:
                payload["last_tick"] = self._last_tick
        return payload

    def _enqueue(self, payload: Dict[str, Any], attempt: int = 1) -> None:
        with self._lock:
            if len(self._queue) >= self._queue_size:
                self._queue.popleft()
                self._stats["dropped"] += 1
                self._log.warning("instrument=%s event=queue_full dropped=1 action=%s", self._instrument, self._action_of(payload))
            self._queue.append((payload, attempt))
            self._stats["queued"] = len(self._queue)

    def _pop(self) -> Optional[Tuple[Dict[str, Any], int]]:
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.popleft()
            self._stats["queued"] = len(self._queue)
            return item

    def _worker(self) -> None:
        next_beat = time.monotonic() + self._interval
        while not self._stop.is_set():
            if self._auth_failed:
                return
            now = time.monotonic()
            if now >= next_beat:
                self._enqueue(self._heartbeat_payload())
                next_beat = now + self._interval
            item = self._pop()
            if item is None:
                self._stop.wait(0.2)
                continue
            payload, attempt = item
            ok, status, detail, latency = self._post(payload)
            self._record(payload, ok, status, detail, latency, attempt)
            if ok:
                continue
            if status == 401:
                self._auth_failed = True
                self._stop.set()
                return
            retryable = status is None or status == 408 or status == 429 or status >= 500
            if retryable:
                delay = min(RETRY_MAX_S, RETRY_BASE_S * (2 ** (attempt - 1)))
                with self._lock:
                    self._queue.appendleft((payload, attempt + 1))
                    self._stats["queued"] = len(self._queue)
                self._log.info(
                    "instrument=%s action=%s event=retry attempt=%s delay_ms=%d error=%s",
                    self._instrument, self._action_of(payload), attempt + 1, int(delay * 1000), detail,
                )
                self._stop.wait(delay)
            else:
                with self._lock:
                    self._stats["dropped"] += 1
                self._log.error(
                    "instrument=%s action=%s event=drop status=%s error=%s",
                    self._instrument, self._action_of(payload), status, detail,
                )
        self._log.info("event=worker_stop instrument=%s", self._instrument)

    def _record(
        self,
        payload: Dict[str, Any],
        ok: bool,
        status: Optional[int],
        detail: str,
        latency_ms: float,
        attempt: int,
    ) -> None:
        """统一记录一次 HTTP 结果并更新统计（不记录 token）。"""
        action = self._action_of(payload)
        signal_id = payload.get("id") if action == "signal" else None
        with self._lock:
            if ok:
                self._stats["sent"] += 1
            else:
                self._stats["failed"] += 1
                if status is not None and status < 500 and status not in (408, 429):
                    self._stats["dropped"] += 1
                elif status is None or status == 408 or status == 429 or status >= 500:
                    self._stats["retried"] += 1
                self._last_error = detail or "上报失败"
        level = logging.INFO if ok else logging.WARNING
        self._log.log(
            level,
            "instrument=%s action=%s status=%s ok=%s latency_ms=%.1f attempt=%s id=%s error=%s",
            self._instrument, action, status if status is not None else "-", ok,
            latency_ms, attempt, signal_id or "-", "" if ok else (detail or "-"),
        )

    def _post(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[int], str, float]:
        """POST /api/v1/report；返回 (ok, status, detail, latency_ms)。不抛出网络异常。"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._url,
            data=body,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "qwatch-python/0.3.0",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
                status = response.status
        except HTTPError as exc:
            detail = ""
            try:
                data = json.loads(exc.read() or b"{}")
                detail = str(data.get("detail") or "")
            except ValueError:
                detail = ""
            return False, exc.code, detail or ("HTTP " + str(exc.code)), (time.perf_counter() - started) * 1000
        except (URLError, TimeoutError, OSError) as exc:
            return False, None, str(exc), (time.perf_counter() - started) * 1000
        latency_ms = (time.perf_counter() - started) * 1000
        if not raw:
            return status < 300, status, "空响应", latency_ms
        try:
            result = json.loads(raw)
        except ValueError:
            return False, status, "响应不是 JSON", latency_ms
        if status >= 300:
            return False, status, str(result.get("detail") or ("HTTP " + str(status))), latency_ms
        if result.get("ok") is False:
            return False, status, str(result.get("detail") or "服务端返回失败"), latency_ms
        return True, status, "", latency_ms
