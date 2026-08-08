"""FastAPI 依赖：当前登录用户。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from .database import get_db
from .models import User
from .security import decode_access_token

# 告诉 FastAPI 前端要用 Bearer Token 认证（登录接口除外）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """校验令牌并返回当前用户；失败返回 401。"""
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期或令牌无效，请重新登录",
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

