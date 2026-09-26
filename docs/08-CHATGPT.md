# 08 - ChatGPT 接入方案（streamable HTTP + Cloudflare Tunnel）

> 阶段 8。日期：2026-09-26。前置：阶段 7 已发布 v0.1.0。

## 背景

ChatGPT 网页版不支持本地 stdio MCP 服务，只接受公网可达的 HTTPS 远程端点
（Streamable HTTP 协议）。本方案把本机 server 经 Cloudflare 快速隧道暴露为
公网 URL，供 ChatGPT 开发者模式自定义连接器调用。

## 架构

```
ChatGPT 云端
   |  HTTPS + Bearer Token
   v
Cloudflare 边缘（*.trycloudflare.com，零配置快速隧道）
   |
   v  本机回环
mcp_diary.server（HTTP 模式，127.0.0.1:8080）
   |
   v
data/（三库分离：ai_private.db 加密 / shared.db 明文 / user_private.db 不在此进程）
```

隐私立场：数据仍全部落在本机；隧道只转发加密 HTTPS 流量；无令牌请求一律 401。
但公网可达性与"电脑开着才在线"是此方案的固有代价，已在 README 与本文档声明。

## 代码改动（commit 见 git log）

1. `server.py` 新增 HTTP 模式：设置 `DIARY_HTTP_TOKEN` 即以 streamable HTTP
   运行，`_BearerAuthMiddleware` 校验 Authorization 头，错/缺同报 401 不泄露原因。
2. **Host 校验修复**：FastMCP 绑定 127.0.0.1 时自动启用 DNS 重绑定防护，
   Host 白名单只有 localhost，隧道域名被拒 421（"Invalid Host header"）。
   `_run_http()` 现按 `DIARY_ALLOWED_HOSTS` 配置白名单；未设置时关闭 Host
   校验（本模式已有 Bearer 令牌鉴权兜底）。stdio 模式完全不受影响。

## 环境变量（HTTP 模式）

| 变量 | 说明 |
|---|---|
| `DIARY_HTTP_TOKEN` | Bearer 令牌，设置即启用 HTTP 模式 |
| `DIARY_HTTP_HOST` | 监听地址，默认 127.0.0.1 |
| `DIARY_HTTP_PORT` | 端口，默认 8080 |
| `DIARY_ALLOWED_HOSTS` | Host 白名单，逗号分隔；留空关闭 Host 校验 |

## 一键启动

`scripts/start-chatgpt.bat`（首次使用先改文件头 PY / CF 两个路径）：

1. 首次运行自动生成持久令牌存 `data/http_token.txt`（data/ 已被 gitignore）
2. 拉起 server 窗口 + 隧道窗口
3. 隧道窗口约 10 秒后打印 `https://xxxx.trycloudflare.com`

## ChatGPT 端配置步骤

1. 开启开发者模式：Settings → Security and login → Developer mode
2. 创建连接器：Settings → Connectors → Create，填入
   - MCP endpoint：`https://<隧道域名>/mcp`
   - 鉴权：自定义连接器界面填 Bearer 令牌
3. 对话中选择该连接器即可调用 8 个日记工具
4. 注意：快速隧道域名每次重启会变，需在 ChatGPT 侧更新 endpoint；
   想固定域名可注册 Cloudflare 账号建 Named Tunnel（免费）

## 验证记录（2026-09-26）

- 本地无令牌 POST /mcp → 401
- 公网无令牌 → 401（鉴权在隧道层之后依然生效）
- 公网带令牌 initialize → 返回 8 个工具 schema
- 公网写 `write_shared_diary`（中文）→ 读回 `list_shared_diary` 内容一致
- 全量测试 57 个通过（stdio 模式无回归）

## 已知限制

- 电脑关机/脚本关闭即离线，ChatGPT 调不通
- 快速隧道域名不固定；国内网络对 trycloudflare 边缘偶发超时（重试即通）
- 公网暴露面：只有 /mcp 端点 + 令牌门槛；用户私密区在本进程无代码路径（阶段 3/5 已验证）
