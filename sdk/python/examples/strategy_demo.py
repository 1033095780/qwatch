"""最小示例：模拟策略主循环，自动心跳 + 信号 + 权益 + 进度。"""

import os
import time

from qwatch import Qwatch

URL = os.environ.get("QWATCH_URL", "http://127.0.0.1:8080")
TOKEN = os.environ.get("QWATCH_TOKEN", "")

if not TOKEN:
    raise SystemExit("请先设置 QWATCH_TOKEN（在 qwatch 后台新建策略后复制）")

with Qwatch(URL, TOKEN, 30) as q:
    for i in range(1, 1000):
        q.tick()
        if i % 20 == 0:
            q.signal("rb2601", "long", "open", 1, price=3521, msg="示例信号")
        if i % 5 == 0:
            q.equity(462300.12)
        time.sleep(2)
