# 03 MCP Server（阶段 3 完成存档）

按 docs/01-ARCHITECTURE.md 第六节实现。本文档记录工具实现、隔离验证结果、运行方式与已知事项。

## 交付物

| 文件 | 内容 |
|---|---|
| `src/mcp_diary/server.py` | FastMCP（stdio），8 个工具，启动期 assert_zone_allowed 双重保险 |
| `tests/test_server_tools.py` | 8 个测试：工具列表断言、源码静态扫描、渗透测试 |
| `scripts/smoke_stdio.py` | 端到端 stdio 冒烟：真实子进程 + 完整 MCP 协议 |
| `pyproject.toml` | mcp 依赖固定为 `>=1.0,<2`；入口 `mcp-diary-server` |
| `README.md` | MCP 接入配置示例（Claude Desktop）与工具清单 |

models.py / storage.py 同步增加了 `author` 字段（公共区区分人写还是 AI 写），entries 表新增 author 列（DEFAULT 'user'，老库 CREATE IF NOT EXISTS 不迁移，0.1.0 阶段无历史数据包袱）。

## 隔离验证结果（34 passed 全绿）

1. **工具列表**：`test_exactly_eight_tools` 断言注册的工具名集合恰为 8 个预期名称；`test_no_user_tools` 断言任何工具名不含 "user"；`test_no_user_zone_in_tool_schemas` 连输入 schema 和描述文本也扫过。
2. **源码静态扫描**：`test_server_source_has_no_user_zone_references` 断言 server.py 中不出现 USER_PRIVATE / user_private.db / user_passphrase 三个字符串。
3. **渗透测试**：`test_pentest_user_content_never_leaks` 预先用 storage 层向用户私密区写入明文标记，然后调用全部 8 个工具 + 恶意探测（用用户明文当关键词搜索、猜 id、拉大 limit），断言输出中无任何用户明文。
4. **stdio 冒烟**：真实子进程走 initialize → tools/list → tools/call，公共区与 AI 区读写往返成功，且断言 server 从不创建 user_private.db。

## 关键实现决策

1. **mcp SDK 版本锁 `>=1.0,<2`**：mcp 2.x 把 FastMCP 改名 MCPServer 且 API 有变。1.x 是各 MCP 客户端文档的通行标准，生态验证最充分。若未来迁移 2.x，按官方迁移指南改 import 即可（https://py.sdk.modelcontextprotocol.io/v2/migration/）。
2. **server 启动方式必须是 `python -m mcp_diary.server` 或安装后的 `mcp-diary-server` 入口**，直接以文件路径跑会让包内相对导入失败、子进程静默崩溃。冒烟脚本踩过此坑，已注释说明。
3. **author 默认值**：server 侧默认 "ai"，storage 层默认 "user"，两边各自的默认值即各自主体。
4. date_from/date_to 工具参数直接收 ISO 8601 字符串，storage.list() 同时兼容字符串与 datetime。
5. 工具返回值统一 JSON 字符串（UTF-8 不转义），错误也走 JSON（如 entry not found），MCP 层不抛异常以免让客户端收到难处理的 stack trace。

## 运行方式（本机备忘）

```bash
PY="C:/Users/26627/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd "E:/work space/mcp-diary"

# 全部测试（34 个）
"$PY" -m pytest tests/ -q --basetemp="$TEMP/mcp-diary-pytest-$$RANDOM"

# stdio 端到端冒烟
"$PY" scripts/smoke_stdio.py
```

注意：--basetemp 每次要用全新路径；复用旧目录时 pytest 启动清理会被系统安全删除保护拦截。

## 已知事项

1. 阶段 3 只做了进程内调用与 stdio 冒烟，WorkBuddy / Claude Desktop 实机接入留到阶段 6 打包后验证。
2. `list_tools` 的 description 与 schema 由 FastMCP 从函数签名自动生成，pydantic 校验保证参数类型。
3. server 进程持有 AI 区密钥与 shared 库句柄，进程崩溃不丢数据（每操作即时 commit），但 WAL 文件在进程运行时存在（.gitignore 已覆盖 *-wal/*-shm）。

## 下一步：阶段 4

用户端 CLI（cli.py）：写/读/列表/搜索用户私密区与公共区，口令优先级 DIARY_USER_PASSPHRASE > getpass 交互。红线对称：cli.py 中不引用 AI_PRIVATE 与 load_or_create_server_key。
