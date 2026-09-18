"""storage 模块测试：CRUD、软删除、加密区搜索、密文落盘验证。"""

import sqlite3

import pytest

from mcp_diary.crypto import WrongPassphraseError, decrypt, derive_key_from_passphrase
from mcp_diary.storage import open_store
from mcp_diary.zones import Zone


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def user_store(data_dir):
    store = open_store(Zone.USER_PRIVATE, data_dir, user_passphrase="my-passphrase")
    yield store
    store.close()


@pytest.fixture
def shared_store(data_dir):
    store = open_store(Zone.SHARED, data_dir)
    yield store
    store.close()


@pytest.fixture
def ai_store(data_dir, tmp_path):
    store = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "keys/ai.key")
    yield store
    store.close()


# ---------- 基础 CRUD ----------

def test_add_and_get_roundtrip(user_store):
    e = user_store.add("标题A", "正文内容", ["tag1", "tag2"])
    got = user_store.get(e.id)
    assert got is not None
    assert got.title == "标题A"
    assert got.body == "正文内容"
    assert got.tags == ["tag1", "tag2"]
    assert got.deleted_at is None


def test_get_missing_returns_none(user_store):
    assert user_store.get("nonexistent") is None


def test_update(user_store):
    e = user_store.add("old", "old body")
    updated = user_store.update(e.id, title="new", body="new body", tags=["x"])
    assert updated.title == "new"
    assert updated.body == "new body"
    assert updated.tags == ["x"]
    assert user_store.get(e.id).body == "new body"


def test_soft_delete(user_store):
    e = user_store.add("t", "b")
    assert user_store.delete(e.id) is True
    assert user_store.get(e.id) is not None  # get 仍可见（含已删）
    assert user_store.list() == []  # list 默认不含已删
    assert user_store.list(include_deleted=True)[0].id == e.id
    assert user_store.delete(e.id) is False  # 重复删除返回 False


def test_list_date_filter(user_store):
    user_store.add("one", "1")
    user_store.add("two", "2")
    assert len(user_store.list(limit=10)) == 2
    assert len(user_store.list(limit=1)) == 1


# ---------- 加密验证：明文绝不出现在库文件里 ----------

def test_user_db_file_contains_no_plaintext(user_store, data_dir):
    user_store.add("绝密标题XYZ", "绝密正文SECRETBODY123")
    raw = (data_dir / "user_private.db").read_bytes()
    assert "绝密标题XYZ".encode("utf-8") not in raw
    assert "绝密正文".encode("utf-8") not in raw
    assert b"SECRETBODY123" not in raw


def test_db_title_column_is_placeholder(user_store, data_dir):
    e = user_store.add("真实标题", "真实正文")
    conn = sqlite3.connect(data_dir / "user_private.db")
    row = conn.execute("SELECT title FROM entries WHERE id=?", (e.id,)).fetchone()
    conn.close()
    assert row[0] == "[encrypted]"  # 表内 title 列只存占位符


def test_wrong_passphrase_cannot_read(user_store, data_dir):
    user_store.add("secret title", "secret body")
    wrong = open_store(Zone.USER_PRIVATE, data_dir, user_passphrase="wrong-pass")
    with pytest.raises(WrongPassphraseError):
        wrong.list()  # 解密在 _unseal 时发生，错误口令必须失败
    wrong.close()


def test_ai_zone_search_after_reopen(data_dir, tmp_path):
    """AI 区关闭重开后（密钥从文件重读），数据仍可解密搜索。"""
    store = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "keys/ai.key")
    store.add("晨间思考", "今天关于架构的笔记 KEYWORD_UNIQUE")
    store.close()
    store2 = open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=tmp_path / "keys/ai.key")
    hits = store2.search("KEYWORD_UNIQUE")
    assert len(hits) == 1
    assert hits[0].title == "晨间思考"
    store2.close()


# ---------- 公共区：明文 + SQL 搜索 ----------

def test_shared_zone_plaintext_sql_search(shared_store):
    shared_store.add("公共标题", "公共正文 needle here")
    hits = shared_store.search("needle")
    assert len(hits) == 1
    assert hits[0].title == "公共标题"


def test_shared_search_by_title(shared_store):
    shared_store.add("独特标题词", "whatever")
    assert len(shared_store.search("独特标题词")) == 1


def test_encrypted_zone_search_by_title_and_body(user_store):
    user_store.add("旅行计划", "去京都")
    user_store.add("工作日志", "今天写了旅行计划文档")
    assert len(user_store.search("旅行计划")) == 2  # 标题命中 + 正文命中
    assert len(user_store.search("京都")) == 1


def test_search_empty_keyword(user_store):
    user_store.add("t", "b")
    assert user_store.search("") == []
    assert user_store.search("   ") == []


# ---------- 三库文件分离 ----------

def test_three_db_files_separate(user_store, ai_store, shared_store, data_dir):
    names = {p.name for p in data_dir.glob("*.db")}
    assert names == {"user_private.db", "ai_private.db", "shared.db"}


def test_user_zone_requires_passphrase(data_dir):
    with pytest.raises(ValueError):
        open_store(Zone.USER_PRIVATE, data_dir, user_passphrase=None)
    with pytest.raises(ValueError):
        open_store(Zone.USER_PRIVATE, data_dir, user_passphrase="")


def test_ai_zone_requires_key_file(data_dir):
    with pytest.raises(ValueError):
        open_store(Zone.AI_PRIVATE, data_dir, ai_key_file=None)
