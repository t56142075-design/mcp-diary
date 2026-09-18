# 01 架构与数据模型定稿

阶段 1 产出。本文档冻结模块划分、API 签名、加密细节。阶段 2 起按此实现，如需变更先改本文档再改代码，并同步更新 PROGRESS.md。

## 一、模块划分

```
mcp-diary/
├── src/mcp_diary/
│   ├── __init__.py
│   ├── zones.py        # Zone 枚举与权限矩阵常量（唯一事实源）
│   ├── models.py       # Entry 数据类
│   ├── crypto.py       # 密钥派生、AES-256-GCM 加解密、密钥文件管理
│   ├── storage.py      # DiaryStore（单区域单实例）+ open_store 工厂
│   ├── server.py       # FastMCP Server，仅注册 ai/shared 共 8 个工具
│   └── cli.py          # 用户端 CLI，仅操作 user_private/shared
├── tests/
│   ├── test_crypto.py       # 加解密、口令派生、错误口令必须失败
│   ├── test_storage.py      # CRUD、软删除、搜索
│   ├── test_isolation.py    # 权限矩阵逐格验证（核心）
│   └── test_server_tools.py # MCP 工具列表静态断言
├── pyproject.toml
└── ...
```

依赖：`mcp`（官方 SDK）、`cryptography`、`pytest`。CLI 用标准库 argparse，不引第三方框架。

## 二、zones.py（权限矩阵唯一事实源）

```python
from enum import StrEnum

class Zone(StrEnum):
    USER_PRIVATE = "user_private"
    AI_PRIVATE = "ai_private"
    SHARED = "shared"

# 谁允许打开哪个区。server.py 与 cli.py 各自对这张表做静态检查。
PRINCIPAL_ALLOWED_ZONES: dict[str, frozenset[Zone]] = {
    "user":  frozenset({Zone.USER_PRIVATE, Zone.SHARED}),
    "ai":    frozenset({Zone.AI_PRIVATE, Zone.SHARED}),
}

DB_FILENAMES: dict[Zone, str] = {
    Zone.USER_PRIVATE: "user_private.db",
    Zone.AI_PRIVATE:   "ai_private.db",
    Zone.SHARED:       "shared.db",
}
```

## 三、models.py

```python
@dataclass
class Entry:
    id: str                  # uuid4 hex
    title: str
    body: str                # 进程内始终是明文；落盘时由 store 决定是否加密
    tags: list[str]
    created_at: datetime     # UTC，ISO 8601 落盘
    updated_at: datetime
    deleted_at: datetime | None = None
```

## 四、crypto.py API

```python
class WrongPassphraseError(Exception): ...

def new_salt() -> bytes:
    """16 字节随机盐，非机密，明文存于库的 meta 表。"""

def derive_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    """scrypt(N=2**15, r=8, p=1, dklen=32)。用户口令 → AES-256 密钥。"""

def load_or_create_server_key(key_file: Path) -> bytes:
    """AI 区密钥：文件存在则读取；不存在则生成 32 随机字节写入（权限 0600）。"""

def encrypt(key: bytes, plaintext: str) -> bytes:
    """AES-256-GCM。输出 = nonce(12B) || ciphertext || tag(16B)。"""

def decrypt(key: bytes, blob: bytes) -> str:
    """解密并校验 GCM tag，失败抛 WrongPassphraseError（口令错或文件被篡改统一报此错，不泄露具体原因）。"""
```

### 密钥生命周期

| 密钥 | 来源 | 存储 | 持有者 |
|---|---|---|---|
| 用户区密钥 | 用户口令 scrypt 派生 | 口令不落盘，salt 存 user_private.db 的 meta 表 | 仅 CLI 进程内存 |
| AI 区密钥 | 首次启动随机生成 | `data/keys/ai_private.key`（0600，gitignored） | 仅 MCP Server 进程 |
| 公共区 | 无密钥 | 明文 | 双方 |

### 加密区搜索的实现取舍

密文无法 SQL LIKE。私密区搜索采用"全量解密进内存后过滤"。日记规模（千条级）下开销可忽略。公共区直接 SQL LIKE。此决策记入文档，不为搜索引入可搜索加密等复杂方案。

## 五、storage.py API

```python
class DiaryStore:
    """单区域单实例。一个实例只认识一个库文件，没有任何跨区能力。"""

    def __init__(self, db_path: Path, zone: Zone, key: bytes | None): ...

    # CRUD
    def add(self, title: str, body: str, tags: list[str] | None = None) -> Entry
    def get(self, entry_id: str) -> Entry | None
    def update(self, entry_id: str, *, title=None, body=None, tags=None) -> Entry | None
    def delete(self, entry_id: str) -> bool      # 软删除：写 deleted_at

    # 查询
    def list(self, *, date_from: datetime | None = None,
             date_to: datetime | None = None, limit: int = 50,
             include_deleted: bool = False) -> list[Entry]
    def search(self, keyword: str, *, limit: int = 20) -> list[Entry]

def open_store(zone: Zone, data_dir: Path, *,
               user_passphrase: str | None = None,
               ai_key_file: Path | None = None) -> DiaryStore:
    """工厂函数，按 zone 组装 db 路径与密钥。
    - USER_PRIVATE 必须给 user_passphrase，否则 ValueError
    - AI_PRIVATE 必须给 ai_key_file，否则 ValueError
    - SHARED 不需要任何密钥
    """
```

表结构（三个库相同）：

```sql
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v BLOB);  -- 仅用户库存 salt
CREATE TABLE IF NOT EXISTS entries (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    body        BLOB NOT NULL,          -- 私密区=密文 BLOB，公共区=明文 TEXT
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
```

私密区 title 也参与加密：加密字段为 title 和 body 序列化后的整体（`encrypt(json.dumps({"t": title, "b": body}))`），表内 title 列存占位符。这样标题同样不泄露。公共区 title 正常存储可被 LIKE 搜索。

## 六、server.py（MCP，阶段 3 实现）

FastMCP（stdio）。启动时仅执行：

```python
ai_store   = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=key_file)
shared_store = open_store(Zone.SHARED, data_dir)
```

注册 8 个工具（签名见 00-PLAN.md 第五节）。公共区写入带 `author: str = "ai"` 参数。不 import、不构造任何 USER_PRIVATE 相关对象。

## 七、cli.py（阶段 4 实现）

```
diary write  [--title T] [-t tag...]        # 正文从 stdin 读；写入用户私密区
diary read   <id> / diary list / diary search <kw> / diary edit <id> / diary delete <id>
diary shared write|read|list|search         # 公共区，author 固定 "user"
diary --data-dir PATH ...                   # 或 DIARY_DATA_DIR 环境变量
```

口令来源优先级：`DIARY_USER_PASSPHRASE` 环境变量 > 交互式输入（getpass）。私密区首次访问时生成 salt 并存 meta 表。

## 八、阶段 5 隔离测试设计（提前冻结验收标准）

1. `test_server_tools.py`：列出 server 注册的全部工具名，断言不含 "user" 子串；断言数量恰为 8。
2. `test_isolation.py`：
   - 用 MCP 客户端在测试态调用每个工具，任何参数组合都不得读出预写入用户私密区的内容。
   - CLI 侧对 AI 私密区无任何入口：断言 cli 模块不引用 `AI_PRIVATE` 与 `load_or_create_server_key`。
   - 错误口令打开用户库必须抛 WrongPassphraseError 且内容不可读。
3. 静态扫描测试：grep `server.py` 源码，断言不出现 `USER_PRIVATE`、`user_private.db`、`user_passphrase` 字样。

## 九、pyproject.toml 要点

- 包名 `mcp-diary`，模块 `mcp_diary`
- 入口：`diary = mcp_diary.cli:main`、`mcp-diary-server = mcp_diary.server:main`
- requires-python >= 3.11（StrEnum 需要）
- 依赖：mcp>=1.0、cryptography>=42
