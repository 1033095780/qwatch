# qwatch Python SDK

零依赖（标准库）策略接入库：**一个策略进程一个实例**。心跳、动态消息、交易信号和策略级权益
统一走 `POST /api/v1/report`，本地按 instrument 分文件记录日志。

v0.4 起 SDK 是**生产安全**的（构造和所有上报方法都不阻塞策略主线程，网络失败后台重试）；
v0.6 起 `equity()` / `nav()` 写入**所属策略**，账户权益由后端对各策略求和、账户净值按权益加权。

## 安装

```bash
cd sdk/python
pip install -e .
```

## 最小接入

```python
import time

from qwatch import Qwatch

# instrument 是稳定进程名（如 rb / ag / IF），不是合约；换月不换名。
# 构造立即返回，不做同步网络请求；参数错误才抛 ValueError。
q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", instrument="rb")

for i in range(1, 100000):
    q.tick()                                       # 主循环每轮调用，心跳携带 loop
    if i % 20 == 0:
        q.signal("rb2601", "long", "open", 2, price=3521, msg="突破前高")
    if i % 60 == 0:
        q.msg("夜盘暂停")                            # 动态消息
    if i % 120 == 0:
        q.equity(1_200_000 + i * 10)                 # 所属策略权益（账户由后端求和）
        q.nav(1.0 + i * 0.00001)                     # 所属策略净值
        q.account_nav(1.01)                          # 可选：账户净值覆盖；不传自动策略加权
    time.sleep(10)

q.close()
```

一个策略 token 下可以挂多个进程：每个进程一个实例，只填自己的 instrument；同一策略下任意进程
上报 equity/nav 都写入该策略（last-wins），建议由主进程定时上报。

```python
rb = Qwatch(URL, TOKEN, instrument="rb")
```

## API

```python
Qwatch(base_url, token, heartbeat=30, timeout=5, queue_size=1000,
       instrument="rb", log_dir="logs", log_path=None)

q.tick(last_tick=None) -> loop          # 只更新 loop，不发请求
q.msg(text)                             # 动态消息（也算心跳）
q.signal(contract, direction, action, qty,
         *, price=None, amount=None, msg=None, id=None) -> signal_id
q.equity(value)                         # 所属策略权益，必须 > 0
q.nav(value)                            # 所属策略净值，必须 > 0
q.account_nav(value)                    # 账户净值覆盖值，可选；不传则自动按策略加权
q.stats                                 # {"sent","failed","retried","dropped","queued"}
q.last_error                            # 最近一次失败原因（网络/HTTP detail）
q.auth_failed                           # token 被 401 拒绝后为 True（不影响调用方）
q.close(flush_timeout=2.0)              # 停止 worker 并在上限内尽力冲刷；支持 with
```

`heartbeat=None` 可关闭自动心跳；默认 30s。

## 生产安全行为

- **构造不阻塞**：只做本地参数校验并启动 daemon worker，不发起任何网络请求。
- **调用不阻塞**：`tick / msg / signal / equity / nav` 全部 O(1) 入队，网络再差也不阻塞主线程、不因发送失败抛异常。
- **有界队列**：默认 1000，满时丢最旧并计数（`stats.dropped`），由 worker 记日志。
- **单 worker 重试**：网络错误 / 408 / 429 / 5xx 指数退避 + 抖动（0.5s 起，上限 5s）重试，不丢队列。
- **4xx 永久错误**：丢弃并记日志（`stats.dropped`）；`401` 标记 `auth_failed` 后继续后台退避，调用方无感知。
- **本地日志**：默认 `log_dir/{instrument}.log`，5MB x 3 轮转；记录动作/HTTP 状态/耗时/重试/错误，**不记录 token**。
- **close 有上限**：`close(flush_timeout)` 最多等待该时长，不会挂死进程。
- **可观测**：`stats` / `last_error` / `auth_failed`。

日志示例：

```
2026-11-04 18:30:00 INFO event=init instrument=rb heartbeat=30 timeout=5 queue_size=1000 url=http://127.0.0.1:8080 log=logs/rb.log
2026-11-04 18:30:00 INFO instrument=rb action=heartbeat status=200 ok=True latency_ms=2.4 attempt=1 id=- error=
2026-11-04 18:30:10 INFO instrument=rb action=equity status=200 ok=True latency_ms=2.1 attempt=1 id=- error=
```

## 注意

- token 无效（401）不再在构造时抛 AuthError；请观测 `last_error` / `auth_failed`。
- 纯心跳也必须带 instrument（SDK 自动补齐）。
- 信号字段：`contract + direction + action + qty` 必填，price/amount 可选且不能为负。
- v0.6 后端按策略汇总：`equity` / `nav` 写入 token 对应策略，账户权益=账户下策略权益之和，账户净值=Σ(nav×equity)/Σ(equity)。
