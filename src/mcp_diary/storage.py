"""DiaryStore：单区域单实例的存储层。

设计红线（docs/01-ARCHITECTURE.md）：
- 一个 store 实例只认识一个库文件，没有任何跨区能力；
- 不提供 read_any_zone 之类的跨区接口；
- 加密区 title 与 body 整体加密，表内 title 列存占位符，标题同样不泄露；
- 加密区搜索 = 全量解密进内存后过滤（日记千条级规模开销可忽略）；
- 公共区明文，SQL LIKE 搜索。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from .crypto import (
    decrypt,
    derive_key_from_passphrase,
    encrypt,
    load_or_create_server_key,
    new_salt,
)
from .models import Entry, from_iso, to_iso, utc_now
from .zones import DB_FILENAMES, Zone

_TITLE_PLACEHOLDER = "[encrypted]"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v BLOB
);
CREATE TABLE IF NOT EXISTS entries (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    body        BLOB NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
"""


class DiaryStore:
    """单区域单实例。zone 决定是否加密，key 为 None 表示公共区明文。"""

    def __init__(self, db_path: Path, zone: Zone, key: bytes | None):
        if zone is Zone.USER_PRIVATE or zone is Zone.AI_PRIVATE:
            if key is None:
                raise ValueError(f"zone {zone} requires an encryption key")
        self.zone = zone
        self._key = key
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---------- 内部：加密序列化 ----------

    def _seal(self, entry: Entry) -> tuple:
        """私密区整体加密 title+body；公共区存明文。返回行元组。"""
        if self._key is not None:
            payload = json.dumps(
                {"t": entry.title, "b": entry.body}, ensure_ascii=False
            )
            blob = encrypt(self._key, payload)
            return entry.to_row(body_blob=blob, title_placeholder=_TITLE_PLACEHOLDER)
        return entry.to_row(body_blob=entry.body)

    def _unseal(self, row: sqlite3.Row) -> Entry:
        id_, title, body_blob, tags_json, created, updated, deleted = row
        deleted_at = from_iso(deleted) if deleted else None
        if self._key is not None:
            payload = decrypt(self._key, bytes(body_blob))
            obj = json.loads(payload)
            title, body = obj["t"], obj["b"]
        else:
            title, body = title, body_blob if isinstance(body_blob, str) else bytes(body_blob).decode("utf-8")
        return Entry(
            id=id_,
            title=title,
            body=body,
            tags=json.loads(tags_json),
            created_at=from_iso(created),
            updated_at=from_iso(updated),
            deleted_at=deleted_at,
        )

    # ---------- CRUD ----------

    def add(self, title: str, body: str, tags: list[str] | None = None) -> Entry:
        entry = Entry(
            id=uuid.uuid4().hex,
            title=title,
            body=body,
            tags=list(tags or []),
        )
        with self._conn:
            self._conn.execute(
                "INSERT INTO entries VALUES (?,?,?,?,?,?,?)", self._seal(entry)
            )
        return entry

    def get(self, entry_id: str) -> Entry | None:
        cur = self._conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        )
        row = cur.fetchone()
        return self._unseal(row) if row else None

    def update(
        self,
        entry_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
    ) -> Entry | None:
        existing = self.get(entry_id)
        if existing is None:
            return None
        if title is not None:
            existing.title = title
        if body is not None:
            existing.body = body
        if tags is not None:
            existing.tags = list(tags)
        existing.updated_at = utc_now()
        title_cell, body_cell, tags_cell = self._seal(existing)[1:4]
        with self._conn:
            self._conn.execute(
                "UPDATE entries SET title=?, body=?, tags=?, updated_at=? WHERE id=?",
                (title_cell, body_cell, tags_cell, to_iso(existing.updated_at), entry_id),
            )
        return existing

    def delete(self, entry_id: str) -> bool:
        """软删除：写 deleted_at。"""
        with self._conn:
            cur = self._conn.execute(
                "UPDATE entries SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                (to_iso(utc_now()), entry_id),
            )
        return cur.rowcount > 0

    # ---------- 查询 ----------

    def list(
        self,
        *,
        date_from=None,
        date_to=None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> list[Entry]:
        sql = "SELECT * FROM entries"
        conds, params = [], []
        if not include_deleted:
            conds.append("deleted_at IS NULL")
        if date_from is not None:
            conds.append("created_at >= ?")
            params.append(to_iso(date_from))
        if date_to is not None:
            conds.append("created_at <= ?")
            params.append(to_iso(date_to))
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._unseal(r) for r in rows]

    def search(self, keyword: str, *, limit: int = 20) -> list[Entry]:
        """加密区：解密进内存后过滤。公共区：SQL LIKE。均只搜未删除条目。"""
        kw = keyword.strip().lower()
        if not kw:
            return []
        if self._key is None:
            rows = self._conn.execute(
                "SELECT * FROM entries WHERE deleted_at IS NULL "
                "AND (LOWER(title) LIKE ? OR LOWER(CAST(body AS TEXT)) LIKE ?) "
                "ORDER BY created_at DESC LIMIT ?",
                (f"%{kw}%", f"%{kw}%", limit),
            ).fetchall()
            return [self._unseal(r) for r in rows]
        results = []
        for entry in self.list(limit=10_000):
            if kw in entry.title.lower() or kw in entry.body.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def count(self, *, include_deleted: bool = True) -> int:
        sql = "SELECT COUNT(*) FROM entries"
        if not include_deleted:
            sql += " WHERE deleted_at IS NULL"
        return self._conn.execute(sql).fetchone()[0]

    def close(self) -> None:
        self._conn.close()


def open_store(
    zone: Zone,
    data_dir: Path,
    *,
    user_passphrase: str | None = None,
    ai_key_file: Path | None = None,
) -> DiaryStore:
    """工厂函数：按 zone 组装 db 路径与密钥。

    - USER_PRIVATE 必须给 user_passphrase，否则 ValueError；
      首次访问生成 salt 并存 meta 表，之后从 meta 表读 salt 校验。
    - AI_PRIVATE 必须给 ai_key_file，密钥由 load_or_create_server_key 管理。
    - SHARED 不需要任何密钥。
    """
    data_dir = Path(data_dir)
    db_path = data_dir / DB_FILENAMES[zone]

    if zone is Zone.USER_PRIVATE:
        if not user_passphrase:
            raise ValueError("user_passphrase is required for USER_PRIVATE zone")
        store = _open_with_user_passphrase(db_path, user_passphrase)
        return store
    if zone is Zone.AI_PRIVATE:
        if ai_key_file is None:
            raise ValueError("ai_key_file is required for AI_PRIVATE zone")
        key = load_or_create_server_key(ai_key_file)
        return DiaryStore(db_path, zone, key)
    # SHARED
    return DiaryStore(db_path, zone, None)


def _open_with_user_passphrase(db_path: Path, passphrase: str) -> DiaryStore:
    """用户区打开逻辑：salt 存 meta 表，k='salt'。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # 先以无密钥连接检查/初始化 schema 与 salt
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    row = conn.execute("SELECT v FROM meta WHERE k='salt'").fetchone()
    if row is None:
        salt = new_salt()
        conn.execute("INSERT INTO meta VALUES ('salt', ?)", (salt,))
        conn.commit()
    else:
        salt = bytes(row[0])
    conn.close()
    key = derive_key_from_passphrase(passphrase, salt)
    return DiaryStore(db_path, Zone.USER_PRIVATE, key)
