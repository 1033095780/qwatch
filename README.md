# qwatch

**多策略 / 多市场监控工作台**：净值曲线、交易信号、策略存活 watchdog 与钉钉告警。自用，开源。

## 功能

- **总览**：组合权益、今日盈亏、组合回撤曲线、年化收益 / 最大回撤 / 夏普 / 卡玛 / 波动率 / 盈亏比（与 KPI 同卡展示、可收起），以及策略状态、迷你心跳与最新信号
- **策略**：新建策略即生成接入令牌；净值/回撤、信号、心跳、告警历史、令牌管理；卡片展示累计盈亏 / 夏普 / 最大回撤 / 日胜率 / 盈亏比
- **交易信号**：按策略 / 平台 / 市场 / 方向筛选；收到的信号直接展示，不分执行状态；排序、分页、导出 CSV
- **告警**：只保留「心跳丢失」「策略卡死」两类红色 P0 告警；确认与静默
- **Python SDK**：零依赖，实例化即自动心跳；心跳与信号共用 `POST /api/v1/report`

## 界面

![总览](screenshots/overview.png)

| 策略详情 | 交易信号 |
|---|---|
| ![策略详情](screenshots/strategy-detail.png) | ![交易信号](screenshots/signals.png) |

| 登录 | 手机 |
|---|---|
| ![登录](screenshots/login.png) | ![手机](screenshots/mobile-overview.png) |

## 架构

~~~
策略进程（任意语言 / Python SDK / sim 模拟器）
   │  POST /api/v1/report   心跳 30s；信号也走同一个包
   ▼
FastAPI + SQLite ──▶ Watchdog（60s 判死 / loop 卡死）──▶ 红色 P0 告警 ──▶ 钉钉
   │
   └──▶ Vue 3 面板（总览 / 策略 / 信号 / 告警 / 设置）
~~~

- 纯推送：策略不需要被扫描、不需要开放端口；服务端只认「有没有按时报到」。
- 只读：服务端没有任何下单能力。
- 单机：一台交易机 / NAS / VPS 即可，数据保存在本地 SQLite。

技术栈：Vue 3 + TypeScript + Vite + Naive UI + ECharts（前端）；FastAPI + SQLite（后端）。

## 快速开始

环境：Python 3.10+、Node.js 20+。

### 1. 初始化基础数据

~~~bash
pip install -r backend/requirements.txt

# 只写入账户 / 钉钉渠道 / 交易日历 / 配色（注意：会清空运行时数据）
python -m backend.seed
~~~

### 2. 启动后端

~~~bash
python -m backend
# http://127.0.0.1:8080
~~~

- 默认登录密码：**qwatch**，可用环境变量 `QWATCH_PASSWORD` 修改。
- 数据库：`data/qwatch.db`（自动创建，已 gitignore）。
- 修改前端代码后需要重新构建，后端会直接托管 `frontend/dist`。

### 3. 生成三策略模拟数据（可选）

另开一个终端，运行内置模拟器：通过真实 API 创建 3 个策略和令牌，并持续发送心跳 / 信号 / 权益。

~~~bash
python -m sim.run
# Ctrl+C 退出
~~~

- 策略：螺纹钢趋势（QMT）/ 股指日内（PTrade）/ 白银波段（掘金）
- 首次运行会补齐 180 天历史权益，总览的夏普、回撤、年化等指标立即有数据。
- 令牌保存在 `data/sim_tokens.json`（gitignore），重启后自动复用。
- 环境变量：`QWATCH_URL`、`QWATCH_PASSWORD`。

### 4. 前端开发（可选）

~~~bash
cd frontend
npm install
npm run dev      # http://127.0.0.1:5173，/api 代理到 8080
~~~

生产构建：

~~~bash
cd frontend
npm run build    # 产物在 frontend/dist，由后端直接托管
~~~

## 策略接入（Python SDK）

~~~bash
cd sdk/python
pip install -e .
~~~

~~~python
from qwatch import Qwatch

q = Qwatch("http://127.0.0.1:8080", "qw_xxxxxxxx", 30)  # 初始化即自动心跳
q.signal("rb2601", "long", "open", 10, price=3521, msg="突破前高")
q.tick()            # 主循环每轮调用，心跳带上 loop，服务端据此判断卡死
q.equity(462300.12)          # 出入金：q.equity(新权益, cash_flow=入金正/出金负)
q.close()
~~~

- 什么都不填 = 心跳；信号 = 心跳 + 信号；
- 30 秒自动心跳，60 秒无请求判死；
- 信号字段严格校验：symbol + direction + action + qty 必须完整；
- 出入金用 `cash_flow` 一起上报，累计盈亏会剔除本金变化；
- 完整说明见 [sdk/python/README.md](sdk/python/README.md)。

## 目录

~~~
backend/         FastAPI + SQLite 后端
frontend/        Vue 3 + Naive UI + ECharts
sdk/python/      Python 接入 SDK（零依赖）
sim/             三策略模拟器（通过真实 API）
screenshots/     界面截图
data/            运行时 SQLite / 模拟器令牌（gitignore）
~~~

## 使用说明与限制

- 单用户、单机部署；公网访问建议放在 Cloudflare Tunnel / Nginx + HTTPS 后面。
- 服务端只读：不接券商、不下单。
- 告警渠道当前支持钉钉群机器人；配置后可在设置页发送测试消息。
- 告警规则只保留心跳丢失与策略卡死；其他规则后续按需增加。
- 日胜率、盈亏比等指标基于权益序列计算；接入成交明细后可换成真实交易口径。
- 演示钉钉 Webhook 为占位，请替换后再测试发送。

## License

[Apache-2.0](LICENSE)