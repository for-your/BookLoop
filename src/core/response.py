"""统一响应封装：{code,msg,data}。错误码对用户不可见（需求：错误码对用户不可见）。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def ok(data: Any = None, msg: str = "success") -> dict:
    return {"code": 0, "msg": msg, "data": data if data is not None else {}}


def fail(msg: str, code: int = 400, http_status: int | None = None) -> HTTPException:
    """业务异常统一通过 HTTPException 抛出，由全局处理器转为统一结构"""
    raise HTTPException(status_code=http_status or code, detail=msg)


class BizError(Exception):
    def __init__(self, msg: str, http_status: int = 400):
        self.msg = msg
        self.http_status = http_status
        super().__init__(msg)
