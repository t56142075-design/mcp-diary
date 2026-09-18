"""密钥派生与 AES-256-GCM 加解密。

密钥生命周期（见 docs/01-ARCHITECTURE.md）：
- 用户区密钥：用户口令 scrypt 派生，口令不落盘，salt 存 user_private.db 的 meta 表；
- AI 区密钥：服务端首次启动随机生成，存 data/keys/ai_private.key（0600）；
- 公共区：无密钥，明文。

安全决策：错误口令与 GCM tag 校验失败统一抛 WrongPassphraseError，
不区分失败原因，避免向攻击者泄露信息。
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_SALT_BYTES = 16
_KEY_BYTES = 32
_NONCE_BYTES = 12
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1


class WrongPassphraseError(Exception):
    """口令错误或密文被篡改（不区分原因）。"""


def new_salt() -> bytes:
    """16 字节随机盐，非机密，明文存于用户库 meta 表。"""
    return os.urandom(_SALT_BYTES)


def derive_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    """用户口令 → AES-256 密钥。scrypt：N=2^15, r=8, p=1, dklen=32。"""
    if not passphrase:
        raise ValueError("passphrase must not be empty")
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf = Scrypt(
        salt=salt,
        length=_KEY_BYTES,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def load_or_create_server_key(key_file: Path) -> bytes:
    """AI 区密钥：存在则读取；不存在则生成 32 随机字节写入。

    文件权限尽力设为 0600（Windows 上 chmod 语义有限，尽力而为）。
    """
    key_file = Path(key_file)
    if key_file.exists():
        data = key_file.read_bytes()
        if len(data) != _KEY_BYTES:
            raise ValueError(
                f"key file {key_file} has unexpected size {len(data)}"
            )
        return data
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(_KEY_BYTES)
    key_file.write_bytes(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass  # Windows 权限模型不同，尽力而为
    return key


def encrypt(key: bytes, plaintext: str) -> bytes:
    """AES-256-GCM。输出布局 = nonce(12B) || ciphertext || tag(16B)。"""
    if len(key) != _KEY_BYTES:
        raise ValueError("key must be 32 bytes")
    nonce = os.urandom(_NONCE_BYTES)
    aes = AESGCM(key)
    return nonce + aes.encrypt(nonce, plaintext.encode("utf-8"), None)


def decrypt(key: bytes, blob: bytes) -> str:
    """解密并校验 GCM tag。口令错或被篡改统一抛 WrongPassphraseError。"""
    if len(key) != _KEY_BYTES:
        raise ValueError("key must be 32 bytes")
    if len(blob) < _NONCE_BYTES + 16:
        raise WrongPassphraseError("blob too short")
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    aes = AESGCM(key)
    try:
        return aes.decrypt(nonce, ct, None).decode("utf-8")
    except Exception as exc:  # InvalidTag / UnicodeDecodeError 均视为失败
        raise WrongPassphraseError("decryption failed") from exc
