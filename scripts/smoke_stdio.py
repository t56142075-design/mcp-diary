"""端到端 stdio 冒烟测试脚本。

用 MCP 客户端库以 stdio 拉起 server 子进程，走完整协议：
initialize → tools/list → tools/call（写公共区 + 读回）。
这是 Claude Desktop 等 MCP 客户端接入的同款路径。

用法：
  DIARY_DATA_DIR=<临时目录> DIARY_AI_KEY_FILE=<临时key> python scripts/smoke_stdio.py
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mcp-diary-smoke-"))
    data_dir = tmp / "data"
    data_dir.mkdir(parents=True)
    key_file = tmp / "keys" / "ai.key"

    src_dir = Path(__file__).parent.parent / "src"
    env = {
        **os.environ,
        "DIARY_DATA_DIR": str(data_dir),
        "DIARY_AI_KEY_FILE": str(key_file),
        "PYTHONPATH": str(src_dir) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_diary.server"],  # 必须以模块方式启动，文件直跑会让相对导入失败
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("[ok] initialize:", init.serverInfo.name)

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"[ok] tools/list: {len(names)} tools")
            for n in names:
                print("     -", n)

            assert len(names) == 8, f"expected 8 tools, got {len(names)}"
            assert all("user" not in n for n in names)

            result = await session.call_tool(
                "write_shared_diary",
                {"title": "冒烟测试", "content": "stdio 端到端写入", "author": "ai"},
            )
            payload = json.loads(result.content[0].text)
            print("[ok] tools/call write_shared_diary:", payload["id"])

            result = await session.call_tool(
                "read_shared_diary", {"entry_id": payload["id"]}
            )
            entry = json.loads(result.content[0].text)
            assert entry["title"] == "冒烟测试"
            assert entry["author"] == "ai"
            print("[ok] tools/call read_shared_diary roundtrip")

            result = await session.call_tool(
                "write_ai_private_diary",
                {"title": "AI私密冒烟", "content": "私密内容 smoke"},
            )
            ai_id = json.loads(result.content[0].text)["id"]
            result = await session.call_tool(
                "read_ai_private_diary", {"entry_id": ai_id}
            )
            entry = json.loads(result.content[0].text)
            assert entry["content"] == "私密内容 smoke"
            print("[ok] ai_private roundtrip")

    # 验证库文件与密钥落盘
    assert (data_dir / "shared.db").exists()
    assert (data_dir / "ai_private.db").exists()
    assert not (data_dir / "user_private.db").exists(), (
        "MCP server 绝不能创建用户区数据库"
    )
    print("[ok] 三个库检查：server 只创建了 ai_private.db 与 shared.db")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nSMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
