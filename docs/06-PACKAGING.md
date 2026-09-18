# 06 打包与文档完善（阶段 6 完成存档）

## 交付物

| 文件 | 内容 |
|---|---|
| `Dockerfile` | python:3.13-slim，pip 装包后 ENTRYPOINT mcp-diary-server，DIARY_DATA_DIR=/app/data |
| `docker-compose.yml` | data 卷挂载 + 环境变量，stdin_open 供 MCP 客户端拉起 |
| `.dockerignore` | 数据/密钥/测试/文档全部排除出镜像 |
| `README.md` | 状态更新为"核心功能已完成"，补 Docker 一节、开发测试一节、目录结构实况、口令遗忘警告 |

## 设计取舍（自用定位）

1. **Docker 是可选项而非主路径**。stdio MCP server 的工作方式是宿主客户端拉起子进程，本地自用时 `pip install -e .` 直接用最简单。Docker 配置提供给需要容器化隔离或自托管的场景，README 里明确写了这一点，避免误导。
2. **数据全部落在宿主 `./data`**。容器内不持有任何持久状态，备份一个目录等于备份全部。这与本项目的隐私模型一致：真实数据永远不该进镜像或 git。
3. `.dockerignore` 把 tests/ 和 docs/ 也排除，镜像里只有运行必需物。
4. **`.mcpb` 打包跳过**。自用场景不需要分发给第三方，Claude Desktop 用 JSON 配置即可接入。若未来要分发，可再补。

## 已知限制

- 本机无 Docker，镜像构建未实测。Dockerfile 是保守标准写法（官方 slim 基镜像、无多余层），有 Docker 的机器上 `docker compose build` 即可验证。
- compose 里 DIARY_USER_PASSPHRASE 默认注释掉，CLI 走交互输入，避免口令写进 compose 文件。

## 下一步：阶段 7

开源前检查与发布：
1. 泄密扫描：git 全历史扫真实日记内容、密钥、密码、令牌（此前 push_log.txt 事故已清理，正式发布前再做一次全量确认）。
2. 确认 .gitignore 覆盖完整（data/、keys/、.env 不在 git ls-files 里）。
3. 仓库转公开（用户确认后），打 v0.1.0 tag。
