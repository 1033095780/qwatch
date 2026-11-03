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

q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", 30)  # 初始化即自动心跳
q.signal("rb2601", "long", "open", 10, price=3521, msg="突破前高")
q.tick()          # 主循环每轮调用一次，服务端据此判断卡死
q.equity(462300.12)
q.close()
~~~

token 在 qwatch 后台「新建策略」时生成，一个策略一个 token。

## 规则

- 什么都不填 = 心跳；自动每 30 秒发一次，60 秒没发就判死。
- 信号字段（symbol / direction / action / qty）必须完整，SDK 本地先校验，后端再校验一次。
- tick() 只更新内存里的 loop，不发请求；下一次自动心跳会带上，服务端发现 loop 不增长会判「卡死」。
- 网络失败进内存队列重试，不阻塞策略；参数错误立刻 ValueError。
- token 错误抛 AuthError。
- 出入金是用户手工操作，不在 SDK 里上报；请到 qwatch 策略详情的「资金变动」里记录（初始资金自动取第一次权益快照），系统会自动修正累计盈亏。

## API

~~~python
Qwatch(base_url, token, heartbeat=30, timeout=5, queue_size=1000)

q.signal(symbol, direction, action, qty, *, price=None, amount=None,
         account=None, equity=None, msg=None, id=None) -> signal_id
q.heartbeat(*, loop=None, last_tick=None, equity=None, msg=None)
q.tick(last_tick=None) -> loop
q.equity(value, msg=None)
q.msg(text)
q.stats
q.close()
~~~
