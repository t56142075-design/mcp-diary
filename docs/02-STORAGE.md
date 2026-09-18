# 02 存储层实现（阶段 2 完成存档）

按 docs/01-ARCHITECTURE.md 实现并通过测试。本文档记录实现细节、与架构文档的差异、测试结果、已知限制。

## 交付物

| 文件 | 内容 |
|---|---|
| `src/mcp_diary/__init__.py` | 包声明，版本 0.1.0 |
| `src/mcp_diary/zones.py` | Zone 枚举、PRINCIPAL_ALLOWED_ZONES 权限矩阵、DB_FILENAMES、assert_zone_allowed 启动期检查 |
| `src/mcp_diary/models.py` | Entry 数据类、UTC 时间工具、to_row 序列化 |
| `src/mcp_diary/crypto.py` | scrypt 派生、AES-256-GCM 加解密、服务端密钥文件管理 |
| `src/mcp_diary/storage.py` | DiaryStore（单区域单实例）+ open_store 工厂 |
| `tests/test_crypto.py` | 10 个测试 |
| `tests/test_storage.py` | 16 个测试 |
| `pyproject.toml` | hatchling 构建，入口 diary / mcp-diary-server |

## 测试结果

26 passed，0 failed（pytest 9.1.1，Python 3.13.12）。

关键安全测试：
- `test_user_db_file_contains_no_plaintext`：直接读 user_private.db 二进制，断言标题正文明文不在文件中。
- `test_db_title_column_is_placeholder`：表内 title 列只存 `[encrypted]` 占位符。
- `test_wrong_passphrase_cannot_read`：错误口令调用 list() 必须抛 WrongPassphraseError。
- `test_ai_zone_search_after_reopen`：AI 区密钥从文件重读后数据仍可解密。
- `test_tampered_blob_raises`：篡改 GCM tag 必须失败。

## 与架构文档的实现差异

1. `wrong-pass` 打开用户库时，报错发生在首次 `list()`/`get()` 解密时，而非 open_store 时。原因：salt 存在 meta 表可正常读取，错误口令只有在解密时才暴露。行为符合"内容不可读"的安全目标。
2. `assert_zone_allowed` 已实现但 server/cli 尚未接线（阶段 3/4 接入，作为启动期双重保险）。
3. `DiaryStore.update()` 直接复用 `_seal()` 序列化，删除了架构稿中提到的独立辅助函数。

## 运行方式（本机备忘）

```bash
cd "E:/work space/mcp-diary"
PY="C:/Users/26627/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
PYTHONPATH="E:/work space/mcp-diary/src" "$PY" -m pytest tests/ -q --basetemp="E:/work space/mcp-diary/.pytest-tmp"
```

两个本机坑：
- pytest 默认临时目录 `C:\Users\26627\AppData\Local\Temp\pytest-of-26627` 权限拒绝（WinError 5），必须用 `--basetemp` 指到项目内。
- 尚未做 `pip install -e .`（避免提前拉入 mcp 依赖），测试靠 PYTHONPATH=src。

## 已知限制（阶段 5 处理或声明）

1. 加密区搜索是 O(n) 全量解密，万条以内可接受，README 已声明取舍。
2. SQLite 连接未加密、WAL 模式，库文件本身对有文件系统访问权的一方可见（这是本地架构的诚实边界，README 已写）。
3. `soft delete` 后的条目 `get()` 仍可见（带 deleted_at 标记），list 默认过滤。阶段 4 CLI 会把已删条目标记展示；永久删除（purge）未实现，可作后续可选功能。

## 下一步：阶段 3

实现 `server.py`（FastMCP + 8 个工具）+ `test_server_tools.py` 静态断言 + MCP 配置示例。需要先在 venv 安装 `mcp` 包。
