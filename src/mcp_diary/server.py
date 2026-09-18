"""MCP Server：AI 侧入口。只暴露 AI 私密区与公共区，共 8 个工具。

隐私红线（docs/01-ARCHITECTURE.md 第六节）：
- 本文件不 import、不构造任何用户私密区对象；
- Zone.AI_PRIVATE 与 Zone.SHARED 之外的任何区域在此进程中不存在；
- assert_zone_allowed 作为启动期双重保险。

运行：stdio 传输，由 MCP 客户端（Claude Desktop 等）拉起。
环境变量：
- DIARY_DATA_DIR   数据目录，默认 ./data
- DIARY_AI_KEY_FILE AI 区密钥文件，默认 <data_dir>/keys/ai_private.key
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .models import Entry, to_iso
from .storage import DiaryStore, open_store
from .zones import Zone, assert_zone_allowed

mcp = FastMCP("mcp-diary")

_DATA_DIR = Path(os.environ.get("DIARY_DATA_DIR", "data"))
_AI_KEY_FILE = Path(
    os.environ.get("DIARY_AI_KEY_FILE", _DATA_DIR / "keys" / "ai_private.key")
)

# 启动期双重保险：AI 主体只允许这两个区，越界立即崩溃。
assert_zone_allowed("ai", Zone.AI_PRIVATE)
assert_zone_allowed("ai", Zone.SHARED)

# 本进程只持有这两个存储句柄。
ai_store: DiaryStore = open_store(Zone.AI_PRIVATE, _DATA_DIR, ai_key_file=_AI_KEY_FILE)
shared_store: DiaryStore = open_store(Zone.SHARED, _DATA_DIR)


def _entry_dict(e: Entry) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "content": e.body,
        "tags": e.tags,
        "author": e.author,
        "created_at": to_iso(e.created_at),
        "updated_at": to_iso(e.updated_at),
        "deleted": e.is_deleted(),
    }


def _iso_or_none(dt: str | None):
    return dt if dt else None


# ================= AI 私密区（仅 AI 可访问） =================


@mcp.tool()
def write_ai_private_diary(title: str, content: str, tags: list[str] | None = None) -> str:
    """写入一条 AI 私密日记。返回新条目的 id 与时间。"""
    e = ai_store.add(title, content, tags)
    return json.dumps({"id": e.id, "created_at": to_iso(e.created_at)}, ensure_ascii=False)


@mcp.tool()
def read_ai_private_diary(entry_id: str) -> str:
    """读取一条 AI 私密日记。"""
    e = ai_store.get(entry_id)
    if e is None:
        return json.dumps({"error": "entry not found"})
    return json.dumps(_entry_dict(e), ensure_ascii=False)


@mcp.tool()
def list_ai_private_diary(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> str:
    """按时间列出 AI 私密日记，新在前。date_from/date_to 为 ISO 8601，可省略。"""
    entries = ai_store.list(
        date_from=_iso_or_none(date_from),
        date_to=_iso_or_none(date_to),
        limit=limit,
    )
    return json.dumps([_entry_dict(e) for e in entries], ensure_ascii=False)


@mcp.tool()
def search_ai_private_diary(keyword: str, limit: int = 20) -> str:
    """按关键词搜索 AI 私密日记（标题与正文）。"""
    hits = ai_store.search(keyword, limit=limit)
    return json.dumps([_entry_dict(e) for e in hits], ensure_ascii=False)


# ================= 公共区（用户与 AI 共享） =================


@mcp.tool()
def write_shared_diary(
    title: str,
    content: str,
    tags: list[str] | None = None,
    author: str = "ai",
) -> str:
    """写入一条公共日记。author 标记作者（默认 ai）。"""
    e = shared_store.add(title, content, tags, author=author)
    return json.dumps({"id": e.id, "created_at": to_iso(e.created_at)}, ensure_ascii=False)


@mcp.tool()
def read_shared_diary(entry_id: str) -> str:
    """读取一条公共日记。"""
    e = shared_store.get(entry_id)
    if e is None:
        return json.dumps({"error": "entry not found"})
    return json.dumps(_entry_dict(e), ensure_ascii=False)


@mcp.tool()
def list_shared_diary(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> str:
    """按时间列出公共日记，新在前。date_from/date_to 为 ISO 8601，可省略。"""
    entries = shared_store.list(
        date_from=_iso_or_none(date_from),
        date_to=_iso_or_none(date_to),
        limit=limit,
    )
    return json.dumps([_entry_dict(e) for e in entries], ensure_ascii=False)


@mcp.tool()
def search_shared_diary(keyword: str, limit: int = 20) -> str:
    """按关键词搜索公共日记（标题与正文）。"""
    hits = shared_store.search(keyword, limit=limit)
    return json.dumps([_entry_dict(e) for e in hits], ensure_ascii=False)


def main() -> None:
    """MCP 客户端入口：stdio 传输。"""
    mcp.run()


if __name__ == "__main__":
    main()
