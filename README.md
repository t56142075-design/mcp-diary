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

开发中。当前进度见 [docs/PROGRESS.md](docs/PROGRESS.md)，全阶段方案见 [docs/00-PLAN.md](docs/00-PLAN.md)。

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

### 端到端冒烟验证

```bash
python scripts/smoke_stdio.py
```

以 stdio 协议拉起 server，走完整握手、工具列举、读写往返，并断言 server 从不创建用户区数据库。

## 隐私与安全的诚实边界

- 用户私密区内容用你的口令派生密钥做 AES-256-GCM 加密，AI 侧没有口令，拿到文件也无法解密。
- AI 私密区内容同样加密存储，但密钥由本机 MCP Server 保管。
- 本地自用场景下，"用户看不到 AI 私密区"只能做到界面与协议层不可见。技术用户可以直接翻到加密后的数据库文件，看到内容需要密钥，但文件的存在无法隐藏。这是本地单机架构的固有边界，请知悉。
- 任何情况下都不要把 `data/` 目录、`.env`、`*.key` 提交到 git。

## 目录结构（规划）

```
mcp-diary/
├── docs/                # 阶段文档与进度锚点
├── src/mcp_diary/
│   ├── storage.py       # 存储层：按区域隔离的 DiaryStore
│   ├── crypto.py        # 密钥派生与 AES-GCM 加解密
│   ├── server.py        # MCP Server（仅 ai/shared 工具）
│   └── cli.py           # 用户端 CLI（仅 user/shared）
├── tests/               # 权限矩阵隔离测试
├── .env.example
├── Dockerfile           # 阶段 6
└── README.md
```

## License

MIT
