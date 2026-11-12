"""
安全工具：AES-256-GCM 字段加密、密码哈希、JWT 令牌签发与校验。
需求对应：安全性需求 —— 手机号/学号 AES-256 加密存储、列表脱敏；
JWT + 会话，令牌 2 小时、刷新 7 天。
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from .config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AES_KEY,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)


# ------------------------- 密码 -------------------------
# 直接使用 bcrypt（passlib 1.7.4 与 bcrypt>=4.1 存在兼容性问题）
def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


# ------------------------- AES-256-GCM 字段加密 -------------------------
def _cipher():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(AES_KEY)


def _nonce_for(plain: str) -> bytes:
    """
    确定性 nonce：由密钥与明文派生（HMAC-SHA256 前 12 字节）。
    说明：学号/手机号需要支持等值查询与唯一性校验，随机 nonce 会导致同一明文密文不同。
    采用确定性加密后既满足 AES-256-GCM 认证加密，又支持密文索引查询。
    """
    import hmac
    import hashlib

    return hmac.new(AES_KEY, plain.encode("utf-8"), hashlib.sha256).digest()[:12]


def encrypt_field(plain: str | None) -> str | None:
    """加密后返回 base64 字符串（含 12 字节 nonce）。同一明文密文稳定，可用于唯一索引查询。"""
    if plain is None or plain == "":
        return plain
    nonce = _nonce_for(str(plain))
    ct = _cipher().encrypt(nonce, str(plain).encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def decrypt_field(token: str | None) -> str | None:
    """解密；失败时返回原值，避免脏数据导致整站不可用。"""
    if token is None or token == "":
        return token
    try:
        raw = base64.b64decode(token)
        return _cipher().decrypt(raw[:12], raw[12:], None).decode("utf-8")
    except Exception:
        return token


# ------------------------- 脱敏 -------------------------
def mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return phone or ""
    return phone[:3] + "****" + phone[-4:]


def mask_student_no(no: str | None) -> str:
    if not no or len(no) < 6:
        return no or ""
    return no[:2] + "*" * (len(no) - 4) + no[-2:]


# ------------------------- JWT -------------------------
def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_wechat_token(openid: str, extra: dict[str, Any] | None = None) -> str:
    """微信注册/绑定临时令牌：承载 openid，10 分钟有效，服务端签名防伪造。"""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(openid),
        "type": "wechat",
        "iat": now,
        "exp": now + timedelta(minutes=10),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
