# MCP 双人日记

一个可接入 MCP（Model Context Protocol）的双主体日记系统。人和 AI 各有私密日记，还有一片共享区，三方边界在代码层强制隔离。

## 核心理念

| 区域 | 用户 | AI / MCP |
|---|---|---|
| 用户私密区 | 可读写 | 完全不可见（MCP 层零工具、零路径、零密钥） |
| AI 私密区 | 界面不可见 | 可读写 |
| 公共区 | 可读写 | 可读写 |

隐私隔离在服务层和存储层强制实现，不依赖提示词约束。MCP Server 进程中根本不存在用户私密区的文件路径与解密密钥，AI 无代码路径可走。

## 状态

核心功能已完成（57 个测试全绿）。进度与阶段文档见 [docs/PROGRESS.md](docs/PROGRESS.md)，安全模型见 [docs/05-SECURITY.md](docs/05-SECURITY.md)。

## 快速开始

```bash
git clone <repo-url>
cd mcp-diary
cp .env.example .env
pip install -e .          # 需要 Python 3.11+
```

首次以 MCP 方式启动时会自动生成：
- `data/ai_private.db`（AI 私密区，AES-256-GCM 加密）
- `data/shared.db`（公共区）
- `data/keys/ai_private.key`（AI 区密钥，已被 .gitignore 忽略）

用户私密区 `data/user_private.db` 由 CLI 首次使用时创建，用你的口令加密。

### MCP 接入

Claude Desktop（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "diary": {
      "command": "mcp-diary-server",
      "env": {
        "DIARY_DATA_DIR": "/absolute/path/to/mcp-diary/data",
        "DIARY_AI_KEY_FILE": "/absolute/path/to/mcp-diary/data/keys/ai_private.key"
      }
    }
  }
}
```

其他 MCP 客户端（WorkBuddy 等）同样配置 command 为 `mcp-diary-server`（或 `python -m mcp_diary.server`），stdio 传输。

### AI 侧可用的 8 个工具

AI 私密区：`write_ai_private_diary` `read_ai_private_diary` `list_ai_private_diary` `search_ai_private_diary`
公共区：`write_shared_diary` `read_shared_diary` `list_shared_diary` `search_shared_diary`

不存在任何能读取用户私密区的工具，这一点有测试保证（tests/test_server_tools.py）。

### 用户端 CLI

```bash
diary write --title "随笔" -t 生活      # 写私密日记（正文走 stdin，交互输入行末 . 结束）
diary list                              # 列私密日记（显示短 id）
diary read 3f2a1b9c                     # 读一条（支持短 id）
diary search 关键词
diary edit 3f2a1b9c --title 新标题
diary delete 3f2a1b9c                   # 软删除

diary shared write --title "给AI的留言"  # 写公共区（AI 通过 MCP 可读）
diary shared list
```

私密区首次使用时设置口令（`DIARY_USER_PASSPHRASE` 环境变量可免交互）。口令只派生密钥、不落盘；忘记口令 = 数据不可恢复，请妥善保管。

### 端到端冒烟验证

```bash
python scripts/smoke_stdio.py
```

以 stdio 协议拉起 server，走完整握手、工具列举、读写往返，并断言 server 从不创建用户区数据库。

### Docker（可选）

stdio 类 MCP server 主要由宿主 MCP 客户端直接拉起，本地自用时不需要 Docker。需要容器化部署时：

```bash
docker compose build
docker run -i -v ./data:/app/data mcp-diary:latest   # 由 MCP 客户端以 stdin/stdout 拉起
```

全部真实数据（三个库 + 密钥）只落在宿主 `./data` 目录，备份这个目录就是备份全部。

### 接入 ChatGPT（远程 MCP，可选）

ChatGPT 网页版只支持公网 HTTPS 远程 MCP，不能拉起本地 stdio 服务。项目内置了 streamable HTTP 模式 + Bearer 令牌鉴权，配合 Cloudflare 快速隧道即可接入：

```bash
# Windows 一键启动（首次先改脚本头部两个路径）
scripts\start-chatgpt.bat
```

脚本会拉起本地 server 和隧道，窗口里出现 `https://xxxx.trycloudflare.com` 后，在 ChatGPT 开发者模式中创建自定义连接器，endpoint 填 `https://<隧道域名>/mcp`，鉴权填脚本生成的 Bearer 令牌。详细步骤与限制（电脑需开机在线、隧道域名每次重启会变）见 [docs/08-CHATGPT.md](docs/08-CHATGPT.md)。

## 隐私与安全的诚实边界

- 用户私密区内容用你的口令派生密钥做 AES-256-GCM 加密，AI 侧没有口令，拿到文件也无法解密。
- AI 私密区内容同样加密存储，但密钥由本机 MCP Server 保管。
- 本地自用场景下，"用户看不到 AI 私密区"只能做到界面与协议层不可见。技术用户可以直接翻到加密后的数据库文件，看到内容需要密钥，但文件的存在无法隐藏。这是本地单机架构的固有边界，请知悉。
- 用户口令忘了就是忘了，没有后门，数据不可恢复。
- 完整威胁模型（防得住什么、防不住什么）见 [docs/05-SECURITY.md](docs/05-SECURITY.md)。
- 任何情况下都不要把 `data/` 目录、`.env`、`*.key` 提交到 git。

## 开发与测试

```bash
pip install -e ".[dev]"
pytest                                    # 57 个测试：加密、存储、MCP 工具、CLI、权限矩阵
python scripts/smoke_stdio.py             # stdio 端到端冒烟
```

## 目录结构

```
mcp-diary/
├── src/mcp_diary/
│   ├── zones.py        # Zone 枚举与权限矩阵（唯一事实源）
│   ├── models.py       # Entry 数据类
│   ├── crypto.py       # scrypt 派生 + AES-256-GCM
│   ├── storage.py      # DiaryStore（单区域单实例）+ open_store 工厂
│   ├── server.py       # MCP Server（仅 ai/shared 共 8 个工具）
│   └── cli.py          # 用户端 CLI（仅 user/shared）
├── tests/              # 57 个测试：加密/存储/MCP工具/CLI/权限矩阵隔离
├── scripts/smoke_stdio.py  # stdio 端到端冒烟
├── docs/               # 阶段文档（00-05）与进度锚点
├── Dockerfile / docker-compose.yml / .dockerignore
├── .env.example
└── README.md
```

## License

MIT
