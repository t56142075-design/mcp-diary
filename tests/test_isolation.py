"""权限矩阵集成测试：阶段 5 核心交付（docs/01-ARCHITECTURE.md 第八节全量落地）。

权限矩阵六格：
| 主体 | user_private | ai_private | shared |
|------|-------------|-----------|--------|
| user | ✅ 读写      | ❌ 必拒    | ✅ 读写 |
| ai   | ❌ 必拒      | ✅ 读写    | ✅ 读写 |

加密码学边界：跨区密钥互用必失败（纵深防御的最后一道闸门）。
"""

import sqlite3

import pytest

from mcp_diary.crypto import WrongPassphraseError, decrypt, derive_key_from_passphrase, load_or_create_server_key, new_salt
from mcp_diary.storage import open_store
from mcp_diary.zones import PRINCIPAL_ALLOWED_ZONES, Zone, assert_zone_allowed


# ---------- 1. 权限矩阵：允许的四格 ----------

@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


def test_matrix_user_opens_user_private(data_dir):
    store = open_store(Zone.USER_PRIVATE, data_dir, user_passphrase="pw")
    e = store.add("标题", "正文")
    assert store.get(e.id).body == "正文"
    store.close()


def test_matrix_user_opens_shared(data_dir):
    store = open_store(Zone.SHARED, data_dir)
    e = store.add("标题", "正文", author="user")
    assert store.get(e.id).body == "正文"
    store.close()


def test_matrix_ai_opens_ai_private(data_dir, tmp_path):
    store = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "k/ai.key")
    e = store.add("标题", "正文")
    assert store.get(e.id).body == "正文"
    store.close()


def test_matrix_ai_opens_shared(data_dir):
    store = open_store(Zone.SHARED, data_dir)
    e = store.add("标题", "正文", author="ai")
    assert store.get(e.id).body == "正文"
    store.close()


# ---------- 2. 权限矩阵：越界的两格必拒 ----------

def test_matrix_ai_cannot_open_user_private():
    with pytest.raises(PermissionError):
        assert_zone_allowed("ai", Zone.USER_PRIVATE)


def test_matrix_user_cannot_open_ai_private():
    with pytest.raises(PermissionError):
        assert_zone_allowed("user", Zone.AI_PRIVATE)


def test_zone_allowed_table_covers_all_six_cells():
    """权限矩阵常量本身与设计一致：每格对得上，无遗漏区域。"""
    assert PRINCIPAL_ALLOWED_ZONES["user"] == frozenset({Zone.USER_PRIVATE, Zone.SHARED})
    assert PRINCIPAL_ALLOWED_ZONES["ai"] == frozenset({Zone.AI_PRIVATE, Zone.SHARED})
    assert len(Zone) == 3


def test_unknown_principal_rejected():
    with pytest.raises(PermissionError):
        assert_zone_allowed("attacker", Zone.SHARED)


# ---------- 3. 跨区密钥互用必失败（纵深加密验证） ----------

def test_user_passphrase_key_cannot_decrypt_ai_zone(data_dir, tmp_path):
    """用户口令派生的密钥，解不开 AI 区的密文。"""
    ai = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "k/ai.key")
    ai.add("AI思考", "AI 私密内容")
    ai.close()

    # 用户视角：拿到 ai_private.db，用自己口令的 salt 流程也派生不出 AI 的密钥
    user_key = derive_key_from_passphrase("my-pass", new_salt())
    conn = sqlite3.connect(data_dir / "ai_private.db")
    rows = conn.execute("SELECT body FROM entries").fetchall()
    conn.close()
    for (blob,) in rows:
        with pytest.raises(WrongPassphraseError):
            decrypt(user_key, bytes(blob))


def test_ai_server_key_cannot_decrypt_user_zone(data_dir):
    """AI 服务端密钥，解不开用户区的密文。"""
    user = open_store(Zone.USER_PRIVATE, data_dir, user_passphrase="my-pass")
    user.add("用户思考", "用户私密内容")
    user.close()

    ai_key = load_or_create_server_key(data_dir / "keys" / "ai_private.key")
    conn = sqlite3.connect(data_dir / "user_private.db")
    rows = conn.execute("SELECT body FROM entries").fetchall()
    conn.close()
    for (blob,) in rows:
        with pytest.raises(WrongPassphraseError):
            decrypt(ai_key, bytes(blob))


def test_shared_zone_has_no_ciphertext(data_dir):
    """公共区明文，任何一方用任何密钥都能读（设计如此，公共区无密钥）。"""
    store = open_store(Zone.SHARED, data_dir)
    store.add("公共", "内容 plaintext-marker")
    store.close()
    conn = sqlite3.connect(data_dir / "shared.db")
    blob = conn.execute("SELECT body FROM entries").fetchone()[0]
    conn.close()
    assert isinstance(blob, str)
    assert "plaintext-marker" in blob


# ---------- 4. 三库物理隔离的汇总断言 ----------

def test_zone_db_filenames_distinct():
    from mcp_diary.zones import DB_FILENAMES
    names = list(DB_FILENAMES.values())
    assert len(set(names)) == 3
    assert "user_private.db" in names
    assert "ai_private.db" in names
    assert "shared.db" in names


def test_one_store_instance_only_owns_one_file(data_dir, tmp_path):
    """每个 store 实例只持有一个库文件路径，无跨区引用。"""
    ai = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "k/ai.key")
    assert ai._db_path.name == "ai_private.db"
    assert not hasattr(ai, "zone_user")  # 无任何其他区域属性
    ai.close()
