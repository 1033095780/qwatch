"""最小示例：主循环 tick、策略组净值、动态消息与交易信号（v0.3）。"""

import os
import time

from qwatch import Qwatch

URL = os.environ.get("QWATCH_URL", "http://127.0.0.1:8080")
TOKEN = os.environ.get("QWATCH_TOKEN", "")
INSTRUMENT = os.environ.get("QWATCH_INSTRUMENT", "rb")       # 稳定进程名
CONTRACT = os.environ.get("QWATCH_CONTRACT", "rb2601")       # 当前合约

if not TOKEN:
    raise SystemExit("请先设置 QWATCH_TOKEN（在 qwatch 后台新建策略后复制）")

with Qwatch(URL, TOKEN, heartbeat=30, instrument=INSTRUMENT) as q:
    for i in range(1, 1000):
        q.tick()
        if i % 30 == 0:
            q.nav(1.0 + i * 0.00001)
        if i % 20 == 0:
            q.signal(CONTRACT, "long", "open", 1, price=3521, msg="示例信号")
        if i % 60 == 0:
            q.msg("示例动态：主循环正常")
        time.sleep(2)
