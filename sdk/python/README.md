# qwatch Python SDK

零依赖（标准库）策略接入库：**一个策略进程一个实例**，心跳、动态消息和交易信号统一走
`POST /api/v1/report`，按进程分文件记录本地日志。v0.3 支持策略组净值/权益 `q.nav()` / `q.equity()`；不提供 PnL。

## 安装

```bash
cd sdk/python
pip install -e .
```

## 最小接入

```python
import time

from qwatch import Qwatch

# instrument 是稳定进程名（如 rb / ag / IF），不是合约；换月不换名
q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", instrument="rb")

for i in range(1, 100000):
    q.tick()                                      # 主循环每轮调用，心跳携带 loop
    if i % 30 == 0:
        q.nav(1.0 + i * 0.00001)                  # 策略组净值（任意进程可报，最后一次为准）
    if i % 20 == 0:
        q.signal("rb2601", "long", "open", 2, price=3521, msg="突破前高")
    if i % 60 == 0:
        q.msg("夜盘暂停")                          # 动态消息
    time.sleep(10)

q.close()
```

一个策略 token 下可以挂多个进程：每个进程一个实例，只填自己的 instrument。
多进程示例（同一 token）：

```python
rb = Qwatch(URL, TOKEN, instrument="rb")
ag = Qwatch(URL, TOKEN, instrument="ag")
```

## API

```python
Qwatch(base_url, token, heartbeat=30, timeout=5, queue_size=1000,
       instrument="rb", log_dir="logs", log_path=None)

q.tick(last_tick=None) -> loop          # 主循环每轮调用；只更新 loop，不发请求
q.nav(value)                            # 策略组净值，必须 > 0
q.equity(value)                         # 策略组权益，必须 > 0
q.msg(text)                             # 动态消息（也算心跳）
q.signal(contract, direction, action, qty,
         *, price=None, amount=None, msg=None, id=None) -> signal_id
q.stats                                 # {"sent", "failed", "retried", "dropped", "queued"}
q.last_error                            # 最近一次失败原因
q.close(flush_timeout=2.0)              # 停止自动心跳并尽力冲刷队列；支持 with
```

不提供 `report` / `pnl` 方法；`nav()` / `equity()` 用于上报策略组净值/权益。

## 行为

- 初始化时同步发一次心跳：token 错误立刻抛 `AuthError`；网络错误只记录并交给后台重试。
- 之后每 `heartbeat` 秒自动心跳；`msg` / `signal` 也顺带刷新心跳。
- tick() 只更新内存 loop，下一次自动心跳带上；服务端连续 3 次 loop 不增长判「卡死」。
- 失败重试：网络错误、408/429/5xx 自动退避重试（0.5s 起，上限 5s，队列不丢）；4xx 参数错误丢弃并记日志；401 立即停止上报，原因写入 `last_error`。
- 本地日志：默认 `log_dir/{instrument}.log`，`log_path` 可自定义单个文件；5MB x 3 轮转；记录动作、HTTP 状态、耗时、重试与错误，**不记录 token**。
- 同一进程内多个实例写同一个日志文件时共享 handler，不会重复打开。

日志示例：

```
2026-11-04 09:30:00 INFO instrument=rb action=heartbeat status=200 ok=True latency_ms=3.1 attempt=1 id=- error=
2026-11-04 09:30:10 INFO instrument=rb action=signal status=200 ok=True latency_ms=2.7 attempt=1 id=sig_... error=
```

## 注意

- 纯心跳也必须带 instrument（SDK 自动补齐），接入后进程会自动出现在策略组下。
- 信号字段：`contract + direction + action + qty` 必填，price/amount 可选且不能为负。
- 旧版 v0.1.x 后端与本文档不兼容（旧接口含 pnl/nav/equity）。
