# qwatch frontend

Vue 3 + TypeScript + Vite + Naive UI（darkTheme + themeOverrides）+ ECharts + Pinia + Vue Router。

## 开发

```bash
npm install
npm run dev          # http://127.0.0.1:5173
npm run typecheck    # vue-tsc --noEmit
npm run build        # 类型检查 + 构建 dist/
node mock-server.mjs # http://127.0.0.1:8080（dist + /api/v1）
```

内置演示数据，登录密码 **qwatch**。

## 结构

- `src/views/`：11 条路由页面（登录 / 总览 / 策略 / 策略详情 / 账户 / 账户详情 / 交易 / 告警 / 日报 / 设置 / 404）
- `src/components/`：设计系统组件与图表封装
- `src/styles/tokens.css`：设计 tokens 唯一来源；`naive-theme.ts` 映射到 Naive UI
- `src/api/types.ts` + `client.ts`：接口契约类型与 fetch 封装
- `mock/data.mjs`：演示数据（7 runner / 3 账户 / 200 成交 / 180 天净值 / 8 告警 / 7 日报）
- `mock/api.mjs`：`/api/v1/*` 路由，Vite 与 `mock-server.mjs` 共用

## 说明

- 接口按契约以真实 HTTP 提供；后端接入后替换 mock 服务即可，页面无需改动。
- 演示数据为 seeded 随机，非真实账户记录。
- 成交表当前一次拉取 ≤200 条后本地排序/分页；数据量增长后改为服务端排序。
- 登录 token 存在 localStorage；接入后端后改为 HttpOnly session cookie。
