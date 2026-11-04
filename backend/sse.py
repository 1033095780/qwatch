"""进程内 SSE 事件总线（单 worker 部署）。

用法：启动时 set_loop(asyncio.get_running_loop())；同步线程里 publish(event)，
事件会被投递到所有 /api/v1/stream 订阅者队列。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

logger = logging.getLogger("qwatch.sse")


class EventBus:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: set[asyncio.Queue] = set()
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._fanout, event)
        except RuntimeError:
            self._loop = None

    def _fanout(self, event: dict[str, Any]) -> None:
        with self._lock:
            queues = list(self._queues)
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:  # noqa: BLE001 - 订阅者关闭中
                    pass

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._queues.discard(queue)


bus = EventBus()


def format_sse(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "message")
    data = json.dumps(event, ensure_ascii=False)
    return "event: " + event_type + "\ndata: " + data + "\n\n"


def publish(event: dict[str, Any]) -> None:
    bus.publish(event)
