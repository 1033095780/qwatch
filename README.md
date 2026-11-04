# qwatch

自托管的**策略进程看门狗 + 账户权益看板**：账户下分策略，策略下可有多个进程；任意进程的心跳、消息、信号、权益都汇总到所属账户。

> v0.4：多券商账户（国金证券、徽商期货等）；权益是**账户级**的。

![总览](screenshots/overview.png)

## 核心模型

```text
账户（国金证券 / 徽商期货）
└─ 策略（一个 token）
   ├─ 进程 rb
   ├─ 进程 ag
   └─ 进程 au
```

- 账户：券商资金账户，权益唯一归属
- 策略：一个 token；同策略下多个进程共用
- 进程：稳定 instrument 名（rb/ag/IF），不是合约号
- 账户权益：同账户任意进程上报，last-wins
- 告警：进程心跳丢失 / loop 卡死，按策略组汇总 P0

## 功能

- 账户卡片：券商、权益、策略数/在线数、权益 sparkline
- 策略大卡片：账户/券商、账户权益、sparkline、整行心跳、进程数/异常
- 总览：总权益、今日权益变动、策略在线、账户级权益曲线、账户切换、周期切换、tooltip
- 详情：无 Tab；左进程/告警，右动态（搜索 + 全部/消息/信号筛选 + 滚动）
- SSE 实时告警/动态；钉钉 P0 投递/重试/恢复
- 生产安全 SDK

## 快速开始

```bash
python -m pip install -r backend/requirements.txt
python -m backend.seed
python -m backend
```

打开 `http://127.0.0.1:8080`，默认密码 `qwatch`。

1. 「账户」→ 新建账户，填账户名/券商
2. 「策略」→ 新建策略，选择所属账户
3. 保存弹窗里的一次性 token

## SDK

```bash
python -m pip install -e sdk/python
```

```python
import time
from qwatch import Qwatch

q = Qwatch("http://127.0.0.1:8080", token="qw_xxx", instrument="rb", log_dir="logs")
while True:
    q.tick()
    q.msg("夜盘正常")
    q.signal(contract="rb2607", direction="long", action="open", qty=1, price=3521)
    q.equity(1_000_000)   # 所属账户权益
    q.nav(1.0023)         # 所属账户净值
    time.sleep(10)
```

SDK v0.4 生产安全：

- 构造不阻塞，不做同步网络请求
- `tick/msg/signal/equity/nav` O(1) 入队，不阻塞、不因网络失败抛异常
- 单 daemon worker：自动心跳 + 指数退避+抖动重试
- 有界队列，满时丢最旧；每 instrument 独立日志 5MB×3，不记 token
- 401 标记 `auth_failed`，不影响调用方
- `close(flush_timeout)` 有上限；`stats/last_error` 可观测

## 账户/权益口径

- 权益/净值账户级，不按策略拆分
- 同账户任意策略进程可上报；last-wins
- 建议只让一个主进程上报，或同账户进程都报同一个账户值
- 总权益 = 各账户最新权益之和
- 策略详情显示的是所属账户权益

## 界面

| 账户 | 策略 |
|---|---|
| ![账户](screenshots/accounts.png) | ![策略](screenshots/strategies.png) |

| 详情 | 告警 |
|---|---|
| ![详情](screenshots/strategy-detail.png) | ![告警](screenshots/alerts.png) |

## 告警与钉钉

- P0：进程心跳丢失 / loop 连续 3 次不增长
- 「设置」→ 钉钉渠道：Webhook、SEC 加签、关键字 `[+]`
- 消息/信号不会触发 P0
- 演示渠道（webhook 含 `demo-`）不会出网

## 模拟器

```bash
python -m backend
python -m sim.run
```

2 个账户：

- 国金证券：螺纹钢趋势、白银波段（ag/au 双进程）
- 徽商期货：股指日内

## 开发

```bash
cd frontend
npm install
npm run typecheck
npm run build

cd ..
python -m compileall -q backend sdk sim
```

## 备份/迁移

- 数据库 `data/qwatch.db`（gitignored）
- 升级前：`Copy-Item data/qwatch.db data/qwatch.backup.db`
- v0.4 自动迁移 v0.3：
  - 已有策略归入默认账户
  - 旧权益迁移为账户权益
  - 旧权益/净值表删除
- 迁移不可回退，请先备份
- 部署保持单 worker

## 已知限制

1. 没有交易日历，策略需要持续 tick
2. 每天只跑一次、跑完退出的策略会被判离线
3. 无显式进程清单，只监控上报过的进程
4. 账户权益 last-wins，不支持多进程权益求和
5. 不提供 PnL/收益/回撤/风险指标/资金流水

## License

Apache-2.0
