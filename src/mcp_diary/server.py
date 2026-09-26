"""MCP Server：AI 侧入口。只暴露 AI 私密区与公共区，共 8 个工具。

隐私红线（docs/01-ARCHITECTURE.md 第六节）：
- 本文件不 import、不构造任何用户私密区对象；
- Zone.AI_PRIVATE 与 Zone.SHARED 之外的任何区域在此进程中不存在；
- assert_zone_allowed 作为启动期双重保险。

两种运行模式：
1. stdio（默认）：由本地 MCP 客户端（WorkBuddy / Claude Desktop 等）拉起。
2. streamable HTTP（设置 DIARY_HTTP_TOKEN 时）：供远程 MCP 客户端
   （如 ChatGPT 开发者模式自定义连接器）经公网隧道访问，全部请求
   必须携带 Authorization: Bearer <DIARY_HTTP_TOKEN>，否则 401。

环境变量：
- DIARY_DATA_DIR    数据目录，默认 ./data
- DIARY_AI_KEY_FILE AI 区密钥文件，默认 <data_dir>/keys/ai_private.key
- DIARY_HTTP_TOKEN  Bearer 令牌；设置后启用 HTTP 模式（存 .env，勿提交）
- DIARY_HTTP_HOST   HTTP 监听地址，默认 127.0.0.1（只暴露给隧道进程）
- DIARY_HTTP_PORT   HTTP 监听端口，默认 8080
- DIARY_ALLOWED_HOSTS 逗号分隔的 Host 白名单（隧道域名），未设置时关闭
  Host 校验（已有 Bearer 令牌鉴权兜底）
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


class _BearerAuthMiddleware:
    """ASGI 中间件：校验 Authorization: Bearer <token>，不匹配返回 401。

    用于 HTTP 模式。令牌错与缺失返回同一个 401，不泄露原因。
    """

    def __init__(self, app, token: str):
        self._app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            if headers.get(b"authorization") != self._expected:
                await self._send_unauthorized(send)
                return
        await self._app(scope, receive, send)

    @staticmethod
    async def _send_unauthorized(send) -> None:
        body = b"unauthorized"
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"text/plain"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


def _run_http(token: str) -> None:
    """streamable HTTP 模式：本机监听，等隧道转发，带令牌鉴权。"""
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    mcp.settings.host = os.environ.get("DIARY_HTTP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.environ.get("DIARY_HTTP_PORT", "8080"))
    mcp.settings.stateless_http = True

    # FastMCP 绑定 127.0.0.1 时默认启用 DNS 重绑定防护，Host 白名单只有
    # localhost，隧道域名（*.trycloudflare.com 等）会被拒 421。
    # DIARY_ALLOWED_HOSTS 可显式指定白名单；未指定时关闭 Host 校验
    # （本模式已有 Bearer 令牌鉴权，Host 校验属于冗余层）。
    allowed = os.environ.get("DIARY_ALLOWED_HOSTS", "").strip()
    if allowed:
        hosts = [h.strip() for h in allowed.split(",") if h.strip()]
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[f"https://{h}" for h in hosts],
        )
    else:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )

    app = _BearerAuthMiddleware(mcp.streamable_http_app(), token)
    uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port, log_level="info")


def main() -> None:
    """MCP 客户端入口：默认 stdio；设置 DIARY_HTTP_TOKEN 时走 HTTP。"""
    token = os.environ.get("DIARY_HTTP_TOKEN")
    if token:
        _run_http(token)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
