"""MCP Server 隔离测试：阶段 5 验收标准的前置冻结（docs/01-ARCHITECTURE.md 第八节）。

三道断言：
1. 工具列表：恰 8 个，名称不含 'user'；
2. 源码静态扫描：server.py 中不出现 USER_PRIVATE / user_private.db / user_passphrase；
3. 渗透测试：预写一条用户私密日记，通过 MCP 客户端调用全部工具，
   任何参数组合的输出中都不含用户区明文。
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

SERVER_SRC = Path(__file__).parent.parent / "src" / "mcp_diary" / "server.py"

USER_SECRET_TITLE = "用户绝密标题PENTEST"
USER_SECRET_BODY = "用户绝密正文PENTESTBODY"

EXPECTED_TOOLS = {
    "write_ai_private_diary",
    "read_ai_private_diary",
    "list_ai_private_diary",
    "search_ai_private_diary",
    "write_shared_diary",
    "read_shared_diary",
    "list_shared_diary",
    "search_shared_diary",
}


@pytest.fixture
def server_module(tmp_path, monkeypatch):
    """在隔离数据目录中导入 server 模块（其 import 时打开存储句柄）。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DIARY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DIARY_AI_KEY_FILE", str(tmp_path / "keys" / "ai.key"))

    # 先直接向用户私密区写入渗透标记（不经 server，走 storage 层）
    from mcp_diary.storage import open_store
    from mcp_diary.zones import Zone

    user_store = open_store(Zone.USER_PRIVATE, data_dir, user_passphrase="pentest-pass")
    user_store.add(USER_SECRET_TITLE, USER_SECRET_BODY)
    user_store.close()

    # 导入 server（只跑一次；pytest 同进程缓存由 importlib 处理）
    sys.modules.pop("mcp_diary.server", None)
    import mcp_diary.server as srv

    yield srv
    srv.ai_store.close()
    srv.shared_store.close()
    sys.modules.pop("mcp_diary.server", None)


def _list_tools(srv):
    return asyncio.run(srv.mcp.list_tools())


def _call(srv, name, args):
    result = asyncio.run(srv.mcp.call_tool(name, args))
    # FastMCP 1.x call_tool 返回 ([TextContent...], {...}) 元组
    parts = []
    content = result[0] if isinstance(result, tuple) else result
    if isinstance(content, list):
        for item in content:
            parts.append(item.text if hasattr(item, "text") else str(item))
    else:
        parts.append(str(content))
    return "\n".join(parts)


# ---------- 1. 工具列表断言 ----------

def test_exactly_eight_tools(server_module):
    tools = _list_tools(server_module)
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS


def test_no_user_tools(server_module):
    tools = _list_tools(server_module)
    for t in tools:
        assert "user" not in t.name.lower(), f"illegal tool name: {t.name}"


def test_no_user_zone_in_tool_schemas(server_module):
    """工具的输入 schema 中也不得出现任何 user 区痕迹。"""
    for t in _list_tools(server_module):
        blob = json.dumps(t.inputSchema) + (t.description or "")
        assert "user_private" not in blob.lower()
        assert "user passphrase" not in blob.lower()


# ---------- 2. 源码静态扫描 ----------

def test_server_source_has_no_user_zone_references():
    src = SERVER_SRC.read_text(encoding="utf-8")
    for banned in ("USER_PRIVATE", "user_private.db", "user_passphrase"):
        assert banned not in src, f"server.py must not reference {banned}"


def test_server_source_zone_imports_are_limited():
    src = SERVER_SRC.read_text(encoding="utf-8")
    assert "Zone.AI_PRIVATE" in src
    assert "Zone.SHARED" in src


# ---------- 3. 渗透测试：用户区内容不可达 ----------

def test_pentest_user_content_never_leaks(server_module):
    srv = server_module

    outputs = []

    # 正常调用全部 8 个工具
    outputs.append(_call(srv, "write_ai_private_diary",
                         {"title": "AI日记", "content": "AI内容 pentest", "tags": ["t"]}))
    ai_id = json.loads(outputs[-1])["id"]
    outputs.append(_call(srv, "read_ai_private_diary", {"entry_id": ai_id}))
    outputs.append(_call(srv, "list_ai_private_diary", {}))
    outputs.append(_call(srv, "search_ai_private_diary", {"keyword": "pentest"}))

    outputs.append(_call(srv, "write_shared_diary",
                         {"title": "公共日记", "content": "公共内容", "author": "ai"}))
    shared_id = json.loads(outputs[-1])["id"]
    outputs.append(_call(srv, "read_shared_diary", {"entry_id": shared_id}))
    outputs.append(_call(srv, "list_shared_diary", {}))
    outputs.append(_call(srv, "search_shared_diary", {"keyword": "公共"}))

    # 恶意探测：用用户区内容做关键词去搜公共区和 AI 区
    outputs.append(_call(srv, "search_shared_diary", {"keyword": USER_SECRET_TITLE}))
    outputs.append(_call(srv, "search_shared_diary", {"keyword": USER_SECRET_BODY}))
    outputs.append(_call(srv, "search_ai_private_diary", {"keyword": USER_SECRET_BODY}))
    outputs.append(_call(srv, "list_shared_diary", {"limit": 1000}))
    outputs.append(_call(srv, "list_ai_private_diary", {"limit": 1000}))
    # 不存在的 id（模拟猜测用户条目 id）
    outputs.append(_call(srv, "read_shared_diary", {"entry_id": "00000000000000000000000000000000"}))

    combined = "\n".join(outputs)
    assert USER_SECRET_TITLE not in combined
    assert USER_SECRET_BODY not in combined
    assert "PENTEST" not in combined


def test_shared_diary_roundtrip_with_author(server_module):
    srv = server_module
    out = _call(srv, "write_shared_diary",
                {"title": "标题", "content": "内容", "author": "ai", "tags": ["x"]})
    entry_id = json.loads(out)["id"]
    read = json.loads(_call(srv, "read_shared_diary", {"entry_id": entry_id}))
    assert read["title"] == "标题"
    assert read["author"] == "ai"
    assert read["tags"] == ["x"]


def test_ai_private_diary_roundtrip(server_module):
    srv = server_module
    out = _call(srv, "write_ai_private_diary",
                {"title": "思考", "content": "关于架构的私密思考"})
    entry_id = json.loads(out)["id"]
    read = json.loads(_call(srv, "read_ai_private_diary", {"entry_id": entry_id}))
    assert read["content"] == "关于架构的私密思考"
    hits = json.loads(_call(srv, "search_ai_private_diary", {"keyword": "架构"}))
    assert len(hits) == 1
