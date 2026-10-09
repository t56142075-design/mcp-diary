# PROGRESS 进度锚点（唯一进度真相源）

> 任何新会话/窗口接续工作：先读完本文档，再读 docs/00-PLAN.md 中对应阶段章节。
> 规则：每完成一个阶段，写 docs/XX-*.md 并更新本文档，然后才允许进入下一阶段。

## 当前状态

- **当前阶段**：v0.1.0 发布后追加完成了 ChatGPT 远程接入（阶段 8，见 docs/08-CHATGPT.md）
- **项目路径**：`E:\work space\mcp-diary`（分支 main）
- **远程仓库**：https://github.com/t56142075-design/mcp-diary
- **最后更新**：2026-10-09（ChatGPT 接入 commit 已推送；git 推送凭据方案修订）

## git 推送操作备忘（Windows 本机重要坑，2026-10-09 修订）

1. 本机 PortableGit 配置了 `credential.helper=helper-selector`。不带认证的读请求（如 `git fetch`）能正常通过；一旦服务器返回 401（push 必走这条路），git 会调它去取凭据，它试图弹交互窗口，无头环境下进程静默挂死、零输出。诊断特征：`GIT_CURL_VERBOSE=1 GIT_TRACE=1` 能看到 `HTTP/1.1 401 Unauthorized` 与 `www-authenticate: Basic realm="GitHub"` 之后就再无任何日志。
2. `-c credential.helper='!gh auth git-credential'` 这个写法在本机不可靠：git 通过子 shell 调 gh，子 shell 的 PATH 里找不到 gh，该 helper 静默失败后仍会落回 helper-selector，照旧卡死。不要再用。
3. 现在可用的写法（本机 gh CLI 已登录账号 t56142075-design，令牌存 keyring，scopes 含 repo）：
   ```bash
   TOKEN=$(gh auth token) && git -c credential.helper= push \
     "https://t56142075-design:${TOKEN}@github.com/t56142075-design/mcp-diary.git" main
   ```
   一次性 URL 不污染 remote 配置，令牌不落任何文件。若要遮蔽可能回显的令牌，管道接 `| sed -E 's/gh[opsu]_[A-Za-z0-9]+/TOKEN_HIDDEN/g'`。
4. 代理层不是病因，排查时别先怀疑它：本机 git 配置了 `http.proxy=127.0.0.1:10808` 走系统代理，fetch 与 `gh api`（含 POST）都能通过。
5. 历史包袱与修正：早期版本要求用户提供短期 PAT 来推送。gh CLI 接管凭据后，**不必再让用户提供 PAT，也不要在对话里传令牌**。

## 已完成

### 阶段 7 ✅（2026-09-26）
- git 全历史泄密扫描（令牌/密钥/AWS Key/PEM 模式）：0 命中
- 版本库敏感文件核查：无 .env、无密钥、无 data/、无数据库文件被跟踪
- 发布门槛：57/57 测试 + stdio 冒烟全过
- docs/07-RELEASE.md 记录扫描明细与历史事故处置结论
- v0.1.0 tag，仓库转公开

### 阶段 6 ✅（2026-09-18）
- Dockerfile / docker-compose.yml / .dockerignore（保守标准写法，本机无 Docker 未实测构建）
- README 达到可发布水平：状态、Docker 一节、开发测试、目录实况、口令遗忘警告
- .mcpb 打包按自用定位跳过（决策记录在 docs/06-PACKAGING.md）

### 阶段 5 ✅（2026-09-18）
- tests/test_isolation.py：13 个集成测试，权限矩阵六格逐格验证全过
- 跨区密钥互用验证：用户密钥解不开 AI 库、AI 密钥解不开用户库（纵深加密最后一道闸门）
- docs/05-SECURITY.md：安全声明 + 威胁模型 + 诚实边界（防得住什么、防不住什么）
- 全部 57 个测试通过

### 阶段 4 ✅（2026-09-18）
- cli.py（argparse，用户私密区 6 命令 + 公共区 4 命令，author 恒 user）+ test_cli.py（10 测试）
- 全部 44 个测试通过；对称渗透证明 AI 区明文在 CLI 全命令输出中不可达
- 修复阶段 2 遗留两 bug：update() WHERE 用错主键（短 id 时不落库）；get/delete 现支持短 id 前缀唯一命中
- 静态扫描自咬：cli.py 文档字符串提及 AI 密钥函数名被自己的测试扫出，已改写（证明扫描有效）
- README 已含 CLI 用法示例；详情 docs/04-CLI.md

### 阶段 3 ✅（2026-09-18）
- server.py（FastMCP stdio，8 个 ai/shared 工具）+ test_server_tools.py（8 测试）+ scripts/smoke_stdio.py 端到端冒烟
- 全部 34 个测试通过；渗透测试证明用户区明文在 MCP 全部工具输出中不可达
- mcp SDK 锁定 `>=1.0,<2`（2.x 改名 FastMCP→MCPServer，暂不跟）
- models/storage 增加 author 字段（公共区区分作者）
- README 已含 Claude Desktop 接入示例与工具清单
- 关键坑：server 必须以 `-m mcp_diary.server` 或入口命令启动，文件直跑相对导入会崩；详情 docs/03-MCP-SERVER.md

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
5. GitHub 远程仓库已建成并推送（现已转公开）。WorkBuddy GitHub 连接器令牌只读，写操作改用本机 gh CLI 的账号令牌（`gho_`，存系统 keyring），不再经手用户 PAT。

## 下一步入口

- ChatGPT 接入（阶段 8）已完成：HTTP 模式 + Bearer 鉴权 + Cloudflare 快速隧道，公网写读往返验证通过，详见 docs/08-CHATGPT.md。用户侧一键启动：`scripts/start-chatgpt.bat`（隧道域名每次重启会变，ChatGPT 端需更新 endpoint）。
- 后续可选方向（都不属于原计划）：
  - Web 界面（用户端从 CLI 升级，隔离逻辑直接复用 storage 层）
  - mcp SDK 升级 2.x（需迁移 FastMCP → MCPServer 改名）
  - Cloudflare Named Tunnel 固定域名（免费账号可建，免去每次更新 endpoint）
  - `.mcpb` 打包分发（需要分发给他人时再做）
- venv python 路径：`C:/Users/26627/.workbuddy/binaries/python/envs/default/Scripts/python.exe`

## 已知问题 / 阻塞

- 无阻塞。推送走 gh CLI 令牌（见上方备忘第 3 条），不再需要用户提供 PAT 或创建新令牌。
- pytest 临时目录：`--basetemp="$TEMP/mcp-diary-pytest-$$RANDOM"` 每次全新路径；复用项目内旧目录会被启动清理 + 安全删除保护卡住。
- Windows 环境注意：代码里路径统一用 pathlib，避免反斜杠问题。
