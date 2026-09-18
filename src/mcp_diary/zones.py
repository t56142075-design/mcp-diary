"""区域枚举与权限矩阵常量。

本模块是三区权限的唯一事实源。server.py 与 cli.py 各自只允许引用
PRINCIPAL_ALLOWED_ZONES 中分配给自己的区域，禁止越界。

隐私红线：
- server.py（AI / MCP 侧）永远不 import Zone.USER_PRIVATE 相关任何能力；
- cli.py（用户侧）永远不 import Zone.AI_PRIVATE 相关任何能力。
"""

from enum import StrEnum


class Zone(StrEnum):
    USER_PRIVATE = "user_private"
    AI_PRIVATE = "ai_private"
    SHARED = "shared"


# 谁允许打开哪个区。
PRINCIPAL_ALLOWED_ZONES: dict[str, frozenset[Zone]] = {
    "user": frozenset({Zone.USER_PRIVATE, Zone.SHARED}),
    "ai": frozenset({Zone.AI_PRIVATE, Zone.SHARED}),
}

DB_FILENAMES: dict[Zone, str] = {
    Zone.USER_PRIVATE: "user_private.db",
    Zone.AI_PRIVATE: "ai_private.db",
    Zone.SHARED: "shared.db",
}


def assert_zone_allowed(principal: str, zone: Zone) -> None:
    """启动期静态检查：principal 不允许打开 zone 时立即抛错，快速失败。"""
    allowed = PRINCIPAL_ALLOWED_ZONES.get(principal)
    if allowed is None or zone not in allowed:
        raise PermissionError(
            f"principal '{principal}' is not allowed to open zone '{zone}'"
        )
