# PROGRESS 进度锚点（唯一进度真相源）

> 任何新会话/窗口接续工作：先读完本文档，再读 docs/00-PLAN.md 中对应阶段章节。
> 规则：每完成一个阶段，写 docs/XX-*.md 并更新本文档，然后才允许进入下一阶段。

## 当前状态

- **当前阶段**：阶段 0、1、2 已完成，下一步进入阶段 3（MCP Server 与 8 个工具）
- **项目路径**：`E:\work space\mcp-diary`（分支 main）
- **远程仓库**：https://github.com/t56142075-design/mcp-diary（私有，发布前做泄密扫描后再转公开）
- **最后更新**：2026-09-18

## git 推送操作备忘（Windows 本机重要坑）

1. 本机 PortableGit 配置了 `credential.helper=helper-selector`，无交互环境下 git push/fetch/ls-remote 会被它带崩且无任何输出。推送时必须禁用：`git -c credential.helper= push origin main`
2. 推送凭据：GitHub 连接器的 OAuth 令牌是只读的（403），建仓库和推送要用 PAT（用户会提供，短期有效）。PAT 不写入任何文件，仅一次性用于命令行。
3. 推送后如把 PAT 嵌入了 remote URL，立即 `git remote set-url origin https://github.com/t56142075-design/mcp-diary.git` 清除。

## 已完成

### 阶段 2 ✅（2026-09-18）
- 存储层四模块（zones/models/crypto/storage）+ pyproject.toml + 26 个单元测试全绿
- 验证了：密文落盘（读库文件二进制找不到明文）、title 列只存占位符、错误口令必失败、篡改必失败、AI 区密钥重读后可解密
- 测试运行命令与两个本机坑（pytest 临时目录权限、PYTHONPATH）记录在 docs/02-STORAGE.md

### 阶段 1 ✅（2026-09-18）
- docs/01-ARCHITECTURE.md 架构定稿：模块划分、全部 API 签名、密钥生命周期表、加密区搜索取舍、隔离测试验收标准、pyproject 要点
- 关键设计增量：私密区把 title 与 body 一起整体加密（表内 title 存占位符），标题同样不泄露；meta 表存用户库 salt
- 技术栈已获用户确认（Python + 官方 mcp SDK + SQLite 三库 + AES-GCM + CLI）

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
5. GitHub 远程仓库已建成并推送（私有）。WorkBuddy GitHub 连接器令牌只读，写操作用用户提供的短期 PAT。

## 下一步入口

- 阶段 3：实现 `server.py`（FastMCP + 8 个 ai/shared 工具）+ `test_server_tools.py` 静态断言（工具名不含 user、数量恰 8）+ MCP 接入配置示例（README 更新）
- 前置：在 managed venv 安装 `mcp` 包，然后 `pip install -e .`
- 阶段 3 完成标准：server 启动冒烟通过，工具列表断言通过，用户区在 server 进程中零引用（源码静态扫描）
- venv python 路径：`C:/Users/26627/.workbuddy/binaries/python/envs/default/Scripts/python.exe`

## 已知问题 / 阻塞

- GitHub 推送需用户提供新 PAT（旧令牌已按用户要求撤销）。推送命令见上方备忘。
- pytest 临时目录必须用 `--basetemp` 指到项目内 `.pytest-tmp`（系统 Temp 下 pytest 目录权限拒绝）。
- Windows 环境注意：代码里路径统一用 pathlib，避免反斜杠问题。
