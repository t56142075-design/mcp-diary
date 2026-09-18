# PROGRESS 进度锚点（唯一进度真相源）

> 任何新会话/窗口接续工作：先读完本文档，再读 docs/00-PLAN.md 中对应阶段章节。
> 规则：每完成一个阶段，写 docs/XX-*.md 并更新本文档，然后才允许进入下一阶段。

## 当前状态

- **当前阶段**：阶段 0 已完成，等待用户确认方案后进入阶段 1
- **项目路径**：`E:\work space\mcp-diary`（本地 git 仓库已初始化，分支 master）
- **最后更新**：2026-09-18

## 已完成

### 阶段 0 ✅（2026-09-18）
- git 仓库初始化（本地，尚未有 GitHub 远程）
- LICENSE（MIT，版权人 Ping）
- .gitignore（忽略 data/、*.db、.env、*.key、keys/、Python 产物）
- .env.example（DIARY_DATA_DIR / DIARY_USER_PASSPHRASE / DIARY_AI_KEY_FILE）
- README.md 草稿（含隐私边界诚实说明）
- docs/00-PLAN.md 全阶段方案（技术选型、架构、数据模型、MCP 工具清单、8 阶段划分）

## 关键决策记录

1. 技术栈：Python 3.13 + 官方 mcp SDK（FastMCP/stdio）+ SQLite 三库分离 + AES-256-GCM + cryptography 库 + CLI 用户端。用户尚未最终确认，进入阶段 1 前需确认。
2. 隔离方案：句柄隔离 + 接口最小化 + 纵深加密，三道闸门详见 00-PLAN.md 第三节。
3. 三个独立库文件而非单库分表：为了让 MCP 进程里彻底不存在用户区路径。
4. 公共区明文存储，私密区密文存储。
5. 本机未安装 gh 命令，GitHub 远程仓库需用户创建空仓库后提供地址，或安装 gh 并登录。

## 下一步入口

- 待用户确认技术栈 → 进入阶段 1：写 `docs/01-ARCHITECTURE.md`（模块划分、API 签名、加密细节）
- 阶段 1 完成标准：架构文档定稿，含每个模块的公开函数签名与密钥生命周期说明

## 已知问题 / 阻塞

- GitHub 远程仓库未建（见决策 5），不影响阶段 1-6 本地开发。
- Windows 环境注意：代码里路径统一用 pathlib，避免反斜杠问题。
