# qwatch

**多策略 / 多市场监控工作台**：净值曲线、交易信号、策略存活 watchdog 与钉钉告警。自用，开源。

## 功能

- **总览**：组合净值一屏看清，可快速切到单个策略查看净值/收益曲线；今日盈亏、策略状态、活跃告警
- **策略**：新建策略即生成接入令牌；净值与回撤、信号、持仓、心跳可用率、告警历史、令牌管理
- **交易信号**：按策略 / 平台 / 市场 / 类型 / 标签 / 方向 / 状态筛选，排序、分页、导出 CSV
- **告警**：P0/P1/P2 分级，确认与静默；心跳丢失、卡死、行情断流、回撤超限等规则
- **Python SDK**：初始化一个实例就自动心跳；信号和心跳共用 `POST /api/v1/report`，零依赖

## 界面

![总览](screenshots/overview.png)

| 策略详情 | 交易信号 |
|---|---|
| ![策略详情](screenshots/strategy-detail.png) | ![交易信号](screenshots/signals.png) |

| 登录 | 手机 |
|---|---|
| ![登录](screenshots/login.png) | ![手机](screenshots/mobile-overview.png) |

## 架构

```
策略进程（任意语言 / Python SDK）
   │  POST /api/v1/report    心跳 30s；信号也走同一个包
   ▼
FastAPI + SQLite ──▶ Watchdog（心跳/进度/交易日历）──▶ 告警引擎 ──▶ 钉钉
   │
   └──▶ Vue 3 面板（总览 / 策略 / 信号 / 告警）
```

- 纯推送：策略不需要被扫描、不需要开放端口；服务端只认「有没有按时报到」。
- 只读：服务端没有任何下单能力。
- 单机：一台交易机 / NAS / VPS 即可，数据保存在本地 SQLite。

技术栈：Vue 3 + TypeScript + Vite + Naive UI + ECharts（前端）；FastAPI + SQLite（后端，开发中）。

## 快速开始（前端）

```bash
cd frontend
npm install
npm run dev                  # http://127.0.0.1:5173
# 或构建后单进程预览
npm run build
node mock-server.mjs         # http://127.0.0.1:8080
# 登录密码：qwatch
```

前端当前使用内置演示数据（真实 HTTP 接口，便于后端按同一契约替换）；真实后端开发中。

## 策略接入（Python SDK）

```bash
cd sdk/python
pip install -e .
```

```python
from qwatch import Qwatch

q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", 30)  # 初始化即自动心跳
q.signal("rb2601", "long", "open", 10, price=3521, msg="突破前高")
q.tick()            # 主循环每轮调用，心跳带上 loop，服务端据此判断卡死
q.equity(462300.12)
q.close()
```

- 什么都不填 = 心跳；信号 = 心跳 + 信号；
- 30 秒自动心跳，60 秒无请求判死；
- 完整说明见 [sdk/python/README.md](sdk/python/README.md)。

## 目录

```
frontend/        前端（Vue 3 + Naive UI + ECharts）
sdk/python/      Python 接入 SDK（零依赖）
screenshots/     界面截图
```

## License

[Apache-2.0](LICENSE)
