# 00 全阶段方案（权威版）

本文档是项目的全程路线图。任何新会话/新窗口接续工作时，先读 `docs/PROGRESS.md` 确认进度，再读本文档对应的阶段章节。每完成一个阶段，写一篇 `docs/XX-*.md` 存档决策，并更新 `PROGRESS.md`。

## 一、项目目标

MCP 双人日记：人和 AI 各写各的私密日记，共享一片公共区。隐私隔离必须在服务层/代码层强制实现，不能只靠提示词。

## 二、技术选型（已定，除非用户推翻）

| 项 | 选择 | 理由 |
|---|---|---|
| 语言 | Python 3.13 | MCP 官方 SDK 成熟，加密库齐全 |
| MCP SDK | 官方 `mcp` 包（FastMCP，stdio 传输） | 事实标准，Claude Desktop / WorkBuddy 均可接 |
| 存储 | SQLite 三库分离 | 单文件天然便于按区域隔离权限 |
| 加密 | AES-256-GCM（cryptography 库） + scrypt 密钥派生 | 认证加密，防篡改 |
| 用户端 | CLI（argparse/typer） | 最快交付；Web 作为后续可选扩展 |
| 测试 | pytest | 权限矩阵隔离测试是硬性验收 |

## 三、架构

```
用户端 CLI ──只持有 user/shared 两个存储句柄──┐
                                              ├──► user_private.db（用户口令派生密钥加密）
MCP Server ──只持有 ai/shared 两个存储句柄──┼──► ai_private.db（服务端密钥加密）
（Claude Desktop 等 MCP 客户端）             └──► shared.db（明文，双方可读写）
```

### 权限隔离三道闸门（全部在代码层）

1. **句柄隔离**：存储层 `DiaryStore` 按区域实例化，构造时传入允许的区域集合。MCP Server 只创建 `ai_private` 和 `shared` 两个实例，用户区文件路径与口令永远不进入 MCP 进程内存。
2. **接口最小化**：存储层不提供跨区查询，没有 `read_any_zone` 之类的接口。每个 store 实例只认识自己的那一个库文件。
3. **纵深加密**：user_private.db 的密钥由用户口令经 scrypt 派生，口令不落盘；ai_private.db 的密钥由服务端首次启动生成，存于 `data/keys/`（gitignored）。即使某一方拿到对方文件，也无法解密。

### 隔离验收标准（阶段 5 的测试必须证明）

- MCP Server 注册的工具列表中不含任何 user 区工具（静态断言）。
- 任何 MCP 工具调用的任何参数组合，都无法读出用户私密区内容（动态渗透测试）。
- CLI 的任何命令都无法读出 AI 私密区内容。
- 三个库文件路径互不可达：MCP 进程里 grep 不到 user_private 字符串。

## 四、数据模型

三个库结构相同，单表：

```sql
CREATE TABLE entries (
    id          TEXT PRIMARY KEY,   -- uuid4
    title       TEXT NOT NULL,
    body        BLOB NOT NULL,      -- 私密区为 AES-GCM 密文；公共区为明文 TEXT
    tags        TEXT NOT NULL DEFAULT '[]',  -- JSON 数组
    created_at  TEXT NOT NULL,      -- ISO 8601
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT                -- 软删除，NULL 表示未删
);
CREATE INDEX idx_entries_created ON entries(created_at);
```

## 五、MCP 工具清单（共 8 个，阶段 3 实现）

AI 私密区：
- `write_ai_private_diary(title, content, tags)`
- `read_ai_private_diary(entry_id)`
- `list_ai_private_diary(date_from, date_to, limit)`
- `search_ai_private_diary(keyword)`

公共区：
- `write_shared_diary(title, content, tags, author)`
- `read_shared_diary(entry_id)`
- `list_shared_diary(date_from, date_to, limit)`
- `search_shared_diary(keyword)`

明确不存在的工具：任何含 `user` 字样的读写工具。`author` 字段用于公共区区分人写的还是 AI 写的。

## 六、阶段划分与产出文档

| 阶段 | 内容 | 产出文档 | 状态 |
|---|---|---|---|
| 0 | 仓库骨架、LICENSE、.gitignore、.env.example、README 草稿、本方案、进度锚点 | 本文档 + PROGRESS.md | ✅ 完成 |
| 1 | 架构与数据模型定稿：模块划分、API 签名、加密方案细节、目录结构 | docs/01-ARCHITECTURE.md | 待开始 |
| 2 | 存储层实现：DiaryStore、密钥管理、三库初始化、单元测试 | docs/02-STORAGE.md | 待开始 |
| 3 | MCP Server：8 个工具注册、stdio server、冒烟测试、MCP 配置示例 | docs/03-MCP-SERVER.md | 待开始 |
| 4 | 用户端 CLI：写/读/列表/搜索 user 与 shared 区 | docs/04-CLI.md | 待开始 |
| 5 | 隔离加固与集成测试：权限矩阵逐格验证、渗透式测试 | docs/05-SECURITY.md | 待开始 |
| 6 | Docker、.env 文档、.mcpb（可选）、README 完善 | docs/06-PACKAGING.md | 待开始 |
| 7 | 开源前检查：泄密扫描（真实日记/密钥/密码）、发布 GitHub | docs/07-RELEASE.md | 待开始 |

## 七、跨会话接续协议

1. 新窗口第一件事：读 `docs/PROGRESS.md`。
2. `PROGRESS.md` 记录：当前阶段、已完成决策、下一步入口文档。
3. 阶段进行中的半成品代码，在 `PROGRESS.md` 里标注"进行中"和已知问题。
4. 禁止跳阶段。禁止在未更新 PROGRESS.md 的情况下结束一个阶段。

## 八、安全红线（全程有效）

- 不生成、不提交任何真实日记内容、真实密钥、真实密码。
- `data/`、`.env`、`*.key` 永远在 .gitignore 里。
- README 必须诚实说明本地架构的隐私边界（AI 私密区文件存在性无法对技术用户隐藏）。
