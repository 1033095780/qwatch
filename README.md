# qwatch

**多策略 / 多市场监控工作台**：净值曲线、交易信号、策略存活 watchdog 与钉钉告警。自用，开源。

## 功能

- **总览**：组合权益、今日盈亏、策略状态、最近信号与活跃告警
- **策略**：新建策略即生成接入令牌；净值/回撤、信号、持仓、心跳、告警历史、令牌管理
- **交易信号**：按策略 / 平台 / 市场 / 类型 / 标签 / 方向 / 状态筛选，排序、分页、导出 CSV
- **告警**：P0/P1/P2 分级，确认与静默；心跳丢失、策略卡死、回撤超限等规则
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
策略进程（任意语言 / Python SDK）
   │  POST /api/v1/report   心跳 30s；信号也走同一个包
   ▼
FastAPI + SQLite ──▶ Watchdog（30s 心跳 / 60s 判死 / loop 卡死）──▶ 告警 ──▶ 钉钉
   │
   └──▶ Vue 3 面板（总览 / 策略 / 信号 / 告警 / 设置）
~~~

- 纯推送：策略不需要被扫描、不需要开放端口；服务端只认「有没有按时报到」。
- 只读：服务端没有任何下单能力。
- 单机：一台交易机 / NAS / VPS 即可，数据保存在本地 SQLite。

技术栈：Vue 3 + TypeScript + Vite + Naive UI + ECharts（前端）；FastAPI + SQLite（后端）。

## 快速开始

环境：Python 3.10+、Node.js 20+。

### 1. 启动后端

~~~bash
pip install -r backend/requirements.txt

# 可选：生成演示数据（策略 / 信号 / 告警 / 钉钉渠道）
python -m backend.seed

# 启动 API + 前端静态文件
python -m backend
# http://127.0.0.1:8080
~~~

- 默认登录密码：**qwatch**，可用环境变量 `QWATCH_PASSWORD` 修改。
- 数据库：`data/qwatch.db`（自动创建，已 gitignore）。
- 修改前端代码后需要重新构建，后端会直接托管 `frontend/dist`。

### 2. 前端开发（可选）

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
q.equity(462300.12)
q.close()
~~~

- 什么都不填 = 心跳；信号 = 心跳 + 信号；
- 30 秒自动心跳，60 秒无请求判死；
- 信号字段严格校验：Symbol + direction + action + qty 必须完整；
- 完整说明见 [sdk/python/README.md](sdk/python/README.md)。

## 目录

~~~
backend/         FastAPI + SQLite 后端、演示数据
frontend/        Vue 3 + Naive UI + ECharts
sdk/python/      Python 接入 SDK（零依赖）
screenshots/     界面截图
data/            运行时 SQLite（gitignore）
~~~

## 使用说明与限制

- 单用户、单机部署；公网访问建议放在 Cloudflare Tunnel / Nginx + HTTPS 后面。
- 服务端只读：不接券商、不下单。
- 告警渠道当前支持钉钉群机器人；配置后可在设置页发送测试消息。
- 真实策略历史数据从接入后开始积累；演示数据只用于本地预览（演示钉钉 Webhook 为占位，请替换后再测试发送）。

## License

[Apache-2.0](LICENSE)
