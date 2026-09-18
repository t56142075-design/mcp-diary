"""CLI 隔离测试：与 test_server_tools.py 对称（docs/01-ARCHITECTURE.md 第八节）。

三道断言：
1. 源码静态扫描：cli.py 中不出现 AI_PRIVATE / ai_private.db / load_or_create_server_key；
2. CLI 功能主流程：写读列搜编删全通；
3. 对称渗透：预写一条 AI 私密日记（走 storage 层），CLI 全命令输出中不含 AI 区明文。
"""

import json
from pathlib import Path

import pytest

from mcp_diary.cli import main

CLI_SRC = Path(__file__).parent.parent / "src" / "mcp_diary" / "cli.py"

AI_SECRET_TITLE = "AI绝密标题CLIPENTEST"
AI_SECRET_BODY = "AI绝密正文CLIPENTESTBODY"


# ---------- 1. 源码静态扫描 ----------

def test_cli_source_has_no_ai_zone_references():
    src = CLI_SRC.read_text(encoding="utf-8")
    for banned in (
        "AI_PRIVATE",
        "ai_private.db",
        "ai_private.key",
        "load_or_create_server_key",
    ):
        assert banned not in src, f"cli.py must not reference {banned}"


def test_cli_zone_imports_are_limited():
    src = CLI_SRC.read_text(encoding="utf-8")
    assert "Zone.USER_PRIVATE" in src
    assert "Zone.SHARED" in src


# ---------- fixtures ----------

@pytest.fixture
def env(tmp_path, monkeypatch):
    """隔离环境：数据目录 + 固定口令。预写一条 AI 私密日记做渗透标记。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DIARY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DIARY_USER_PASSPHRASE", "cli-test-pass")

    from mcp_diary.storage import open_store
    from mcp_diary.zones import Zone

    ai_store = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "keys/ai.key")
    ai_store.add(AI_SECRET_TITLE, AI_SECRET_BODY)
    ai_store.close()
    return data_dir


def run_cli(monkeypatch, capsys, *argv) -> int:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("正文内容 via test\n"))
    code = main(list(argv))
    return code


def outs(capsys) -> str:
    return capsys.readouterr().out


# ---------- 2. 功能主流程 ----------

def test_write_read_roundtrip(env, monkeypatch, capsys):
    code = run_cli(monkeypatch, capsys, "write", "--title", "测试标题", "-t", "a,b")
    assert code == 0
    assert "已写入" in outs(capsys)

    code = run_cli(monkeypatch, capsys, "list")
    assert code == 0
    out = outs(capsys)
    assert "测试标题" in out
    entry_id = out.split("[")[1].split("]")[0]

    code = run_cli(monkeypatch, capsys, "read", entry_id)
    assert code == 0
    assert "正文内容 via test" in outs(capsys)


def test_search(env, monkeypatch, capsys):
    run_cli(monkeypatch, capsys, "write", "--title", "工作日志", "-t", "work")
    code = run_cli(monkeypatch, capsys, "search", "工作")
    assert code == 0
    assert "工作日志" in outs(capsys)


def test_edit_with_args(env, monkeypatch, capsys):
    run_cli(monkeypatch, capsys, "write", "--title", "旧标题")
    out = outs(capsys)  # 吞掉 write 输出
    run_cli(monkeypatch, capsys, "list")
    entry_id = outs(capsys).split("[")[1].split("]")[0]

    code = run_cli(monkeypatch, capsys, "edit", entry_id, "--title", "新标题")
    assert code == 0
    assert "已更新" in outs(capsys)

    run_cli(monkeypatch, capsys, "read", entry_id)
    assert "新标题" in outs(capsys)


def test_delete_and_list_all(env, monkeypatch, capsys):
    run_cli(monkeypatch, capsys, "write", "--title", "待删除")
    outs(capsys)
    run_cli(monkeypatch, capsys, "list")
    entry_id = outs(capsys).split("[")[1].split("]")[0]

    code = run_cli(monkeypatch, capsys, "delete", entry_id)
    assert code == 0

    run_cli(monkeypatch, capsys, "list")
    assert "待删除" not in outs(capsys)
    run_cli(monkeypatch, capsys, "list", "--all")
    out_all = outs(capsys)
    assert "待删除" in out_all and "已删除" in out_all


def test_shared_commands(env, monkeypatch, capsys):
    code = run_cli(monkeypatch, capsys, "shared", "write", "--title", "公共测试", "-t", "pub")
    assert code == 0
    outs(capsys)

    code = run_cli(monkeypatch, capsys, "shared", "list")
    assert code == 0
    out = outs(capsys)
    assert "公共测试" in out
    assert "user" in out  # author 固定为 user
    entry_id = out.split("[")[1].split("]")[0]

    code = run_cli(monkeypatch, capsys, "shared", "read", entry_id)
    assert code == 0
    assert "正文内容 via test" in outs(capsys)

    code = run_cli(monkeypatch, capsys, "shared", "search", "公共")
    assert code == 0
    assert "公共测试" in outs(capsys)


def test_read_missing_returns_error(env, monkeypatch, capsys):
    code = run_cli(monkeypatch, capsys, "read", "nonexistent000")
    assert code == 1
    assert "未找到" in outs(capsys)


# ---------- 3. 对称渗透：AI 区内容不可达 ----------

def test_pentest_ai_content_never_leaks(env, monkeypatch, capsys):
    outputs = []

    run_cli(monkeypatch, capsys, "write", "--title", "我的日记")
    outputs.append(outs(capsys))
    run_cli(monkeypatch, capsys, "list", "--limit", "1000", "--all")
    outputs.append(outs(capsys))
    run_cli(monkeypatch, capsys, "search", "AI绝密")
    outputs.append(outs(capsys))
    run_cli(monkeypatch, capsys, "search", "CLIPENTEST")
    outputs.append(outs(capsys))
    run_cli(monkeypatch, capsys, "shared", "list", "--limit", "1000", "--all")
    outputs.append(outs(capsys))
    run_cli(monkeypatch, capsys, "shared", "search", "AI绝密标题CLIPENTEST")
    outputs.append(outs(capsys))
    # 猜测 AI 条目 id（读不存在的 id 只会报未找到）
    run_cli(monkeypatch, capsys, "read", "00000000000000000000000000000000")
    outputs.append(outs(capsys))

    combined = "\n".join(outputs)
    assert AI_SECRET_TITLE not in combined
    assert AI_SECRET_BODY not in combined
    assert "CLIPENTEST" not in combined


def test_ai_db_exists_but_cli_never_opens(env):
    """AI 区数据库存在于磁盘（由 server 或测试创建），CLI 全流程不碰它。"""
    assert (env / "ai_private.db").exists()
