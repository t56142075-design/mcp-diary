"""用户端 CLI：只操作用户私密区与公共区。

隐私红线（与 server.py 对称，docs/01-ARCHITECTURE.md 第七节）：
- 本文件不 import、不构造任何 AI 私密区对象；
- 不引用 AI 区密钥的任何管理能力；
- assert_zone_allowed 作为启动期双重保险。

口令优先级：环境变量 DIARY_USER_PASSPHRASE > getpass 交互输入。
数据目录：环境变量 DIARY_DATA_DIR 或 --data-dir，默认 ./data。
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from .models import Entry, to_iso
from .storage import DiaryStore, open_store
from .zones import Zone, assert_zone_allowed


def _data_dir(args) -> Path:
    return Path(args.data_dir or os.environ.get("DIARY_DATA_DIR", "data"))


def _open_user_store(args) -> DiaryStore:
    """打开用户私密区。口令：环境变量 > 交互。"""
    assert_zone_allowed("user", Zone.USER_PRIVATE)
    passphrase = os.environ.get("DIARY_USER_PASSPHRASE") or ""
    if not passphrase:
        passphrase = getpass.getpass("日记口令: ")
    return open_store(Zone.USER_PRIVATE, _data_dir(args), user_passphrase=passphrase)


def _open_shared_store(args) -> DiaryStore:
    assert_zone_allowed("user", Zone.SHARED)
    return open_store(Zone.SHARED, _data_dir(args))


# ---------- 输出格式化 ----------

def _print_entry(e: Entry, full: bool = False) -> None:
    flags = " [已删除]" if e.is_deleted() else ""
    author = f" · {e.author}" if e.author else ""
    print(f"[{e.id[:8]}] {to_iso(e.created_at)[:19]}{author}{flags} {e.title}")
    if e.tags:
        print(f"         标签: {', '.join(e.tags)}")
    if full:
        print()
        print(e.body)
        print()


def _print_list(entries: list[Entry]) -> None:
    if not entries:
        print("（无条目）")
        return
    for e in entries:
        _print_entry(e)


def _read_body_from_stdin() -> str:
    if sys.stdin.isatty():
        print("输入正文，单独一行输入 . 结束：")
        lines = []
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
        return "\n".join(lines)
    return sys.stdin.read().strip()


def _parse_tags(tags: list[str] | None) -> list[str]:
    result = []
    for t in tags or []:
        result.extend(x.strip() for x in t.split(",") if x.strip())
    return result


# ---------- 用户私密区命令 ----------


def cmd_write(args) -> int:
    store = _open_user_store(args)
    try:
        body = _read_body_from_stdin()
        e = store.add(args.title or "无标题", body, _parse_tags(args.tag))
        print(f"已写入 [{e.id[:8]}] {e.title}")
        return 0
    finally:
        store.close()


def cmd_read(args) -> int:
    store = _open_user_store(args)
    try:
        e = store.get(args.id)
        if e is None:
            print("未找到该条目")
            return 1
        _print_entry(e, full=True)
        return 0
    finally:
        store.close()


def cmd_list(args) -> int:
    store = _open_user_store(args)
    try:
        entries = store.list(limit=args.limit, include_deleted=args.all)
        _print_list(entries)
        return 0
    finally:
        store.close()


def cmd_search(args) -> int:
    store = _open_user_store(args)
    try:
        hits = store.search(args.keyword, limit=args.limit)
        _print_list(hits)
        return 0
    finally:
        store.close()


def cmd_edit(args) -> int:
    store = _open_user_store(args)
    try:
        e = store.get(args.id)
        if e is None:
            print("未找到该条目")
            return 1
        if args.title is None and not args.tag and args.body is None:
            # 无任何修改参数时进入交互编辑
            print(f"当前标题: {e.title}")
            new_title = input("新标题（回车保留）: ").strip() or e.title
            print("输入新正文，单独一行输入 . 结束（直接 . 保留原文）:")
            lines = []
            while True:
                line = input()
                if line.strip() == ".":
                    break
                lines.append(line)
            new_body = "\n".join(lines) if lines else e.body
            e = store.update(args.id, title=new_title, body=new_body) or e
        else:
            e = store.update(
                args.id,
                title=args.title,
                tags=_parse_tags(args.tag) if args.tag else None,
                body=args.body,
            )
        if e is None:
            print("更新失败")
            return 1
        print(f"已更新 [{e.id[:8]}] {e.title}")
        return 0
    finally:
        store.close()


def cmd_delete(args) -> int:
    store = _open_user_store(args)
    try:
        if store.delete(args.id):
            print(f"已删除 [{args.id[:8]}]")
            return 0
        print("未找到或已删除")
        return 1
    finally:
        store.close()


# ---------- 公共区命令（author 固定 user） ----------


def cmd_shared_write(args) -> int:
    store = _open_shared_store(args)
    try:
        body = _read_body_from_stdin()
        e = store.add(args.title or "无标题", body, _parse_tags(args.tag), author="user")
        print(f"已写入公共区 [{e.id[:8]}] {e.title}")
        return 0
    finally:
        store.close()


def cmd_shared_read(args) -> int:
    store = _open_shared_store(args)
    try:
        e = store.get(args.id)
        if e is None:
            print("未找到该条目")
            return 1
        _print_entry(e, full=True)
        return 0
    finally:
        store.close()


def cmd_shared_list(args) -> int:
    store = _open_shared_store(args)
    try:
        entries = store.list(limit=args.limit, include_deleted=args.all)
        _print_list(entries)
        return 0
    finally:
        store.close()


def cmd_shared_search(args) -> int:
    store = _open_shared_store(args)
    try:
        hits = store.search(args.keyword, limit=args.limit)
        _print_list(hits)
        return 0
    finally:
        store.close()


# ---------- 参数解析 ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="diary", description="MCP 双人日记 · 用户端")
    parser.add_argument("--data-dir", help="数据目录（默认 DIARY_DATA_DIR 或 ./data）")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--title", help="标题")
        p.add_argument("-t", "--tag", action="append", help="标签，可多次或逗号分隔")

    p = sub.add_parser("write", help="写用户私密日记（正文走 stdin）")
    common(p)
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("read", help="读一条私密日记")
    p.add_argument("id", help="条目 id")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("list", help="列私密日记")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--all", action="store_true", help="含已删除")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="搜私密日记")
    p.add_argument("keyword")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("edit", help="编辑私密日记")
    p.add_argument("id")
    common(p)
    p.add_argument("--body", help="新正文（不给则交互输入）")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("delete", help="删除私密日记（软删除）")
    p.add_argument("id")
    p.set_defaults(func=cmd_delete)

    shared = sub.add_parser("shared", help="公共区（人与 AI 共写）")
    ssub = shared.add_subparsers(dest="shared_command", required=True)

    p = ssub.add_parser("write", help="写公共日记")
    common(p)
    p.set_defaults(func=cmd_shared_write)

    p = ssub.add_parser("read", help="读公共日记")
    p.add_argument("id")
    p.set_defaults(func=cmd_shared_read)

    p = ssub.add_parser("list", help="列公共日记")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--all", action="store_true", help="含已删除")
    p.set_defaults(func=cmd_shared_list)

    p = ssub.add_parser("search", help="搜公共日记")
    p.add_argument("keyword")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_shared_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
