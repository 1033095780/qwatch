# qwatch 安全说明与渗透测试报告

## 部署安全

- 默认监听 `127.0.0.1:13337`
- 首次启动必须设置访问密码；密码最少 10 位
- PBKDF2-HMAC-SHA256（310,000 次）加盐存储
- 已配置密码后重复初始化返回 409
- 初始化默认只允许本机；远程初始化需设置 `QWATCH_SETUP_TOKEN`，并在请求中携带同名 `setup_token`
- 生产建议 HTTPS 反向代理；`QWATCH_HOST` 默认仅本机

可选环境变量：

```text
QWATCH_HOST=127.0.0.1
QWATCH_PORT=13337
QWATCH_PASSWORD=...        # 自动化部署；设置后跳过初始化
QWATCH_SETUP_TOKEN=...     # 远程初始化保护
```

## 防攻击措施

- 默认密码已移除；密码只存 PBKDF2 哈希
- 会话 token 使用 256-bit 随机值，数据库只保存 SHA-256 哈希，12 小时过期
- 登录失败 5 次/分钟/IP 触发 429
- 所有业务 API 需要 Bearer 会话；策略 token 不能调用管理 API
- SSE 只接受 Authorization 头，已移除 URL query token，避免 token 进入访问日志/Referrer
- API 请求体上限 512KB，超大请求返回 413
- 策略上报限速 600 次/分钟/token，超出返回 429
- 单策略进程数上限 64，防止伪造 instrument 无限建进程
- 钉钉 Webhook 仅允许 `https://oapi.dingtalk.com/robot/send`，并禁止 HTTP 重定向，防止 SSRF
- CSP、X-Frame-Options、X-Content-Type-Options、Referrer-Policy、Permissions-Policy
- 关闭 FastAPI /docs、/redoc、/openapi.json 路由；未知路径只回 SPA 壳
- CORS 仅允许本机 5173 / 13337；恶意 Origin 不返回 Allow-Origin
- 静态文件路径做 resolve/is_relative_to 检查，阻止路径穿越
- SQL 全部参数化；动态 SQL 片段只来自固定代码
- 初始密码设置、密码修改、重复初始化均有竞态锁/状态检查
- 原始权益点保留 30 天、日权益长期、心跳桶 30 天、事件 180 天

## 渗透测试结果（隔离临时 DB + 13338 端口）

| 检查项 | 结果 |
|---|---|
| 未登录访问 /overview | 401 |
| 错误密码登录 | 401 |
| 连续 6 次错误登录 | 第 6 次 429 |
| 首次初始化弱密码 | 400 |
| 已初始化后再次 setup | 409 |
| 策略 token 调用 /overview | 401 |
| 会话 token 调用 /report | 401 |
| SSE query token | 401（已禁止） |
| 1MB 请求体 | 413 |
| 策略上报 620 次/分钟 | 前 600 次 200，之后 429 |
| 非法 loop / equity / signal | 400 |
| SQL 注入搜索参数 | 200，参数化查询，无异常 |
| Webhook 内网地址 / 非钉钉域名 | 400 |
| 路径穿越 3 种编码 | 404 |
| 恶意 Origin CORS | 不返回 Allow-Origin |
| 密码/会话明文落库 | 无 |
| 安全响应头 | 已返回 |
| CSP | 已启用，脚本仅 self |
| 旧 /alerts | 跳转 /activity |
| 前端 E2E | 0 JS 错误，SSE 正常 |

## 剩余风险

1. 当前为 HTTP 本机/内网部署；公网必须加 HTTPS 与 HSTS。
2. 浏览器会话 token 存于 localStorage，已用 CSP 限制脚本源；更高隔离可改为 HttpOnly Cookie。
3. 登录限速按来源 IP，反向代理后需确保真实客户端 IP 不被统一代理 IP 合并。
4. 请求体限制依赖 Content-Length；分块传输上限需要在反向代理层补 client_max_body_size。
5. 策略 token 被窃取后仍可在 600 次/分钟、64 进程上限内上报；请妥善保管 token。
6. SQLite 文件与 dingtalk secret 未加密，请限制 data/qwatch.db 文件权限。
7. 无 MFA；单用户模型不适合多租户直接暴露。

## 复现方式

安全测试使用独立数据库：

```text
QWATCH_DB=<temp.db>
QWATCH_PASSWORD=<test-pass>
QWATCH_PORT=13338
```

未对 13337 生产数据库执行破坏性测试。
