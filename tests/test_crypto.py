"""crypto 模块测试：派生一致性、加解密往返、错误口令必须失败。"""

import pytest

from mcp_diary.crypto import (
    WrongPassphraseError,
    decrypt,
    derive_key_from_passphrase,
    encrypt,
    load_or_create_server_key,
    new_salt,
)


def test_salt_length():
    assert len(new_salt()) == 16


def test_derive_key_deterministic():
    salt = new_salt()
    k1 = derive_key_from_passphrase("correct horse", salt)
    k2 = derive_key_from_passphrase("correct horse", salt)
    assert k1 == k2
    assert len(k1) == 32


def test_derive_key_different_salt_or_passphrase():
    salt = new_salt()
    assert derive_key_from_passphrase("a", salt) != derive_key_from_passphrase("b", salt)
    assert derive_key_from_passphrase("a", salt) != derive_key_from_passphrase("a", new_salt())


def test_derive_empty_passphrase_rejected():
    with pytest.raises(ValueError):
        derive_key_from_passphrase("", new_salt())


def test_encrypt_decrypt_roundtrip():
    key = derive_key_from_passphrase("pw", new_salt())
    blob = encrypt(key, "标题：今天\n正文内容 with unicode 中文 🎈")
    assert decrypt(key, blob) == "标题：今天\n正文内容 with unicode 中文 🎈"


def test_encrypt_produces_distinct_ciphertexts():
    key = derive_key_from_passphrase("pw", new_salt())
    b1, b2 = encrypt(key, "same"), encrypt(key, "same")
    assert b1 != b2  # 随机 nonce


def test_wrong_key_raises():
    blob = encrypt(derive_key_from_passphrase("right", new_salt()), "secret")
    with pytest.raises(WrongPassphraseError):
        decrypt(derive_key_from_passphrase("wrong", new_salt()), blob)


def test_tampered_blob_raises():
    key = derive_key_from_passphrase("pw", new_salt())
    blob = bytearray(encrypt(key, "secret"))
    blob[-1] ^= 0xFF  # 篡改 GCM tag
    with pytest.raises(WrongPassphraseError):
        decrypt(key, bytes(blob))


def test_truncated_blob_raises():
    key = derive_key_from_passphrase("pw", new_salt())
    with pytest.raises(WrongPassphraseError):
        decrypt(key, b"short")


def test_server_key_file_roundtrip(tmp_path):
    kf = tmp_path / "keys" / "ai_private.key"
    k1 = load_or_create_server_key(kf)
    assert len(k1) == 32
    assert kf.exists()
    k2 = load_or_create_server_key(kf)  # 第二次读取同一个
    assert k1 == k2
