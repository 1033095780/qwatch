# qwatch Python SDK

零依赖（标准库）策略接入库：**一个实例、一个接口、心跳和信号合并**。

## 安装

~~~bash
cd sdk/python
pip install -e .
~~~

## 5 行接入

~~~python
from qwatch import Qwatch

q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", instrument="rb2601")
q.tick()                              # 主循环每轮调用，服务端据此判断卡死
q.report(nav=1.1236, pnl=51300.12)    # 净值 / 累计盈亏，均由策略自己算
q.report(msg="夜盘暂停")               # 普通消息
q.close()
~~~

一个 strategy token 下可以有多个 instrument；每个脚本初始化时只填一次自己的 instrument，后续 report 不再填。日期由 SDK 自动带，服务端同时记录收到时间。

## 规则

- 什么都不填 = 心跳；自动每 30 秒发一次，60 秒没发就判死。
- 信号字段（symbol / direction / action / qty）必须完整，SDK 本地先校验，后端再校验一次。
- tick() 只更新内存里的 loop，不发请求；下一次自动心跳会带上，服务端发现 loop 不增长会判「卡死」。
- 网络失败进内存队列重试，不阻塞策略；参数错误立刻 ValueError。
- token 错误抛 AuthError。
- `pnl` 是策略累计盈亏金额（含浮盈），`nav` 是策略单位净值；两者都由策略自己计算后提交，qwatch 只存储和展示。
- 这样即使两个策略共用一个股票账户、或账户有入金出金，也不影响策略盈亏曲线。

## API

~~~python
Qwatch(base_url, token, heartbeat=30, timeout=5, queue_size=1000, instrument="主账户")

q.report(equity=None, nav=None, pnl=None, msg=None, signal=None)
q.tick(last_tick=None) -> loop
q.stats
q.close()
~~~

- 不传参数 = 心跳；自动心跳每 30 秒一次。
- instrument 与 trade_date 由 SDK 自动补齐。
- signal 传 dict：direction / action / qty / price 等。
