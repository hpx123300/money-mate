"""
安全模块：密码哈希 + JWT。

知识点：
1. 密码绝不明文存储：用 Argon2（当前业界推荐）做单向哈希
2. JWT（JSON Web Token）：登录后签发令牌，客户端带令牌访问受保护接口，
   服务器用密钥验证签名，无需查询数据库
3. 为什么密钥要放环境变量：泄漏密钥 = 任何人都能伪造登录令牌
"""

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from .config import settings

password_hash = PasswordHash.recommended()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """生成密码哈希（存库）。"""
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码是否正确。"""
    return password_hash.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    """签发 JWT：携带用户 ID 和过期时间。"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """解析 JWT，返回用户 ID；无效/过期返回 None。"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None

