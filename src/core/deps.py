"""
依赖注入：当前用户解析、角色（RBAC）校验、学院数据可见范围控制。
需求：三级角色 + 学院维度数据范围；越权访问返回 403 并记录告警。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .config import ROLE_PLATFORM_ADMIN, ROLE_POINT_ADMIN
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    payload = decode_token(cred.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    user = db.get(User, int(payload.get("sub", 0)))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用，请联系管理员")
    request.state.user = user
    return user


def require_roles(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限执行该操作")
        return user

    return _dep


get_admin = require_roles(ROLE_PLATFORM_ADMIN)
get_point_admin = require_roles(ROLE_PLATFORM_ADMIN, ROLE_POINT_ADMIN)


def visible_scope_filter(user: User):
    """学院维度数据可见范围：普通用户仅本学院，平台管理员全量"""
    if user.role == ROLE_PLATFORM_ADMIN:
        return None
    return user.college


def touch_login(user: User, db: Session) -> None:
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.login_fail_count = 0
    user.locked_until = None
    db.commit()
