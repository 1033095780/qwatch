"""qwatch Python SDK — 零依赖，只依赖标准库。"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("qwatch")

__all__ = ["Qwatch", "QwatchError", "AuthError"]


class QwatchError(Exception):
    """SDK 基础异常。"""


class AuthError(QwatchError):
    """token 无效或已吊销。"""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class Qwatch:
    """一个策略对应一个实例。

    初始化即开始自动心跳：
        q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", 30)

    - 30 是心跳间隔（秒），不传默认 30。
    - 纯心跳 = 服务器收到一次请求；信号也顺带刷新心跳。
    - 主循环里调用 q.tick() 可让心跳带上 loop 进度，服务端据此判断卡死。
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
    ) -> None:
        if not str(base_url).startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        if not str(token).strip():
            raise ValueError("token 不能为空")
        if heartbeat <= 0:
            raise ValueError("heartbeat 必须大于 0")

        self._url = str(base_url).rstrip("/") + "/api/v1/report"
        self._token = str(token).strip()
        self._interval = float(heartbeat)
        self._timeout = float(timeout)
        self._queue: Deque[Dict[str, Any]] = deque()
        self._queue_size = int(queue_size)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop = 0
        self._last_tick: Optional[str] = None
        self._auth_failed = False
        self._last_error: Optional[str] = None
        self._stats = {"sent": 0, "failed": 0, "dropped": 0, "queued": 0}

        # 初始化时先同步发一次心跳：token 错立刻暴露；网络问题只记录，后台继续重试
        ok, status, detail = self._post({"ts": _now_iso()})
        if status == 401:
            raise AuthError("token 无效或已吊销")
        if ok:
            self._stats["sent"] += 1
        else:
            self._last_error = detail
            logger.warning("qwatch 初始化心跳失败（将持续重试）：%s", detail)

        self._thread = threading.Thread(target=self._worker, name="qwatch-heartbeat", daemon=True)
        self._thread.start()

    # ---------- 对外方法 ----------

    def signal(
        self,
        symbol: str,
        direction: str,
        action: str,
        qty: float,
        *,
        price: Optional[float] = None,
        amount: Optional[float] = None,
        account: Optional[str] = None,
        equity: Optional[float] = None,
        pnl: Optional[float] = None,
        nav: Optional[float] = None,
        msg: Optional[str] = None,
        id: Optional[str] = None,
    ) -> str:
        """上报一个交易信号，自动补齐 ts / id。返回 signal_id。

        参数错误立刻抛 ValueError（这是代码 bug，应该暴露）。
        网络错误不抛异常，进入本地队列重试。
        """
        symbol = str(symbol or "").strip()
        if not symbol:
            raise ValueError("symbol 不能为空")
        direction = str(direction or "").strip().lower()
        if direction not in self.DIRECTIONS:
            raise ValueError("direction 必须是 long 或 short")
        action = str(action or "").strip().lower()
        if action not in self.ACTIONS:
            raise ValueError("action 必须是 open / close / add / reduce")
        qty = float(qty)
        if not math.isfinite(qty) or qty <= 0:
            raise ValueError("qty 必须是正数")

        payload: Dict[str, Any] = {
            "ts": _now_iso(),
            "symbol": symbol,
            "direction": direction,
            "action": action,
            "qty": qty,
        }
        if price is not None:
            payload["price"] = self._number(price, "price")
        if amount is not None:
            payload["amount"] = self._number(amount, "amount")
        if account:
            payload["account"] = str(account).strip()
        if equity is not None:
            payload["equity"] = self._number(equity, "equity")
        if pnl is not None:
            payload["pnl"] = self._number(pnl, "pnl")
        if nav is not None:
            payload["nav"] = self._number(nav, "nav")
        if msg:
            payload["msg"] = str(msg).strip()[:200]
        payload["id"] = str(id).strip() if id else "sig_" + uuid.uuid4().hex

        self._enqueue(payload)
        return payload["id"]

    def heartbeat(
        self,
        *,
        loop: Optional[int] = None,
        last_tick: Optional[str] = None,
        equity: Optional[float] = None,
        msg: Optional[str] = None,
    ) -> None:
        """主动发一次心跳；可携带 loop / last_tick / equity / msg。"""
        if loop is not None:
            with self._lock:
                self._loop = int(loop)
        if last_tick is not None:
            with self._lock:
                self._last_tick = str(last_tick)
        payload: Dict[str, Any] = {"ts": _now_iso()}
        with self._lock:
            if self._loop:
                payload["loop"] = self._loop
            if self._last_tick:
                payload["last_tick"] = self._last_tick
        if equity is not None:
            payload["equity"] = self._number(equity, "equity")
        if msg:
            payload["msg"] = str(msg).strip()[:200]
        self._enqueue(payload)

    def tick(self, last_tick: Optional[str] = None) -> int:
        """主循环每轮调用：loop 自增（不发请求，由自动心跳携带）。返回当前 loop。"""
        with self._lock:
            self._loop += 1
            if last_tick is not None:
                self._last_tick = str(last_tick)
            return self._loop

    def equity(self, value: float, pnl: Optional[float] = None, nav: Optional[float] = None, msg: Optional[str] = None) -> None:
        """更新权益；可同时提交策略累计盈亏 pnl 和策略净值 nav（都由策略自己计算）。"""
        payload: Dict[str, Any] = {"ts": _now_iso(), "equity": self._number(value, "equity")}
        if pnl is not None:
            payload["pnl"] = self._number(pnl, "pnl")
        if nav is not None:
            payload["nav"] = self._number(nav, "nav")
        if msg:
            payload["msg"] = str(msg).strip()[:200]
        self._enqueue(payload)

    def msg(self, text: str) -> None:
        """只发一条注释（也算心跳）。"""
        self._enqueue({"ts": _now_iso(), "msg": str(text).strip()[:200]})

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def close(self, flush_timeout: float = 2.0) -> None:
        """停止自动心跳，尽量把队列里剩余请求发完。"""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=flush_timeout)
        deadline = time.monotonic() + flush_timeout
        while time.monotonic() < deadline:
            item = self._pop()
            if item is None:
                break
            self._send(item)

    def __enter__(self) -> "Qwatch":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------- 内部 ----------

    @staticmethod
    def _number(value: Any, name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(name + " 必须是数字") from None
        if not math.isfinite(number):
            raise ValueError(name + " 必须是有限数字")
        return number

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            if len(self._queue) >= self._queue_size:
                self._queue.popleft()
                self._stats["dropped"] += 1
                logger.warning("qwatch 本地队列已满，丢弃最旧一条")
            self._queue.append(payload)
            self._stats["queued"] = len(self._queue)

    def _pop(self) -> Optional[Dict[str, Any]]:
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
            item = self._pop()
            if item is not None:
                if not self._send(item):
                    time.sleep(min(2.0, 0.2 * (self._stats["failed"] + 1)))
            now = time.monotonic()
            if now >= next_beat:
                self._send(self._heartbeat_payload())
                next_beat = time.monotonic() + self._interval
            self._stop.wait(0.2)

    def _heartbeat_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"ts": _now_iso()}
        with self._lock:
            if self._loop:
                payload["loop"] = self._loop
            if self._last_tick:
                payload["last_tick"] = self._last_tick
        return payload

    def _send(self, payload: Dict[str, Any]) -> bool:
        ok, status, detail = self._post(payload)
        if ok:
            with self._lock:
                self._stats["sent"] += 1
            return True
        if status == 401:
            self._auth_failed = True
            self._last_error = "token 无效或已吊销"
            logger.error("qwatch token 无效或已吊销，停止上报")
            self._stop.set()
            return False
        with self._lock:
            self._stats["failed"] += 1
        self._last_error = detail
        logger.warning("qwatch 上报失败：%s", detail)
        return False

    def _post(self, payload: Dict[str, Any]):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._url,
            data=data,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "qwatch-python/0.1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
                status = response.status
        except HTTPError as exc:
            try:
                body = json.loads(exc.read() or b"{}")
            except Exception:
                body = {}
            return False, exc.code, str(body.get("detail") or ("HTTP " + str(exc.code)))
        except (URLError, TimeoutError, OSError) as exc:
            return False, None, str(exc)
        if not raw:
            return status < 300, status, "空响应"
        try:
            result = json.loads(raw)
        except Exception:
            return False, status, "响应不是 JSON"
        if status >= 300:
            return False, status, str(result.get("detail") or "HTTP " + str(status))
        if result.get("ok") is False:
            return False, status, str(result.get("detail") or "服务端返回失败")
        return True, status, ""
