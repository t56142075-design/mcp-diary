"""Entry 数据模型。进程内 body/title 始终是明文；是否加密落盘由 DiaryStore 决定。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


@dataclass
class Entry:
    id: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: datetime | None = None

    def to_row(self, *, body_blob: bytes | str, title_placeholder: str | None = None) -> tuple:
        """转为 INSERT/UPDATE 用的行。加密区传 body_blob=密文与占位标题。"""
        title = self.title if title_placeholder is None else title_placeholder
        return (
            self.id,
            title,
            body_blob,
            json.dumps(self.tags, ensure_ascii=False),
            to_iso(self.created_at),
            to_iso(self.updated_at),
            to_iso(self.deleted_at) if self.deleted_at else None,
        )

    def is_deleted(self) -> bool:
        return self.deleted_at is not None
