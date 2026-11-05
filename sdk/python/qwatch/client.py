"""qwatch Python SDK v0.6 — 生产安全：构造和调用绝不阻塞策略主线程。

构造 Qwatch 只做本地参数校验并启动后台 daemon worker，不发起任何网络请求；
tick / msg / signal / equity / nav 全部 O(1) 入队，绝不阻塞、绝不因发送失败抛异常。
单个 worker 负责自动心跳与上报：网络/5xx 指数退避+抖动重试（不丢队列），
4xx 永久错误丢弃并记日志，401 标记 auth_failed 后继续后台退避，不影响调用方。
本地按 instrument 分文件轮转日志（默认 logs/{instrument}.log），不记录 token。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
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
# 网络类失败重试退避：0.5s 起，上限 5s；401 单独回退到 30s
RETRY_BASE_S = 0.5
RETRY_MAX_S = 5.0
AUTH_RETRY_MAX_S = 30.0
RETRY_JITTER = 0.2

_LOGGERS: Dict[str, logging.Logger] = {}
_LOGGERS_LOCK = threading.Lock()


class QwatchError(Exception):
    """SDK 基础异常。"""


class AuthError(QwatchError):
    """保留的异常类型；v0.4+ 起构造不再同步校验 token，401 通过 auth_failed 观测。"""


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

        q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", instrument="rb")  # 立即返回
        q.tick()                                    # 主循环每轮调用，只更新 loop
        q.msg("夜盘暂停")                            # 动态消息
        q.signal("rb2601", "long", "open", 2, price=3521)  # 交易信号
        q.equity(462300.12)                         # 所属策略权益（账户由后端求和）

    - 构造不同步联网；参数错误（base_url/token/instrument/heartbeat 等）才抛 ValueError。
    - 所有上报方法只入队，网络失败不抛异常；401 / 断网通过 stats、last_error、auth_failed 观测。
    - 队列有界（queue_size），满时丢最旧并计数/日志；close(flush_timeout) 有硬上限。
    - 本地日志默认 log_dir/{instrument}.log，5MB x 3 轮转，不记录 token。
    """

    DIRECTIONS = {"long", "short"}
    ACTIONS = {"open", "close", "add", "reduce"}

    def __init__(
        self,
        base_url: str,
        token: str,
        heartbeat: Optional[float] = 30,
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
        interval = 0.0
        if heartbeat is not None:
            interval = float(heartbeat)
            if not math.isfinite(interval) or interval < 0:
                raise ValueError("heartbeat 必须大于 0，或传 None 关闭自动心跳")
        wait = float(timeout)
        if not math.isfinite(wait) or wait <= 0:
            raise ValueError("timeout 必须大于 0")
        capacity = int(queue_size)
        if capacity <= 0:
            raise ValueError("queue_size 必须大于 0")

        # ---- 以下只做内存初始化，不做网络请求 / 不写文件 ----
        self._url = base.rstrip("/") + "/api/v1/report"
        self._token = secret
        self._instrument = instrument
        self._heartbeat = interval
        self._timeout = wait
        self._queue_size = capacity
        self._log_file = Path(log_path) if log_path else Path(log_dir) / (_safe_name(instrument) + ".log")

        self._queue: Deque[Tuple[Dict[str, Any], int]] = deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._loop = 0
        self._last_tick: Optional[str] = None
        self._auth_failed = False
        self._last_error: Optional[str] = None
        self._log: Optional[logging.Logger] = None
        self._dropped_pending = 0
        self._stats = {"sent": 0, "failed": 0, "retried": 0, "dropped": 0, "queued": 0}

        self._thread = threading.Thread(target=self._worker, name="qwatch-" + _safe_name(instrument), daemon=True)
        self._thread.start()

    # ---------- 对外方法（全部 O(1) 入队，不阻塞、不抛网络异常） ----------

    def tick(self, last_tick: Optional[str] = None) -> int:
        """主循环每轮调用：loop 自增，不发请求；下一次自动心跳携带 loop。"""
        with self._lock:
            self._loop += 1
            if last_tick is not None:
                self._last_tick = str(last_tick)
            return self._loop

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
        qty = self._positive_number(qty, "qty")

        payload: Dict[str, Any] = {
            "ts": _now_iso(),
            "instrument": self._instrument,
            # v0.2+ 契约信号字段写作 symbol / contract，两个命名携带同一合约代码
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

    def equity(self, value: float) -> None:
        """上报所属策略权益（写入 token 对应的策略，last-wins；账户权益由后端对策略求和）。"""
        number = self._positive_number(value, "equity")
        self._enqueue({"ts": _now_iso(), "instrument": self._instrument, "equity": number})

    def nav(self, value: float) -> None:
        """上报所属策略净值（v0.6 策略级 nav；账户净值由后端按权益加权）。"""
        number = self._positive_number(value, "nav")
        self._enqueue({"ts": _now_iso(), "instrument": self._instrument, "nav": number})

    def account_nav(self, value: float) -> None:
        """上报所属账户净值覆盖值（v0.6；账户未提交时后端自动用策略加权）。"""
        number = self._positive_number(value, "account_nav")
        self._enqueue({"ts": _now_iso(), "instrument": self._instrument, "account_nav": number})

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def auth_failed(self) -> bool:
        return self._auth_failed

    @property
    def instrument(self) -> str:
        return self._instrument

    @property
    def log_path(self) -> str:
        return str(self._log_file)

    def close(self, flush_timeout: float = 2.0) -> None:
        """停止 worker，并在硬上限内尽力冲刷队列；任何情况下不抛异常、不挂死。"""
        try:
            limit = max(0.0, float(flush_timeout))
        except (TypeError, ValueError):
            limit = 0.0
        deadline = time.monotonic() + limit
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        log = self._ensure_logger()
        while time.monotonic() < deadline:
            item = self._pop()
            if item is None:
                break
            payload, attempt = item
            remaining = deadline - time.monotonic()
            if remaining <= 0.01:
                break
            ok, status, detail, latency = self._post(payload, timeout=min(self._timeout, remaining))
            self._record(log, payload, ok, status, detail, latency, attempt)
        log.info(
            "event=close instrument=%s sent=%s failed=%s dropped=%s retried=%s queued=%s",
            self._instrument, self._stats["sent"], self._stats["failed"],
            self._stats["dropped"], self._stats["retried"], self._stats["queued"],
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

    @classmethod
    def _positive_number(cls, value: Any, name: str) -> float:
        number = cls._number(value, name)
        if number <= 0:
            raise ValueError(name + " 必须大于 0")
        return number

    @staticmethod
    def _action_of(payload: Dict[str, Any]) -> str:
        if "symbol" in payload or "contract" in payload:
            return "signal"
        if "msg" in payload:
            return "msg"
        if "equity" in payload:
            return "equity"
        if "nav" in payload:
            return "nav"
        return "heartbeat"

    def _heartbeat_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"ts": _now_iso(), "instrument": self._instrument}
        with self._lock:
            if self._loop:
                payload["loop"] = self._loop
            if self._last_tick:
                payload["last_tick"] = self._last_tick
        return payload

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        """O(1) 入队；满时丢最旧，只计数不写日志（避免阻塞调用方）。"""
        with self._lock:
            if len(self._queue) >= self._queue_size:
                self._queue.popleft()
                self._stats["dropped"] += 1
                self._dropped_pending += 1
            self._queue.append((payload, 1))
            self._stats["queued"] = len(self._queue)

    def _pop(self) -> Optional[Tuple[Dict[str, Any], int]]:
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.popleft()
            self._stats["queued"] = len(self._queue)
            return item

    def _schedule_retry(self, payload: Dict[str, Any], attempt: int) -> None:
        with self._lock:
            if len(self._queue) >= self._queue_size:
                self._queue.popleft()
                self._stats["dropped"] += 1
                self._dropped_pending += 1
            self._queue.appendleft((payload, attempt + 1))
            self._stats["queued"] = len(self._queue)
            self._stats["retried"] += 1

    def _ensure_logger(self) -> logging.Logger:
        logger = self._log
        if logger is None:
            logger = _file_logger(self._log_file)
            self._log = logger
        return logger

    def _worker(self) -> None:
        """唯一后台 worker：自动心跳 + 串行上报 + 指数退避抖动重试。"""
        log = self._ensure_logger()
        log.info(
            "event=init instrument=%s heartbeat=%s timeout=%s queue_size=%s url=%s log=%s",
            self._instrument, self._heartbeat, self._timeout, self._queue_size,
            self._url.rsplit("/api/", 1)[0], self._log_file,
        )
        interval = self._heartbeat
        next_beat = time.monotonic()  # 首个心跳尽快发出
        while not self._stop.is_set():
            with self._lock:
                dropped = self._dropped_pending
                self._dropped_pending = 0
            if dropped:
                log.warning(
                    "instrument=%s event=queue_full dropped=%s queue=%s",
                    self._instrument, dropped, self._stats["queued"],
                )
            now = time.monotonic()
            if interval and not self._auth_failed and now >= next_beat:
                self._enqueue(self._heartbeat_payload())
                next_beat = now + interval
            item = self._pop()
            if item is None:
                self._stop.wait(0.2)
                continue
            payload, attempt = item
            ok, status, detail, latency = self._post(payload)
            self._record(log, payload, ok, status, detail, latency, attempt)
            if ok:
                continue
            if status == 401:
                self._auth_failed = True
                self._last_error = detail or "token 无效或已吊销"
                self._schedule_retry(payload, attempt)
                delay = min(AUTH_RETRY_MAX_S, max(1.0, RETRY_BASE_S * (2 ** (attempt - 1))))
                delay *= 1 + random.uniform(-RETRY_JITTER, RETRY_JITTER)
                log.error(
                    "instrument=%s event=auth_failed attempt=%s retry_in_ms=%s error=%s",
                    self._instrument, attempt, int(delay * 1000), self._last_error,
                )
                self._stop.wait(delay)
                continue
            retryable = status is None or status in (408, 429) or (status or 0) >= 500
            if retryable:
                self._schedule_retry(payload, attempt)
                delay = min(RETRY_MAX_S, RETRY_BASE_S * (2 ** (attempt - 1)))
                delay *= 1 + random.uniform(-RETRY_JITTER, RETRY_JITTER)
                log.info(
                    "instrument=%s action=%s event=retry attempt=%s delay_ms=%s error=%s",
                    self._instrument, self._action_of(payload), attempt + 1, int(delay * 1000), detail,
                )
                self._stop.wait(delay)
                continue
            with self._lock:
                self._stats["dropped"] += 1
            log.error(
                "instrument=%s action=%s event=drop status=%s error=%s",
                self._instrument, self._action_of(payload), status, detail,
            )
        log.info(
            "event=worker_stop instrument=%s sent=%s failed=%s dropped=%s retried=%s",
            self._instrument, self._stats["sent"], self._stats["failed"],
            self._stats["dropped"], self._stats["retried"],
        )

    def _record(
        self,
        log: logging.Logger,
        payload: Dict[str, Any],
        ok: bool,
        status: Optional[int],
        detail: str,
        latency_ms: float,
        attempt: int,
    ) -> None:
        """记录一次 HTTP 结果并更新统计；只做内存操作 + 后台日志，不记录 token。"""
        action = self._action_of(payload)
        signal_id = payload.get("id") if action == "signal" else None
        with self._lock:
            if ok:
                self._stats["sent"] += 1
            else:
                self._stats["failed"] += 1
                self._last_error = detail or "上报失败"
        level = logging.INFO if ok else logging.WARNING
        log.log(
            level,
            "instrument=%s action=%s status=%s ok=%s latency_ms=%.1f attempt=%s id=%s error=%s",
            self._instrument, action, status if status is not None else "-", ok,
            latency_ms, attempt, signal_id or "-", "" if ok else (detail or "-"),
        )

    def _post(
        self, payload: Dict[str, Any], timeout: Optional[float] = None
    ) -> Tuple[bool, Optional[int], str, float]:
        """POST /api/v1/report；返回 (ok, status, detail, latency_ms)。不抛出网络异常。"""
        wait = self._timeout if timeout is None else max(0.05, min(self._timeout, float(timeout)))
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._url,
            data=body,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "qwatch-python/0.6.0",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=wait) as response:
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
