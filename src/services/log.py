"""操作日志：全部管理操作留痕（操作人、时间、IP、变更前后值）"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import OperationLog


def write_log(
    db: Session,
    operator_id: int | None,
    action: str,
    target: str = "",
    before: Any = None,
    after: Any = None,
    request: Request | None = None,
) -> None:
    ip = ""
    if request is not None:
        ip = request.client.host if request.client else ""
        ip = request.headers.get("x-forwarded-for", ip)
    db.add(
        OperationLog(
            operator_id=operator_id,
            action=action,
            target=target,
            before=str(before) if before is not None else "",
            after=str(after) if after is not None else "",
            ip=ip,
        )
    )
    db.commit()
