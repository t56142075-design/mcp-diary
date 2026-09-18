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

## 快速开始（占位，阶段 6 完善）

```bash
git clone <repo-url>
cd mcp-diary
cp .env.example .env
pip install -e .
```

MCP 接入示例（Claude Desktop / 其他 MCP 客户端）：

```json
{
  "mcpServers": {
    "diary": {
      "command": "python",
      "args": ["-m", "mcp_diary.server"]
    }
  }
}
```

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
