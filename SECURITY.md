# qwatch 安全说明

## 部署

- 默认监听 `127.0.0.1:13337`
- 首次启动必须进入「初始化 qwatch」设置访问密码
- 密码最少 10 位，使用 PBKDF2-HMAC-SHA256（310,000 次）加盐存储
- 设置完成后才允许登录；重复初始化返回 409
- 服务默认只绑定本机；如需局域网访问，请放在 HTTPS 反向代理后，并显式设置 `QWATCH_HOST`

可选环境变量：

```text
QWATCH_HOST=127.0.0.1
QWATCH_PORT=13337
QWATCH_PASSWORD=...   # 自动化部署专用；设置后跳过首次初始化
```

## 已实施的安全措施

- 默认密码已移除；没有 `password_hash` 时只开放初始化页面
- 密码使用 PBKDF2 加盐哈希，不保存明文
- 会话 token 使用 256-bit 随机值，数据库只保存 SHA-256 哈希，12 小时过期
- 登录失败 5 次/分钟/IP 触发 429
- 所有业务 API 需要 Bearer 会话鉴权
- CSP、X-Frame-Options、X-Content-Type-Options、Referrer-Policy、Permissions-Policy
- 禁用 FastAPI /docs、/redoc、/openapi.json 路由
- CORS 仅允许本机 5173 / 13337
- 钉钉 Webhook 仅允许 `https://oapi.dingtalk.com/robot/send`，阻止 SSRF
- 静态文件路径做 `resolve/is_relative_to` 检查，阻止路径穿越
- SQL 全部参数化；动态表名仅来自固定代码
- 看门狗、告警、令牌、设置接口均要求登录
- 原始权益点保留 30 天、日权益长期、心跳桶 30 天、事件 180 天，防止存储无限增长

## 对抗性检查结果

| 检查 | 结果 |
|---|---|
| 未登录访问 /overview | 401 |
| 弱密码初始化 | 400 |
| 重复初始化 | 409 |
| 错误密码登录 | 401 |
| 恶意 Origin CORS | 不返回 Allow-Origin |
| 路径穿越 | 404 |
| 伪造钉钉 Webhook / SSRF | 400 |
| 明文密码落库 | 无，只有 PBKDF2 哈希 |
| 安全响应头 | 已返回 |
| 旧 /alerts | 302/跳转到 /activity |

## 仍需注意

1. 生产环境建议 HTTPS；本项目默认 HTTP 仅适合本机/内网。
2. 浏览器端会话 token 仍存于 localStorage，CSP 已限制脚本源；若需要更强隔离，可改为 HttpOnly Cookie。
3. 请定期备份 `data/qwatch.db`，限制文件权限。
4. 钉钉 Webhook 与加签密钥属于敏感配置，页面只显示掩码。
5. `QWATCH_PASSWORD` 环境变量仅建议用于自动化部署，不要写入 shell history 或公开脚本。
